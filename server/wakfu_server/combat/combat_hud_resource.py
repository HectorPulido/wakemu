"""Server projection for native breed HUD resources, distinct from state icons.

bgV.h reads ffw values; bgV.j independently chooses a state popup. Rules here
are explicit emulated-server producers, not a universal popup-level copy.
Yopuka Concentration (3442) and Sacrier Furor (9312) have explicit
resource projections. Sacrier 9313 tracks HP percent and is NOT Furor.
Unverified breeds keep their existing characteristic authority unchanged.
"""

# breed -> (HUD characteristic, authoritative running-state reference).
STATE_RESOURCE_RULES = {8: (67, 3442), 11: (50, 9312)}


def sync_actor_hud_resource(actor):
    rule = STATE_RESOURCE_RULES.get(getattr(actor, "native_hud_breed", None))
    if rule is None:
        return None
    stat, reference = rule
    if not isinstance(actor.effect_stats, dict) or stat not in actor.effect_stats:
        raise ValueError("Missing authoritative breed HUD characteristic")
    matches = [
        entry for entry in actor.state_ledger.entries if entry.reference == reference
    ]
    # Native eGj state lookup is ordered; do not sum duplicate carriers.
    value = matches[0].level if matches else 0
    if type(value) is not int or not 0 <= value < 2**31:
        raise ValueError("Invalid authoritative breed HUD state level")
    previous = actor.effect_stats[stat]
    actor.effect_stats[stat] = value
    return (actor.id, stat, previous, value) if previous != value else None


def sync_hud_resources(fight):
    return tuple(
        change
        for actor in fight.actors.values()
        if (change := sync_actor_hud_resource(actor)) is not None
    )
