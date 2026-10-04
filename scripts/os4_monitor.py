"""Collecte Docker CPU et RAM à 10 secondes sans accès aux données métier."""
import subprocess
import json
import time
import datetime
from pathlib import Path
out=Path('docs/os4/load/resources.json');rows=[]
while True:
    p=subprocess.run(['docker','stats','--no-stream','--format','{{json .}}','ecoute-os4-api-1','ecoute-os4-db-1','ecoute-os4-worker-1','ecoute-os4-proxy-1'],capture_output=True,text=True)
    for line in p.stdout.splitlines():
        row=json.loads(line);row['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();rows.append(row)
    out.write_text(json.dumps(rows,indent=2))
    if Path('docs/os4/load/summary.json').exists():break
    time.sleep(10)
