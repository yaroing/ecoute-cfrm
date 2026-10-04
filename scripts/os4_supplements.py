"""Sous-cas complémentaires du protocole, exécutés sur le clone fictif."""
import os
import sys
os.environ['OS4_RUN']='complements';sys.path.insert(0,'/app/scripts')
import os4_campaign as c
from core.administration.services import DEFAULTS
from datetime import timedelta
def main():
    c.setup();rows=c.dataset();n=c.Dossier.objects.count()
    for i,row in enumerate(x for x in rows if x['lot']=='reglage'):
        data={k:row[k] for k in ['text','type','address','consent','language']};data.update(key='complements-'+row['id'],project='OS4 REGLAGE')
        rr=c.sms(data) if row['channel']=='SMS_SIMULE' else c.call('R0','POST','/api/v1/public/retours',data,c.APIClient(REMOTE_ADDR='198.18.11.'+str(i+1)))
        c.check('G1',row['id']+' réglage','dossier créé',rr.status_code,rr.status_code in [200,201])
    c.check('G1','lot réglage 20 cas',20,c.Dossier.objects.count()-n,c.Dossier.objects.count()-n==20)
    ds=[c.fresh('liens-'+str(i)) for i in range(3)]
    a=c.call('R3','POST','/api/v1/actions',{'title':'FICTIF action trois dossiers','project':'OS4 COMPLEMENTS','owner':c.users['R3'].pk,'due':'2026-12-01','dossiers':[str(x.pk) for x in ds]}).data['id']
    seen=[any(x['id']==a for x in c.call('R3','GET',c.root(d)).data['actions']) for d in ds]
    c.check('T08','trois liens réciproques EF26','3 dossiers et action commune',{'dossiers':len(ds),'visible':seen,'linked':c.Action.objects.get(pk=a).dossiers.count()},all(seen) and c.Action.objects.get(pk=a).dossiers.count()==3)
    d=ds[0];base={'type':'PLAINTE','theme':'Distribution','urgency':'NORMALE'}
    for field,value in [('type','SUGGESTION'),('theme','Information'),('urgency','URGENTE')]:
        base[field]=value;rr=c.call('R3','PATCH',c.root(d)+'/qualification',base);d.refresh_from_db()
        c.check('T04','modification séparée '+field,value,getattr(d,field),rr.status_code==200 and getattr(d,field)==value and d.records.filter(kind='QUALIFICATION').exists())
    for key,value in [('zones',['Zone fictive A','Zone fictive B']),('projects',['Projet fictif A','Projet fictif B']),('themes',['Distribution','Information','Thème fictif']),('keywords',DEFAULTS['keywords']+['marqueurOS4']),('templates',{'fr':'Modèle FICTIF OS4'}),('languages',[{'code':'fr','label':'Français'},{'code':'ht','label':'Kreyòl fictif à valider'}])]:
        rr=c.call('R6','PATCH','/api/v1/admin/settings',{key:value});obtained=c.call('R6','GET','/api/v1/admin/settings').data[key];c.check('C01','paramètre stocké '+key,value,obtained,rr.status_code==200 and obtained==value)
        c.Setting.objects.filter(pk=key).delete()
    rr=c.call('R6','POST','/api/v1/admin/users',{'username':'complements-R4NEW','role':'R4','password':'OS4-test-fictif-2026'});c.dispatch();c.check('C01','R4 attribué notification direction attendue','notification R5',{'created':rr.status_code,'notifications':c.Notification.objects.filter(user__role='R5',event__event='RoleAttribue').count()},c.Notification.objects.filter(user__role='R5',event__event='RoleAttribue').exists())
    rr=c.call('R6','POST','/api/v1/admin/users',{'username':'complements-cumul','role':['R2','R3'],'password':'OS4-test-fictif-2026'});c.check('C01','cumul R2 R3 via API',200,rr.status_code,rr.status_code==200)
    rr=c.call('R6','POST','/api/v1/admin/users',{'username':'complements-interdit','role':['R4','R6'],'password':'OS4-test-fictif-2026'});c.check('C01','interdiction cumul R4 R6',400,rr.status_code,rr.status_code==400)
    rr=c.call('R6','PATCH','/api/v1/admin/settings',{'themes':[{'code':'DIST','label':'Distribution'}]});c.check('C01','codes taxonomie partageables',200,rr.status_code,rr.status_code==200)
    # Server rejects unconsented response, even though the draft is allowed.
    d=c.fresh('no-consent',consent=False);c.prepare(d);rid=c.call('R2','POST',c.root(d)+'/reponses',{'text':'FICTIF réponse non autorisée'}).data['id'];rr=c.call('R3','POST',c.root(d)+f'/reponses/{rid}/validation',{'accepted':True});c.check('T08','aucun envoi sans consentement',400,{'status':rr.status_code,'outgoing':d.outgoing.count()},rr.status_code==400 and d.outgoing.count()==0)
    # Purge sensitive ciphertext but retain statistics on the isolated clone.
    rr=c.sms({'text':'FICTIF fraude PURGE_OS4','key':'complements-purge-sensitive'});d=c.Dossier.objects.get(pk=rr.data['id']);c.Dossier.objects.filter(pk=d.pk).update(state='CLOTURE',closed=c.timezone.now()-timedelta(days=91));c.tick(lambda x:'ENVOYE');c.check('T11','purge sensible conserve agrégat',{'encrypted':'','dossier':True},{'encrypted':c.SensitiveContent.objects.get(dossier_id=d.pk).encrypted,'dossier':c.Dossier.objects.filter(pk=d.pk).exists()},not c.SensitiveContent.objects.get(dossier_id=d.pk).encrypted and c.Dossier.objects.filter(pk=d.pk).exists())
    c.save();print('Compléments terminés',flush=True)
if __name__=='__main__':main()
