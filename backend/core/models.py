import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    role = models.CharField(max_length=2, default="R1")
    totp_secret = models.TextField(blank=True)
    last_totp_step = models.BigIntegerField(default=-1)
    failed_logins = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True)


class Session(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    expires = models.DateTimeField()
    refresh_hash = models.CharField(max_length=64)
    refresh_expires = models.DateTimeField()
    last_seen = models.DateTimeField(default=timezone.now)


class Setting(models.Model):
    key = models.CharField(max_length=80, primary_key=True)
    value = models.JSONField()


class Contact(models.Model):
    fingerprint = models.CharField(max_length=64, unique=True)
    encrypted_address = models.TextField()
    channel = models.CharField(max_length=30)
    consent = models.BooleanField(default=False)
    stopped = models.BooleanField(default=False)


class Dossier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=30, unique=True)
    channel = models.CharField(max_length=30)
    type = models.CharField(max_length=20, default="PLAINTE")
    theme = models.CharField(max_length=80, default="À qualifier")
    zone = models.CharField(max_length=80, default="Non précisée")
    project = models.CharField(max_length=80, default="Assistance communautaire")
    language = models.CharField(max_length=10, default="fr")
    urgency = models.CharField(max_length=20, default="NORMALE")
    state = models.CharField(max_length=30, default="RECU", db_index=True)
    sensitive = models.BooleanField(default=False, db_index=True)
    suspected = models.BooleanField(default=False)
    contact = models.ForeignKey(Contact, null=True, on_delete=models.SET_NULL)
    owner = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="assigned")
    agent = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="collected")
    created = models.DateTimeField(default=timezone.now, db_index=True)
    due = models.DateTimeField(null=True, db_index=True)
    acknowledged = models.DateTimeField(null=True)
    responded = models.DateTimeField(null=True)
    closed = models.DateTimeField(null=True)
    sensitive_taken = models.DateTimeField(null=True)
    closure_reason = models.CharField(max_length=40, blank=True)
    reopen_count = models.PositiveIntegerField(default=0)
    reopen_requested = models.BooleanField(default=False)
    merged_into = models.ForeignKey("self", null=True, on_delete=models.SET_NULL)


class Counter(models.Model):
    year = models.IntegerField(primary_key=True)
    value = models.PositiveIntegerField(default=0)


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="messages")
    key = models.CharField(max_length=180, unique=True)
    external_id = models.CharField(max_length=120)
    text = models.TextField(blank=True)
    channel = models.CharField(max_length=30)
    created = models.DateTimeField(default=timezone.now)


class Record(models.Model):
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="records")
    kind = models.CharField(max_length=30)
    data = models.JSONField(default=dict)
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(default=timezone.now)


class Reply(models.Model):
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="replies")
    text = models.TextField()
    status = models.CharField(max_length=20, default="PREPAREE")
    author = models.ForeignKey(User, on_delete=models.PROTECT, related_name="drafts")
    validator = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name="validations")
    created = models.DateTimeField(default=timezone.now)
    sent = models.DateTimeField(null=True)
    understood = models.DateTimeField(null=True)


class Outgoing(models.Model):
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="outgoing")
    reply = models.OneToOneField(Reply, null=True, on_delete=models.CASCADE)
    kind = models.CharField(max_length=20, default="ACK")
    text = models.TextField()
    channel = models.CharField(max_length=30)
    status = models.CharField(max_length=20, default="EN_FILE")
    attempts = models.PositiveIntegerField(default=0)
    next_attempt = models.DateTimeField(default=timezone.now)
    created = models.DateTimeField(default=timezone.now)
    sent = models.DateTimeField(null=True)


class Action(models.Model):
    title = models.CharField(max_length=200)
    project = models.CharField(max_length=80)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    due = models.DateField()
    status = models.CharField(max_length=20, default="PLANIFIEE")
    proof = models.TextField(blank=True)
    dossiers = models.ManyToManyField(Dossier, related_name="actions")
    created = models.DateTimeField(default=timezone.now)


class Restitution(models.Model):
    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="restitutions")
    date = models.DateField()
    channel = models.CharField(max_length=40)
    zone = models.CharField(max_length=80)
    message = models.TextField()


class Outbox(models.Model):
    event = models.CharField(max_length=60)
    object_id = models.CharField(max_length=60)
    actor_id = models.IntegerField(null=True)
    created = models.DateTimeField(default=timezone.now)
    processed = models.DateTimeField(null=True)


class Audit(models.Model):
    event_id = models.OneToOneField(Outbox, on_delete=models.PROTECT)
    action = models.CharField(max_length=60)
    object_id = models.CharField(max_length=60)
    actor_id = models.IntegerField(null=True)
    created = models.DateTimeField()
    previous = models.CharField(max_length=64)
    digest = models.CharField(max_length=64)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Journal en insertion seule")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Journal en insertion seule")


class Notification(models.Model):
    event = models.ForeignKey(Outbox, on_delete=models.PROTECT)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    read = models.BooleanField(default=False)


class Fusion(models.Model):
    source = models.ForeignKey(Dossier, on_delete=models.PROTECT, related_name="fusions_source")
    target = models.ForeignKey(Dossier, on_delete=models.PROTECT, related_name="fusions_target")
    message_ids = models.JSONField()
    previous_state = models.CharField(max_length=30)
    undone = models.BooleanField(default=False)
