from datetime import timedelta
from core.administration.services import config


def business_due(start, kind, urgency):
    days = config("delays").get(urgency if urgency == "URGENTE" else kind, 10)
    while days > 0:
        start += timedelta(days=1)
        if start.weekday() < 5:
            days -= 1
    return start
