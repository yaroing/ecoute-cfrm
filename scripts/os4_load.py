"""OS4 T16 : trois répétitions de 120 s de montée et 900 s de plateau.
Exécuter exclusivement dans l'instance ecoute-os4 isolée.
"""
import os
import sys
import json
import time
import csv
import random
import threading
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen
from urllib.error import HTTPError
sys.path.insert(0, '/app/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.db import close_old_connections
from core.models import User, Dossier, Message, Record, Outbox
from api.views import issue_session

OUT=Path('/app/os4/load'); OUT.mkdir(exist_ok=True)
PROJECT='OS4 CHARGE'
BASE='http://api:8000/api/v1'
RAMP=120; PLATEAU=900; REPEATS=3; USERS=20
lock=threading.Lock(); abort=threading.Event()
def http(path, token, payload=None):
    raw=json.dumps(payload).encode() if payload is not None else None
    req=Request(BASE+path,raw,{'Authorization':'Bearer '+token,'Content-Type':'application/json'})
    t=time.perf_counter()
    try:
        with urlopen(req,timeout=15) as r: body=r.read(); code=r.status
    except HTTPError as e: code=e.code; body=e.read()
    except Exception as e: code=0; body=str(e).encode()
    return code,(time.perf_counter()-t)*1000,body

def main():
    if os.getenv('POSTGRES_HOST')!='db': raise RuntimeError('Instance OS4 PostgreSQL requise')
    if Dossier.objects.filter(project=PROJECT).exists(): raise RuntimeError('Lot de charge déjà présent')
    user=User.objects.create_user('os4_load',password='OS4-fictive-load-2026',role='R3')
    rows=[Dossier(reference=f'LOAD-{i:06d}',channel='WEB',project=PROJECT,theme='Distribution' if i%2 else 'Information',zone='Zone A' if i%3 else 'Zone B',state='EN_TRAITEMENT',owner=user,due=datetime.now(timezone.utc)+timedelta(days=10)) for i in range(5000)]
    Dossier.objects.bulk_create(rows,batch_size=500)
    Message.objects.bulk_create([Message(dossier=d,key=f'load-{i}',external_id=f'LOAD-{i}',channel='WEB',text=f'FICTIF Retour de charge {i}') for i,d in enumerate(rows)],batch_size=500)
    Record.objects.bulk_create([Record(dossier=d,kind='NOTE',data={'text':'Historique fictif initial'},author=user) for d in rows],batch_size=500)
    ids=[str(d.pk) for d in rows]; samples=[]; series=[]
    with open(OUT/'requests.csv','w',newline='') as f:
        w=csv.writer(f);w.writerow(['repeat','phase','virtual_user','sequence','route','status','duration_ms','utc'])
        def actor(rep,n,start):
            close_old_connections(); rng=random.Random(20261004+rep*100+n)
            time.sleep(n*RAMP/USERS)
            token=issue_session(user)['token'];refresh_at=time.monotonic()+540
            k=0
            while not abort.is_set() and time.monotonic()-start<RAMP+PLATEAU:
                if time.monotonic()>refresh_at:
                    # Separate ORM session issue avoids adding login throttling to the business mix.
                    token=issue_session(user)['token']; refresh_at=time.monotonic()+540
                draw=k%10;pk=rng.choice(ids)
                route='list' if draw<5 else ('detail' if draw<9 else 'write')
                path='/dossiers?project=OS4%20CHARGE&theme=Distribution' if route=='list' else '/dossiers/'+pk+('/notes' if route=='write' else '')
                code,ms,body=http(path,token,{'text':f'FICTIF charge {rep}/{n}/{k}'} if route=='write' else None)
                phase='ramp' if time.monotonic()-start<RAMP else 'plateau'
                row=[rep,phase,n,k,route,code,round(ms,3),datetime.now(timezone.utc).isoformat()]
                with lock: w.writerow(row);samples.append(row);f.flush()
                k+=1; time.sleep(1)
            close_old_connections()
        for rep in range(1,REPEATS+1):
            print(f'T16 répétition {rep} : montée 120 s puis plateau 900 s',flush=True)
            start=time.monotonic()
            with ThreadPoolExecutor(max_workers=USERS) as pool:
                futures=[pool.submit(actor,rep,n,start) for n in range(USERS)]
                while any(not x.done() for x in futures):
                    backlog=Outbox.objects.filter(processed=None).count()
                    oldest=Outbox.objects.filter(processed=None).order_by('created').first()
                    series.append({'repeat':rep,'elapsed':round(time.monotonic()-start,1),'pending_events':backlog,'worker_lag_seconds':round((datetime.now(timezone.utc)-oldest.created).total_seconds(),2) if oldest else 0})
                    (OUT/'worker.json').write_text(json.dumps(series,indent=2))
                    time.sleep(10)
                for fu in futures: fu.result()
            time.sleep(15)
    stats=[]
    for rep in range(1,REPEATS+1):
        for phase in ['ramp','plateau']:
            for route in ['list','detail','write','all']:
                selected=[x for x in samples if x[0]==rep and x[1]==phase and (x[4]==route or route=='all')]
                values=sorted(x[6] for x in selected);n=len(values)
                stats.append({'repeat':rep,'phase':phase,'route':route,'n':n,'p95_ms':values[math.ceil(.95*n)-1] if n else None,'under_2s':sum(x[6]<2000 and 200<=x[5]<300 for x in selected),'errors':sum(not 200<=x[5]<300 for x in selected),'throughput_per_second':n/(PLATEAU if phase=='plateau' else RAMP)})
    expected_writes=sum(x[4]=='write' and x[5]==201 for x in samples)
    actual_writes=Record.objects.filter(dossier__project=PROJECT).count()-5000
    result={'ramp_seconds':RAMP,'plateau_seconds':PLATEAU,'repeats':REPEATS,'virtual_users':USERS,'think_seconds':1,'initial_dossiers':5000,'final_dossiers':Dossier.objects.filter(project=PROJECT).count(),'writes_expected':expected_writes,'writes_observed':actual_writes,'integrity':actual_writes==expected_writes,'stats':stats}
    (OUT/'summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
