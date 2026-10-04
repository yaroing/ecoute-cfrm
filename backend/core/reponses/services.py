from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from core.models import Reply, Outgoing
from core.dossiers.services import require, record
from core.events.services import emit


@transaction.atomic
def prepare(dossier, text, actor):
    require(actor, ["R2", "R3"])
    if dossier.sensitive or dossier.state != "EN_TRAITEMENT":
        raise ValidationError("Le dossier doit être ordinaire et en traitement.")
    reply = Reply.objects.create(dossier=dossier, text=text, author=actor)
    dossier.state = "REPONSE_PREPAREE"
    dossier.save()
    record(dossier, "REPONSE_PREPAREE", {"reply": reply.pk}, actor)
    emit("ReponsePreparee", dossier, actor)
    return reply


@transaction.atomic
def validate(dossier, reply, accepted, actor, reason=""):
    require(actor, ["R3"])
    if dossier.state != "REPONSE_PREPAREE" or reply.status != "PREPAREE":
        raise ValidationError("Réponse déjà traitée ou état invalide.")
    if not accepted:
        if not reason.strip():
            raise ValidationError("Motif de refus obligatoire.")
        reply.status = "REFUSEE"
        dossier.state = "EN_TRAITEMENT"
        dossier.save()
    else:
        if not dossier.contact or not dossier.contact.consent or dossier.contact.stopped:
            raise ValidationError("Aucun canal de rappel consenti, ou réception arrêtée par STOP.")
        if dossier.contact.channel not in ["SMS_SIMULE", "MESSAGERIE_SIMULEE"]:
            raise ValidationError(
                "Ce canal ne dispose pas d’adaptateur sortant. Documentez le contact et son issue ; aucun envoi fictif ne sera déclaré."
            )
        reply.status = "VALIDEE"
        Outgoing.objects.create(
            dossier=dossier, reply=reply, kind="REPLY", channel=dossier.contact.channel, text=reply.text
        )
    reply.validator = actor
    reply.save()
    record(dossier, "VALIDATION", {"reply": reply.pk, "accepted": accepted, "reason": reason}, actor)
    emit("ReponseValidee" if accepted else "ReponseRefusee", dossier, actor)
    return reply


@transaction.atomic
def document_manual_delivery(dossier, reply, actor, evidence):
    require(actor, ["R3"])
    if dossier.sensitive or dossier.state != "REPONSE_PREPAREE" or reply.status != "PREPAREE":
        raise ValidationError("Réponse préparée requise.")
    if not dossier.contact or not dossier.contact.consent or dossier.contact.stopped:
        raise ValidationError("Rappel non consenti ou STOP enregistré.")
    if dossier.contact.channel not in ["WEB", "AGENT"]:
        raise ValidationError("Utiliser l’envoi par le canal simulé.")
    now = timezone.now()
    reply.status, reply.sent, reply.validator = "TRANSMISE", now, actor
    reply.save()
    dossier.state, dossier.responded = "REPONSE_TRANSMISE", now
    dossier.save()
    record(
        dossier,
        "TRANSMISSION_MANUELLE",
        {"reply": reply.pk, "evidence": evidence, "channel": dossier.contact.channel},
        actor,
    )
    emit("ReponseTransmise", dossier, actor)
    return reply
