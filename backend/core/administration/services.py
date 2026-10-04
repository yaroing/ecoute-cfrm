from core.models import Setting

DEFAULTS = {
    "themes": ["Distribution", "Eau et assainissement", "Santé", "Éducation", "Information", "Autre"],
    "zones": ["Tillabéri", "Niamey", "Dosso", "Maradi", "Tahoua"],
    "projects": ["Assistance communautaire", "Accès à l’eau", "Sécurité alimentaire"],
    "keywords": ["abus", "exploitation", "fraude", "danger", "harcèlement", "violence sexuelle"],
    "delays": {"URGENTE": 3, "QUESTION": 5, "PLAINTE": 10, "SUGGESTION": 10, "SATISFACTION": 5},
    "retention_days": 90,
    "templates": {"fr": "Merci pour votre retour. Voici les mesures prises par notre équipe : "},
    "languages": [{"code": "fr", "label": "Français"}],
    "referral_contact": "Contactez le référent de votre organisation par le canal sécurisé convenu.",
}


def config(key):
    item = Setting.objects.filter(pk=key).first()
    return item.value if item else DEFAULTS[key]


def is_sensitive(text):
    return any(word.casefold() in text.casefold() for word in config("keywords"))
