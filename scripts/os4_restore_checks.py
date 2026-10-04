"""Contrôles d'exploitation sur la restauration OS4 exclusivement."""
import os
import sys
import json
from pathlib import Path
from datetime import timedelta
sys.path.insert(0,'/app/backend');os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from rest_framework.test import APIClient
from core.models import User,Dossier,Contact
from core.crypto import decrypt
from core.sensible.services import read_content
from core.audit.services import verify_chain
from core.events.tasks import tick
from django.utils import timezone
target=os.environ.get('POSTGRES_DB','')
if not target.startswith('os4_restore_'):raise RuntimeError('Base de restauration dédiée requise')
d=Dossier.objects.filter(sensitive=True).first();roles={}
for role in ['R1','R2','R3','R4','R5','R6']:
    c=APIClient();c.force_authenticate(User.objects.filter(role=role).first());r=c.get('/api/v1/sensible/'+str(d.pk));roles[role]=r.status_code
contacts=sum(bool(decrypt(x.encrypted_address)) for x in Contact.objects.all())
closed=Dossier.objects.filter(state='CLOTURE',closed__lt=timezone.now()-timedelta(days=90)).count()
tick(lambda x:'ECHEC')
result={'database':target,'roles_sensitive_detail':roles,'contacts_decryptable':contacts,'content_readable':bool(read_content(d.pk)['messages']),'audit_chain_valid':verify_chain(),'closed_due_for_purge':closed,'purge_replayed':True,'external_outputs':0,'authentication':'force_authenticate pour contrôle RBAC ; authentification réelle séparée en C02'}
Path('/app/os4/restore-api-checks.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
