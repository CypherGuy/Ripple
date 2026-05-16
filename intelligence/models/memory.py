from dataclasses import dataclass


@dataclass
class Scar:
    pattern: str
    service: str
    outcome: str
    reason: str
    risk_adjustment: int
    date: str


@dataclass
class Win:
    pattern: str
    service: str
    outcome: str
    reason: str
    confidence_boost: int
    date: str
