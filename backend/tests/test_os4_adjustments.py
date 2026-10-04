import pytest
from rest_framework.test import APIClient
from core.models import Dossier, Outgoing

pytestmark = pytest.mark.django_db(databases=["default", "sensible"])


def test_sensitive_ack_has_reference_and_deadline_without_disclosing_nature():
    response = APIClient().post(
        "/api/v1/public/retours",
        {"text": "EXERCICE FICTIF fraude MARQUEUR_SECRET", "key": "os4-ack", "address": "FICTIF-OS4", "consent": True},
        format="json",
    )
    assert response.status_code == 201
    dossier = Dossier.objects.get()
    assert dossier.sensitive
    ack = Outgoing.objects.get().text
    assert dossier.reference in ack
    assert dossier.due.strftime("%d/%m/%Y") in ack
    assert "fraude" not in ack.lower()
    assert "MARQUEUR_SECRET" not in ack
