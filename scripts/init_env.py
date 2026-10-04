import secrets
from pathlib import Path

path = Path(__file__).resolve().parent.parent / ".env"
if path.exists():
    raise SystemExit(".env existe déjà ; aucune clé remplacée.")
keys = [
    "DJANGO_SECRET",
    "FIELD_KEY",
    "HMAC_KEY",
    "SMS_SECRET",
    "MESSAGING_SECRET",
    "DB_ADMIN_PASSWORD",
    "POSTGRES_PASSWORD",
    "SENSITIVE_PASSWORD",
    "OWNER_PASSWORD",
    "SENSITIVE_OWNER_PASSWORD",
    "REPORT_PASSWORD",
    "BACKUP_KEY",
]
path.write_text(
    "APP_ENV=local\nSIMULATION=1\nALLOWED_HOSTS=localhost,127.0.0.1,api\nSITE_ADDRESS=http://localhost:8080\n"
    + "".join(k + "=" + secrets.token_hex(32) + "\n" for k in keys)
)
print("Configuration de recette créée dans .env (ignorée par Git).")
