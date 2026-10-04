from django.db import models


class SensitiveContent(models.Model):
    dossier_id = models.UUIDField(unique=True)
    encrypted = models.TextField()
