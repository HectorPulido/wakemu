"""Native eKr fighter maximum and eKW global player-level cap queries."""


def fighters_max_level(rows, kind="player", in_play_only=True):
    """eKr: type1 monsters or type0/5 players, excluding property114."""
    if type(kind) is not str or type(in_play_only) is not bool:
        raise ValueError("Invalid native fighter maximum-level arguments")
    types = (1,) if kind.lower() == "monster" else (0, 5)
    result = 0
    for actor_type, in_play, properties, level in rows:
        if type(actor_type) is not int:
            raise ValueError("Missing native maximum-level actor type")
        if actor_type not in types:
            continue
        if in_play_only:
            if type(in_play) is not bool:
                raise ValueError("Missing native maximum-level in-play membership")
            if not in_play:
                continue
        if not isinstance(properties, (set, frozenset)):
            raise ValueError("Missing native maximum-level fight properties")
        if 114 in properties:
            continue
        if type(level) is not int or not -32768 <= level <= 32767:
            raise ValueError("Missing native cmZ signed-short level")
        result = max(result, level)
    return result


def fighters_min_level(rows, kind="player", in_play_only=True):
    """eKs: type1 monsters or type0/5 players, excluding property114."""
    if type(kind) is not str or type(in_play_only) is not bool:
        raise ValueError("Invalid native fighter minimum-level arguments")
    types = (1,) if kind.lower() == "monster" else (0, 5)
    result = 32767
    for actor_type, in_play, properties, level in rows:
        if type(actor_type) is not int:
            raise ValueError("Missing native minimum-level actor type")
        if actor_type not in types:
            continue
        if in_play_only:
            if type(in_play) is not bool:
                raise ValueError("Missing native minimum-level in-play membership")
            if not in_play:
                continue
        if not isinstance(properties, (set, frozenset)):
            raise ValueError("Missing native minimum-level fight properties")
        if 114 in properties:
            continue
        if type(level) is not int or not -32768 <= level <= 32767:
            raise ValueError("Missing native cmZ signed-short level")
        result = min(result, level)
    return result


def player_max_level(fight):
    """eKW reads eEL.pab, not any actor's level (native default245)."""
    from .combat_system_conditions import CONFIG_SOURCE

    state = getattr(fight, "native_system_configuration", None)
    if (
        not isinstance(state, dict)
        or state.get("source") != CONFIG_SOURCE
        or not isinstance(state.get("overrides"), dict)
    ):
        raise ValueError("Missing current native player-level configuration producer")
    # eEL.pab constructor: config31, player.level.cap, fallback string "245".
    value = state["overrides"].get("player.level.cap", 245)
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise ValueError("Invalid native eEI integer player-level cap")
    return value
