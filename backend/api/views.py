import csv
import io
import json
import secrets
import time
import uuid
from datetime import timedelta
import pyotp
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError, NotFound, AuthenticationFailed
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from core.models import (
    User,
    Session,
    Dossier,
    Message,
    Record,
    Reply,
    Outgoing,
    Action,
    Setting,
    Audit,
    Fusion,
    Notification,
)
from core.crypto import decrypt, encrypt
from core.administration.services import DEFAULTS, config, is_sensitive
from core.dossiers.services import require, qualify, transition, record
from core.reception.services import receive
from core.reponses.services import prepare, validate, document_manual_delivery
from core.apprentissage.services import save_action, save_restitution
from core.events.services import emit
from core.audit.services import dispatch, verify_chain
from core.sensible.services import read_content
from core.pilotage.services import indicators, filtered
from adapters.inbound.channels import normalize, verify, signature
from adapters.worker import run
from api.security import token_hash, PublicThrottle, LoginThrottle
from api.serializers import (
    InputSerializer,
    QualificationSerializer,
    TransitionSerializer,
    UserSerializer,
    DossierSerializer,
    ReplySerializer,
    ActionSerializer,
    RestitutionSerializer,
)


def checked(cls, data, **kwargs):
    s = cls(data=data, **kwargs)
    s.is_valid(raise_exception=True)
    return s


def required_text(data, key="text", maximum=8000):
    s = serializers.CharField(max_length=maximum, trim_whitespace=True)
    return s.run_validation(data.get(key))


def visible(user):
    qs = Dossier.objects.filter(sensitive=False)
    if user.role == "R2":
        return qs.filter(owner=user)
    if user.role == "R3":
        return qs
    if user.role == "R1":
        return qs.filter(agent=user, created__gte=timezone.now() - timedelta(days=7))
    return qs.none()


def get_case(request, pk, sensitive=False, lock=False):
    try:
        pk = uuid.UUID(str(pk))
    except (ValueError, TypeError):
        raise NotFound()
    qs = Dossier.objects.filter(sensitive=True) if sensitive and request.user.role == "R4" else visible(request.user)
    if sensitive and request.user.role != "R4":
        emit("AccesRefuse", pk, request.user)
        raise NotFound()
    if lock:
        qs = qs.select_for_update()
    obj = qs.filter(pk=pk).first()
    if not obj:
        emit("AccesRefuse", pk, request.user)
        raise NotFound()
    return obj


def issue_session(user):
    access, refresh = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    Session.objects.create(
        key=token_hash(access),
        user=user,
        expires=timezone.now() + timedelta(minutes=15),
        refresh_hash=token_hash(refresh),
        refresh_expires=timezone.now() + timedelta(hours=8),
    )
    return {"token": access, "refresh": refresh, "user": UserSerializer(user).data, "expires_in": 900}


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    user = User.objects.filter(username=request.data.get("username"), is_active=True).first()
    now = timezone.now()
    if user and user.locked_until and user.locked_until > now:
        raise AuthenticationFailed("Compte temporairement verrouillé (15 minutes).")
    valid = user and user.check_password(str(request.data.get("password", "")))
    if valid and user.role in ["R4", "R6"]:
        step = int(time.time()) // 30
        valid = bool(
            user.totp_secret
            and step > user.last_totp_step
            and pyotp.TOTP(decrypt(user.totp_secret)).verify(str(request.data.get("otp", "")))
        )
        if valid:
            user.last_totp_step = step
    if not valid:
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_logins = 0
            user.save()
        raise AuthenticationFailed("Identifiants ou code de double authentification incorrects.")
    user.failed_logins = 0
    user.locked_until = None
    user.last_login = now
    user.save()
    emit("Connexion", user, user)
    return Response(issue_session(user))


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def refresh(request):
    with transaction.atomic():
        session = (
            Session.objects.select_for_update()
            .select_related("user")
            .filter(refresh_hash=token_hash(str(request.data.get("refresh", ""))))
            .first()
        )
        now = timezone.now()
        if (
            not session
            or session.refresh_expires < now
            or not session.user.is_active
            or now - session.last_seen > timedelta(minutes=15 if session.user.role == "R4" else 30)
        ):
            raise AuthenticationFailed("Session expirée.")
        user = session.user
        session.delete()
        return Response(issue_session(user))


@api_view(["POST"])
def logout(request):
    request.auth.delete()
    return Response(status=204)


@api_view(["GET"])
@permission_classes([AllowAny])
def configuration(request):
    return Response(
        {
            **{k: config(k) for k in ["themes", "zones", "projects", "languages", "referral_contact", "keywords"]},
            "simulation": settings.SIMULATION,
        }
    )


def incoming_result(data, channel, key, actor=None):
    with transaction.atomic():
        dossier, duplicate = receive(normalize(data, channel, key), actor)
    run()
    return {
        "id": str(dossier.pk) if dossier else None,
        "reference": dossier.reference if dossier else None,
        "duplicate": duplicate,
        "key": key,
        "due": dossier.due if dossier else None,
        "message": "Merci, votre message est bien reçu." if dossier else "Les messages sortants sont désactivés.",
    }


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([PublicThrottle])
def public_return(request):
    data = checked(InputSerializer, request.data).validated_data
    key = request.headers.get("Idempotency-Key") or data.get("key") or str(uuid.uuid4())
    if len(key) > 120:
        raise ValidationError("Clé trop longue.")
    return Response(incoming_result(data, "WEB", key), status=201)


@api_view(["POST"])
def agent_sync(request):
    require(request.user, ["R1"])
    items = request.data.get("items")
    if not isinstance(items, list) or len(items) > 100:
        raise ValidationError("Lot attendu, de 100 retours au plus.")
    results = []
    for item in items:
        try:
            data = checked(InputSerializer, item).validated_data
            if not data.get("key"):
                raise ValidationError("Clé obligatoire.")
            # A queued sensitive item is refused, never copied into the ordinary store.
            if data.get("sensitive") or is_sensitive(data["text"]):
                raise ValidationError("SENSIBLE: supprimer la saisie locale et contacter le référent.")
            results.append(
                incoming_result(data, "AGENT", f"{request.user.pk}:{data['key']}", request.user) | {"key": data["key"]}
            )
        except ValidationError as error:
            results.append({"key": item.get("key"), "error": str(error.detail)})
    return Response({"results": results})


def signed_ingest(channel, timestamp, raw, supplied):
    if not settings.SIMULATION:
        raise NotFound()
    if channel not in ["sms", "messagerie"]:
        raise NotFound()
    verify(channel, timestamp, raw, supplied)
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("JSON invalide.")
    data = checked(InputSerializer, body).validated_data
    if not data.get("key"):
        raise ValidationError("Identifiant du fournisseur obligatoire.")
    return incoming_result(data, "SMS_SIMULE" if channel == "sms" else "MESSAGERIE_SIMULEE", data["key"])


@api_view(["POST"])
@permission_classes([AllowAny])
def webhook(request, channel):
    return Response(
        signed_ingest(channel, request.headers.get("X-Timestamp"), request.body, request.headers.get("X-Signature", ""))
    )


@api_view(["POST", "GET"])
def simulator(request):
    require(request.user, ["R3"])
    if not settings.SIMULATION:
        raise NotFound()
    if request.method == "GET":
        return Response(
            list(
                Outgoing.objects.filter(channel__in=["SMS_SIMULE", "MESSAGERIE_SIMULEE"])
                .order_by("-id")
                .values("id", "dossier__reference", "text", "channel", "status", "attempts", "created")[:80]
            )
        )
    channel = request.data.get("channel", "sms")
    if channel not in ["sms", "messagerie"]:
        raise ValidationError("Canal invalide.")
    data = checked(InputSerializer, request.data).validated_data
    data.setdefault("key", str(uuid.uuid4()))
    raw = json.dumps(data).encode()
    timestamp = str(int(time.time()))
    # The console and public webhook share exactly the same signed handler.
    return Response(signed_ingest(channel, timestamp, raw, signature(channel, timestamp, raw)))


@api_view(["POST"])
@permission_classes([AllowAny])
def delivery(request, channel):
    if not settings.SIMULATION or channel not in ["sms", "messagerie"]:
        raise NotFound()
    verify(channel, request.headers.get("X-Timestamp"), request.body, request.headers.get("X-Signature", ""))
    with transaction.atomic():
        message = get_object_or_404(
            Outgoing.objects.select_for_update(),
            pk=request.data.get("id"),
            channel="SMS_SIMULE" if channel == "sms" else "MESSAGERIE_SIMULEE",
        )
        if message.status not in ["ENVOYE", "LIVRE"]:
            raise ValidationError("Le message doit avoir été envoyé.")
        message.status = "LIVRE"
        message.save()
        if message.reply:
            message.reply.status = "RECUE"
            message.reply.save()
        emit("MessageLivre", message.dossier)
    return Response({"status": "LIVRE"})


@api_view(["GET"])
def dossiers(request):
    qs = visible(request.user).select_related("owner", "agent").prefetch_related("messages").order_by("-created", "-id")
    for field in ["state", "theme", "zone", "owner", "project"]:
        if request.query_params.get(field):
            qs = qs.filter(**{field: request.query_params[field]})
    if request.query_params.get("q"):
        q = request.query_params["q"]
        qs = qs.filter(Q(reference__icontains=q) | Q(messages__text__icontains=q)).distinct()
    if request.query_params.get("late") == "1":
        qs = qs.filter(due__lt=timezone.now()).exclude(state="CLOTURE")
    from django.core import signing

    total = qs.count()
    cursor = request.query_params.get("cursor")
    if cursor:
        try:
            moment, pk = signing.loads(cursor, salt="cursor", max_age=86400)
            qs = qs.filter(Q(created__lt=moment) | Q(created=moment, id__lt=pk))
        except Exception:
            raise ValidationError("Curseur invalide.")
    page = list(qs[:31])
    next_cursor = (
        signing.dumps([page[29].created.isoformat(), str(page[29].pk)], salt="cursor") if len(page) > 30 else None
    )
    return Response({"results": DossierSerializer(page[:30], many=True).data, "next": next_cursor, "count": total})


@api_view(["GET"])
def detail(request, pk):
    dossier = get_case(request, pk)
    result = DossierSerializer(dossier).data
    result["messages"] = list(dossier.messages.order_by("created").values("id", "text", "channel", "created"))
    result["records"] = list(
        dossier.records.order_by("-created").values("id", "kind", "data", "author__first_name", "created")
    )
    result["replies"] = ReplySerializer(dossier.replies.all(), many=True).data
    result["actions"] = ActionSerializer(dossier.actions.all(), many=True).data
    result["contact"] = {
        "available": bool(dossier.contact_id),
        "consent": bool(dossier.contact and dossier.contact.consent),
        "stopped": bool(dossier.contact and dossier.contact.stopped),
        "channel": dossier.contact.channel if dossier.contact else None,
    }
    result["outgoing"] = list(dossier.outgoing.values("id", "status", "attempts", "kind", "sent"))
    result["fusions"] = list(dossier.fusions_target.filter(undone=False).values("id", "source__reference"))
    return Response(result)


@api_view(["PATCH"])
def qualification(request, pk):
    data = checked(QualificationSerializer, request.data).validated_data
    with transaction.atomic():
        dossier = qualify(get_case(request, pk, lock=True), data, request.user)
    dispatch()
    return Response({"id": str(dossier.pk), "state": dossier.state})


@api_view(["POST"])
def transitions(request, pk):
    data = checked(TransitionSerializer, request.data).validated_data
    with transaction.atomic():
        dossier = transition(get_case(request, pk, lock=True), data, request.user)
    dispatch()
    return Response(DossierSerializer(dossier).data)


@api_view(["POST"])
def notes(request, pk):
    require(request.user, ["R2", "R3"])
    dossier = get_case(request, pk)
    text = required_text(request.data)
    if is_sensitive(text):
        raise ValidationError("Ce texte peut être sensible. Basculez le dossier avant de poursuivre.")
    kind = "TENTATIVE" if request.data.get("attempt") else "NOTE"
    record(dossier, kind, {"text": text}, request.user)
    emit("NoteAjoutee", dossier, request.user)
    return Response(status=201)


@api_view(["POST"])
def referrals(request, pk):
    require(request.user, ["R2", "R3"])
    dossier = get_case(request, pk)
    recipient = required_text(request.data, "recipient", 200)
    issue = str(request.data.get("issue", "Issue attendue"))[:1000]
    if is_sensitive(recipient + issue):
        raise ValidationError("Utiliser le circuit sensible pour ces informations.")
    if dossier.state != "EN_TRAITEMENT":
        raise ValidationError("Dossier en traitement requis.")
    if request.data.get("id"):
        row = get_object_or_404(Record, pk=request.data["id"], dossier=dossier, kind="REFERENCEMENT")
        row.data = {"recipient": recipient, "issue": issue}
        row.save()
    else:
        record(dossier, "REFERENCEMENT", {"recipient": recipient, "issue": issue}, request.user)
    emit("ReferencementEnregistre", dossier, request.user)
    return Response(status=201)


@api_view(["POST"])
def replies(request, pk):
    text = required_text(request.data)
    if is_sensitive(text):
        raise ValidationError("Ce texte peut être sensible : utilisez le circuit cloisonné.")
    with transaction.atomic():
        reply = prepare(get_case(request, pk, lock=True), text, request.user)
    return Response(ReplySerializer(reply).data, status=201)


@api_view(["POST"])
def validation(request, pk, rid):
    with transaction.atomic():
        dossier = get_case(request, pk, lock=True)
        reply = get_object_or_404(Reply, pk=rid, dossier=dossier)
        accepted = serializers.BooleanField().run_validation(request.data.get("accepted", True))
        validate(dossier, reply, accepted, request.user, str(request.data.get("reason", "")))
    run()
    reply.refresh_from_db()
    return Response(ReplySerializer(reply).data)


@api_view(["POST"])
def understanding(request, pk, rid):
    require(request.user, ["R2", "R3"])
    dossier = get_case(request, pk)
    reply = get_object_or_404(Reply, pk=rid, dossier=dossier, status__in=["TRANSMISE", "RECUE"])
    reply.understood = timezone.now()
    reply.save()
    emit("ComprehensionConfirmee", dossier, request.user)
    return Response(ReplySerializer(reply).data)


@api_view(["GET"])
def contact_detail(request, pk):
    require(request.user, ["R2", "R3"])
    dossier = get_case(request, pk)
    if not dossier.contact or not dossier.contact.consent or dossier.contact.stopped:
        raise ValidationError("Aucun contact autorisé.")
    emit("ContactConsulte", dossier, request.user)
    return Response({"address": decrypt(dossier.contact.encrypted_address)})


@api_view(["POST"])
def manual_delivery(request, pk, rid):
    evidence = required_text(request.data, "evidence", 1000)
    if is_sensitive(evidence):
        raise ValidationError("Utiliser le circuit sensible.")
    with transaction.atomic():
        dossier = get_case(request, pk, lock=True)
        reply = get_object_or_404(Reply, pk=rid, dossier=dossier)
        document_manual_delivery(dossier, reply, request.user, evidence)
    return Response(ReplySerializer(reply).data)


@api_view(["POST"])
def fusion(request, pk):
    require(request.user, ["R3"])
    with transaction.atomic():
        target = get_case(request, pk, lock=True)
        if request.data.get("undo"):
            row = get_object_or_404(
                Fusion.objects.select_for_update(), pk=request.data["undo"], target=target, undone=False
            )
            if target.sensitive or row.source.sensitive:
                raise ValidationError("Fusion sensible non autorisée.")
            Message.objects.filter(pk__in=row.message_ids).update(dossier=row.source)
            row.source.merged_into = None
            row.source.state = row.previous_state
            row.source.closed = None
            row.source.closure_reason = ""
            row.source.save()
            row.undone = True
            row.save()
            emit("FusionAnnulee", target, request.user)
        else:
            source = get_case(request, request.data.get("source"), lock=True)
            reason = required_text(request.data, "reason", 500)
            if (
                source.pk == target.pk
                or source.merged_into_id
                or target.merged_into_id
                or source.state == "CLOTURE"
                or target.state == "CLOTURE"
            ):
                raise ValidationError("Deux dossiers ouverts distincts sont requis.")
            ids = [str(i) for i in source.messages.values_list("id", flat=True)]
            Fusion.objects.create(source=source, target=target, message_ids=ids, previous_state=source.state)
            source.messages.update(dossier=target)
            source.merged_into = target
            source.state = "CLOTURE"
            source.closed = timezone.now()
            source.closure_reason = "DOUBLON"
            source.save()
            record(target, "FUSION", {"source": str(source.pk), "reason": reason}, request.user)
            emit("DossiersFusionnes", target, request.user)
    return Response({"ok": True})


@api_view(["GET", "POST", "PATCH"])
def actions(request, pk=None):
    require(request.user, ["R3", "R5"])
    if request.method == 'PATCH' and pk is None:
        raise ValidationError('Identifiant d’action obligatoire.')
    if request.method == "GET":
        return Response(
            ActionSerializer(
                Action.objects.prefetch_related("dossiers", "restitutions").select_related("owner").order_by("-id"),
                many=True,
            ).data
        )
    instance = get_object_or_404(Action, pk=pk) if pk else None
    serializer = ActionSerializer(instance, data=request.data, partial=request.method == "PATCH")
    serializer.is_valid(raise_exception=True)
    save_action(serializer, request.user)
    return Response(serializer.data, status=200 if pk else 201)


@api_view(["POST"])
def restitution(request, pk):
    require(request.user, ["R3", "R5"])
    action = get_object_or_404(Action, pk=pk)
    serializer = checked(RestitutionSerializer, request.data)
    save_restitution(serializer, action, request.user)
    return Response(serializer.data, status=201)


@api_view(["GET"])
def sensitive_list(request):
    require(request.user, ["R4"])
    return Response(DossierSerializer(Dossier.objects.filter(sensitive=True).order_by("-created"), many=True).data)


@api_view(["GET", "POST"])
def sensitive_detail(request, pk):
    with transaction.atomic():
        dossier = get_case(request, pk, sensitive=True, lock=request.method == "POST")
        if request.method == "POST":
            transition(dossier, checked(TransitionSerializer, request.data).validated_data, request.user)
        emit("LectureSensible", dossier, request.user)
    dispatch()
    return Response({**DossierSerializer(dossier).data, **read_content(pk)})


@api_view(["GET"])
def dashboard(request):
    require(request.user, ["R3", "R5"])
    return Response(indicators(request.query_params))


@api_view(["POST"])
def export(request):
    require(request.user, ["R3", "R5"])
    fields = ["reference", "channel", "type", "theme", "zone", "project", "state", "closure_reason", "created", "due"]
    qs = filtered(Dossier.objects.filter(sensitive=False, merged_into=None), request.data)
    rows = [fields]
    for row in qs.values_list(*fields):
        # Prevent spreadsheet formula injection in both formats.
        rows.append(
            [("'" + str(v)) if str(v).startswith(("=", "+", "-", "@", "\t", "\r")) else str(v or "") for v in row]
        )
    emit("ExportRealise", "export", request.user)
    dispatch()
    if request.data.get("format") == "xlsx":
        from openpyxl import Workbook

        workbook = Workbook()
        for row in rows:
            workbook.active.append(row)
        output = io.BytesIO()
        workbook.save(output)
        response = HttpResponse(
            output.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        extension = "xlsx"
    else:
        output = io.StringIO()
        csv.writer(output).writerows(rows)
        response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
        extension = "csv"
    response["Content-Disposition"] = f'attachment; filename="feedback-export.{extension}"'
    return response


@api_view(["GET", "PATCH"])
def admin_settings(request):
    require(request.user, ["R3", "R6"])
    if request.method == "PATCH":
        for key, value in request.data.items():
            if key not in DEFAULTS or not isinstance(value, type(DEFAULTS[key])):
                raise ValidationError("Paramètre ou format inconnu.")
            if key == "retention_days" and not 1 <= value <= 3650:
                raise ValidationError("Durée attendue : 1 à 3650 jours.")
            if key == "delays" and (
                set(value) != set(DEFAULTS[key]) or any(type(v) is not int or not 1 <= v <= 365 for v in value.values())
            ):
                raise ValidationError("Règles de délai invalides.")
            if key in ["themes", "zones", "projects", "keywords"] and (
                not value or any(not isinstance(v, str) or not v.strip() or len(v) > 80 for v in value)
            ):
                raise ValidationError("Liste de libellés non vides attendue.")
        with transaction.atomic():
            for key, value in request.data.items():
                Setting.objects.update_or_create(key=key, defaults={"value": value})
                emit("ParametreModifie", key, request.user)
    return Response({k: config(k) for k in DEFAULTS})


@api_view(["GET", "POST", "PATCH"])
def users(request, pk=None):
    require(request.user, ["R3", "R5", "R6"])
    if request.method == 'PATCH' and pk is None:
        raise ValidationError('Identifiant de compte obligatoire.')
    if request.method == "GET":
        qs = (
            User.objects.all()
            if request.user.role == "R6"
            else User.objects.filter(role__in=["R2", "R3", "R5"], is_active=True)
        )
        return Response(UserSerializer(qs, many=True).data)
    require(request.user, ["R6"])
    user = get_object_or_404(User, pk=pk) if pk else User()
    if user.pk == request.user.pk:
        raise ValidationError("La modification de son propre rôle ou compte est interdite.")
    role = request.data.get("role", user.role)
    if role not in ["R1", "R2", "R3", "R4", "R5", "R6"]:
        raise ValidationError("Rôle invalide.")
    user.username = request.data.get("username", user.username)
    user.first_name = request.data.get("first_name", user.first_name)[:100]
    user.role = role
    user.is_active = serializers.BooleanField().run_validation(request.data.get("is_active", True))
    password = request.data.get("password")
    if not user.pk and not password:
        raise ValidationError("Mot de passe requis.")
    if password:
        if len(password) < 10:
            raise ValidationError("Au moins 10 caractères.")
        user.set_password(password)
    enrollment = None
    if role in ["R4", "R6"] and not user.totp_secret:
        enrollment = pyotp.random_base32()
        user.totp_secret = encrypt(enrollment)
    if not user.username or User.objects.filter(username=user.username).exclude(pk=user.pk).exists():
        raise ValidationError("Nom de compte manquant ou déjà utilisé.")
    user.save()
    Session.objects.filter(user=user).delete()
    emit("RoleAttribue" if role == "R4" else "CompteModifie", user, request.user)
    return Response({**UserSerializer(user).data, "totp_enrollment": enrollment})


@api_view(["GET"])
def audit(request):
    require(request.user, ["R3", "R6"])
    dispatch()
    # Ordinary auditors get neither sensitive object identifiers nor contents.
    hidden = [str(pk) for pk in Dossier.objects.filter(sensitive=True).values_list("pk", flat=True)]
    rows = list(
        Audit.objects.exclude(object_id__in=hidden)
        .order_by("-id")
        .values("id", "action", "object_id", "actor_id", "created", "digest")[:150]
    )
    return Response({"valid": verify_chain(), "results": rows})


@api_view(["GET"])
def notifications(request):
    dispatch()
    return Response(
        list(
            Notification.objects.filter(user=request.user)
            .order_by("-id")
            .values("id", "event__event", "event__object_id", "event__created", "read")[:50]
        )
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok", "simulation": settings.SIMULATION})
