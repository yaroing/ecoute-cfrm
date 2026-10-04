import hashlib
import hmac
import time
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed
from core.crypto import encrypt, fingerprint
from core.models import Contact
from core.reception.contracts import Incoming


def signature(channel, timestamp, body):
    return hmac.new(
        settings.WEBHOOK_SECRETS[channel].encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()


def verify(channel, timestamp, body, supplied):
    try:
        fresh = abs(time.time() - int(timestamp)) <= 300
    except (ValueError, TypeError):
        fresh = False
    if not fresh or not hmac.compare_digest(signature(channel, str(timestamp), body), supplied):
        raise AuthenticationFailed("Signature ou horodatage invalide.")


@transaction.atomic
def normalize(data, channel, key):
    address = data.get("address", "").strip()
    contact = None
    if address:
        contact, _ = Contact.objects.get_or_create(
            fingerprint=fingerprint(address),
            defaults={"encrypted_address": encrypt(address), "channel": channel, "consent": data.get("consent", False)},
        )
    return Incoming(
        channel=channel,
        key=channel + ":" + key,
        external_id=key,
        text=data["text"],
        contact_id=contact.pk if contact else None,
        type=data.get("type", "PLAINTE"),
        zone=data.get("zone", "Non précisée"),
        project=data.get("project", "Assistance communautaire"),
        language=data.get("language", "fr"),
        sensitive=data.get("sensitive", False),
    )
