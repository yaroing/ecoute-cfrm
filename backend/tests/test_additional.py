import pytest
from django.db import connections, transaction, DatabaseError
from core.models import Audit, User, Dossier, Record, Reply
from core.audit.services import dispatch
from core.events.services import emit
from core.sensible.services import read_content
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db(databases=['default', 'sensible'])

def test_sql_audit_update_and_delete_are_rejected():
    emit('Test', 'test');dispatch()
    for sql in ["UPDATE core_audit SET action='changed'", 'DELETE FROM core_audit']:
        with pytest.raises(DatabaseError):
            with transaction.atomic():
                with connections['default'].cursor() as cursor:
                    cursor.execute(sql)
    assert Audit.objects.count()==1

def test_manual_web_response_and_sensitive_history_preservation():
    c=APIClient();u=User.objects.create_user('s',role='R3');manager=User.objects.create_user('m',role='R2')
    r=c.post('/api/v1/public/retours',{'text':'Retour test','address':'TEST-MANUAL','consent':True},format='json')
    root='/api/v1/dossiers/'+r.data['id'];c.force_authenticate(u)
    assert c.patch(root+'/qualification',{'type':'PLAINTE','theme':'Distribution','urgency':'NORMALE'},format='json').status_code==200
    assert c.post(root+'/transitions',{'state':'ATTRIBUE','owner':manager.pk},format='json').status_code==200
    assert c.post(root+'/transitions',{'state':'EN_TRAITEMENT'},format='json').status_code==200
    assert c.get(root+'/contact').data['address']=='TEST-MANUAL'
    rid=c.post(root+'/reponses',{'text':'Réponse manuelle de test'},format='json').data['id']
    assert c.post(root+f'/reponses/{rid}/transmission-manuelle',{},format='json').status_code==400
    assert c.post(root+f'/reponses/{rid}/transmission-manuelle',{'evidence':'Appel fictif du 3 octobre, réponse expliquée'},format='json').status_code==200
    assert Dossier.objects.get().state=='REPONSE_TRANSMISE'
    assert c.patch(root+'/qualification',{'type':'PLAINTE','theme':'Distribution','urgency':'NORMALE','sensitive':True},format='json').status_code==200
    d=Dossier.objects.get()
    content=read_content(d.pk)
    assert any('Réponse manuelle' in m['text'] for m in content['messages'])
    assert not Reply.objects.exists()
    assert not Record.objects.exists()
    assert c.get(root).status_code==404
