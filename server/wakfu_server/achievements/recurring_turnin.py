"""Explicit reconstructed periodic dialogue deliveries using native journal state.

Callers authenticate and authorize the offered NPC edge; all writes share their
transaction. A fixed native anchor is an explicit reconstruction of the reset
boundary, not a claim about the original server's scheduling.
"""

from . import native_effective_eligibility
import struct
from . import recurring_missions, storage, wire


def _cycle(definition, now_ms, policy):
    return recurring_missions.cycle_index(definition, now_ms, policy=policy)


def _last(db, character_id, quest_id):
    return db.execute(
        "SELECT cycle_index,completed_at_ms FROM character_recurring_mission_cycles "
        "WHERE character_id=%s AND definition_id=%s ORDER BY cycle_index DESC LIMIT 1",
        (character_id, quest_id),
    ).fetchone()


def can_offer(db, character, definition, config, *, now_ms, state=None):
    if character.get("level", 0) < definition["cjP"]:
        return False
    cycle = _cycle(definition, now_ms, config["cycle_policy"])
    previous = _last(db, character["id"], definition["d"])
    if previous is not None:
        return previous["cycle_index"] < cycle
    # Never overwrite a preexisting unrelated/unknown completion or running state.
    if state is None:
        row = db.execute(
            "SELECT state FROM character_achievement_progress WHERE character_id=%s",
            (character["id"],),
        ).fetchone()
        if row is None:
            row = db.execute(
                "SELECT snapshot AS state FROM character_achievement_authority WHERE character_id=%s",
                (character["id"],),
            ).fetchone()
        if row is None:
            return False
        state = row["state"]
    return (
        definition["d"] not in state["running"]
        and definition["d"] not in state["completed"]
    )


def accept(db, store, character, definition, config):
    now_ms = int(store.now().timestamp() * 1000)
    before = storage.load_locked(db, character["id"])
    if not can_offer(db, character, definition, config, now_ms=now_ms, state=before):
        raise ValueError("Recurring mission is not available")
    from wakfu_server.dungeon_achievement_authority import queries_from_state
    from wakfu_server import dungeon_criteria

    authority = queries_from_state(before)
    if not dungeon_criteria.evaluate(
        store,
        native_effective_eligibility.criterion(definition),
        character=character,
        queries=authority,
        now_ms=now_ms,
    ):
        raise ValueError("Recurring mission native eligibility not met")
    prior = _last(db, character["id"], definition["d"])
    after, cycle, changed = recurring_missions.begin(
        before,
        definition,
        now_ms=now_ms,
        previous_cycle=None if prior is None else prior["cycle_index"],
        policy=config["cycle_policy"],
    )
    if not changed:
        return []
    fact = {
        "kind": "reconstructed_recurring_dialogue_accept_v1",
        "quest_id": definition["d"],
        "cycle": cycle,
    }
    if not storage.record_event(
        db,
        character["id"],
        f"recurring-dialogue:{definition['d']}:{cycle}:accept",
        fact,
    ):
        raise ValueError("Recurring acceptance receipt lacks state")
    db.execute(
        "INSERT INTO character_recurring_mission_cycles "
        "(character_id,definition_id,cycle_index,accepted_at_ms) VALUES (%s,%s,%s,%s)",
        (character["id"], definition["d"], cycle, now_ms),
    )
    storage.store(db, character["id"], after)
    packets = []
    baseline = before
    if prior is not None:
        packets.append((13205, struct.pack(">qi", character["id"], definition["d"])))
        # Client reset removed both prior completion and active flags. Compare
        # against that reset projection so the new cycle is announced even
        # when the old cycle was still running or had been completed.
        baseline = recurring_missions.reset(before, definition)
    packets.extend(
        wire.changes(
            character["id"],
            baseline,
            after,
            [],
            [],
            now_ms,
            already_reset=(definition["d"],) if prior is not None else (),
        )
    )
    return packets


def deliver(db, store, character, definition, config):
    from .service import drain_rewards
    from wakfu_server.native_generic_rewards import _payment

    now_ms = int(store.now().timestamp() * 1000)
    cycle = _cycle(definition, now_ms, config["cycle_policy"])
    before = storage.load_locked(db, character["id"])
    receipt = _last(db, character["id"], definition["d"])
    if receipt is None or receipt["cycle_index"] != cycle:
        raise ValueError("Recurring mission is not accepted in this cycle")
    if receipt["completed_at_ms"] is not None:
        return {"applied": False, "packets": [], "completed": []}
    after, rewards, changed = recurring_missions.finish(
        before,
        definition,
        config["objective_id"],
        now_ms=now_ms,
        accepted_cycle=cycle,
        policy=config["cycle_policy"],
    )
    if not changed:
        return {"applied": False, "packets": [], "completed": []}
    _, paid_packets, _ = _payment(
        db,
        store,
        character,
        {"group_cod": config["item_reference"], "group_coe": config["item_quantity"]},
    )
    fact = {
        "kind": "reconstructed_recurring_dialogue_delivery_v1",
        "quest_id": definition["d"],
        "objective_id": config["objective_id"],
        "cycle": cycle,
        "item_reference": config["item_reference"],
        "item_quantity": config["item_quantity"],
    }
    if not storage.record_event(
        db,
        character["id"],
        f"recurring-dialogue:{definition['d']}:{cycle}:deliver",
        fact,
    ):
        raise ValueError("Recurring delivery receipt lacks state")
    completed = (
        [definition["d"]]
        if definition["d"] in after["completed"]
        and definition["d"] not in before["completed"]
        else []
    )
    for reward in rewards:
        storage.claim_reward(
            db, character["id"], definition["d"], f"cycle:{cycle}", reward["d"], reward
        )
    storage.store(db, character["id"], after)
    if completed:
        db.execute(
            "UPDATE character_recurring_mission_cycles SET completed_at_ms=%s "
            "WHERE character_id=%s AND definition_id=%s AND cycle_index=%s AND completed_at_ms IS NULL",
            (now_ms, character["id"], definition["d"], cycle),
        )
    packets = paid_packets + wire.changes(
        character["id"], before, after, [config["objective_id"]], completed, now_ms
    )
    packets.extend(drain_rewards(db, store, character))
    return {"applied": True, "packets": packets, "completed": completed}


def activation_dates(db, character_id):
    rows = db.execute(
        "SELECT DISTINCT ON (definition_id) definition_id,accepted_at_ms "
        "FROM character_recurring_mission_cycles WHERE character_id=%s "
        "ORDER BY definition_id,cycle_index DESC",
        (character_id,),
    ).fetchall()
    return {row["definition_id"]: row["accepted_at_ms"] for row in rows}
