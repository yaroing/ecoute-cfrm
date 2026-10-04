import json
from django.db import transaction
from core.crypto import decrypt, encrypt
from core.sensible.models import SensitiveContent


def append_content(dossier_id, items):
    # Encrypt before crossing the dedicated database boundary; no plaintext is staged in public.
    with transaction.atomic(using="sensible"):
        row = SensitiveContent.objects.select_for_update().filter(dossier_id=dossier_id).first()
        data = json.loads(decrypt(row.encrypted)) if row else {"messages": [], "transfer": {}}
        known = {x["id"] for x in data["messages"]}
        data["messages"].extend(x for x in items if x["id"] not in known)
        SensitiveContent.objects.update_or_create(
            dossier_id=dossier_id, defaults={"encrypted": encrypt(json.dumps(data))}
        )


def read_content(dossier_id):
    row = SensitiveContent.objects.filter(dossier_id=dossier_id).first()
    return json.loads(decrypt(row.encrypted)) if row and row.encrypted else {"messages": [], "transfer": {}}


def set_transfer(dossier_id, data):
    with transaction.atomic(using="sensible"):
        row = SensitiveContent.objects.select_for_update().get(dossier_id=dossier_id)
        content = json.loads(decrypt(row.encrypted))
        content["transfer"].update(data)
        row.encrypted = encrypt(json.dumps(content))
        row.save()


def purge_content(dossier_id):
    SensitiveContent.objects.filter(dossier_id=dossier_id).update(encrypted="")


def archive_ordinary(dossier):
    """Preserve ordinary history before removing plaintext copies during a switch."""
    items = [{"id": str(m.pk), "text": m.text, "created": m.created.isoformat()} for m in dossier.messages.all()]
    items += [
        {"id": f"record-{r.pk}", "text": json.dumps(r.data, ensure_ascii=False), "created": r.created.isoformat()}
        for r in dossier.records.all()
    ]
    items += [{"id": f"reply-{r.pk}", "text": r.text, "created": r.created.isoformat()} for r in dossier.replies.all()]
    append_content(dossier.pk, items)
