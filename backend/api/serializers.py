from rest_framework import serializers
from core.models import Dossier, Action, Restitution, Reply, User


class InputSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=8000, trim_whitespace=True)
    address = serializers.CharField(max_length=120, required=False, allow_blank=True)
    consent = serializers.BooleanField(default=False)
    type = serializers.ChoiceField(choices=["QUESTION", "PLAINTE", "SUGGESTION", "SATISFACTION"], default="PLAINTE")
    zone = serializers.CharField(max_length=80, default="Non précisée")
    project = serializers.CharField(max_length=80, default="Assistance communautaire")
    language = serializers.CharField(max_length=10, default="fr")
    sensitive = serializers.BooleanField(default=False)
    key = serializers.CharField(max_length=120, required=False)


class QualificationSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["QUESTION", "PLAINTE", "SUGGESTION", "SATISFACTION"])
    theme = serializers.CharField(max_length=80)
    urgency = serializers.ChoiceField(choices=["NORMALE", "URGENTE"])
    zone = serializers.CharField(max_length=80, required=False)
    project = serializers.CharField(max_length=80, required=False)
    sensitive = serializers.BooleanField(default=False)


class TransitionSerializer(serializers.Serializer):
    state = serializers.CharField(max_length=30)
    reason = serializers.CharField(max_length=500, required=False, allow_blank=True)
    owner = serializers.IntegerField(required=False)
    recipient = serializers.CharField(max_length=200, required=False)
    receipt = serializers.CharField(max_length=500, required=False)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "first_name", "role", "is_active"]


class DossierSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.first_name", default=None)
    agent_name = serializers.CharField(source="agent.first_name", default=None)
    preview = serializers.SerializerMethodField()

    class Meta:
        model = Dossier
        fields = [
            "id",
            "reference",
            "channel",
            "type",
            "theme",
            "zone",
            "project",
            "language",
            "urgency",
            "state",
            "owner",
            "owner_name",
            "agent_name",
            "created",
            "due",
            "closed",
            "closure_reason",
            "reopen_count",
            "reopen_requested",
            "preview",
        ]

    def get_preview(self, obj):
        if obj.sensitive:
            return "Contenu confidentiel"
        first = next(iter(obj.messages.all()), None)
        return first.text[:150] if first else ""


class ReplySerializer(serializers.ModelSerializer):
    class Meta:
        model = Reply
        fields = ["id", "text", "status", "created", "sent", "understood", "author", "validator"]


class RestitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restitution
        fields = ["id", "date", "channel", "zone", "message"]


class ActionSerializer(serializers.ModelSerializer):
    restitutions = RestitutionSerializer(many=True, read_only=True)
    owner_name = serializers.CharField(source="owner.first_name", read_only=True)
    dossiers = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Dossier.objects.filter(sensitive=False), required=False
    )
    status = serializers.ChoiceField(choices=["PLANIFIEE", "EN_COURS", "REALISEE"], default="PLANIFIEE")

    class Meta:
        model = Action
        fields = ["id", "title", "project", "owner", "owner_name", "due", "status", "proof", "dossiers", "restitutions"]

    def validate(self, attrs):
        if attrs.get("status") == "REALISEE" and not attrs.get("proof", getattr(self.instance, "proof", "")):
            raise serializers.ValidationError("Une preuve de mise en œuvre est obligatoire.")
        return attrs
