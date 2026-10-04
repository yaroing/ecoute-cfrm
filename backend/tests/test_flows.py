import json
import time
from datetime import timedelta
import pytest
import pyotp
from django.utils import timezone
from rest_framework.test import APIClient
from core.models import User, Dossier, Message, Contact, Outgoing, Outbox, Reply
from core.crypto import encrypt, decrypt
from core.sensible.models import SensitiveContent
from core.audit.services import dispatch, verify_chain
from core.events.tasks import tick
from adapters.inbound.channels import signature

pytestmark = pytest.mark.django_db(databases=["default", "sensible"])


@pytest.fixture
def users():
    return {
        role: User.objects.create_user(
            username=role,
            password="Test-password-123",
            first_name=role,
            role=role,
            totp_secret=encrypt(pyotp.random_base32()) if role in ["R4", "R6"] else "",
        )
        for role in ["R1", "R2", "R3", "R4", "R5", "R6"]
    }


def client(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user=user)
    return c


def sms(text="Les kits ne sont pas arrivés", key="one", address="TEST-001", **extra):
    body = json.dumps({"text": text, "key": key, "address": address, "consent": True, **extra}).encode()
    timestamp = str(int(time.time()))
    return client().post(
        "/webhooks/sms/simule",
        body,
        content_type="application/json",
        HTTP_X_TIMESTAMP=timestamp,
        HTTP_X_SIGNATURE=signature("sms", timestamp, body),
    )


def case():
    r = sms()
    assert r.status_code == 200, r.data
    return Dossier.objects.get(pk=r.data["id"])


def qualify_assign(d, users):
    c = client(users["R3"])
    assert (
        c.patch(
            f"/api/v1/dossiers/{d.pk}/qualification",
            {"type": "PLAINTE", "theme": "Distribution", "urgency": "NORMALE"},
            format="json",
        ).status_code
        == 200
    )
    assert (
        c.post(
            f"/api/v1/dossiers/{d.pk}/transitions", {"state": "ATTRIBUE", "owner": users["R2"].pk}, format="json"
        ).status_code
        == 200
    )
    c = client(users["R2"])
    assert c.post(f"/api/v1/dossiers/{d.pk}/transitions", {"state": "EN_TRAITEMENT"}, format="json").status_code == 200
    d.refresh_from_db()


def test_complete_response_learning_cycle(users):
    d = case()
    qualify_assign(d, users)
    c = client(users["R2"])
    s = client(users["R3"])
    root = f"/api/v1/dossiers/{d.pk}"
    assert c.post(root + "/notes", {"text": "Note interne de suivi"}, format="json").status_code == 201
    assert (
        c.post(
            root + "/referencements", {"recipient": "Partenaire eau", "issue": "En attente"}, format="json"
        ).status_code
        == 201
    )
    r = c.post(root + "/reponses", {"text": "La distribution aura lieu demain."}, format="json")
    assert r.status_code == 201
    rid = r.data["id"]
    assert c.post(root + f"/reponses/{rid}/validation", {"accepted": True}, format="json").status_code == 403
    assert s.post(root + f"/reponses/{rid}/validation", {"accepted": True}, format="json").status_code == 200
    d.refresh_from_db()
    assert d.state == "REPONSE_TRANSMISE"
    assert s.post(root + "/transitions", {"state": "CLOTURE"}, format="json").status_code == 400
    assert s.post(root + "/transitions", {"state": "CLOTURE", "reason": "RESOLU"}, format="json").status_code == 200
    r = s.post(
        "/api/v1/actions",
        {
            "title": "Nouveau point de distribution",
            "project": d.project,
            "owner": users["R3"].pk,
            "due": "2026-12-01",
            "dossiers": [str(d.pk)],
        },
        format="json",
    )
    assert r.status_code == 201, r.data
    aid = r.data["id"]
    assert s.patch(f"/api/v1/actions/{aid}", {"status": "REALISEE"}, format="json").status_code == 400
    assert (
        s.patch(
            f"/api/v1/actions/{aid}", {"status": "REALISEE", "proof": "Compte rendu fictif"}, format="json"
        ).status_code
        == 200
    )
    assert s.get("/api/v1/indicateurs").data["actions_without_restitution"] == 1
    assert (
        s.post(
            f"/api/v1/actions/{aid}/restitutions",
            {"date": "2026-10-03", "channel": "Réunion", "zone": "Tillabéri", "message": "Information restituée"},
            format="json",
        ).status_code
        == 201
    )
    assert s.get("/api/v1/indicateurs").data["indicators"]["I07"] == 100
    assert (
        s.post(
            root + "/transitions", {"state": "EN_TRAITEMENT", "reason": "Retour complémentaire"}, format="json"
        ).status_code
        == 200
    )
    d.refresh_from_db()
    assert d.reopen_count == 1
    dispatch()
    assert verify_chain()
    assert not Outgoing.objects.filter(text__contains="Note interne").exists()


def test_replay_and_sender_attachment(users):
    d = case()
    for _ in range(3):
        assert sms().data["duplicate"] is True
    assert Message.objects.count() == 1
    assert sms("Un complément", key="two").data["id"] == str(d.pk)
    assert Message.objects.count() == 2
    # An attacker mentioning a reference must not be attached to another contact.
    r = sms(f"REF {d.reference} commentaire", key="three", address="TEST-OTHER")
    assert r.data["id"] != str(d.pk)


@pytest.mark.parametrize("role", ["R1", "R2", "R3", "R5", "R6"])
def test_sensitive_denied_everywhere(users, role):
    r = sms("Exercice de fraude : contenu confidentiel")
    pk = r.data["id"]
    c = client(users[role])
    assert c.get("/api/v1/dossiers/" + pk).status_code == 404
    assert c.get("/api/v1/sensible/" + pk).status_code == 404
    listing = c.get("/api/v1/dossiers").content.decode()
    assert pk not in listing
    assert "contenu confidentiel" not in listing
    assert Message.objects.get().text == ""
    assert "fraude" not in SensitiveContent.objects.get().encrypted
    assert "TEST-001" not in Contact.objects.get().encrypted_address


def test_sensitive_lifecycle_and_exports(users):
    r = sms("EXERCICE FICTIF fraude")
    pk = r.data["id"]
    c = client(users["R4"])
    root = "/api/v1/sensible/" + pk
    assert "fraude" in c.get(root).data["messages"][0]["text"]
    assert c.post(root, {"state": "TRANSFERE", "recipient": "Protection"}, format="json").status_code == 400
    assert c.post(root, {"state": "PRIS_EN_CHARGE"}, format="json").status_code == 200
    assert c.post(root, {"state": "TRANSFERE", "recipient": "Protection"}, format="json").status_code == 200
    assert c.post(root, {"state": "CLOTURE"}, format="json").status_code == 400
    assert c.post(root, {"state": "CLOTURE", "receipt": "Reçu par le service"}, format="json").status_code == 200
    c = client(users["R3"])
    exported = c.post("/api/v1/exports", {}, format="json").content.decode("utf-8-sig")
    assert r.data["reference"] not in exported
    assert c.get("/api/v1/indicateurs").data["sensitive_total"] == 1
    assert c.get("/api/v1/indicateurs").data["total"] == 0
    assert Outbox.objects.filter(event="LectureSensible").count() >= 4
    assert "fraude" not in str(list(Outbox.objects.values()))


def test_idempotent_agent_batch_and_sensitive_block(users):
    c = client(users["R1"])
    items = [{"key": f"offline-{i}", "text": f"Retour ordinaire {i}"} for i in range(100)]
    for _ in range(3):
        r = c.post("/api/v1/agent/sync", {"items": items}, format="json")
        assert r.status_code == 200
        assert all(x.get("reference") for x in r.data["results"])
    assert Dossier.objects.count() == 100
    r = c.post("/api/v1/agent/sync", {"items": [{"key": "sensitive", "text": "Fraude fictive"}]}, format="json")
    assert "SENSIBLE" in r.data["results"][0]["error"]
    assert Dossier.objects.count() == 100
    assert Dossier.objects.filter(agent=users["R1"]).count() == 100


def test_state_guards_ownership_and_negative_matrix(users):
    d = case()
    root = f"/api/v1/dossiers/{d.pk}"
    assert (
        client(users["R3"])
        .post(root + "/transitions", {"state": "ATTRIBUE", "owner": users["R2"].pk}, format="json")
        .status_code
        == 400
    )
    for role in ["R1", "R4", "R5", "R6"]:
        c = client(users[role])
        assert c.get(root).status_code == 404
        assert c.post(root + "/notes", {"text": "Test"}, format="json").status_code == 403
    assert client(users["R2"]).get(root).status_code == 404
    qualify_assign(d, users)
    other = User.objects.create_user("other", role="R2")
    assert client(other).get(root).status_code == 404
    for role in ["R1", "R2", "R4", "R6"]:
        c = client(users[role])
        assert c.post("/api/v1/exports", {}, format="json").status_code == 403
        assert c.get("/api/v1/indicateurs").status_code == 403
    assert (
        client(users["R3"])
        .post(root + "/transitions", {"state": "CLOTURE", "reason": "RESOLU"}, format="json")
        .status_code
        == 400
    )


def test_webhook_rejects_bad_signatures_stale_and_disabled(settings):
    c = client()
    body = b'{"text":"test","key":"one"}'
    assert c.post("/webhooks/sms/simule", body, content_type="application/json").status_code == 401
    timestamp = str(int(time.time()) - 301)
    assert (
        c.post(
            "/webhooks/sms/simule",
            body,
            content_type="application/json",
            HTTP_X_TIMESTAMP=timestamp,
            HTTP_X_SIGNATURE=signature("sms", timestamp, body),
        ).status_code
        == 401
    )
    settings.SIMULATION = False
    assert sms().status_code == 404
    assert Dossier.objects.count() == 0


def test_stop_and_consent_no_automatic_switch(users):
    d = case()
    qualify_assign(d, users)
    assert sms("STOP", key="stop").data["reference"] is None
    c = client(users["R2"])
    s = client(users["R3"])
    root = f"/api/v1/dossiers/{d.pk}"
    r = c.post(root + "/reponses", {"text": "Une réponse"}, format="json")
    assert s.post(root + f"/reponses/{r.data['id']}/validation", {"accepted": True}, format="json").status_code == 400
    assert Reply.objects.get().status == "PREPAREE"


def test_merge_and_reverse(users):
    a = case()
    b = Dossier.objects.get(pk=sms("Autre retour", key="other", address="TEST-002").data["id"])
    c = client(users["R3"])
    root = f"/api/v1/dossiers/{a.pk}"
    assert c.post(root + "/fusion", {"source": str(b.pk), "reason": "Même problème"}, format="json").status_code == 200
    assert a.messages.count() == 2
    fid = c.get(root).data["fusions"][0]["id"]
    assert c.post(root + "/fusion", {"undo": fid}, format="json").status_code == 200
    assert a.messages.count() == b.messages.count() == 1
    b.refresh_from_db()
    assert b.state == "RECU"


def test_retry_delays_alerts_and_purge(users):
    d = case()
    out = Outgoing.objects.get()
    out.status = "EN_FILE"
    out.attempts = 0
    out.save()
    for attempt in range(4):
        Outgoing.objects.filter(pk=out.pk).update(next_attempt=timezone.now() - timedelta(seconds=1))
        tick(lambda message: "ECHEC")
        out.refresh_from_db()
        assert out.attempts == attempt + 1
    assert out.status == "ECHEC"
    assert Outbox.objects.filter(event="EnvoiEchoue").exists()
    d.due = timezone.now() - timedelta(days=1)
    d.save()
    tick(lambda message: "ENVOYE")
    assert Outbox.objects.filter(event="EcheanceDepassee").exists()
    d.state = "CLOTURE"
    d.closed = timezone.now() - timedelta(days=100)
    d.save()
    tick(lambda message: "ENVOYE")
    d.refresh_from_db()
    assert d.contact is None
    assert Contact.objects.count() == 0


def test_login_mfa_lockout_refresh(users):
    c = client()
    u = users["R4"]
    assert (
        c.post("/api/v1/auth/login", {"username": "R4", "password": "Test-password-123"}, format="json").status_code
        == 401
    )
    otp = pyotp.TOTP(decrypt(u.totp_secret)).now()
    r = c.post("/api/v1/auth/login", {"username": "R4", "password": "Test-password-123", "otp": otp}, format="json")
    assert r.status_code == 200
    c.credentials(HTTP_AUTHORIZATION="Bearer " + r.data["token"])
    assert c.get("/api/v1/sensible").status_code == 200
    c.credentials()
    assert c.post("/api/v1/auth/refresh", {"refresh": r.data["refresh"]}, format="json").status_code == 200
    assert c.post("/api/v1/auth/refresh", {"refresh": r.data["refresh"]}, format="json").status_code == 401
    for _ in range(5):
        c.post("/api/v1/auth/login", {"username": "R2", "password": "wrong"}, format="json")
    assert (
        c.post("/api/v1/auth/login", {"username": "R2", "password": "Test-password-123"}, format="json").status_code
        == 401
    )


def test_contact_encryption_and_business_delay():
    from core.attribution.services import business_due
    from datetime import datetime, timezone as tz

    start = datetime(2026, 10, 2, tzinfo=tz.utc)
    assert business_due(start, "QUESTION", "URGENTE").day == 7
    secret = "TEST-PRIVATE"
    assert decrypt(encrypt(secret)) == secret
    assert secret not in encrypt(secret)


def test_public_anonymous_and_validation():
    c = client()
    r = c.post("/api/v1/public/retours", {"text": "Une question anonyme", "key": "anonymous"}, format="json")
    assert r.status_code == 201
    assert Dossier.objects.get().contact_id is None
    assert c.post("/api/v1/public/retours", {"text": ""}, format="json").status_code == 400
    assert c.post("/api/v1/public/retours", {"text": "x", "type": "INVALID"}, format="json").status_code == 400


def test_export_formula_protection_and_settings(users):
    d = case()
    d.zone = "=1+2"
    d.save()
    c = client(users["R3"])
    r = c.post("/api/v1/exports", {}, format="json")
    assert "'=1+2" in r.content.decode("utf-8-sig")
    assert "TEST-001" not in r.content.decode("utf-8-sig")
    assert c.post("/api/v1/exports", {"format": "xlsx"}, format="json").content[:2] == b"PK"
    assert c.patch("/api/v1/admin/settings", {"retention_days": 0}, format="json").status_code == 400
    assert c.patch("/api/v1/admin/settings", {"retention_days": 30}, format="json").status_code == 200
