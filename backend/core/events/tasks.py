from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from core.models import Dossier, Outgoing, Outbox, Session
from core.events.services import emit
from core.audit.services import dispatch
from core.administration.services import config
from core.sensible.services import purge_content


def tick(sender):
    now = timezone.now()
    for pk in Outgoing.objects.filter(status__in=["EN_FILE", "REESSAI"], next_attempt__lte=now).values_list(
        "pk", flat=True
    ):
        with transaction.atomic():
            msg = (
                Outgoing.objects.select_for_update(of=("self",)).select_related("dossier__contact", "reply").get(pk=pk)
            )
            if msg.status not in ["EN_FILE", "REESSAI"]:
                continue
            contact = msg.dossier.contact
            if not contact or not contact.consent or contact.stopped:
                msg.status = "ANNULE"
            else:
                try:
                    result = sender(msg)
                except Exception:
                    result = "ECHEC"
                msg.attempts += 1
                if result == "ENVOYE":
                    msg.status = "ENVOYE"
                    msg.sent = now
                    if msg.reply:
                        msg.reply.status = "TRANSMISE"
                        msg.reply.sent = now
                        msg.reply.save()
                        msg.dossier.responded = now
                        msg.dossier.state = "REPONSE_TRANSMISE"
                        msg.dossier.save()
                        emit("ReponseTransmise", msg.dossier)
                elif msg.attempts <= 3:
                    msg.status = "REESSAI"
                    msg.next_attempt = now + timedelta(minutes=[1, 5, 30][msg.attempts - 1])
                else:
                    msg.status = "ECHEC"
                    emit("EnvoiEchoue", msg.dossier)
            msg.save()
    for dossier in Dossier.objects.exclude(state="CLOTURE").filter(due__lte=now + timedelta(days=1)):
        event = "EcheanceDepassee" if dossier.due <= now else "EcheanceProche"
        if not Outbox.objects.filter(
            event=event, object_id=str(dossier.pk), created__gte=now - timedelta(days=1)
        ).exists():
            emit(event, dossier)
    cutoff = now - timedelta(days=config("retention_days"))
    for dossier in Dossier.objects.filter(closed__lte=cutoff):
        if dossier.contact_id:
            contact = dossier.contact
            if (
                not contact.dossier_set.filter(closed__isnull=True).exists()
                and not contact.dossier_set.filter(closed__gt=cutoff).exists()
            ):
                contact.dossier_set.update(contact=None)
                contact.delete()
                emit("PurgeRealisee", dossier)
        if dossier.sensitive:
            purge_content(dossier.pk)
    Session.objects.filter(refresh_expires__lt=now).delete()
    dispatch()
