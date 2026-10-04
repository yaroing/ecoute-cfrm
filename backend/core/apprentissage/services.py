from django.db import transaction
from core.events.services import emit


@transaction.atomic
def save_action(serializer, actor):
    action = serializer.save()
    emit("ActionRealisee" if action.status == "REALISEE" else "ActionEnregistree", action, actor)
    return action


@transaction.atomic
def save_restitution(serializer, action, actor):
    result = serializer.save(action=action)
    emit("RestitutionEnregistree", action, actor)
    return result
