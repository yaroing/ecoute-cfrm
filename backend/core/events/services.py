from core.models import Outbox


def emit(name, obj, actor=None):
    return Outbox.objects.create(
        event=name, object_id=str(obj.pk if hasattr(obj, "pk") else obj), actor_id=actor.pk if actor else None
    )
