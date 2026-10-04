"""Encrypted PostgreSQL dumps; plaintext is piped in memory, never written to disk."""

import datetime
import os
from pathlib import Path
import subprocess
import sys
import time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def backup():
    data = subprocess.check_output(["pg_dump", "--format=custom", "--no-owner", "--no-acl"])
    nonce = os.urandom(12)
    encrypted = AESGCM(bytes.fromhex(os.environ["BACKUP_KEY"])).encrypt(nonce, data, b"cfrm-backup-v1")
    directory = Path(os.getenv("BACKUP_DIR", "/app/backups"))
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".dump.aes")
    path.write_bytes(nonce + encrypted)
    print(f"Sauvegarde chiffrée : {path}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restore":
        # Restore only into an explicitly supplied, empty target database.
        data = Path(sys.argv[2]).read_bytes()
        plain = AESGCM(bytes.fromhex(os.environ["BACKUP_KEY"])).decrypt(data[:12], data[12:], b"cfrm-backup-v1")
        subprocess.run(
            ["pg_restore", "--exit-on-error", "--no-owner", "--no-acl", "--dbname", os.environ["PGDATABASE"]],
            input=plain,
            check=True,
        )
    else:
        while True:
            backup()
            if len(sys.argv) < 2 or sys.argv[1] != "loop":
                break
            time.sleep(86400)
