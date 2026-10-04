import hashlib
from datetime import timedelta
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.throttling import AnonRateThrottle
from core.models import Session


def token_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


class AccessAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return None
        session = Session.objects.select_related("user").filter(pk=token_hash(auth[7:])).first()
        now = timezone.now()
        if (
            not session
            or session.expires <= now
            or not session.user.is_active
            or now - session.last_seen > timedelta(minutes=15 if session.user.role == "R4" else 30)
        ):
            raise AuthenticationFailed("Session expirée. Reconnectez-vous.")
        session.last_seen = now
        session.save(update_fields=["last_seen"])
        return session.user, session

    def authenticate_header(self, request):
        return "Bearer"


class PublicThrottle(AnonRateThrottle):
    scope = "public"


class LoginThrottle(AnonRateThrottle):
    scope = "login"


def problem_handler(exc, context):
    from rest_framework.views import exception_handler

    response = exception_handler(exc, context)
    if response is not None:
        response.data = {
            "type": "about:blank",
            "title": "Requête refusée",
            "status": response.status_code,
            "detail": response.data,
        }
        response["Content-Type"] = "application/problem+json"
    return response


class NoStoreMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        response["X-Frame-Options"] = "DENY"
        return response
