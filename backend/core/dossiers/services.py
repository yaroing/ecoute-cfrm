from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from core.models import Record, User
from core.events.services import emit
from core.attribution.services import business_due
from core.sensible.services import archive_ordinary, set_transfer


def require(actor, roles):
    if actor.role not in roles:
        raise PermissionDenied("Action non autorisée pour ce rôle.")


def record(dossier, kind, data, actor):
    Record.objects.create(dossier=dossier, kind=kind, data=data, author=actor)


@transaction.atomic
def qualify(dossier, data, actor):
    require(actor, ["R3"])
    if dossier.sensitive:
        raise ValidationError("Utiliser l’espace sensible.")
    before = {k: getattr(dossier, k) for k in ["type", "theme", "urgency", "zone", "project"]}
    for key in before:
        if key in data:
            setattr(dossier, key, data[key])
    if data.get("sensitive"):
        archive_ordinary(dossier)
        dossier.messages.update(text="")
        dossier.records.all().delete()
        dossier.replies.all().delete()
        dossier.outgoing.all().delete()
        dossier.actions.clear()
        dossier.sensitive = True
        dossier.state = "CLOISONNE"
        dossier.closed = None
        dossier.closure_reason = ""
        dossier.owner = None
        dossier.zone = dossier.theme = "Confidentiel"
        dossier.due = timezone.now() + timedelta(hours=24)
        emit("DossierBascule", dossier, actor)
    else:
        if dossier.state == "RECU":
            dossier.state = "TRIE"
        dossier.due = business_due(dossier.created, dossier.type, dossier.urgency)
        record(dossier, "QUALIFICATION", {"before": before, "after": {k: getattr(dossier, k) for k in before}}, actor)
        emit("DossierQualifie", dossier, actor)
    dossier.save()
    return dossier


@transaction.atomic
def transition(dossier, data, actor):
    target = data["state"]
    reason = data.get("reason", "").strip()
    if dossier.sensitive:
        require(actor, ["R4"])
        allowed = {"CLOISONNE": "PRIS_EN_CHARGE", "PRIS_EN_CHARGE": "TRANSFERE", "TRANSFERE": "CLOTURE"}
        if allowed.get(dossier.state) != target:
            raise ValidationError("Transition sensible interdite.")
        if target == "PRIS_EN_CHARGE":
            dossier.sensitive_taken = timezone.now()
            dossier.suspected = False
            dossier.due = dossier.created + timedelta(hours=48)
        elif target == "TRANSFERE":
            if not data.get("recipient", "").strip():
                raise ValidationError("Destinataire obligatoire.")
            set_transfer(dossier.pk, {"recipient": data["recipient"], "date": timezone.now().isoformat()})
        elif target == "CLOTURE":
            if not data.get("receipt", "").strip():
                raise ValidationError("Accusé de prise en charge obligatoire.")
            set_transfer(dossier.pk, {"receipt": data["receipt"]})
            dossier.closure_reason = "TRANSFERE"
            dossier.closed = timezone.now()
    else:
        if target == "ATTRIBUE":
            require(actor, ["R3"])
            if dossier.state not in ["TRIE", "ATTRIBUE", "EN_TRAITEMENT"]:
                raise ValidationError("Qualification obligatoire avant attribution.")
            if dossier.owner_id and not reason:
                raise ValidationError("Motif de réattribution obligatoire.")
            owner = User.objects.filter(pk=data.get("owner"), role="R2", is_active=True).first()
            if not owner:
                raise ValidationError("Choisir un gestionnaire actif.")
            dossier.owner = owner
        elif target == "EN_TRAITEMENT":
            if dossier.state == "CLOTURE":
                require(actor, ["R3"])
                if not reason or dossier.merged_into_id:
                    raise ValidationError("Motif obligatoire ; annuler d’abord une éventuelle fusion.")
                dossier.reopen_count += 1
                dossier.reopen_requested = False
                dossier.closed = None
                dossier.closure_reason = ""
                dossier.due = business_due(timezone.now(), dossier.type, dossier.urgency)
            elif dossier.state == "ATTRIBUE":
                require(actor, ["R2", "R3"])
            else:
                raise ValidationError("Transition interdite.")
        elif target == "CLOTURE":
            require(actor, ["R3"])
            options = ["RESOLU", "REPONDU_SANS_ACTION", "REFERE", "NON_JOIGNABLE", "HORS_MANDAT", "DOUBLON"]
            if reason not in options or dossier.state not in ["EN_TRAITEMENT", "REPONSE_TRANSMISE"]:
                raise ValidationError("État ou motif de clôture invalide.")
            if dossier.state != "REPONSE_TRANSMISE" and reason in ["RESOLU", "REPONDU_SANS_ACTION", "REFERE"]:
                raise ValidationError("Une réponse transmise est requise pour ce motif.")
            if reason == "NON_JOIGNABLE" and dossier.records.filter(kind="TENTATIVE").count() < 3:
                raise ValidationError("Trois tentatives de contact documentées sont requises.")
            dossier.closed = timezone.now()
            dossier.closure_reason = reason
        else:
            raise ValidationError("Transition interdite ; utiliser le parcours de réponse.")
        record(
            dossier,
            "TRANSITION",
            {"before": dossier.state, "after": target, "reason": reason, "owner": dossier.owner_id},
            actor,
        )
    dossier.state = target
    dossier.save()
    emit(
        {"ATTRIBUE": "DossierAttribue", "CLOTURE": "DossierCloture", "TRANSFERE": "SignalementTransfere"}.get(
            target, "EtatModifie"
        ),
        dossier,
        actor,
    )
    return dossier
