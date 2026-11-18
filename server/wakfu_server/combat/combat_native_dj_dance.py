"""Owner-side input validator for the native Bilbyza DJ dance challenge.

The reducer consumes facts only after the ordinary native spell executor has
accepted a cast.  It does not create the DJ's state, colored areas, or the
player's temporary control book.  Those must be produced by the pinned native
encounter path before a challenge can start.
"""
from copy import deepcopy
from hashlib import sha256
import json
from weakref import ref


SCHEMA = "bilbyza-native-dj-dance-v2"
QUEST_ID = 1264
OBJECTIVE_ID = 2393
SETUP_ACTOR = 2502
CONSUMER_ACTOR = 2518
CONTROL_BOOK_SPELLS = (3713, 3714, 3715, 3716, 3701, 3702, 3703, 3704)
SETUP_SPELL = 3700
SETUP_ROOT = 95219
SETUP_STATE_EFFECT = 95845
CHALLENGE_STATE = 1941
TURN_BOUNDARY_EVENT = 1001
EVENT_REFERENCE = OBJECTIVE_ID

# The four native floor areas and the corresponding state/spell in the
# original DJ control book.  Dance and beatbox are distinct commands for each
# color; native state levels determine their order.
INPUTS = {
    1932: dict(color="red", area=527, mode="dance", spell=3701),
    1933: dict(color="blue", area=528, mode="dance", spell=3702),
    1934: dict(color="green", area=529, mode="dance", spell=3703),
    1935: dict(color="violet", area=530, mode="dance", spell=3704),
    1942: dict(color="red", area=527, mode="beatbox", spell=3713),
    1943: dict(color="blue", area=528, mode="beatbox", spell=3714),
    1944: dict(color="green", area=529, mode="beatbox", spell=3715),
    1945: dict(color="violet", area=530, mode="beatbox", spell=3716),
}
SPELL_INPUTS = {row["spell"]: state for state, row in INPUTS.items()}


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def _native_state_rows(rows):
    selected = []
    for row in rows:
        if not isinstance(row, dict) or row.get("reference") not in INPUTS:
            continue
        if type(row.get("level")) is not int or row["level"] not in (1, 2, 3, 4):
            raise ValueError("DJ order states require their actual native levels1-4")
        uid = row.get("uid")
        if type(uid) is not int or uid <= 0:
            raise ValueError(
                "DJ control states require their native carrier identities"
            )
        selected.append(dict(reference=row["reference"], level=row["level"], uid=uid))
    selected_areas = {INPUTS[row["reference"]]["area"] for row in selected}
    if (
        len(selected) != 4
        or len({row["reference"] for row in selected}) != 4
        or selected_areas != {527, 528, 529, 530}
    ):
        raise ValueError(
            "DJ challenge requires the four actual active color/mode states"
        )
    if {row["level"] for row in selected} != {1, 2, 3, 4}:
        raise ValueError("DJ challenge native order has an ambiguous tied state level")
    if len({row["uid"] for row in selected}) != 4:
        raise ValueError("DJ challenge states reuse a carrier identity")
    return sorted(selected, key=lambda row: row["level"])


def start(
    *,
    owner_id,
    owner_account_id,
    owner_level,
    setup_actor_id,
    setup_actor_reference,
    setup_spell_id,
    setup_root,
    setup_state_effect,
    applied_state_reference,
    challenge_state_uid,
    area_subscription_event,
    control_states,
):
    """Build a challenge only from the successful original setup cast.

    Call this at the actual successful 304 state-application boundary for
    95845, after the native 3700/95219 executor has committed the 1941 state.
    """
    if (
        type(owner_id) is not int
        or owner_id <= 0
        or type(owner_account_id) is not int
        or owner_account_id <= 0
        or type(owner_level) is not int
        or owner_level < 85
        or type(setup_actor_id) is not int
        or setup_actor_id <= 0
        or setup_actor_reference != SETUP_ACTOR
        or setup_spell_id != SETUP_SPELL
        or setup_root != SETUP_ROOT
        or setup_state_effect != SETUP_STATE_EFFECT
        or applied_state_reference != CHALLENGE_STATE
        or type(challenge_state_uid) is not int
        or challenge_state_uid <= 0
        or area_subscription_event != TURN_BOUNDARY_EVENT
    ):
        raise ValueError("DJ challenge lacks its actual native 2502 setup witness")
    ordered = _native_state_rows(control_states)
    contract = dict(
        schema=SCHEMA,
        owner_id=owner_id,
        owner_account_id=owner_account_id,
        owner_level=owner_level,
        setup_actor_id=setup_actor_id,
        setup_actor_reference=SETUP_ACTOR,
        setup_spell_id=SETUP_SPELL,
        setup_root=SETUP_ROOT,
        setup_state_effect=SETUP_STATE_EFFECT,
        challenge_state=CHALLENGE_STATE,
        challenge_state_uid=challenge_state_uid,
        area_subscription_event=TURN_BOUNDARY_EVENT,
        expected=ordered,
        index=0,
        stage="active",
        accepted=[],
        failures=[],
        terminal=None,
    )
    contract["source_sha256"] = digest(contract)
    return contract


def _validate_contract(state):
    if (
        not isinstance(state, dict)
        or state.get("schema") != SCHEMA
        or state.get("stage") not in {"active", "failed", "complete"}
        or type(state.get("owner_id")) is not int
        or type(state.get("owner_account_id")) is not int
        or type(state.get("owner_level")) is not int
        or state.get("owner_level") < 85
        or type(state.get("index")) is not int
        or not 0 <= state["index"] <= 4
        or type(state.get("challenge_state_uid")) is not int
        or state.get("challenge_state_uid") <= 0
        or not isinstance(state.get("expected"), list)
        or len(state["expected"]) != 4
        or state.get("source_sha256")
        != digest({k: v for k, v in state.items() if k != "source_sha256"})
    ):
        raise ValueError("Changed or malformed DJ challenge state")
    expected = state["expected"]
    accepted = state.get("accepted")
    failures = state.get("failures")
    if (
        any(not isinstance(row, dict) for row in expected)
        or any(
            type(row.get("reference")) is not int
            or row.get("reference") not in INPUTS
            or type(row.get("level")) is not int
            or row.get("level") not in (1, 2, 3, 4)
            or type(row.get("uid")) is not int
            or row.get("uid") <= 0
            for row in expected
        )
        or [row.get("level") for row in expected] != [1, 2, 3, 4]
        or len({row.get("reference") for row in expected}) != 4
        or {INPUTS.get(row.get("reference"), {}).get("area") for row in expected}
        != {527, 528, 529, 530}
        or len({row.get("uid") for row in expected}) != 4
        or not isinstance(accepted, list)
        or len(accepted) != state["index"]
        or not isinstance(failures, list)
        or (state["stage"] == "active" and state["index"] >= 4)
        or (state["stage"] == "complete" and state["index"] != 4)
        or (state["stage"] == "failed" and not failures)
        or (state["stage"] == "failed" and state["index"] >= 4)
        or (
            state["terminal"] is not None
            and state["stage"] not in {"complete", "failed"}
        )
        or state.get("control_book_spells", list(CONTROL_BOOK_SPELLS))
        != list(CONTROL_BOOK_SPELLS)
        or not isinstance(state.get("grant_uids", []), list)
        or any(type(uid) is not int or uid <= 0 for uid in state.get("grant_uids", []))
        or len(set(state.get("grant_uids", []))) != len(state.get("grant_uids", []))
        or ("control_book_spells" in state and len(state.get("grant_uids", [])) != 8)
    ):
        raise ValueError("Changed DJ state order or input receipt sequence")
    for index, receipt in enumerate(accepted):
        command = INPUTS[expected[index]["reference"]]
        if (
            not isinstance(receipt, dict)
            or receipt.get("kind") != "accepted_input"
            or receipt.get("owner_id") != state["owner_id"]
            or receipt.get("target_id") != state["owner_id"]
            or receipt.get("spell_id") != command["spell"]
            or receipt.get("actual_color_area") != command["area"]
            or receipt.get("expected_state") != expected[index]["reference"]
            or receipt.get("expected_level") != expected[index]["level"]
            or type(receipt.get("event_id")) is not int
            or receipt["event_id"] <= 0
            or type(receipt.get("event_sequence")) is not int
            or receipt["event_sequence"] <= 0
        ):
            raise ValueError("Changed native DJ input receipt")
    if failures:
        receipt = failures[0]
        expected = state["expected"][state["index"]]
        command = INPUTS[expected["reference"]]
        if (
            len(failures) != 1
            or state["stage"] != "failed"
            or not isinstance(receipt, dict)
            or receipt.get("kind") != "wrong_input"
            or receipt.get("owner_id") != state["owner_id"]
            or receipt.get("target_id") != state["owner_id"]
            or receipt.get("spell_id") not in SPELL_INPUTS
            or receipt.get("expected_state") != expected["reference"]
            or receipt.get("expected_level") != expected["level"]
            or type(receipt.get("event_id")) is not int
            or receipt["event_id"] <= 0
            or type(receipt.get("event_sequence")) is not int
            or receipt["event_sequence"] <= 0
            or (
                receipt["spell_id"] == command["spell"]
                and receipt.get("actual_color_area") == command["area"]
            )
        ):
            raise ValueError("Changed native DJ failure receipt")
    terminal = state.get("terminal")
    if terminal is not None:
        failed = state["stage"] == "failed"
        receipts = [*accepted, *failures] if failed else accepted
        if (
            not isinstance(terminal, dict)
            or terminal.get("policy")
            != (
                "reviewed_wrong_native_input_challenge_terminal_v1"
                if failed
                else "reviewed_four_native_inputs_challenge_terminal_v1"
            )
            or terminal.get("owner_id") != state["owner_id"]
            or terminal.get("inputs") != [row["event_sequence"] for row in receipts]
            or terminal.get("result")
            != ("challenge_failed" if failed else "challenge_completed")
            or type(terminal.get("event_sequence")) is not int
            or terminal["event_sequence"] <= 0
            or terminal.get("source_sha256")
            != digest(
                {
                    key: value
                    for key, value in terminal.items()
                    if key != "source_sha256"
                }
            )
        ):
            raise ValueError("DJ terminal lost its four-input reviewed authority")
    return state


def apply_input(
    state,
    *,
    actor_id,
    spell_id,
    target_id,
    target_cell,
    actual_color_area,
    cast_committed,
    cast_event_id,
):
    """Record one ordinary committed control-book cast or a real wrong input.

    ``actual_color_area`` must come from the live native area registry at the
    accepted target cell, not from the client request. Invalid or rejected
    casts are not inputs and leave the challenge untouched.
    """
    state = _validate_contract(state)
    after = deepcopy(state)
    if state["stage"] != "active":
        return after, None
    if (
        cast_committed is not True
        or cast_event_id is None
        or actor_id != state["owner_id"]
        or target_id != state["owner_id"]
        or type(spell_id) is not int
        or spell_id not in SPELL_INPUTS
        or not isinstance(target_cell, (list, tuple))
        or len(target_cell) != 3
        or any(type(value) is not int for value in target_cell)
    ):
        return after, None
    current = after["expected"][after["index"]]
    command = INPUTS[current["reference"]]
    expected_spell = command["spell"]
    correct = spell_id == expected_spell and actual_color_area == command["area"]
    receipt = dict(
        owner_id=actor_id,
        spell_id=spell_id,
        target_id=target_id,
        target_cell=list(target_cell),
        actual_color_area=actual_color_area,
        expected_state=current["reference"],
        expected_level=current["level"],
        event_id=cast_event_id,
        event_sequence=cast_event_id,
    )
    if not correct:
        receipt["kind"] = "wrong_input"
        after["failures"].append(receipt)
        after["stage"] = "failed"
        after["source_sha256"] = digest(
            {k: v for k, v in after.items() if k != "source_sha256"}
        )
        return after, dict(kind="failed", reason="native_order_or_color_mismatch")
    receipt["kind"] = "accepted_input"
    after["accepted"].append(receipt)
    after["index"] += 1
    if after["index"] == len(after["expected"]):
        after["stage"] = "complete"
        result = dict(
            kind="scenario_completed",
            quest_id=QUEST_ID,
            objective_id=OBJECTIVE_ID,
            evidence="four_native_ordered_dj_inputs",
        )
    else:
        result = dict(kind="input_accepted", index=after["index"])
    after["source_sha256"] = digest(
        {k: v for k, v in after.items() if k != "source_sha256"}
    )
    return after, result


def control_book_source(monster_source=None):
    """Return the exact eight commands from the original level85 consumer."""
    if monster_source is None:
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        monster_source = native_catalog.record(
            DATA_ROOT / "monster-encyclopedia.json", "monsters", str(CONSUMER_ACTOR)
        )
    abilities = (
        monster_source.get("native_abilities")
        if isinstance(monster_source, dict)
        else None
    )
    spells = [row.get("spell_id") for row in abilities or () if isinstance(row, dict)]
    if (
        monster_source.get("ref") != CONSUMER_ACTOR
        or monster_source.get("min_level") != 85
        or monster_source.get("max_level") != 85
        or tuple(spells) != CONTROL_BOOK_SPELLS
    ):
        raise ValueError("DJ control book differs from the actual native 2518 source")
    return tuple(spells)


def start_from_native_state(
    handler,
    effect,
    invocation,
    entry,
    *,
    actor_reference,
    actor_real_level,
    active_roots,
):
    """Attach challenge state at the successful native 1941 state boundary.

    This is called from NativeStateHandler only after the original 304 effect
    has actually registered the state on the controlled player.
    """
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_ledger import RunningState
    from .combat_active_spell import active_spell_id

    fight = handler.fight
    caster = fight.actors.get(invocation.caster_id)
    target = fight.actors.get(invocation.target_id)
    if (
        not callable(actor_reference)
        or not callable(actor_real_level)
        or effect.get("effect_class") != 304
        or invocation.reference != SETUP_STATE_EFFECT
        or active_spell_id(fight) != SETUP_SPELL
        or tuple(active_roots) != (SETUP_ROOT,)
    ):
        return None
    try:
        caster_reference = actor_reference(caster) if caster is not None else None
        owner_level = actor_real_level(target) if target is not None else None
    except Exception:
        return None
    if (
        type(invocation) is not EffectInvocation
        or effect.get("effect_class") != 304
        or invocation.reference != SETUP_STATE_EFFECT
        or active_spell_id(fight) != SETUP_SPELL
        or type(entry) is not RunningState
        or entry.reference != CHALLENGE_STATE
        or entry.target_id != invocation.target_id
        or entry.caster_id != invocation.caster_id
        or target is None
        or target.owner_id is None
        or target.controlled is not True
        or caster is None
        or caster_reference != SETUP_ACTOR
        or caster.team == target.team
        or fight.actors.get(target.id) is not target
        or not any(current is entry for current in target.state_ledger.entries)
    ):
        return None
    controls = [
        dict(reference=row.reference, level=row.level, uid=row.uid)
        for row in target.state_ledger.entries
        if row.reference in INPUTS
    ]
    try:
        contract = start(
            owner_id=target.id,
            owner_account_id=target.owner_id,
            owner_level=owner_level,
            setup_actor_id=caster.id,
            setup_actor_reference=SETUP_ACTOR,
            setup_spell_id=SETUP_SPELL,
            setup_root=SETUP_ROOT,
            setup_state_effect=invocation.reference,
            applied_state_reference=entry.reference,
            challenge_state_uid=entry.uid,
            area_subscription_event=TURN_BOUNDARY_EVENT,
            control_states=controls,
        )
    except ValueError:
        # State1941 is also a valid native state outside this reconstructed
        # challenge. Missing or ambiguous control carriers must not abort the
        # original cast or create a partial challenge.
        return None
    fight.native_dj_dance = contract
    install_control_book(
        fight,
        target.id,
        handler.packets,
        action_id=handler.action_id,
        allocate_uid=handler.allocate_uid,
    )
    return contract


def observe_native_state(
    handler,
    effect,
    invocation,
    entry,
    *,
    actor_reference,
    actor_real_level,
    active_roots,
):
    """Wait for the actual post-setup native turn to produce its order states.

    Original3700 installs1941 before removing the old color states. The next
    original1895/1001 creates the randomized order; observing1941 alone cannot
    freeze a valid fresh sequence.
    """
    from .combat_active_spell import active_spell_id
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_ledger import RunningState

    fight = handler.fight
    if type(invocation) is not EffectInvocation or type(entry) is not RunningState:
        return None
    owner = fight.actors.get(entry.target_id)
    if (
        owner is None
        or owner.controlled is not True
        or owner.owner_id is None
        or not any(row is entry for row in owner.state_ledger.entries)
    ):
        return None
    if (
        effect.get("effect_class") == 304
        and invocation.reference == SETUP_STATE_EFFECT
        and entry.reference == CHALLENGE_STATE
        and active_spell_id(fight) == SETUP_SPELL
        and tuple(active_roots) == (SETUP_ROOT,)
    ):
        caster = fight.actors.get(entry.caster_id)
        if (
            caster is None
            or caster.team == owner.team
            or actor_reference(caster) != SETUP_ACTOR
            or actor_real_level(owner) < 85
        ):
            return None
        pending = dict(
            owner_id=owner.id,
            account_id=owner.owner_id,
            owner_level=actor_real_level(owner),
            caster_id=caster.id,
            state_uid=entry.uid,
            state_reference=entry.reference,
            setup_spell=SETUP_SPELL,
            setup_root=SETUP_ROOT,
            setup_effect=SETUP_STATE_EFFECT,
        )
        pending["source_sha256"] = digest(pending)
        fight.native_dj_setup_pending = pending
        return None
    pending = getattr(fight, "native_dj_setup_pending", None)
    if (
        pending is None
        or entry.reference not in INPUTS
        or getattr(fight, "native_dj_dance", None) is not None
        or active_spell_id(fight) == SETUP_SPELL
    ):
        return None
    if pending.get("source_sha256") != digest(
        {k: v for k, v in pending.items() if k != "source_sha256"}
    ) or (pending.get("owner_id"), pending.get("account_id")) != (
        owner.id,
        owner.owner_id,
    ):
        raise ValueError("DJ delayed setup differs from its accepted source")
    challenge = next(
        (
            row
            for row in owner.state_ledger.entries
            if row.uid == pending["state_uid"]
            and row.reference == CHALLENGE_STATE
            and row.caster_id == pending["caster_id"]
        ),
        None,
    )
    if challenge is None:
        return None
    controls = [
        dict(reference=row.reference, level=row.level, uid=row.uid)
        for row in owner.state_ledger.entries
        if row.reference in INPUTS
    ]
    try:
        contract = start(
            owner_id=owner.id,
            owner_account_id=owner.owner_id,
            owner_level=pending["owner_level"],
            setup_actor_id=pending["caster_id"],
            setup_actor_reference=SETUP_ACTOR,
            setup_spell_id=pending["setup_spell"],
            setup_root=pending["setup_root"],
            setup_state_effect=pending["setup_effect"],
            applied_state_reference=challenge.reference,
            challenge_state_uid=challenge.uid,
            area_subscription_event=TURN_BOUNDARY_EVENT,
            control_states=controls,
        )
    except ValueError:
        return None
    fight.native_dj_dance = contract
    install_control_book(
        fight,
        owner.id,
        handler.packets,
        action_id=handler.action_id,
        allocate_uid=handler.allocate_uid,
    )
    fight.native_dj_setup_pending = None
    return contract


class _NativeDjEvent(dict):
    """A cast witness tied to the preview that accepted its native action."""


def _publish_input(fight, **fields):
    row = _NativeDjEvent(fight._event("native_dj_dance_input", **fields))
    row._origin = ref(fight)
    row._source_digest = digest(row)
    fight.events[-1] = row
    return row


class _NativeDjTerminalEvent(dict):
    """A reviewed challenge result tied to the accepted fight graph."""


def finish_challenge(fight, runtime):
    """Finish after four correct commands or one committed wrong command.

    The client cannot request this result. The only caller is the shared cast
    commit boundary after it has adopted the ordinary spell preview. The
    terminal is a reviewed server reconstruction of the challenge result
    callback; its authority is the signed native casts and their state/area
    checks. A wrong committed input loses without settling the quest.
    """
    state = getattr(fight, "native_dj_dance", None)
    if state is None:
        return False
    state = _validate_contract(state)
    if state["stage"] not in {"complete", "failed"}:
        return False
    from .combat_runtime_messages import RuntimeMessages

    if type(runtime) is not RuntimeMessages or runtime.fight is not fight:
        raise ValueError("DJ terminal requires the actual adopted fight runtime")
    validate_fight(fight)
    if state.get("terminal") is not None:
        return False
    owner = fight.actors.get(state["owner_id"])
    if (
        owner is None
        or owner.owner_id != state["owner_account_id"]
        or owner.controlled is not True
        or fight.phase != "active"
        or fight.winner is not None
    ):
        raise ValueError("DJ challenge terminal lost its original active owner")
    failed = state["stage"] == "failed"
    input_events = [
        event
        for event in fight.events
        if type(event) is _NativeDjEvent
        and event.get("kind") == "native_dj_dance_input"
        and event.get("result", {}).get("kind")
        in ("input_accepted", "scenario_completed", "failed")
    ]
    receipts = [*state["accepted"], *state["failures"]] if failed else state["accepted"]
    if (
        (not failed and len(input_events) != 4)
        or (
            failed
            and (
                len(state["failures"]) != 1
                or not input_events
                or input_events[-1].get("result", {}).get("kind") != "failed"
            )
        )
        or [event["sequence"] for event in input_events]
        != [row["event_sequence"] for row in receipts]
    ):
        raise ValueError("DJ terminal requires its actual committed native inputs")
    winner = owner.team
    if failed:
        setup_actor = fight.actors.get(state["setup_actor_id"])
        if setup_actor is None or setup_actor.team == owner.team:
            raise ValueError("DJ failure lost its original opposing setup actor")
        winner = setup_actor.team
    result = "challenge_failed" if failed else "challenge_completed"
    policy = (
        "reviewed_wrong_native_input_challenge_terminal_v1"
        if failed
        else "reviewed_four_native_inputs_challenge_terminal_v1"
    )
    terminal_sequence = fight.sequence + 1
    terminal = dict(
        policy=policy,
        result=result,
        owner_id=owner.id,
        owner_account_id=owner.owner_id,
        team=winner,
        inputs=[event["sequence"] for event in input_events],
        event_sequence=terminal_sequence,
    )
    terminal["source_sha256"] = digest(
        {key: value for key, value in terminal.items() if key != "source_sha256"}
    )
    state["terminal"] = terminal
    state["source_sha256"] = digest(
        {key: value for key, value in state.items() if key != "source_sha256"}
    )
    terminal_event = _NativeDjTerminalEvent(
        fight._event(
            "challenge_terminal",
            policy=terminal["policy"],
            owner_id=owner.id,
            owner_account_id=owner.owner_id,
            result=result,
            input_sequences=list(terminal["inputs"]),
            terminal_sequence=terminal_sequence,
            source_sha256=terminal["source_sha256"],
        )
    )
    terminal_event._origin = ref(fight)
    terminal_event._source_digest = digest(terminal_event)
    fight.events[-1] = terminal_event
    if terminal_event["sequence"] != terminal_sequence:
        raise ValueError("DJ terminal event sequence changed during adjudication")
    _validate_contract(state)
    fight.phase = "finished"
    fight.winner = winner
    fight._event(
        "finished",
        winner=winner,
        reason="reviewed_native_dj_challenge_terminal",
        challenge_terminal_sequence=terminal_event["sequence"],
    )
    runtime._close_terminal_turn()
    return True


def validate_fight(fight):
    state = getattr(fight, "native_dj_dance", None)
    if state is None:
        return None
    state = _validate_contract(state)
    owner = fight.actors.get(state["owner_id"])
    if (
        owner is None
        or owner.owner_id != state["owner_account_id"]
        or owner.controlled is not True
    ):
        raise ValueError("Native DJ challenge lost its real controlled owner/state")
    events = [
        event
        for event in fight.events
        if isinstance(event, _NativeDjEvent)
        and event.get("kind") == "native_dj_dance_input"
    ]
    receipts = [*state["accepted"], *state["failures"]]
    for index, receipt in enumerate(receipts):
        matches = [
            event for event in events if event.get("action_id") == receipt["event_id"]
        ]
        expected_result = (
            "failed"
            if receipt["kind"] == "wrong_input"
            else "scenario_completed"
            if index == 3
            else "input_accepted"
        )
        if (
            len(matches) != 1
            or not callable(getattr(matches[0], "_origin", None))
            or matches[0]._origin() is not fight
            or matches[0]._source_digest != digest(matches[0])
            or matches[0].get("owner_id") != state["owner_id"]
            or matches[0].get("spell_id") != receipt["spell_id"]
            or matches[0].get("target_id") != state["owner_id"]
            or matches[0].get("target_cell") != receipt["target_cell"]
            or matches[0].get("area_reference") != receipt["actual_color_area"]
            or matches[0].get("result", {}).get("kind") != expected_result
            or matches[0].get("sequence") != receipt["event_sequence"]
        ):
            raise ValueError(
                "Native DJ completion lacks its actual committed cast event"
            )
    terminal = state.get("terminal")
    if terminal is not None:
        terminals = [
            event
            for event in fight.events
            if type(event) is _NativeDjTerminalEvent
            and event.get("kind") == "challenge_terminal"
        ]
        if (
            len(terminals) != 1
            or terminals[0].get("sequence") != terminal["event_sequence"]
            or terminals[0].get("input_sequences") != terminal["inputs"]
            or terminals[0].get("source_sha256") != terminal["source_sha256"]
            or not callable(getattr(terminals[0], "_origin", None))
            or terminals[0]._origin() is not fight
            or terminals[0]._source_digest != digest(terminals[0])
            or fight.phase != "finished"
            or fight.winner != terminal["team"]
        ):
            raise ValueError(
                "Native DJ terminal event differs from its reviewed receipt"
            )
    return state


def validate_checkpoint(state):
    """Validate the JSON sidecar shape; it cannot recreate cast authenticity."""
    if not isinstance(state, dict) or "native_dj_dance" not in state:
        return None
    return _validate_contract(state["native_dj_dance"])


def validate_state(state):
    """Validate the source-bound contract before any checkpoint serialization."""
    return _validate_contract(state)


def adopt_witnesses(destination, candidate, *, previous_sequence):
    """Rebind committed DJ cast witnesses after the fight preview is adopted."""
    if getattr(candidate, "native_dj_dance", None) is None:
        return 0
    if (
        destination is candidate
        or destination.id != candidate.id
        or destination.events is not candidate.events
        or destination.native_dj_dance is not candidate.native_dj_dance
        or type(previous_sequence) is not int
        or previous_sequence < 0
        or previous_sequence > candidate.sequence
    ):
        raise ValueError("DJ witness transfer requires actual owned fight adoption")
    total = 0
    for event in reversed(candidate.events):
        if event.get("sequence", 0) <= previous_sequence:
            break
        if event.get("kind") != "native_dj_dance_input":
            continue
        origin = getattr(event, "_origin", None)
        if (
            type(event) is not _NativeDjEvent
            or not callable(origin)
            or origin() is not candidate
            or getattr(event, "_source_digest", None) != digest(event)
        ):
            raise ValueError("DJ cast witness changed before owned adoption")
        event._origin = ref(destination)
        total += 1
    return total


def install_control_book(fight, actor_id, packets, *, action_id, allocate_uid):
    """Copy the real2518 commands onto the owner after 1941 is present.

    Grant carriers use the standard native temporary-spell book lifecycle;
    the source list is taken from 2518's actual NPC ability declarations.
    """
    contract = _validate_contract(getattr(fight, "native_dj_dance", None))
    actor = fight.actors.get(actor_id)
    if (
        contract.get("owner_id") != actor_id
        or actor is None
        or not any(
            row.reference == CHALLENGE_STATE for row in actor.state_ledger.entries
        )
    ):
        raise ValueError("DJ control book requires the actual owner's 1941 state")
    spells = control_book_source()
    from .combat_spell_grant import NativeSpellGrantHandler
    from .combat_effect_dispatch import EffectInvocation
    from .combat_stat_handler import StatExecutionContext
    from .rii_lesson_spell_catalog import GRANT_EFFECT

    if any(
        spell in getattr(fight, "native_spell_grants", {}).get(actor_id, {})
        for spell in spells
    ):
        raise ValueError("DJ control book is already installed")
    handler = NativeSpellGrantHandler(
        fight,
        packets,
        action_id=action_id,
        allocate_uid=allocate_uid,
        context=lambda *_: StatExecutionContext(True, True, None, True, None),
    )
    invocation = EffectInvocation(GRANT_EFFECT, 1, actor_id, actor_id, actor.position)
    from .combat_retained_runtime import NativeRetainedRuntime, native_retained_metadata
    from .combat_retained_effects import RetainedEffect

    metadata = native_retained_metadata()
    definition = metadata.get("effects", {}).get(str(GRANT_EFFECT))
    if (
        not isinstance(definition, dict)
        or definition.get("effect_class") != 649
        or definition.get("subscription") is not False
    ):
        raise ValueError(
            "DJ control book grant requires the standard native eWn carrier"
        )
    retention = NativeRetainedRuntime(
        fight,
        packets,
        plan={"native_retained_container": {"present": False}},
        state_catalog={},
        action_id=action_id,
        timing=None,
        metadata=metadata,
    )
    installed = []
    for slot, spell in enumerate(spells):
        before = set(fight.owned_stat_effects)
        handler(
            {
                "effect_class": 649,
                "parameters": [
                    2.0,
                    0.0,
                    float(slot),
                    0.0,
                    float(spell),
                    0.0,
                    -1.0,
                    0.0,
                ],
            },
            [],
            invocation,
        )
        added = set(fight.owned_stat_effects) - before
        if len(added) != 1:
            raise ValueError("DJ eWn command grant has no unique native carrier")
        uid = added.pop()
        retention.record(
            RetainedEffect(
                uid,
                actor_id,
                649,
                GRANT_EFFECT,
                manager_id=actor_id,
                definition_type=definition["definition_type"],
                definition_dispellable=definition["definition_dispellable"],
                container_present=False,
            )
        )
        installed.append(uid)
    contract["grant_uids"] = installed
    contract["control_book_spells"] = list(spells)
    contract["source_sha256"] = digest(
        {k: v for k, v in contract.items() if k != "source_sha256"}
    )
    return tuple(installed)


def record_committed_cast(fight, plan, *, action_id):
    """Observe the ordinary committed spell against actual area/state facts."""
    current = getattr(fight, "native_dj_dance", None)
    if current is None:
        return None
    current = _validate_contract(current)
    spell = plan.get("spell_id")
    if spell not in SPELL_INPUTS:
        return None
    if current.get("control_book_spells") != list(CONTROL_BOOK_SPELLS):
        return None
    actor_id = plan.get("actor_id")
    target_id = plan.get("target_id")
    target_cell = plan.get("target")
    if (
        type(action_id) is not int
        or action_id <= 0
        or not isinstance(target_cell, (list, tuple))
        or len(target_cell) != 3
        or any(type(value) is not int for value in target_cell)
    ):
        raise ValueError("DJ input lacks an accepted native cast plan")
    from .combat_effect_area_queries import cell_contains_specific

    actor = fight.actors.get(actor_id)
    actual_carriers = {
        (row.reference, row.uid)
        for row in (() if actor is None else actor.state_ledger.entries)
    }
    if (
        actor is None
        or actor.owner_id != current["owner_account_id"]
        or actor.controlled is not True
        or tuple(actor.position) != tuple(target_cell)
        or (CHALLENGE_STATE, current["challenge_state_uid"]) not in actual_carriers
    ):
        actual_area = None
    else:
        matches = [
            area
            for area in (527, 528, 529, 530)
            if cell_contains_specific(fight, cell=target_cell, reference=area)
        ]
        actual_area = matches[0] if len(matches) == 1 else None
    after, result = apply_input(
        current,
        actor_id=actor_id,
        spell_id=spell,
        target_id=actor_id,
        target_cell=target_cell,
        actual_color_area=actual_area,
        cast_committed=True,
        cast_event_id=action_id,
    )
    if after == current:
        return None
    fight.native_dj_dance = after
    event = _publish_input(
        fight,
        owner_id=actor_id,
        spell_id=spell,
        target_id=target_id,
        target_cell=list(target_cell),
        area_reference=actual_area,
        result=result,
        challenge_index=after["index"],
        stage=after["stage"],
        action_id=action_id,
    )
    if result is not None and result.get("kind") in (
        "input_accepted",
        "scenario_completed",
        "failed",
    ):
        receipts = fight.native_dj_dance[
            "failures" if result["kind"] == "failed" else "accepted"
        ]
        receipts[-1]["event_sequence"] = event["sequence"]
        fight.native_dj_dance["source_sha256"] = digest(
            {
                key: value
                for key, value in fight.native_dj_dance.items()
                if key != "source_sha256"
            }
        )
    return event


def stage(db, store, fight):
    """Settle the reviewed challenge result at the existing terminal boundary."""
    state = getattr(fight, "native_dj_dance", None)
    if (
        state is None
        or state.get("stage") != "complete"
        or state.get("terminal") is None
        or fight.phase != "finished"
    ):
        return {}
    validate_fight(fight)
    owner_id = state["owner_id"]
    account_id = state["owner_account_id"]
    checkpoint = db.execute(
        "SELECT f.status AS fight_status,c.status AS checkpoint_status,c.snapshot "
        "FROM combat_fights f JOIN fight_checkpoints c ON c.fight_id=f.id "
        "WHERE f.id=%s FOR UPDATE OF f,c",
        (fight.id,),
    ).fetchone()
    if (
        checkpoint is None
        or checkpoint["fight_status"] != "finished"
        or checkpoint["checkpoint_status"] not in ("active", "ended")
        or not isinstance(checkpoint["snapshot"], dict)
        or checkpoint["snapshot"].get("phase") != "finished"
        or checkpoint["snapshot"].get("native_dj_dance") != state
    ):
        raise ValueError("DJ completion has no matching accepted terminal checkpoint")
    participant = db.execute(
        "SELECT account_id FROM combat_fight_participants "
        "WHERE fight_id=%s AND character_id=%s",
        (fight.id, owner_id),
    ).fetchone()
    if participant is None or participant["account_id"] != account_id:
        raise ValueError("DJ completion lost its durable original participant")
    character = store.character(account_id, owner_id, db)
    if character is None:
        raise ValueError("DJ completion owner no longer exists")
    from wakfu_server.achievements import mission_toolkit

    identity = digest(
        {
            "challenge": SCHEMA,
            "fight_id": fight.id,
            "owner_id": owner_id,
            "accepted": state["accepted"],
            "source_sha256": state["source_sha256"],
        }
    )
    packets = mission_toolkit.settle(
        db,
        store,
        character,
        f"native-dj-dance:{fight.id}:{identity}",
        "scenario_completed",
        EVENT_REFERENCE,
    )
    return {account_id: packets} if packets else {}
