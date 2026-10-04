import re
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from core.models import Contact, Counter, Dossier, Message, Outgoing
from core.administration.services import is_sensitive
from core.attribution.services import business_due
from core.events.services import emit
from core.sensible.services import append_content, archive_ordinary


@transaction.atomic
def receive(incoming, actor=None):
    # Serialize the deduplication check with reference allocation, including anonymous submissions.
    counter, _ = Counter.objects.select_for_update().get_or_create(year=timezone.now().year)
    existing = Message.objects.filter(key=incoming.key).select_related("dossier").first()
    if existing:
        return existing.dossier, True
    contact = Contact.objects.select_for_update().filter(pk=incoming.contact_id).first()
    if incoming.text.strip().upper() == "STOP" and contact:
        contact.stopped = True
        contact.save()
        emit("ContactDesabonne", contact, actor)
        return None, False
    now = timezone.now()
    dossier = None
    if contact:
        ref = re.search(r"FB-\d{4}-\d{6}", incoming.text)
        if ref:
            dossier = Dossier.objects.select_for_update().filter(reference=ref.group(), contact=contact).first()
        if not dossier:
            dossier = (
                Dossier.objects.select_for_update()
                .filter(
                    contact=contact,
                    channel=incoming.channel,
                    state="RECU",
                    created__gte=now - timedelta(minutes=30),
                    sensitive=False,
                )
                .first()
            )
    flagged = incoming.sensitive or is_sensitive(incoming.text)
    if not dossier:
        counter.value += 1
        counter.save()
        dossier = Dossier.objects.create(
            reference=f"FB-{now.year}-{counter.value:06d}",
            channel=incoming.channel,
            contact=contact,
            agent=actor,
            type=incoming.type,
            zone=incoming.zone,
            project=incoming.project,
            language=incoming.language,
            due=business_due(now, incoming.type, "NORMALE"),
        )
    if flagged and not dossier.sensitive:
        archive_ordinary(dossier)
        dossier.messages.update(text="")
        dossier.records.all().delete()
        dossier.replies.all().delete()
        dossier.outgoing.all().delete()
        dossier.actions.clear()
        dossier.sensitive = True
        dossier.suspected = True
        dossier.state = "CLOISONNE"
        dossier.closed = None
        dossier.closure_reason = ""
        dossier.theme = "Confidentiel"
        dossier.zone = "Confidentiel"
        dossier.owner = None
        dossier.due = now + timedelta(hours=24)
        emit("DossierBascule", dossier, actor)
    msg = Message(
        dossier=dossier,
        key=incoming.key,
        external_id=incoming.external_id,
        channel=incoming.channel,
        text="" if dossier.sensitive else incoming.text,
    )
    if dossier.sensitive:
        append_content(dossier.pk, [{"id": str(msg.pk), "text": incoming.text, "created": now.isoformat()}])
    msg.save()
    if dossier.state == "CLOTURE":
        dossier.reopen_requested = True
    if not dossier.acknowledged:
        dossier.acknowledged = now
    dossier.save()
    emit("MessageRecu", dossier, actor)
    neutral = (
        f"Merci, votre message est bien reçu. Référence {dossier.reference}. "
        f"Réponse prévue le {dossier.due:%d/%m/%Y}. "
        "Une personne habilitée vous contactera si vous l’avez accepté."
    )
    ack = (
        neutral
        if dossier.sensitive
        else f"Merci. Référence {dossier.reference}. Réponse prévue le {dossier.due:%d/%m/%Y}. Pour compléter : REF {dossier.reference} + message."
    )
    if contact and contact.consent and not contact.stopped:
        Outgoing.objects.create(dossier=dossier, text=ack, channel=contact.channel)
    return dossier, False
