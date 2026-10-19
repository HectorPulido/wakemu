"""Native Wakfu XP base shared by the client's monster and level models.

MU.L and MT.nS are verified against an offline export from the original JAR.
Species-specific server coefficients are unavailable; the local policy uses 1.
"""
import math

MAX_XP = (1 << 63) - 1


def monster_base_xp(level):
    if type(level) is not int or not 1 <= level <= 32767:
        raise ValueError("Invalid monster level")
    if level < 57:
        value = 100 * level + 1.5 * math.pow(level, 2.2) + 630 * math.pow(level / 20, 4)
    else:
        exponent = level / 21
        if exponent >= math.log2(MAX_XP / 8860):
            return MAX_XP
        value = 8860 * math.pow(2, exponent)
    return min(MAX_XP, math.floor(value + 0.5))


def intended_fights(level):
    if level < 98:
        return math.pow(level, 0.8)
    if level < 170:
        return math.pow(level - 79, 1.25)
    if level < 200:
        return math.pow(level - 105, 1.35)
    return math.pow(level - 119, 1.4)


def level_factor(player_level, monster_level):
    """Community cosine model with local terminal-tail clamps.

    The reference does not specify extreme-gap behavior. Clamp its tails to
    prevent periodic cosine bonuses when the level gap exceeds the first tail.
    """
    gap = monster_level - player_level
    if gap == 0:
        return 1.0
    if gap > 0:
        return 0.5 * (math.cos(min(60, gap - 10) / 60 * math.pi) + 1)
    return 0.3 + 0.35 * (math.cos(min(70, -gap - 10) / 70 * math.pi) + 1)
