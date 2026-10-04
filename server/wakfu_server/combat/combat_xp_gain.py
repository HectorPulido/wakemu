"""Native cvu13613 XP-gain action, preceding fight cleanup and absolute XP sync."""
import struct


def notification(character_id, reward):
    """Own fCs/fCq: characterID, won XP DELTA, gained levels, zero spell records.

    This event calls biB.jH(delta) and the level/HUD update path. A later
    absolute format3 snapshot reconciles totals. Emitting after that snapshot
    would add XP twice. Idempotent award retries must not send another delta.
    """
    if (
        reward["character"]["id"] != character_id
        or type(character_id) is not int
        or not 0 < character_id < 2**63
    ):
        raise ValueError("XP notice requires matching own character")
    if not reward["awarded"] or reward["xp"] == 0:
        return None
    info = reward.get("xp_info")
    if not info or info["won_xp"] != reward["xp"]:
        raise ValueError("Missing committed XP-gain receipt")
    gained_levels = info["end_level"] - info["start_level"]
    if not 0 <= gained_levels <= 199 or not 0 < reward["xp"] < 2**63:
        raise ValueError("Invalid native XP-gain notification")
    # cvu boolean enabled; fCs countbyte; fCq ID+fCx(delta,leveldelta)+spellcount.
    return (
        13613,
        struct.pack(">BBqqhB", 1, 1, character_id, reward["xp"], gained_levels, 0),
    )
