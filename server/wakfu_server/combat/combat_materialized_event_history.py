"""Discard only superseded diagnostic materialization events at wave boundaries."""


def prune_materialized_events(fight):
    """Keep current-turn events, the facing tail and all historical authorities.

    State application/removal is materialized in state ledgers/retained stores.
    Completed turn/cast diagnostics are superseded by the current turn anchor.
    HP characteristic events remain protected-kill invalidation evidence.
    Never renumber sequence identities or truncate causal death predecessors.
    This is called only after the accepted action and wave callbacks finish.
    """
    events = getattr(fight, "events", None)
    turn = getattr(fight, "turn_id", None)
    if (
        type(events) is not list
        or len(events) <= 256
        or type(turn) is not int
        or getattr(fight, "_resolution_depth", 0) != 0
    ):
        return 0
    current_start = None
    previous_sequence = 0
    death_predecessors = set()
    for index, event in enumerate(events):
        if type(event) is not dict:
            return 0
        sequence = event.get("sequence")
        if type(sequence) is not int or sequence <= previous_sequence:
            return 0
        previous_sequence = sequence
        if event.get("kind") == "turn_started" and event.get("turn_id") == turn:
            current_start = index
        if event.get("kind") == "death" and index:
            death_predecessors.add(index - 1)
    if current_start is None:
        return 0
    cutoff = min(current_start, len(events) - 256)
    retained = []
    for index, event in enumerate(events):
        kind = event.get("kind")
        obsolete = (
            kind in ("state_applied", "state_removed", "movement", "orientation")
            or kind in ("turn_ended", "npc_cast")
            and type(event.get("turn_id")) is int
            and event["turn_id"] < turn
            or kind == "characteristic_changed"
            and type(event.get("stat_id")) is int
            and event["stat_id"] != 1
        )
        if index >= cutoff or index in death_predecessors or not obsolete:
            retained.append(event)
    removed = len(events) - len(retained)
    if removed:
        fight.events = retained
    return removed
