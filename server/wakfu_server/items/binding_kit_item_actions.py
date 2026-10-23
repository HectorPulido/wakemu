"""Reviewed reconstruction of the native binding-kit material transaction.

The original source supplies eligibility, scenario and objective identities.
Debit minima, output quantity and retained kit are explicit Wakemu policy.
"""
from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct

SOURCE_SHA256 = "52791b14e46913ebde9267b5b14c4484b8f291827694a99a982d89279ee91af1"


@lru_cache(maxsize=1)
def descriptor():
    raw = Path(__file__).with_name("native_binding_assembly_contract.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("The configured binding assembly source has changed")
    return json.loads(raw)


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native binding assembly header")
    action, uid = struct.unpack_from(">iq", body)
    if action != descriptor()["action_id"]:
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid native binding assembly grammar")
    return "bIn"


def _eligibility(db, store, character, document):
    from wakfu_server.achievements import storage

    state = storage.load_locked(db, character["id"])
    definition, objective = document["definition_id"], document["objective_id"]
    if (
        type(character.get("level")) is not int
        or character["level"] < document["minimum_real_level"]
        or definition not in state["running"]
        or definition in state["completed"]
        or objective in state["objectives"]
        or not set(document["required_objectives"]) <= set(state["objectives"])
    ):
        raise ValueError(
            "The binding mission and its native prerequisites must already be satisfied"
        )
    for ref, quantity in document["materials"].items():
        if (
            sum(
                item["quantity"]
                for item in character["inventory_items"]
                if item["reference"] == int(ref)
            )
            < quantity
        ):
            raise ValueError(
                "Collect every native binding material before using the kit"
            )
    return dict(
        real_level=character["level"],
        definition_id=definition,
        running=True,
        required_objectives=list(document["required_objectives"]),
    )


def _capacity(db, document, character):
    from wakfu_server import account_quest_inventory, quest_inventory
    from wakfu_server.inventory_move import ACQUISITION_STACKS
    from wakfu_server.achievements.rewards import RewardCapacity

    for ref, quantity in document["products"].items():
        reference = int(ref)
        if (
            reference not in quest_inventory.REFERENCES
            or reference in account_quest_inventory.REFERENCES
            or ACQUISITION_STACKS.get(reference, {}).get("maximum")
            != quest_inventory.MAXIMUMS[reference]
        ):
            raise ValueError("The configured assembly quest output is unavailable")
        old = next(
            (
                row["quantity"]
                for row in quest_inventory.load(db, character["id"])
                if row["reference"] == reference
            ),
            0,
        )
        if old + quantity > quest_inventory.MAXIMUMS[reference]:
            raise RewardCapacity("The restored journal quest quantity capacity is full")


def _settle(db, store, character, document, receipt_id, context):
    from wakfu_server.achievements import storage, wire, rewards

    receipt = db.execute(
        "SELECT * FROM scenario_assembly_receipts WHERE id=%s FOR UPDATE", (receipt_id,)
    ).fetchone()
    if (
        receipt is None
        or receipt["account_id"] != character["account_id"]
        or receipt["character_id"] != character["id"]
        or receipt["policy"] != document["policy"]
        or receipt["definition_id"] != document["definition_id"]
        or receipt["objective_id"] != document["objective_id"]
        or receipt["fact"]["eligibility"] != context
        or receipt["fact"]["products"] != document["products"]
    ):
        raise ValueError(
            "The binding mission requires its exact owned assembly receipt"
        )
    before = storage.load_locked(db, character["id"])
    if (
        document["definition_id"] not in before["running"]
        or document["definition_id"] in before["completed"]
        or document["objective_id"] in before["objectives"]
        or not set(document["required_objectives"]) <= set(before["objectives"])
    ):
        raise ValueError("The binding mission changed during its material transaction")
    key = "scenario-assembly:" + str(receipt_id)
    if not storage.record_event(
        db, character["id"], key, dict(receipt_id=receipt_id, assembly=receipt["fact"])
    ):
        raise ValueError(
            "The binding assembly event already exists before its transition"
        )
    after = deepcopy(before)
    identity, objective = document["definition_id"], document["objective_id"]
    after["objectives"] = sorted(set(after["objectives"]) | {objective})
    after["running"] = [value for value in after["running"] if value != identity]
    after["completed"] = sorted(set(after["completed"]) | {identity})
    after["tracking"] = [value for value in after["tracking"] if value != identity]
    now = int(store.now().timestamp() * 1000)
    after["completion_dates"][str(identity)] = now
    after["recent"] = (after["recent"] + [dict(id=identity, date_ms=now)])[-255:]
    reward = document["reward"]
    rewards.validate(reward)
    if not storage.claim_reward(
        db, character["id"], identity, "once", reward["d"], reward
    ):
        raise ValueError("The binding mission reward already exists before completion")
    storage.store(db, character["id"], after)
    packets = wire.changes(character["id"], before, after, [objective], [identity], now)
    packets.extend(rewards.grant(db, store, character, reward))
    storage.mark_reward_delivered(db, character["id"], identity, "once", reward["d"])
    return dict(
        packets=packets,
        xp_changed=True,
        applied=True,
        new_objectives=[objective],
        completed=[identity],
    )


def use(
    store, account_id, generation, character_id, body, *, in_fight, native_map_id=None
):
    if action_class(body) != "bIn":
        raise ValueError("Unsupported configured binding assembly action")
    from wakfu_server.item_set_assembly import assemble

    document = descriptor()
    return assemble(
        store,
        account_id,
        generation,
        character_id,
        body,
        in_fight=in_fight,
        document=document,
        plan=document,
        source_sha256=SOURCE_SHA256,
        policy=document["policy"],
        authority_table="configured_scenario_assembly_actions",
        availability=_capacity,
        material_matrix={int(ref): qty for ref, qty in document["materials"].items()},
        eligibility=_eligibility,
        settlement=_settle,
        native_map_id=native_map_id,
    )
