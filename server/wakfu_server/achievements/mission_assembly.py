"""Advance an already-running journal mission from committed assembly facts.

This adapter has no mission activation, combat-event or client-objective API.
The caller owns the complete assembly transaction and account/session fence.
"""
from copy import deepcopy

from . import rewards, storage, wire


DEFINITION = 2907
MINIMUM_LEVEL = 178
OBJECTIVES = {
    "journal_part_1": (5923, 20443),
    "journal_part_2": (5911, 20444),
    "journal_part_3": (5912, 20445),
}
# Original aJP4496, GIVE_PLAYER_XP. Native definition has duration/period0,
# three required objectives and no recurring/repeatable qualification.
REWARD = {"d": 4496, "aeV": 6, "ckk": False, "ckl": [200000000]}


def _qualified_fact(receipt):
    from wakfu_server.journal_part_item_actions import descriptors, POLICY

    fact = receipt["fact"]
    if receipt["policy"] != POLICY or not isinstance(fact, dict):
        raise ValueError("Unqualified journal assembly receipt")
    group = next(
        (
            row
            for row in descriptors()["groups"]
            if row["group_id"] == fact.get("group_id")
        ),
        None,
    )
    if group is None or group["group_id"] not in OBJECTIVES:
        raise ValueError("Unknown journal mission assembly group")
    objective, output = OBJECTIVES[group["group_id"]]
    binding = {"definition_id": DEFINITION, "objective_id": objective}
    if (
        group.get("mission_binding") != binding
        or group["products"] != {str(output): 1}
        or fact.get("kind") != "item_set_assembled"
        or fact.get("native_objective_binding") != binding
        or fact.get("products") != group["products"]
        or fact.get("source_uid") != receipt["source_uid"]
        or type(fact.get("binding_inherited")) is not bool
    ):
        raise ValueError("Conflicting journal mission assembly authority")
    inputs = fact.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != len(group["input_references"]):
        raise ValueError("Incomplete journal mission assembly inputs")
    if any(
        not isinstance(row, dict)
        or set(row) != {"uid", "reference", "quantity"}
        or type(row["uid"]) is not int
        or row["uid"] <= 0
        or type(row["reference"]) is not int
        or type(row["quantity"]) is not int
        or row["quantity"] != 1
        for row in inputs
    ):
        raise ValueError("Malformed journal mission assembly input")
    if len({row["uid"] for row in inputs}) != len(inputs) or sorted(
        row["reference"] for row in inputs
    ) != sorted(group["input_references"]):
        raise ValueError("Journal mission assembly input identity mismatch")
    source = next((row for row in inputs if row["uid"] == receipt["source_uid"]), None)
    if source is None or not any(
        row["item_ref"] == source["reference"]
        and row["action_id"] == fact.get("action_id")
        for row in group["items"]
    ):
        raise ValueError("Journal mission action does not match its source")
    return fact, objective


def settle(db, store, character, receipt_id):
    """Apply one owner-bound real assembly once, inside its inventory transaction.

    Old/nonrunning/low-level receipts cannot activate or backfill a mission.
    Foreign/malformed receipts fail rather than changing another owner's facts.
    """
    from .service import _owner

    _owner(db, character)
    if type(receipt_id) is not int or receipt_id <= 0:
        raise ValueError("Invalid journal mission receipt identity")
    receipt = db.execute(
        "SELECT * FROM item_set_assembly_receipts WHERE id=%s FOR UPDATE",
        (receipt_id,),
    ).fetchone()
    if (
        receipt is None
        or receipt["account_id"] != character["account_id"]
        or receipt["character_id"] != character["id"]
    ):
        raise ValueError("Missing owned journal mission assembly receipt")
    fact, objective = _qualified_fact(receipt)
    noop = dict(
        packets=[], xp_changed=False, new_objectives=[], completed=[], applied=False
    )
    level = fact.get("assembly_real_level")
    if (
        fact.get("mission_running_at_assembly") is not True
        or type(level) is not int
        or level < MINIMUM_LEVEL
        or character["level"] < MINIMUM_LEVEL
    ):
        return noop
    before = storage.load_locked(db, character["id"])
    if DEFINITION not in before["running"] or DEFINITION in before["completed"]:
        return noop
    event_key = f"journal-assembly:{receipt_id}"
    event = dict(receipt_id=receipt_id, assembly=fact)
    if not storage.record_event(db, character["id"], event_key, event):
        return noop
    after = deepcopy(before)
    after["objectives"] = sorted(set(after["objectives"]) | {objective})
    new_objectives = sorted(set(after["objectives"]) - set(before["objectives"]))
    completed = []
    now_ms = int(store.now().timestamp() * 1000)
    # Previously completed objective flags alone are not invented assembly
    # evidence. Every required part must have its own accredited receipt/event.
    observed = set()
    for prior in db.execute(
        "SELECT r.*,e.payload AS event_payload FROM item_set_assembly_receipts r "
        "JOIN character_achievement_events e ON e.character_id=r.character_id "
        "AND e.event_key='journal-assembly:'||r.id::text "
        "WHERE r.character_id=%s AND r.account_id=%s ORDER BY r.id",
        (character["id"], character["account_id"]),
    ):
        prior_fact, prior_objective = _qualified_fact(prior)
        if prior["event_payload"] != dict(receipt_id=prior["id"], assembly=prior_fact):
            raise ValueError(
                "Journal mission receipt conflicts with its accredited event"
            )
        prior_level = prior_fact.get("assembly_real_level")
        if (
            prior_fact.get("mission_running_at_assembly") is True
            and type(prior_level) is int
            and prior_level >= MINIMUM_LEVEL
        ):
            observed.add(prior_objective)
    if {row[0] for row in OBJECTIVES.values()} <= observed and {
        row[0] for row in OBJECTIVES.values()
    } <= set(after["objectives"]):
        after["running"] = [
            identity for identity in after["running"] if identity != DEFINITION
        ]
        after["completed"] = sorted(set(after["completed"]) | {DEFINITION})
        after["tracking"] = [
            identity for identity in after["tracking"] if identity != DEFINITION
        ]
        after["completion_dates"][str(DEFINITION)] = now_ms
        after["recent"] = (after["recent"] + [{"id": DEFINITION, "date_ms": now_ms}])[
            -255:
        ]
        completed = [DEFINITION]
        rewards.validate(REWARD)
        if not storage.claim_reward(
            db, character["id"], DEFINITION, "once", REWARD["d"], REWARD
        ):
            raise ValueError("Journal mission reward already exists before completion")
    storage.store(db, character["id"], after)
    packets = wire.changes(
        character["id"], before, after, new_objectives, completed, now_ms
    )
    if completed:
        packets.extend(rewards.grant(db, store, character, REWARD))
        storage.mark_reward_delivered(
            db, character["id"], DEFINITION, "once", REWARD["d"]
        )
    return dict(
        packets=packets,
        xp_changed=bool(completed),
        new_objectives=new_objectives,
        completed=completed,
        applied=True,
    )
