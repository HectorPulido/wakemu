"""Read committed attack evidence from the complete native fight ledger."""


def damaged_targets_this_turn(graph, fight, actor_id):
    """Targets of positive damage committed by this actor's current turn casts."""
    try:
        turn = graph.plain(graph.field(fight, "turn_id"))
        events = graph.plain(graph.field(fight, "events"))
    except (KeyError, ValueError):
        return frozenset()
    pending, committed = set(), set()
    for event in events:
        kind = event.get("kind")
        if kind in ("turn_started", "turn_ended"):
            pending.clear()
            committed.clear()
        elif kind == "damage" and event.get("source_id") == actor_id:
            target = event.get("target_id")
            if event.get("amount", 0) > 0 and type(target) is int:
                pending.add(target)
        elif kind == "npc_cast":
            if event.get("actor_id") == actor_id and event.get("turn_id") == turn:
                committed.update(pending)
            pending.clear()
    return frozenset(committed)


def attacked_this_turn(graph, fight, actor_id):
    try:
        turn = graph.plain(graph.field(fight, "turn_id"))
        events = graph.plain(graph.field(fight, "events"))
    except (KeyError, ValueError):
        return False
    pending_damage = False
    attacked = False
    for event in events:
        kind = event.get("kind")
        if kind in ("turn_started", "turn_ended"):
            pending_damage = attacked = False
        elif kind == "damage" and event.get("source_id") == actor_id:
            pending_damage |= event.get("amount", 0) > 0
        elif kind == "npc_cast":
            if event.get("actor_id") == actor_id and event.get("turn_id") == turn:
                attacked |= pending_damage
            pending_damage = False
    return attacked


def battleground_border_cells(graph, fight):
    """Registered scenario perimeter; no map, spell or prototype ID lookup."""
    try:
        return frozenset(
            tuple(cell)
            for cell in graph.plain(graph.field(fight, "native_border_cells"))
        )
    except (KeyError, ValueError):
        return frozenset()
