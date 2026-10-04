"""Owned bare-character HP and the verified csX regeneration clock.

Equipment, passives and aptitude HP bonuses are excluded until implemented.
Store integration must CAS account/generation/actor and expected prior HP.
"""
from .paths import DATA_ROOT
import json
import math
import struct
from pathlib import Path

BASE_HEALTH = json.loads((DATA_ROOT / "base-health.json").read_text())["breeds"]
REGEN_DENOMINATOR_MS = 4000


def maximum(breed, level):
    if type(breed) is not int or str(breed) not in BASE_HEALTH:
        raise ValueError("Unsupported character breed")
    if type(level) is not int or not 1 <= level <= 200:
        raise ValueError("Character level must be between1 and200")
    stats = BASE_HEALTH[str(breed)]
    return stats["base"] + math.floor(level * stats["per_level"])


def packet(actor_id, hp, coefficient=0):
    if type(actor_id) is not int or actor_id <= 0 or type(hp) is not int or hp < 0:
        raise ValueError("Invalid owned health")
    if type(coefficient) is not int or not 0 <= coefficient <= 2**31 - 1:
        raise ValueError("Invalid regeneration coefficient")
    return struct.pack(">qii", actor_id, hp, coefficient)


def regenerated(initial_hp, max_hp, elapsed_ms, coefficient):
    """Evaluate one baseline, mirroring Java Math.round, without tick drift.

    Persist the baseline HP/time along with CAS state or reset it only after a
    confirmed health sync. Calling with elapsed since last tick loses fractions.
    coefficient0 disables regeneration during combat or when already full.
    """
    if any(type(v) is not int for v in (initial_hp, max_hp, elapsed_ms, coefficient)):
        raise ValueError("Health inputs must be integers")
    if (
        not 0 <= initial_hp <= max_hp
        or max_hp <= 0
        or elapsed_ms < 0
        or coefficient < 0
    ):
        raise ValueError("Invalid regeneration state")
    gained = (
        coefficient * elapsed_ms + REGEN_DENOMINATOR_MS // 2
    ) // REGEN_DENOMINATOR_MS
    return min(max_hp, initial_hp + gained)
