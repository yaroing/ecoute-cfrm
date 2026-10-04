import hashlib
import json
from django.db import transaction
from django.utils import timezone
from core.models import Audit, Outbox, Counter, Notification, Dossier, User


def digest(previous, event):
    payload = [previous, event.pk, event.event, event.object_id, event.actor_id, event.created.isoformat()]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


@transaction.atomic
def dispatch():
    # A dedicated lock serializes chain appends, including across worker processes.
    Counter.objects.get_or_create(year=0)
    Counter.objects.select_for_update().get(year=0)
    for event in Outbox.objects.select_for_update().filter(processed=None).order_by("id")[:500]:
        previous = Audit.objects.order_by("-id").values_list("digest", flat=True).first() or "0" * 64
        Audit.objects.create(
            event_id=event,
            action=event.event,
            object_id=event.object_id,
            actor_id=event.actor_id,
            created=event.created,
            previous=previous,
            digest=digest(previous, event),
        )
        dossier = Dossier.objects.filter(pk=event.object_id).first() if len(event.object_id) == 36 else None
        if dossier and event.event in [
            "DossierBascule",
            "DossierAttribue",
            "EcheanceProche",
            "EcheanceDepassee",
            "EnvoiEchoue",
        ]:
            recipients = User.objects.filter(role="R4" if dossier.sensitive else "R3", is_active=True)
            ids = set(recipients.values_list("id", flat=True))
            if dossier.owner_id and not dossier.sensitive:
                ids.add(dossier.owner_id)
            Notification.objects.bulk_create([Notification(event=event, user_id=uid) for uid in ids])
        event.processed = timezone.now()
        event.save()


def verify_chain():
    previous = "0" * 64
    for row in Audit.objects.select_related("event_id").order_by("id"):
        if row.previous != previous or row.digest != digest(previous, row.event_id):
            return False
        previous = row.digest
    return True
