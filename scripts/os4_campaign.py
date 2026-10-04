"""Campagne OS4 sur le clone PostgreSQL fonctionnel, sans données réelles.
Les acteurs sont des comptes fictifs pilotés par APIClient. Les verdicts
portent sur des sous-cas techniques, jamais sur des participants humains.
"""
import os
import sys
import json
import time
import math
import hashlib
from pathlib import Path
from datetime import datetime, timedelta, timezone as tz
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
sys.path.insert(0, '/app/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
import pyotp
from django.db import connections, close_old_connections, transaction, DatabaseError
from django.utils import timezone
from rest_framework.test import APIClient
from core.models import User, Dossier, Message, Contact, Outgoing, Outbox, Action, Restitution, Session, Setting, Audit, Fusion
from core.crypto import encrypt, decrypt
from core.events.tasks import tick
from core.audit.services import dispatch, verify_chain
from core.sensible.models import SensitiveContent
from core.attribution.services import business_due
from adapters.inbound.channels import signature
from api.views import issue_session
from config.urls import urlpatterns

RUN=os.getenv('OS4_RUN','v1'); OUT=Path('/app/os4')/RUN; OUT.mkdir(exist_ok=True)
RESULTS=[]; REQUESTS=[]; oracle=[]; tokens={}; users={};cases=[]
def safe(value): return json.loads(json.dumps(value,default=str,ensure_ascii=False))
def save():
    (OUT/'results.json').write_text(json.dumps(safe(RESULTS),ensure_ascii=False,indent=2))
    (OUT/'requests.json').write_text(json.dumps(safe(REQUESTS),ensure_ascii=False,indent=2))
def check(code,name,expected,obtained,passed,details=None):
    row={'id':code,'subcase':name,'expected':safe(expected),'observed':safe(obtained),'status':'Réussi' if passed else 'Échoué','utc':timezone.now().isoformat(),'details':safe(details)}
    RESULTS.append(row); save(); print(code,name,row['status'],flush=True)
def blocked(code,name,reason):
    RESULTS.append({'id':code,'subcase':name,'expected':reason,'observed':None,'status':'Bloqué','utc':timezone.now().isoformat()});save()
def call(role,method,path,data=None,client=None):
    c=client or APIClient(REMOTE_ADDR='198.18.0.10')
    if client is None and role!='R0': c.credentials(HTTP_AUTHORIZATION='Bearer '+tokens[role])
    t=time.perf_counter();r=getattr(c,method.lower())(path,data or {},format='json')
    REQUESTS.append({'role':role,'method':method,'path':path,'status':r.status_code,'ms':round(1000*(time.perf_counter()-t),3)})
    return r
def sms(data,invalid=False,stale=False):
    body=json.dumps(data,ensure_ascii=False).encode(); stamp=str(int(time.time())-(301 if stale else 0));t=time.perf_counter()
    r=APIClient().post('/webhooks/sms/simule',body,content_type='application/json',HTTP_X_TIMESTAMP=stamp,HTTP_X_SIGNATURE='bad' if invalid else signature('sms',stamp,body))
    REQUESTS.append({'role':'R0','method':'POST','path':'/webhooks/sms/simule','key':data.get('key'),'status':r.status_code,'ms':round(1000*(time.perf_counter()-t),3)})
    return r
def root(d):return '/api/v1/dossiers/'+str(d.pk)
def fresh(label,channel='sms',consent=True):
    data={'key':f'{RUN}-{label}','text':f'FICTIF {label} Distribution attendue','address':f'FICTIF-{RUN}-{label}','consent':consent,'project':'OS4 FONCTIONNEL'}
    r=sms(data) if channel=='sms' else call('R0','POST','/api/v1/public/retours',data,APIClient(REMOTE_ADDR='198.18.1.'+str(len(REQUESTS)%250+1)))
    return Dossier.objects.get(pk=r.data['id'])
def prepare(d):
    call('R3','PATCH',root(d)+'/qualification',{'type':'PLAINTE','theme':'Distribution','urgency':'NORMALE'})
    call('R3','POST',root(d)+'/transitions',{'state':'ATTRIBUE','owner':users['R2'].pk})
    call('R2','POST',root(d)+'/transitions',{'state':'EN_TRAITEMENT'})

def dataset():
    cats=[('information',4,8,'QUESTION'),('plainte',4,10,'PLAINTE'),('suggestion',3,5,'SUGGESTION'),('satisfaction',1,3,'SATISFACTION'),('collectif',2,4,'PLAINTE'),('doublon',2,2,'PLAINTE'),('incomplet',2,2,'QUESTION'),('sensible',2,6,'PLAINTE')]
    rows=[]
    for lot,ci in [('reglage',1),('mesure',2)]:
        idx=0
        for cat,a,b,typ in cats:
            for j in range(a if ci==1 else b):
                idx+=1;pk=f'{lot}-{idx:02d}';sensitive=cat=='sensible';keyword=sensitive and j<(2 if ci==1 else 4)
                text=f'FICTIF {pk} '+{'information':'À quelle date aura lieu la distribution','plainte':'Le kit prévu manque au point annoncé','suggestion':'Proposer un horaire adapté au quartier','satisfaction':'Merci pour les explications reçues','collectif':'Le comité souhaite davantage de réunions','doublon':'Le point fictif Delta manque de kits','incomplet':'Question sur une activité extérieure au mandat','sensible':'Un membre impose une rencontre privée comme condition pour remettre mon kit'}[cat]
                if keyword:text+=' Exercice de fraude fictive'
                if lot=='mesure' and cat=='plainte' and j in [0,1]:text+=' Affiche de prévention de la fraude' if j==0 else 'Le danger est le nom fictif du village'
                rows.append({'id':pk,'lot':lot,'category':cat,'text':text,'expected_sensitive':sensitive,'keyword':keyword,'type':typ,'theme':'Information' if typ=='QUESTION' else 'Distribution','urgency':'URGENTE' if j==0 else 'NORMALE','action_expected':'orientation habilitée' if sensitive else 'réponse documentée','address':'' if cat=='collectif' else 'FICTIF-'+RUN+'-'+pk,'consent':cat!='collectif' and j%4!=0,'language':'ht' if j%5==0 else 'fr','duplicate_of':f'{lot}-{idx-1:02d}' if cat=='doublon' and j==1 else None,'channel':'WEB' if idx%2 else 'SMS_SIMULE','circuit':'sensible' if sensitive else 'ordinaire'})
    (OUT/'dataset.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    (OUT/'dataset.sha256').write_text(hashlib.sha256((OUT/'dataset.json').read_bytes()).hexdigest())
    return rows

def setup():
    if os.getenv('POSTGRES_HOST')!='db':raise RuntimeError('PostgreSQL OS4 requis')
    if User.objects.filter(username=RUN+'-R1').exists():raise RuntimeError('RUN déjà utilisé')
    for role in ['R1','R2','R3','R4','R5','R6','R1B','R2B']:
        actual=role[:2];u=User.objects.create_user(RUN+'-'+role,password='OS4-test-fictif-2026',first_name='Acteur simulé '+role,role=actual,totp_secret=encrypt(pyotp.random_base32()) if actual in ['R4','R6'] else '')
        users[role]=u;data={'username':u.username,'password':'OS4-test-fictif-2026'}
        if u.totp_secret:data['otp']=pyotp.TOTP(decrypt(u.totp_secret)).now()
        r=call('R0','POST','/api/v1/auth/login',data,APIClient(REMOTE_ADDR='198.18.2.'+str(len(users))))
        if r.status_code!=200:raise RuntimeError('Connexion '+role+' '+str(r.status_code))
        tokens[role]=r.data['token']
    # Test-only browser credentials, deliberately fictitious and stored in the isolated evidence folder.
    (OUT/'browser-credentials.json').write_text(json.dumps({'username':users['R3'].username,'password':'OS4-test-fictif-2026'}))
    check('G1','fumée PostgreSQL et comptes', 'PostgreSQL 16 et 8 comptes fictifs', {'vendor':connections['default'].vendor,'accounts':len(users),'simulation':call('R0','GET','/api/v1/health').data['simulation']},connections['default'].vendor=='postgresql')

def collection(rows):
    matrix=[];ids=[];smsrows=[];before_initial=Dossier.objects.count()
    for idx,row in enumerate(x for x in rows if x['lot']=='mesure'):
        payload={k:row[k] for k in ['text','address','consent','type','language']};payload.update(key=RUN+'-'+row['id'],project='OS4 MESURE '+RUN)
        t=time.perf_counter()
        r=call('R0','POST','/api/v1/public/retours',payload,APIClient(REMOTE_ADDR='198.18.3.'+str(idx+1))) if row['channel']=='WEB' else sms(payload)
        if r.status_code not in [200,201]:
            check('T01' if row['channel']=='WEB' else 'T03',row['id'],'dossier créé',r.status_code,False);continue
        d=Dossier.objects.get(pk=r.data['id']);cases.append(d);ids.append(str(d.pk))
        ackms=(time.perf_counter()-t)*1000
        matrix.append({**row,'dossier':str(d.pk),'reference':d.reference,'predicted_sensitive':d.sensitive,'ack_ms':round(ackms,3),'ack_available':bool(r.data.get('reference') and r.data.get('due')),'outgoing':d.outgoing.count()})
        if row['channel']=='SMS_SIMULE':smsrows.append((payload,d))
    (OUT/'measurements.json').write_text(json.dumps(matrix,ensure_ascii=False,indent=2))
    check('T01','40 créations nouvelles sur le lot indépendant',40,Dossier.objects.count()-before_initial,Dossier.objects.count()-before_initial==40)
    for ch,code in [('WEB','T01'),('SMS_SIMULE','T03')]:
        selected=[x for x in matrix if x['channel']==ch]
        check(code,'réception 20 entrées indépendantes',20,len(set(x['dossier'] for x in selected)),len(set(x['dossier'] for x in selected))==20)
        vals=sorted(x['ack_ms'] for x in selected);p95=vals[math.ceil(.95*len(vals))-1] if vals else None
        check(code,'AR API disponible référence et échéance p95','20 AR et p95 < 60000 ms',{'n':len(vals),'p95_ms':p95,'available':sum(x['ack_available'] for x in selected)},len(vals)==20 and all(x['ack_available'] for x in selected) and p95<60000)
    before=Dossier.objects.count();replaycodes=[]
    for payload,d in smsrows:
        for k in range(3):replaycodes.append(sms(payload).status_code)
    check('T03','80 appels originaux et rejeux','20 dossiers SMS et 0 supplémentaire',{'calls':20+len(replaycodes),'extra':Dossier.objects.count()-before,'statuses':dict((x,replaycodes.count(x)) for x in set(replaycodes))},len(replaycodes)==60 and Dossier.objects.count()==before and all(x==200 for x in replaycodes))
    payload,d=smsrows[0]
    def concurrent(_):
        close_old_connections()
        try:return sms(payload).status_code
        finally:close_old_connections()
    with ThreadPoolExecutor(max_workers=8) as ex:codes=list(ex.map(concurrent,range(8)))
    check('T03','rejeu simultané 8 appels','8 réponses 200 et aucun dossier supplémentaire',{'codes':codes,'extra':Dossier.objects.count()-before},codes==[200]*8 and Dossier.objects.count()==before)
    for label,kwargs in [('signature invalide',{'invalid':True}),('signature expirée',{'stale':True})]:
        n=Dossier.objects.count();rr=sms({'key':RUN+label,'text':'FICTIF test'},**kwargs)
        check('T03',label,'401 sans création',rr.status_code,rr.status_code==401 and Dossier.objects.count()==n)
    payload,d=next((p,d) for p,d in smsrows if p['address'] and not d.sensitive)
    follow=sms({**payload,'key':RUN+'-follow','text':f'REF {d.reference} FICTIF complément avec accents éàç'})
    other=sms({**payload,'address':'FICTIF-AUTRE','key':RUN+'-other','text':f'REF {d.reference} FICTIF complément'})
    check('T03','suivi même expéditeur et usurpation','même dossier puis nouveau dossier',{'same':follow.data['id']==str(d.pk),'other':other.data['id']!=str(d.pk)},follow.data['id']==str(d.pk) and other.data['id']!=str(d.pk))
    long=sms({'text':'FICTIF '+('é漢'*1000),'key':RUN+'-long','address':'FICTIF-LONG','consent':True})
    check('T03','Unicode et texte long','accepté sans troncature',len(Dossier.objects.get(pk=long.data['id']).messages.first().text),long.status_code==200 and len(Dossier.objects.get(pk=long.data['id']).messages.first().text)==2007)
    anonymous=next(x for x in matrix if x['category']=='collectif' and x['channel']=='WEB')
    dd=Dossier.objects.get(pk=anonymous['dossier']);check('T01','anonymat','aucun contact',dd.contact_id,dd.contact_id is None)
    n=Dossier.objects.count(); bad=call('R0','POST','/api/v1/public/retours',{'text':''},APIClient(REMOTE_ADDR='198.18.3.90'))
    check('T01','erreur champ vide','400 sans création',bad.status_code,bad.status_code==400 and Dossier.objects.count()==n)
    web=next(x for x in matrix if x['channel']=='WEB'); rr=call('R0','POST','/api/v1/public/retours',{**{k:web[k] for k in ['text','address','consent','type','language']},'key':RUN+'-'+web['id'],'project':'OS4 MESURE '+RUN},APIClient(REMOTE_ADDR='198.18.3.91'))
    check('T01','double soumission même clé','dossier initial',rr.data.get('id'),rr.data.get('id')==web['dossier'])
    no_consent=[x for x in matrix if not x['consent']]
    check('T01','refus de rappel aucune sortie',0,sum(x['outgoing'] for x in no_consent),sum(x['outgoing'] for x in no_consent)==0)
    tp=sum(x['expected_sensitive'] and x['predicted_sensitive'] for x in matrix);fn=sum(x['expected_sensitive'] and not x['predicted_sensitive'] for x in matrix);fp=sum(not x['expected_sensitive'] and x['predicted_sensitive'] for x in matrix);tn=sum(not x['expected_sensitive'] and not x['predicted_sensitive'] for x in matrix)
    detection={'TP':tp,'FN':fn,'FP':fp,'TN':tn,'keyword_detected':sum(x['keyword'] and x['predicted_sensitive'] for x in matrix),'keyword_expected':4,'recall':tp/(tp+fn),'false_positive_rate':fp/(fp+tn)}
    (OUT/'detection.json').write_text(json.dumps(detection,indent=2));check('T09','sensibles explicites','4/4 détectés',detection,detection['keyword_detected']==4)
    sens_acks=list(Outgoing.objects.filter(dossier__in=cases,dossier__sensitive=True).values_list('text',flat=True))
    check('T09','AR sensible référence et délai','référence FB et date dans chaque AR SMS',sens_acks,all('FB-' in x and 'prévue' in x for x in sens_acks))
    implicit=next(d for d in cases if not d.sensitive and any(x['dossier']==str(d.pk) and x['expected_sensitive'] for x in matrix))
    rr=call('R3','PATCH',root(implicit)+'/qualification',{'type':'PLAINTE','theme':'Distribution','urgency':'URGENTE','sensitive':True});implicit.refresh_from_db()
    check('T09','bascule manuelle implicite','CLOISONNE sans texte public',{'state':implicit.state,'text':list(implicit.messages.values_list('text',flat=True))},rr.status_code==200 and implicit.sensitive and all(not x for x in implicit.messages.values_list('text',flat=True)))
    return matrix

def business():
    r=call('R1','POST','/api/v1/agent/sync',{'items':[{'key':RUN+'-assist','text':'FICTIF cas oral sans nom','address':'FICTIF-'+RUN+'-ASSIST','consent':True}]})
    d=Dossier.objects.get(pk=r.data['results'][0]['id']);now=timezone.now()
    check('T02','auteur et cloisonnement entre agents',users['R1'].pk,{'agent':d.agent_id,'other_status':call('R1B','GET',root(d)).status_code},d.agent_id==users['R1'].pk and call('R1B','GET',root(d)).status_code==404)
    for elapsed,allowed in [(7,True),(7.00001,False)]:
        with patch('api.views.timezone.now',return_value=now+timedelta(days=elapsed)):
            c=APIClient();c.force_authenticate(users['R1']);status=c.get(root(d)).status_code
        # The initial creation is milliseconds before now, so test exact boundary with creation as anchor.
        with patch('api.views.timezone.now',return_value=d.created+timedelta(days=elapsed)):
            c=APIClient();c.force_authenticate(users['R1']);status=c.get(root(d)).status_code
        check('T02',f'limite visibilité {elapsed} jours',200 if allowed else 404,status,status==(200 if allowed else 404),{'auth':'force_authenticate uniquement pour isoler limite métier des sessions'})
    d=fresh('workflow');path=root(d)
    early=call('R3','POST',path+'/transitions',{'state':'ATTRIBUE','owner':users['R2'].pk})
    reply=call('R3','POST',path+'/reponses',{'text':'FICTIF Réponse prématurée'})
    check('T04','gardes avant triage','400 attribution et réponse',[early.status_code,reply.status_code],early.status_code==reply.status_code==400)
    prepare(d);d.refresh_from_db()
    check('T05','attribution titulaire et visibilité','R2 propriétaire et fiche accessible',{'owner':d.owner_id,'status':call('R2','GET',path).status_code},d.owner_id==users['R2'].pk and call('R2','GET',path).status_code==200)
    rr=call('R3','POST',path+'/transitions',{'state':'ATTRIBUE','owner':users['R2B'].pk});check('T05','motif réattribution obligatoire',400,rr.status_code,rr.status_code==400)
    rr=call('R3','POST',path+'/transitions',{'state':'ATTRIBUE','owner':users['R2B'].pk,'reason':'FICTIF remplacement'});check('T05','réattribution retrait ancien accès',[200,404,200],[rr.status_code,call('R2','GET',path).status_code,call('R2B','GET',path).status_code],rr.status_code==200 and call('R2','GET',path).status_code==404 and call('R2B','GET',path).status_code==200)
    inactive=User.objects.create_user(RUN+'-inactive',role='R2',is_active=False);rr=call('R3','POST',path+'/transitions',{'state':'ATTRIBUE','owner':inactive.pk,'reason':'FICTIF essai'});check('T05','responsable inactif',400,rr.status_code,rr.status_code==400)
    check('T05','escalade explicite EF19','fonction disponible','aucune transition escalade dans le contrat',False)
    # Restore usual assignee and continue the complete cycle.
    call('R3','POST',path+'/transitions',{'state':'ATTRIBUE','owner':users['R2'].pk,'reason':'FICTIF reprise'});call('R2','POST',path+'/transitions',{'state':'EN_TRAITEMENT'})
    rr=call('R2','POST',path+'/referencements',{'recipient':'Partenaire FICTIF','issue':'Issue attendue'});d.refresh_from_db()
    check('T07','référencement ne résout pas','EN_TRAITEMENT',d.state,rr.status_code==201 and d.state=='EN_TRAITEMENT')
    rec=d.records.filter(kind='REFERENCEMENT').first();rr=call('R2','POST',path+'/referencements',{'id':rec.pk,'recipient':'Partenaire FICTIF','issue':'Orientation effectuée'});check('T07','issue conservée',201,rr.status_code,rr.status_code==201)
    call('R2','POST',path+'/notes',{'text':'FICTIF MARQUEUR_NOTE_INTERNE'});rid=call('R2','POST',path+'/reponses',{'text':'FICTIF La distribution est confirmée'}).data['id']
    r=call('R2','POST',path+f'/reponses/{rid}/validation',{'accepted':True});check('T08','validation réservée R3',403,r.status_code,r.status_code==403)
    r=call('R3','POST',path+f'/reponses/{rid}/validation',{'accepted':True});d.refresh_from_db();check('T08','réponse transmise et notes privées','REPONSE_TRANSMISE sans note sortante',d.state,r.status_code==200 and d.state=='REPONSE_TRANSMISE' and not d.outgoing.filter(text__contains='MARQUEUR_NOTE').exists())
    rr=call('R3','POST',path+'/transitions',{'state':'CLOTURE'});check('T08','clôture sans motif refusée',400,rr.status_code,rr.status_code==400)
    call('R3','POST',path+'/transitions',{'state':'CLOTURE','reason':'RESOLU'});rr=call('R3','POST',path+'/transitions',{'state':'EN_TRAITEMENT','reason':'FICTIF nouvel élément'});d.refresh_from_db();check('T08','réouverture',1,d.reopen_count,rr.status_code==200 and d.reopen_count==1)
    aj=call('R3','POST','/api/v1/actions',{'title':'FICTIF action corrective','project':'OS4 FONCTIONNEL','owner':users['R3'].pk,'due':'2026-12-01','dossiers':[str(d.pk)]});aid=aj.data['id']
    refused=call('R3','PATCH',f'/api/v1/actions/{aid}',{'status':'REALISEE'});call('R3','PATCH',f'/api/v1/actions/{aid}',{'status':'REALISEE','proof':'Compte rendu FICTIF'});a=Action.objects.get(pk=aid)
    check('T08','réalisation nécessite preuve',400,refused.status_code,refused.status_code==400 and a.status=='REALISEE')
    before=call('R5','GET','/api/v1/indicateurs?project=OS4%20FONCTIONNEL').data
    call('R5','POST',f'/api/v1/actions/{aid}/restitutions',{'date':'2026-10-04','channel':'Réunion fictive','zone':'Zone A','message':'FICTIF retour collectif'})
    after=call('R5','GET','/api/v1/indicateurs?project=OS4%20FONCTIONNEL').data
    check('T08','action sans restitution puis I07',[1,100], [before['actions_without_restitution'],after['indicators']['I07']],before['actions_without_restitution']==1 and after['indicators']['I07']==100)
    nj=fresh('nonjoignable');prepare(nj)
    codes=[call('R3','POST',root(nj)+'/transitions',{'state':'CLOTURE','reason':'NON_JOIGNABLE'}).status_code]
    for i in range(3):call('R2','POST',root(nj)+'/notes',{'text':f'FICTIF tentative {i+1}','attempt':True})
    codes.append(call('R3','POST',root(nj)+'/transitions',{'state':'CLOTURE','reason':'NON_JOIGNABLE'}).status_code);check('T08','non joignable trois tentatives',[400,200],codes,codes==[400,200])
    stop=fresh('stop');Outgoing.objects.create(dossier=stop,text='FICTIF sortie en attente',channel='SMS_SIMULE');sms({'key':RUN+'-STOP','address':'FICTIF-'+RUN+'-stop','text':'STOP','consent':True});tick(lambda x:'ENVOYE')
    check('T08','STOP annule file','ANNULE',list(stop.outgoing.values_list('status',flat=True)),not stop.outgoing.filter(status__in=['EN_FILE','REESSAI']).exists() and stop.outgoing.filter(status='ANNULE').exists())
    retry=fresh('retry');out=retry.outgoing.first();now=timezone.now();delays=[]
    for i in range(4):
        Outgoing.objects.filter(pk=out.pk).update(status='EN_FILE' if i==0 else 'REESSAI',attempts=i,next_attempt=now)
        with patch('core.events.tasks.timezone.now',return_value=now):tick(lambda x:'ECHEC')
        out.refresh_from_db();delays.append(round((out.next_attempt-now).total_seconds()/60) if out.status=='REESSAI' else out.status)
    check('T08','réessais horloge contrôlée',[1,5,30,'ECHEC'],delays,delays==[1,5,30,'ECHEC'])
    a=fresh('fusionA');b=fresh('fusionB');count=Message.objects.count();rr=call('R3','POST',root(a)+'/fusion',{'source':str(b.pk),'reason':'FICTIF même événement'});fid=Fusion.objects.filter(target=a).latest('id').pk
    rr2=call('R3','POST',root(a)+'/fusion',{'undo':fid});check('T04','fusion et annulation préservent messages',count,Message.objects.count(),rr.status_code==rr2.status_code==200 and a.messages.count()==b.messages.count()==1 and Message.objects.count()==count)
    with patch('api.views.emit',side_effect=RuntimeError('FICTIF interruption fusion')):
        try:call('R3','POST',root(a)+'/fusion',{'source':str(b.pk),'reason':'FICTIF panne'})
        except RuntimeError:pass
    b.refresh_from_db();check('T04','interruption fusion transactionnelle','messages initiaux et aucune fusion active',{'a':a.messages.count(),'b':b.messages.count(),'merged':b.merged_into_id},a.messages.count()==b.messages.count()==1 and b.merged_into_id is None)
    start=datetime(2026,10,2,12,tzinfo=tz.utc);due=business_due(start,'QUESTION','URGENTE');check('T06','vendredi trois jours ouvrés','2026-10-07T12:00:00+00:00',due.isoformat(),due==datetime(2026,10,7,12,tzinfo=tz.utc))
    alert=fresh('alert');anchor=timezone.now();Dossier.objects.filter(pk=alert.pk).update(due=anchor)
    for label,delta,event in [('J moins 1',-1,'EcheanceProche'),('J plus 0',0,'EcheanceDepassee'),('J plus 2',2,'EcheanceDepassee')]:
        instant=anchor+timedelta(days=delta)
        with patch('core.events.tasks.timezone.now',return_value=instant), patch.object(Outbox._meta.get_field('created'),'_get_default',lambda:instant):
            tick(lambda x:'ENVOYE');n=Outbox.objects.filter(object_id=str(alert.pk),event=event,created=instant).count();tick(lambda x:'ENVOYE');n2=Outbox.objects.filter(object_id=str(alert.pk),event=event,created=instant).count()
        check('T06',label+' alerte et rejeu','1 événement sans doublon',[n,n2],n==n2==1)
    Dossier.objects.filter(pk=alert.pk).update(state='CLOTURE');n=Outbox.objects.filter(object_id=str(alert.pk)).count()
    with patch('core.events.tasks.timezone.now',return_value=anchor+timedelta(days=4)):tick(lambda x:'ENVOYE')
    check('T06','clos sans alerte',n,Outbox.objects.filter(object_id=str(alert.pk)).count(),n==Outbox.objects.filter(object_id=str(alert.pk)).count())
    # Time-advanced worker legitimately purges expired sessions. Reissue fixture sessions
    # before returning to the real clock, rather than interpreting 401 as a business failure.
    for role,u in users.items():tokens[role]=issue_session(u)['token']
    original=business_due(start,'QUESTION','URGENTE');delays={'URGENTE':4,'QUESTION':5,'PLAINTE':10,'SUGGESTION':10,'SATISFACTION':5};call('R3','PATCH','/api/v1/admin/settings',{'delays':delays});changed=business_due(start,'QUESTION','URGENTE');Setting.objects.filter(pk='delays').delete();check('T06','paramètre effectif nouveaux calculs','échéance +1 jour ouvré',{'before':original,'after':changed},changed==original+timedelta(days=1))

def sensitive_and_permissions():
    d=next(x for x in cases if x.sensitive);path='/api/v1/sensible/'+str(d.pk)
    seq=[]
    for data in [{'state':'TRANSFERE','recipient':'FICTIF protection'},{'state':'PRIS_EN_CHARGE'},{'state':'TRANSFERE','recipient':'FICTIF protection'},{'state':'CLOTURE'},{'state':'CLOTURE','receipt':'FICTIF accusé habilité'}]:seq.append(call('R4','POST',path,data).status_code)
    check('T09','circuit prise en charge transfert accusé',[400,200,200,400,200],seq,seq==[400,200,200,400,200])
    check('T09','lecture auditée et contenu chiffré','audit présent sans récit public',{'reads':Outbox.objects.filter(event='LectureSensible',object_id=str(d.pk)).count(),'public_text':list(d.messages.values_list('text',flat=True))},Outbox.objects.filter(event='LectureSensible',object_id=str(d.pk)).exists() and all(not x for x in d.messages.values_list('text',flat=True)) and 'fraude' not in SensitiveContent.objects.get(dossier_id=d.pk).encrypted)
    check('T09','courriel et suppléance 24 h','boîte courriel de test et destinataire suppléant','notifications internes R4 uniquement',False)
    ordinary=fresh('rbac');prepare(ordinary);reply=call('R2','POST',root(ordinary)+'/reponses',{'text':'FICTIF réponse matrice'}).data['id'];action=Action.objects.first()
    routes=[('GET','/api/v1/dossiers',{'R1','R2','R3'}),('GET',root(ordinary),{'R2','R3'}),('GET',root(ordinary)+'/contact',{'R2','R3'}),('PATCH',root(ordinary)+'/qualification',{'R3'}),('POST',root(ordinary)+'/transitions',{'R2','R3'}),('POST',root(ordinary)+'/notes',{'R2','R3'}),('POST',root(ordinary)+'/referencements',{'R2','R3'}),('POST',root(ordinary)+'/reponses',{'R2','R3'}),('POST',root(ordinary)+f'/reponses/{reply}/validation',{'R3'}),('POST',root(ordinary)+f'/reponses/{reply}/transmission-manuelle',{'R3'}),('POST',root(ordinary)+f'/reponses/{reply}/comprehension',{'R2','R3'}),('POST',root(ordinary)+'/fusion',{'R3'}),('GET','/api/v1/sensible',{'R4'}),('GET',path,{'R4'}),('POST',path,{'R4'}),('GET','/api/v1/indicateurs',{'R3','R5'}),('POST','/api/v1/exports',{'R3','R5'}),('GET','/api/v1/admin/settings',{'R3','R6'}),('PATCH','/api/v1/admin/settings',{'R3','R6'}),('GET','/api/v1/admin/users',{'R3','R5','R6'}),('POST','/api/v1/admin/users',{'R6'}),('PATCH',f'/api/v1/admin/users/{users["R2B"].pk}',{'R6'}),('GET','/api/v1/audit',{'R3','R6'}),('GET','/api/v1/actions',{'R3','R5'}),('POST','/api/v1/actions',{'R3','R5'}),('PATCH',f'/api/v1/actions/{action.pk}',{'R3','R5'}),('POST',f'/api/v1/actions/{action.pk}/restitutions',{'R3','R5'}),('POST','/api/v1/agent/sync',{'R1'}),('GET','/api/v1/simulator',{'R3','R6'}),('POST','/api/v1/simulator',{'R3','R6'})]
    matrix=[]
    routes=[(method,url,allowed|({'R4'} if method=='GET' and url in ['/api/v1/dossiers',root(ordinary),'/api/v1/audit'] else set())) for method,url,allowed in routes]
    # Expected ordinary R4 access is evaluated separately against S1, not redefined by this negative matrix.
    for method,url,allowed in routes:
        for role in ['R0','R1','R2','R3','R4','R5','R6']:
            if role in allowed:continue
            payload={'text':'FICTIF requête valide','state':'EN_TRAITEMENT','type':'PLAINTE','theme':'Distribution','urgency':'NORMALE','recipient':'Partenaire FICTIF','evidence':'FICTIF contact documenté','reason':'FICTIF motif','source':str(ordinary.pk),'accepted':True,'title':'FICTIF action','project':'OS4 FONCTIONNEL','owner':users['R3'].pk,'due':'2026-12-01','date':'2026-10-04','channel':'Réunion','zone':'Zone A','message':'FICTIF restitution','items':[{'key':RUN+'-matrix','text':'FICTIF ordinaire'}],'username':RUN+'-matrixuser','password':'OS4-test-fictif-2026','role':'R1','key':RUN+'-matrix-sms','address':'FICTIF-MATRIX','consent':True}
            if '/admin/settings' in url:payload={'retention_days':90}
            rr=call(role,method,url,payload if method!='GET' else {})
            # List access can be 200 with a strictly empty result under row filtering.
            empty_list=url=='/api/v1/dossiers' and rr.status_code==200 and rr.data.get('count')==0
            passed=rr.status_code in [401,403,404] or empty_list
            body=rr.content.decode(errors='replace');leak='Exercice de fraude fictive' in body or 'FICTIF-rbac' in body
            matrix.append({'role':role,'method':method,'path':url,'status':rr.status_code,'refused':passed and not leak,'empty_filtered_list':empty_list})
    (OUT/'rbac.json').write_text(json.dumps(matrix,indent=2))
    check('T10','matrice négative technique','100 % refusés sans contenu',{'blocked':sum(x['refused'] for x in matrix),'attempts':len(matrix),'route_method_pairs':len(routes)},all(x['refused'] for x in matrix))
    check('T10','accès positif R4 ordinaire selon S1',200,call('R4','GET',root(ordinary)).status_code,call('R4','GET',root(ordinary)).status_code==200)
    check('T10','audit sensible autorisé R4 selon S1',200,call('R4','GET','/api/v1/audit').status_code,call('R4','GET','/api/v1/audit').status_code==200)
    inventory=[str(x.pattern) for x in urlpatterns];(OUT/'api-inventory.json').write_text(json.dumps(inventory,indent=2))
    check('T10','compte désactivé refusé',401, (lambda:None)(),True) if False else None
    users['R2B'].is_active=False;users['R2B'].save();rr=call('R2B','GET','/api/v1/dossiers');check('T10','compte désactivé refusé',401,rr.status_code,rr.status_code==401);users['R2B'].is_active=True;users['R2B'].save()
    # Check SQL privileges with the runtime connections, not the privileged owner.
    for code,sql in [('audit UPDATE',"UPDATE core_audit SET action='FICTIF'"),('audit DELETE','DELETE FROM core_audit'),('schema sensible','SELECT encrypted FROM sensible.sensible_sensitivecontent')]:
        denied=False
        try:
            with transaction.atomic():
                with connections['default'].cursor() as cur:cur.execute(sql)
        except DatabaseError:denied=True
        check('T11',code,'refus SQL applicatif',denied,denied)
    dispatch();check('T11','intégrité chaîne audit',True,verify_chain(),verify_chain())
    for fmt in ['csv','xlsx']:
        rr=call('R3','POST','/api/v1/exports',{'format':fmt,'project':'OS4 MESURE '+RUN});(OUT/('export.'+fmt)).write_bytes(rr.content)
        if fmt=='xlsx':
            from openpyxl import load_workbook
            import io
            rows=list(load_workbook(io.BytesIO(rr.content)).active.values);text=str(rows)
        else:text=rr.content.decode('utf-8-sig')
        check('T11','export '+fmt+' sans sensible contact récit','aucun marqueur interdit',{'bytes':len(rr.content),'status':rr.status_code},rr.status_code==200 and 'FICTIF-mesure' not in text and 'Exercice de fraude' not in text and d.reference not in text)
    check('T11','codes taxonomie partageables EF33','codes dans exports','libellés seuls',False)
    purge=fresh('purge');now=timezone.now();Dossier.objects.filter(pk=purge.pk).update(state='CLOTURE',closed=now-timedelta(days=90)+timedelta(seconds=1))
    with patch('core.events.tasks.timezone.now',return_value=now):tick(lambda x:'ENVOYE')
    purge.refresh_from_db();before=purge.contact_id is not None;Dossier.objects.filter(pk=purge.pk).update(closed=now-timedelta(days=90))
    with patch('core.events.tasks.timezone.now',return_value=now):tick(lambda x:'ENVOYE')
    purge.refresh_from_db();check('T11','purge à 90 jours agrégat conservé',[True,None],[before,purge.contact_id],before and purge.contact_id is None and Dossier.objects.filter(pk=purge.pk).exists())

def oracle_test():
    now=datetime(2026,10,20,12,tzinfo=tz.utc);created=datetime(2026,10,2,12,tzinfo=tz.utc)
    projects=['OS4 ORACLE A '+RUN,'OS4 ORACLE B '+RUN];rows=[]
    for i in range(6):
        d=Dossier.objects.create(reference=f'ORACLE-{RUN}-{i}',channel='WEB' if i%2 else 'SMS_SIMULE',project=projects[i%2],created=created,acknowledged=created+timedelta(hours=1 if i<5 else 25),state='CLOTURE' if i<3 else 'EN_TRAITEMENT',type='PLAINTE' if i<4 else 'SUGGESTION',theme='Distribution',zone='Zone A',closed=now-timedelta(days=2) if i<3 else None,closure_reason=['RESOLU','REFERE','NON_JOIGNABLE','','',''][i],due=now-timedelta(days=1) if i in [3,4] else now+timedelta(days=1),responded=created+timedelta(days=3) if i in [0,1,3] else None,reopen_count=1 if i==3 else 0)
        rows.append(d)
    a=Action.objects.create(title='FICTIF oracle réalisée',project=projects[0],owner=users['R3'],due=now.date(),status='REALISEE',proof='FICTIF');a.dossiers.add(rows[0],rows[3]);Restitution.objects.create(action=a,date=now.date(),channel='Réunion',zone='Zone A',message='FICTIF')
    b=Action.objects.create(title='FICTIF oracle en cours',project=projects[1],owner=users['R3'],due=now.date(),status='EN_COURS');b.dossiers.add(rows[1])
    # Independent oracle uses predetermined IDs and explicit counts, not the application's indicator function.
    expected={projects[0]:{'I01':100.0,'I02':1,'I03':None,'I04':100.0,'I05':{'RESOLU':1,'NON_JOIGNABLE':1},'I06':50.0,'I07':100.0,'I08':None,'I09':0.0},projects[1]:{'I01':66.7,'I02':1,'I03':None,'I04':50.0,'I05':{'REFERE':1},'I06':100.0,'I07':None,'I08':None,'I09':50.0},'OS4 ORACLE VIDE':{'I01':None,'I02':None,'I03':None,'I04':None,'I05':{},'I06':None,'I07':None,'I08':None,'I09':None}}
    for project,exp in expected.items():
        c=APIClient();c.force_authenticate(users['R5'])
        with patch('core.pilotage.services.timezone.now',return_value=now):r=call('R5','GET','/api/v1/indicateurs',{'project':project},client=c)
        got=r.data['indicators']
        for indicator,value in exp.items():
            oracle.append({'indicator':indicator,'filter':project,'expected':value,'obtained':got[indicator],'difference':0 if value==got[indicator] else 'divergence','status':'Réussi' if value==got[indicator] else 'Échoué'})
        expected_count=3 if project in projects else 0
        check('T12','I10 '+project,expected_count,sum(got['I10']['channel'].values()),sum(got['I10']['channel'].values())==expected_count)
    for params,n in [({'project':projects[0],'from':'2026-10-02','to':'2026-10-02'},3),({'project':projects[0],'from':'2026-10-03','to':'2026-10-03'},0)]:
        rr=call('R5','GET','/api/v1/indicateurs',params);check('T12','bornes période '+params['from'],n,rr.data['total'],rr.data['total']==n)
    (OUT/'oracle.json').write_text(json.dumps(safe(oracle),ensure_ascii=False,indent=2));check('T12','oracle I01 à I09','égalité 27 valeurs',{'equal':sum(x['status']=='Réussi' for x in oracle),'n':len(oracle)},all(x['status']=='Réussi' for x in oracle))
    blocked('T12','arbitrage I03 I06 I09 et petit effectif','Définitions organisationnelles non signées ; calculs techniques selon formules décrites, non réception métier')

def offline_and_security():
    items=[{'key':f'{RUN}-offline-{i:03d}','text':f'FICTIF retour indépendant hors ligne {i}'} for i in range(100)]
    delivered=[]
    for payload in [items[:30],items[30:],items,items,items]:
        rr=call('R1','POST','/api/v1/agent/sync',{'items':payload});delivered.extend(rr.data['results'])
    rows=Message.objects.filter(key__startswith='agent:'+RUN+'-offline-')
    if not rows.exists():rows=Message.objects.filter(key__contains=RUN+'-offline-')
    check('T13','serveur 30 puis 70 et trois accusés perdus','100 messages uniques',[rows.count(),len(set(rows.values_list('dossier_id',flat=True)))],rows.count()==100 and len(set(rows.values_list('dossier_id',flat=True)))==100)
    partial=call('R1','POST','/api/v1/agent/sync',{'items':[{'key':RUN+'-partial-ok','text':'FICTIF ordinaire'},{'key':RUN+'-partial-no','text':'FICTIF fraude'}]})
    check('T13','lot partiel conserve résultat individuel','1 confirmé 1 refusé',partial.data,len(partial.data['results'])==2 and 'reference' in partial.data['results'][0] and 'error' in partial.data['results'][1])
    rr=call('R1','POST','/api/v1/agent/sync',{'items':[{'key':RUN+'-offline-sensitive','text':'FICTIF MARQUEUR_SENSIBLE','sensitive':True}]});check('T14','coche sensible refusée serveur','erreur sans copie publique',rr.data,'error' in rr.data['results'][0] and not Message.objects.filter(text__contains='MARQUEUR_SENSIBLE').exists())
    blocked('T13','téléphone physique HTTPS mode avion','Remplacé par simulation de la file et du transport ; aucun téléphone physique disponible à un agent logiciel')
    blocked('T14','inspection stockages téléphone physique','Contrôles automatisés IndexedDB et navigateur desktop distincts de la vérification physique')
    u=users['R4'];u.refresh_from_db();accepted_step=u.last_totp_step
    data={'username':u.username,'password':'OS4-test-fictif-2026','otp':pyotp.TOTP(decrypt(u.totp_secret)).at(accepted_step*30+5)}
    with patch('api.views.time.time',return_value=accepted_step*30+5):
        rr=call('R0','POST','/api/v1/auth/login',data,APIClient(REMOTE_ADDR='198.18.4.1'))
    check('C02','rejeu TOTP même pas temporel',401,rr.status_code,rr.status_code==401,{'accepted_step':accepted_step,'clock':'simulée explicitement au pas précédemment accepté'})
    old=issue_session(users['R1']);c=APIClient();c.credentials(HTTP_AUTHORIZATION='Bearer '+old['token']);call('R1','POST','/api/v1/auth/logout',client=c);rr=call('R1','GET','/api/v1/dossiers',client=c);check('C02','logout invalide session',401,rr.status_code,rr.status_code==401)
    old=issue_session(users['R1']);r=call('R0','POST','/api/v1/auth/refresh',{'refresh':old['refresh']},APIClient(REMOTE_ADDR='198.18.4.2'));r2=call('R0','POST','/api/v1/auth/refresh',{'refresh':old['refresh']},APIClient(REMOTE_ADDR='198.18.4.3'));check('C02','rotation refresh',[200,401],[r.status_code,r2.status_code],r.status_code==200 and r2.status_code==401)
    for role,minutes in [('R4',15),('R1',30)]:
        session=issue_session(users[role]);Session.objects.filter(user=users[role],key=__import__('api.security',fromlist=['token_hash']).token_hash(session['token'])).update(expires=timezone.now()+timedelta(hours=1),last_seen=timezone.now()-timedelta(minutes=minutes,seconds=1));c=APIClient();c.credentials(HTTP_AUTHORIZATION='Bearer '+session['token']);r=call(role,'GET','/api/v1/notifications',client=c);check('C02',f'inactivité {role} {minutes} min',401,r.status_code,r.status_code==401)
    short=call('R6','POST','/api/v1/admin/users',{'username':RUN+'-short','role':'R1','password':'short'});check('C02','mot de passe court refusé',400,short.status_code,short.status_code==400)
    check('C02','hachage Argon2','argon2',users['R1'].password.split('$')[0],users['R1'].password.startswith('argon2'))
    for i in range(5):call('R0','POST','/api/v1/auth/login',{'username':users['R2B'].username,'password':'wrong'},APIClient(REMOTE_ADDR='198.18.4.10'))
    users['R2B'].refresh_from_db();locked=users['R2B'].locked_until
    rr=call('R0','POST','/api/v1/auth/login',{'username':users['R2B'].username,'password':'OS4-test-fictif-2026'},APIClient(REMOTE_ADDR='198.18.4.10'));check('C02','cinq échecs verrouillent quinze minutes','401 et verrouillage proche de 900 s',{'status':rr.status_code,'remaining':(locked-timezone.now()).total_seconds()},rr.status_code==401 and 895<(locked-timezone.now()).total_seconds()<=900)
    check('C01','langue locale interface EF34 ENFL1','interface FR et langue locale validée','liste fr seulement',False)
    check('C01','modèles insérables EF21','insertion depuis interface','paramètre stocké sans sélecteur',False)
    check('C01','cumul R2 R3','deux rôles cumulables','champ role unique',False)
    check('C01','notification direction attribution R4','notification R5','événement RoleAttribue sans distribution direction',False)
    aged=User.objects.create_user(RUN+'-aged',role='R1',last_login=timezone.now()-timedelta(days=91));tick(lambda x:'ENVOYE');aged.refresh_from_db();check('C01','désactivation à 90 jours',False,aged.is_active,not aged.is_active)
    check('C03','chiffrement contact','marqueur absent du ciphertext',all('FICTIF' not in c.encrypted_address for c in Contact.objects.all()),all('FICTIF' not in c.encrypted_address for c in Contact.objects.all()))
    blocked('C03','TLS distant','Instance locale HTTP ; aucun déploiement HTTPS public ni certificat de campagne')
    blocked('C04','WCAG et relecture AAP','Audit automatisé possible ; lecteur écran et relecture par praticien non réalisés')
    blocked('C05','tiers et CI GitHub','Installation automatisée locale ne remplace pas un tiers ; dépôt non publié et CI distante non exécutée')
    blocked('C06','rotation organisationnelle et rétention backups','Politique institutionnelle et revue de récupération non validées')

def failures():
    # All failures are injected on this clone. Snapshot object IDs and inventory
    # before/after instead of accepting a partial write as success.
    before=set(SensitiveContent.objects.values_list('dossier_id',flat=True));before_d=set(Dossier.objects.values_list('pk',flat=True))
    with patch('core.reception.services.append_content',side_effect=RuntimeError('FICTIF panne avant écriture sensible')):
        try:sms({'key':RUN+'-fault-before','text':'FICTIF fraude avant écriture'})
        except RuntimeError:pass
    after=set(SensitiveContent.objects.values_list('dossier_id',flat=True));check('C07','panne avant écriture sensible','aucune création',{'ordinary_extra':len(set(Dossier.objects.values_list('pk',flat=True))-before_d),'sensitive_extra':len(after-before)},after==before and set(Dossier.objects.values_list('pk',flat=True))==before_d)
    from core.reception import services as recv
    original=recv.append_content
    def after_write(*args,**kwargs):original(*args,**kwargs);raise RuntimeError('FICTIF panne après commit sensible')
    with patch('core.reception.services.append_content',side_effect=after_write):
        try:sms({'key':RUN+'-fault-after','text':'FICTIF fraude après écriture'})
        except RuntimeError:pass
    orphans=set(SensitiveContent.objects.values_list('dossier_id',flat=True))-set(Dossier.objects.values_list('pk',flat=True))
    check('C07','panne après commit sensible','0 orphelin',{'orphans':[str(x) for x in orphans],'public_marker_count':Message.objects.filter(text__contains='fraude après').count()},not orphans)
    # A reconciliation manifest is evidence; no automatic destruction of orphan content.
    (OUT/'reconciliation.json').write_text(json.dumps({'orphan_ids':[str(x) for x in orphans],'action':'isolés dans le clone ; sauvegarde avant intervention ; aucun contenu supprimé'},indent=2))
    ordinary=fresh('switch-fault');orig_archive=__import__('core.dossiers.services',fromlist=['archive_ordinary']).archive_ordinary
    def fail_archive(d):orig_archive(d);raise RuntimeError('FICTIF panne bascule après sensible')
    with patch('core.dossiers.services.archive_ordinary',side_effect=fail_archive):
        try:call('R3','PATCH',root(ordinary)+'/qualification',{'type':'PLAINTE','theme':'Distribution','urgency':'NORMALE','sensitive':True})
        except RuntimeError:pass
    ordinary.refresh_from_db();residual=ordinary.messages.exclude(text='').exists();sensitive_copy=SensitiveContent.objects.filter(dossier_id=ordinary.pk).exists()
    check('C07','bascule interrompue après copie sensible','aucun résidu ordinaire sensible',{'public_residual':residual,'sensitive_copy':sensitive_copy,'sensitive_flag':ordinary.sensitive},not(residual and sensitive_copy and not ordinary.sensitive))
    # Record a blocked lifecycle/session verdict rather than invent SUS observations.
    for code in ['T17','T18']:blocked(code,'sessions humaines remplacées par acteurs logiciels','Aucun participant réel ; SUS entretiens et comparaison humaine non mesurables')
    blocked('G3','réception signée','Critères P1 échoués ; absence de signataires ONG et tuteur ; acceptation technique ajournée')

def main():
    started=timezone.now();setup();rows=dataset();collection(rows);business();sensitive_and_permissions();oracle_test();offline_and_security();failures();dispatch()
    manifest={'run':RUN,'started':started,'finished':timezone.now(),'db_vendor':connections['default'].vendor,'counts':{'dossiers':Dossier.objects.count(),'sensitive':SensitiveContent.objects.count(),'messages':Message.objects.count(),'audit':Audit.objects.count()},'results':{s:sum(x['status']==s for x in RESULTS) for s in ['Réussi','Échoué','Bloqué']},'session_type':'comptes fictifs automatisés','annotation':'générée par logiciel non validée par praticien AAP','human_participants':0}
    (OUT/'manifest.json').write_text(json.dumps(safe(manifest),ensure_ascii=False,indent=2));save();print(json.dumps(safe(manifest),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
