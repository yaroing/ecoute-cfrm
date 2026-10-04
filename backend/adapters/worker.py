from adapters.outbound.channels import send
from core.events.tasks import tick


def run():
    tick(send)
