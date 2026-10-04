import json
import os
from pathlib import Path
import secrets
import time
from datetime import timedelta
import pyotp
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from core.crypto import encrypt
from core.models import User, Dossier, Action
from core.dossiers.services import qualify, transition
from core.reponses.services import prepare, validate
from api.views import signed_ingest
from adapters.inbound.channels import signature
from adapters.worker import run


class Command(BaseCommand):
    help = "Crée les six rôles et 60 dossiers exclusivement fictifs, via le traitement signé."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=60)
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Réinitialise uniquement les six comptes fictifs de démonstration.",
        )

    def handle(self, **options):
        if not settings.SIMULATION:
            raise CommandError("Simulation désactivée.")
        credentials = []
        for role, name, label in [
            ("R1", "agent", "Aïcha • collecte"),
            ("R2", "gestionnaire", "Moussa • gestion"),
            ("R3", "superviseur", "Aminata • MEAL"),
            ("R4", "referent", "Référent • protection"),
            ("R5", "direction", "Direction • programmes"),
            ("R6", "admin", "Administration technique"),
        ]:
            if User.objects.filter(username=name).exists() and not options["reset_passwords"]:
                continue
            password = secrets.token_urlsafe(12)
            otp = pyotp.random_base32() if role in ["R4", "R6"] else ""
            user, _ = User.objects.get_or_create(username=name)
            user.set_password(password)
            user.first_name, user.role = label, role
            user.totp_secret = encrypt(otp) if otp else ""
            user.last_totp_step = -1
            user.save()
            credentials.append({"username": name, "password": password, "role": role, "totp_secret": otp})
        file = Path(os.getenv("DEMO_CREDENTIALS_FILE", str(settings.BASE_DIR.parent / ".demo-credentials.json")))
        if credentials:
            file.write_text(json.dumps(credentials, indent=2), encoding="utf-8")
        supervisor = User.objects.get(username="superviseur")
        manager = User.objects.get(username="gestionnaire")
        texts = [
            "Où se tiendra la prochaine distribution ?",
            "Les kits annoncés ne sont pas encore arrivés.",
            "Proposer un point d’eau près du marché.",
            "Merci pour l’accueil de l’équipe.",
        ]
        zones = ["Tillabéri", "Niamey", "Dosso", "Maradi", "Tahoua"]
        for i in range(options["count"]):
            kind = (
                "QUESTION"
                if i < 12
                else "PLAINTE"
                if i < 26
                else "SUGGESTION"
                if i < 34
                else "SATISFACTION"
                if i < 38
                else "PLAINTE"
            )
            text = texts[["QUESTION", "PLAINTE", "SUGGESTION", "SATISFACTION"].index(kind)]
            if 52 <= i < 60:
                text = "EXERCICE FICTIF : signalement de fraude, aucun fait réel."
            data = {
                "key": f"DEMO-{i:06d}",
                "text": text,
                "address": f"TEST-{i:06d}" if not 38 <= i < 44 else "",
                "consent": True,
                "type": kind,
                "zone": zones[i % 5],
            }
            raw = json.dumps(data).encode()
            timestamp = str(int(time.time()))
            result = signed_ingest("sms", timestamp, raw, signature("sms", timestamp, raw))
            dossier = Dossier.objects.get(pk=result["id"])
            if result["duplicate"] or dossier.sensitive or i % 5 == 0:
                continue
            qualify(
                dossier,
                {
                    "type": kind,
                    "theme": "Distribution" if i % 2 else "Eau et assainissement",
                    "urgency": "URGENTE" if i % 7 == 0 else "NORMALE",
                },
                supervisor,
            )
            transition(dossier, {"state": "ATTRIBUE", "owner": manager.pk}, supervisor)
            if i % 5 >= 2:
                transition(dossier, {"state": "EN_TRAITEMENT"}, manager)
            if i % 5 >= 3 and dossier.contact_id:
                reply = prepare(
                    dossier,
                    "EXERCICE FICTIF : une nouvelle distribution est programmée. Les horaires seront annoncés au point d’accueil.",
                    manager,
                )
                validate(dossier, reply, True, supervisor)
                run()
                dossier.refresh_from_db()
                if i % 5 == 4:
                    transition(dossier, {"state": "CLOTURE", "reason": "RESOLU"}, supervisor)
            if i % 7 == 0 and dossier.state != "CLOTURE":
                dossier.due = timezone.now() - timedelta(days=1)
                dossier.save()
        if not Action.objects.exists():
            action = Action.objects.create(
                title="Rapprocher les points de distribution des communautés",
                project="Assistance communautaire",
                owner=supervisor,
                due=(timezone.now() + timedelta(days=14)).date(),
                status="EN_COURS",
            )
            action.dossiers.set(Dossier.objects.filter(sensitive=False, state="CLOTURE")[:3])
        run()
        self.stdout.write(f"{Dossier.objects.count()} dossiers. Identifiants locaux : {file}")
