"""Drop completed native turn receipts after publication callbacks have settled."""

_PHASES = {"start": 1001, "end": 1002, "regeneration": 1037}
_FIELDS = {"actor_id", "turn_id", "event_id", "phase", "suppressed"}


def _native_turn(key, row):
    if type(key) is not str or type(row) is not dict:
        return None
    parts = key.split(":")
    if len(parts) != 3 or parts[2] not in _PHASES:
        return None
    try:
        turn, actor = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if turn < 1 or actor == 0 or key != f"{turn}:{actor}:{parts[2]}":
        return None
    if (
        any(type(name) is not str for name in row)
        or set(row) != _FIELDS
        or type(row["actor_id"]) is not int
        or row["actor_id"] != actor
        or type(row["turn_id"]) is not int
        or row["turn_id"] < turn
        or type(row["event_id"]) is not int
        or row["event_id"] != _PHASES[parts[2]]
        or type(row["phase"]) is not str
        or row["phase"] != parts[2]
        or type(row["suppressed"]) is not bool
    ):
        return None
    return turn


def prune_published_turn_receipts(fight, runtime, packets):
    """Only the final private publication candidate may discard old markers.

    Historical consumers are fixed at admission. A missing terminal policy
    cannot be installed after placement; the native factory rejects that call.
    ACK may still be pending: its packets and barrier have their own storage.
    """
    from .combat_state import Fight
    from .combat_runtime_messages import RuntimeMessages
    from .combat_retained_gc_authority import native_callbacks_known

    if (
        type(fight) is not Fight
        or type(runtime) is not RuntimeMessages
        or type(packets) is not tuple
    ):
        return
    state, execution = vars(fight), vars(runtime)
    if (
        execution.get("fight") is not fight
        or state.get("phase") != "active"
        or type(state.get("turn_id")) is not int
        or state["turn_id"] < 1
        or state.get("_resolution_depth", 0) != 0
        or state.get("_native_delivery_depth", 0) != 0
        or execution.get("_native_delivery_depth", 0) != 0
        or not native_callbacks_known(runtime)
    ):
        return
    if (
        "native_optional_ballot_challenge" not in state
        or state["native_optional_ballot_challenge"] is not None
        or state.get("native_encounter_terminal_cleanup_policy") is not None
    ):
        return
    # freeze_terminal_cleanup_policy requires placement when this field is
    # absent. Active native runtimes cannot acquire a historical policy later.
    receipts = state.get("native_turn_event_deliveries")
    if type(receipts) is not dict or any(type(key) is not str for key in receipts):
        return
    current = state["turn_id"]
    old = [
        key
        for key, row in receipts.items()
        if (turn := _native_turn(key, row)) is not None and turn < current
    ]
    if old:
        remaining = dict(receipts)
        for key in old:
            del remaining[key]
        fight.native_turn_event_deliveries = remaining
