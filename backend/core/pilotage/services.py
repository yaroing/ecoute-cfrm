from collections import Counter
from statistics import median
from datetime import timedelta
from django.utils import timezone
from rest_framework import serializers
from core.models import Dossier, Action


def ratio(a, b):
    return round(100 * a / b, 1) if b else None


def working_days(a, b):
    n = 0
    while a.date() < b.date():
        a += timedelta(days=1)
        n += a.weekday() < 5
    return n


def filtered(qs, params):
    if params.get("project"):
        qs = qs.filter(project=params["project"])
    if params.get("from"):
        qs = qs.filter(created__date__gte=serializers.DateField().run_validation(params["from"]))
    if params.get("to"):
        qs = qs.filter(created__date__lte=serializers.DateField().run_validation(params["to"]))
    return qs


def indicators(params):
    rows = list(filtered(Dossier.objects.filter(sensitive=False, merged_into=None), params).prefetch_related("actions"))
    now = timezone.now()
    opened = [d for d in rows if d.state != "CLOTURE"]
    closed = [d for d in rows if d.state == "CLOTURE"]
    late = [d for d in opened if d.due and d.due < now]
    eligible = [d for d in rows if d.contact_id]
    actionable = [d for d in closed if d.type in ["PLAINTE", "SUGGESTION"]]
    actions = list(filtered(Action.objects.all(), params).prefetch_related("restitutions"))
    done = [a for a in actions if a.status == "REALISEE"]
    sensitive = list(filtered(Dossier.objects.filter(sensitive=True), params).values("created", "sensitive_taken"))
    counts = {
        field: dict(Counter(getattr(d, field) for d in rows)) for field in ["channel", "type", "theme", "zone", "state"]
    }
    delays = [working_days(d.created, d.responded) for d in rows if d.responded]
    return {
        "total": len(rows),
        "open": len(opened),
        "late": len(late),
        "closed": len(closed),
        "sensitive_total": len(sensitive),
        "anonymous": len(rows) - len(eligible),
        "actions_without_restitution": sum(not a.restitutions.all() for a in done),
        "indicators": {
            "I01": ratio(
                sum(bool(d.acknowledged and d.acknowledged - d.created < timedelta(hours=24)) for d in rows), len(rows)
            ),
            "I02": median(delays) if delays else None,
            "I03": ratio(sum(bool(d.responded) for d in eligible), len(eligible)),
            "I04": ratio(len(late), len(opened)),
            "I05": dict(Counter(d.closure_reason for d in closed)),
            "I06": ratio(sum(bool(d.actions.all()) for d in actionable), len(actionable)),
            "I07": ratio(sum(bool(a.restitutions.all()) for a in done), len(done)),
            "I08": ratio(
                sum(
                    bool(d["sensitive_taken"] and d["sensitive_taken"] - d["created"] < timedelta(hours=24))
                    for d in sensitive
                ),
                len(sensitive),
            ),
            "I09": ratio(
                sum(d.reopen_count > 0 for d in rows), sum(d.state == "CLOTURE" or d.reopen_count > 0 for d in rows)
            ),
            "I10": counts,
        },
        "counts": counts,
    }
