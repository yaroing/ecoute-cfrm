import base64
import hashlib
import hmac
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


def encrypt(text):
    nonce = os.urandom(12)
    data = AESGCM(bytes.fromhex(settings.FIELD_KEY)).encrypt(nonce, text.encode(), b"cfrm-v1")
    return base64.b64encode(nonce + data).decode()


def decrypt(value):
    if not value:
        return ""
    data = base64.b64decode(value)
    return AESGCM(bytes.fromhex(settings.FIELD_KEY)).decrypt(data[:12], data[12:], b"cfrm-v1").decode()


def fingerprint(value):
    return hmac.new(bytes.fromhex(settings.HMAC_KEY), value.strip().encode(), hashlib.sha256).hexdigest()
