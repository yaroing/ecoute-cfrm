from dataclasses import dataclass


@dataclass(frozen=True)
class Incoming:
    channel: str
    key: str
    external_id: str
    text: str
    contact_id: int | None = None
    type: str = "PLAINTE"
    zone: str = "Non précisée"
    project: str = "Assistance communautaire"
    language: str = "fr"
    sensitive: bool = False
