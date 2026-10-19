"""Owned bare-character HP and the verified csX regeneration clock.

Equipment, passives and aptitude HP bonuses are excluded until implemented.
Store integration must CAS account/generation/actor and expected prior HP.
"""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import json
import math
import struct
from pathlib import Path
from wakfu_server.character_levels import validate_character_level

BASE_HEALTH = protocol_catalog.load(DATA_ROOT / "base-health.json")["breeds"]
REGEN_DENOMINATOR_MS = 4000
EXPLORATION_RECOVERY_MS = 120000


def exploration_coefficient(max_hp, hp):
    """Explicit Wakemu policy: recover a full HP bar in about two minutes.

    The original client/server coefficient still means HP per 4000 ms. Scale
    that coefficient with the owned maximum; never change the native clock.
    Call only outside combat. Dead characters require an owned return first.
    """
    if (
        type(max_hp) is not int
        or not 0 < max_hp < 2**31
        or type(hp) is not int
        or not 0 <= hp <= max_hp
    ):
        raise ValueError("Invalid exploration health")
    if hp == 0:
        return 0
    return (
        max_hp * REGEN_DENOMINATOR_MS + EXPLORATION_RECOVERY_MS - 1
    ) // EXPLORATION_RECOVERY_MS


def maximum(breed, level):
    if type(breed) is not int or str(breed) not in BASE_HEALTH:
        raise ValueError("Unsupported character breed")
    validate_character_level(level)
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
