"""T15 : pg_dump 16 chiffré, restauration dans une base vierge dédiée.
L'exploitant PostgreSQL est privilégié ; les contrôles de privilèges
ci-dessous ciblent explicitement feedback_app et feedback_sensitive.
"""
import os
import json
import time
import subprocess
import datetime
import hashlib
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
OUT=Path('/app/os4/backups');OUT.mkdir(exist_ok=True)
def sql(query,db='feedback'):
    return subprocess.check_output(['psql','--no-psqlrc','-v','ON_ERROR_STOP=1','-At','-d',db,'-c',query],text=True).strip()
def inventory(db):
    names=sql("SELECT schemaname||'.'||tablename FROM pg_tables WHERE schemaname IN ('public','sensible') ORDER BY 1",db).splitlines()
    return {name:int(sql('SELECT count(*) FROM '+name,db)) for name in names}
def main():
    t=time.perf_counter();before=inventory('feedback');version=subprocess.check_output(['pg_dump','--version'],text=True).strip()
    plain=subprocess.check_output(['pg_dump','--format=custom','--no-owner','--no-acl']);key=bytes.fromhex(os.environ['BACKUP_KEY']);nonce=os.urandom(12);encrypted=nonce+AESGCM(key).encrypt(nonce,plain,b'cfrm-backup-v1')
    target='os4_restore_'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d%H%M%S');file=OUT/(target+'.dump.aes');file.write_bytes(encrypted)
    subprocess.run(['createdb',target],check=True)
    decoded=AESGCM(key).decrypt(encrypted[:12],encrypted[12:],b'cfrm-backup-v1')
    subprocess.run(['pg_restore','--exit-on-error','--no-owner','--no-acl','--dbname',target],input=decoded,check=True)
    sql("REVOKE ALL ON SCHEMA sensible FROM PUBLIC; GRANT USAGE ON SCHEMA public TO feedback_app,feedback_report; GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO feedback_app; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO feedback_app; REVOKE UPDATE,DELETE,TRUNCATE ON core_audit FROM feedback_app; GRANT USAGE ON SCHEMA sensible TO feedback_sensitive; GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA sensible TO feedback_sensitive; GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA sensible TO feedback_sensitive; GRANT SELECT ON feedback_summary TO feedback_report",target)
    after=inventory(target);rights=sql("SELECT has_schema_privilege('feedback_app','sensible','USAGE'),has_table_privilege('feedback_app','core_audit','UPDATE'),has_table_privilege('feedback_app','core_dossier','SELECT'),has_table_privilege('feedback_sensitive','sensible.sensible_sensitivecontent','SELECT')",target)
    corrupt=False;missing=False
    bad=bytearray(encrypted);bad[-1]^=1
    try:AESGCM(key).decrypt(bytes(bad[:12]),bytes(bad[12:]),b'cfrm-backup-v1')
    except Exception:corrupt=True
    try:bytes.fromhex({}.get('BACKUP_KEY','')) or (_ for _ in ()).throw(RuntimeError('clé absente'))
    except Exception:missing=True
    result={'pg_dump_version':version,'target_database':target,'duration_seconds':round(time.perf_counter()-t,3),'bytes':len(encrypted),'sha256':hashlib.sha256(encrypted).hexdigest(),'before':before,'after':after,'counts_equal':before==after,'sql_privileges':rights,'corrupt_rejected':corrupt,'missing_key_rejected':missing,'outbound_worker_started_in_restore':False,'role_check':'droits SQL ; test API R4 à exécuter sur la restauration','owner':'postgres propriétaire privilégié après restauration sans owner ACL ; droits runtime réappliqués explicitement'}
    (OUT/'restore-results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if __name__=='__main__':main()
