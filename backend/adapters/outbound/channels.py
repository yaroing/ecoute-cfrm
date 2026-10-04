from django.conf import settings


def send(message):
    # No provider is configured in this prototype. Never claim an actual delivery.
    if message.channel in ["SMS_SIMULE", "MESSAGERIE_SIMULEE"] and settings.SIMULATION:
        return "ENVOYE"
    return "ECHEC"
