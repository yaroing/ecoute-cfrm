"""Explicit schema for function-based DRF endpoints."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, inline_serializer, OpenApiParameter
from rest_framework import serializers
from api import views
from api.serializers import (
    InputSerializer,
    QualificationSerializer,
    TransitionSerializer,
    ActionSerializer,
    RestitutionSerializer,
)


class AccessScheme(OpenApiAuthenticationExtension):
    target_class = "api.security.AccessAuthentication"
    name = "BearerToken"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "description": "Jeton court obtenu par /auth/login ; renouvellement rotatif.",
        }


schemas = {
    "login": inline_serializer(
        "Login",
        {
            "username": serializers.CharField(),
            "password": serializers.CharField(write_only=True),
            "otp": serializers.CharField(required=False),
        },
    ),
    "refresh": inline_serializer("Refresh", {"refresh": serializers.CharField()}),
    "public_return": InputSerializer,
    "agent_sync": inline_serializer("AgentBatch", {"items": InputSerializer(many=True)}),
    "webhook": InputSerializer,
    "simulator": InputSerializer,
    "qualification": QualificationSerializer,
    "transitions": TransitionSerializer,
    "sensitive_detail": TransitionSerializer,
    "actions": ActionSerializer,
    "restitution": RestitutionSerializer,
    "replies": inline_serializer("ReplyDraft", {"text": serializers.CharField()}),
    "notes": inline_serializer(
        "Note", {"text": serializers.CharField(), "attempt": serializers.BooleanField(required=False)}
    ),
    "validation": inline_serializer(
        "ReplyValidation", {"accepted": serializers.BooleanField(), "reason": serializers.CharField(required=False)}
    ),
}

descriptions = {
    "public_return": "Public, limité à 20 requêtes/minute/IP. Clé Idempotency-Key ou key. Texte sensible immédiatement chiffré et cloisonné.",
    "agent_sync": "R1. Lot de 100 retours ordinaires maximum. Résultat individuel par clé, supprimer uniquement les entrées confirmées.",
    "dossiers": "R1 : collecte récente ; R2 : dossiers attribués ; R3 : ordinaires. Pagination par curseur signé.",
    "sensitive_detail": "R4 avec TOTP uniquement. Toute lecture est journalisée. Refus 404 pour les autres rôles.",
    "dashboard": "R3, R5. Indicateurs agrégés I01 à I10. Aucune ligne sensible ni contact.",
    "export": "R3, R5. CSV ou XLSX sans contenu libre ni contacts, avec protection contre les formules. Export journalisé.",
    "webhook": "Simulation uniquement. HMAC-SHA256(secret, timestamp + point + corps brut), horodatage valide 5 minutes.",
    "audit": "R3, R6. Lecture seule. Contrôle du chaînage SHA-256 ; événements sensibles exclus de la liste ordinaire.",
}

for name in [
    "login",
    "refresh",
    "logout",
    "configuration",
    "public_return",
    "agent_sync",
    "webhook",
    "simulator",
    "delivery",
    "dossiers",
    "detail",
    "qualification",
    "transitions",
    "notes",
    "referrals",
    "replies",
    "validation",
    "understanding",
    "manual_delivery",
    "contact_detail",
    "fusion",
    "actions",
    "restitution",
    "sensitive_list",
    "sensitive_detail",
    "dashboard",
    "export",
    "admin_settings",
    "users",
    "audit",
    "notifications",
    "health",
]:
    parameters = []
    if name in ["webhook", "delivery"]:
        parameters = [
            OpenApiParameter("X-Timestamp", str, OpenApiParameter.HEADER, required=True),
            OpenApiParameter("X-Signature", str, OpenApiParameter.HEADER, required=True),
        ]
    if name == "dossiers":
        parameters = [
            OpenApiParameter(k, str) for k in ["cursor", "q", "state", "zone", "theme", "project", "owner", "late"]
        ]
    if name == "dashboard":
        parameters = [OpenApiParameter(k, str) for k in ["from", "to", "project"]]
    func = getattr(views, name)
    setattr(
        views,
        name,
        extend_schema(
            request=schemas.get(name, OpenApiTypes.OBJECT),
            responses={
                200: {"type": "object"},
                400: {"type": "object"},
                401: {"type": "object"},
                403: {"type": "object"},
                404: {"type": "object"},
            },
            description=descriptions.get(name, "Permissions vérifiées côté serveur. Voir docs/API.md."),
            parameters=parameters,
        )(func),
    )
