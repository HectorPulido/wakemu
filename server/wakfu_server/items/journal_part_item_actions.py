"""Assemble native journal page sets; do not invent quest completion authority."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct

SOURCE_SHA256 = "6b86bacf770090f5f59737e0b4e5466aaf3ef5eb8759c9502012ef258027ece7"
POLICY = "supported_inference_wakemu_native_journal_part"


@lru_cache(maxsize=1)
def descriptors():
    raw = Path(__file__).with_name("native_journal_part_items.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting native journal assembly descriptors")
    return json.loads(raw)


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid journal assembly header")
    action_id, uid = struct.unpack_from(">iq", body)
    if not any(
        row["action_id"] == action_id
        for group in descriptors()["groups"]
        for row in group["items"]
    ):
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid journal assembly grammar")
    return "bIn"


def _available_output(db, document):
    from . import quest_inventory, account_quest_inventory
    from .inventory_move import ACQUISITION_STACKS

    if len(document["products"]) != 1:
        raise ValueError("Invalid qualified journal output")
    reference, quantity = next(iter(document["products"].items()))
    reference = int(reference)
    if (
        reference not in quest_inventory.REFERENCES
        or reference in account_quest_inventory.REFERENCES
        or ACQUISITION_STACKS.get(reference, {}).get("maximum") != 99
        or quantity != 1
    ):
        raise ValueError("The native personal quest journal output is unavailable")


def use(
    store, account_id, generation, character_id, body, *, in_fight, native_map_id=None
):
    if action_class(body) != "bIn":
        raise ValueError("Unsupported journal assembly action")
    action_id = struct.unpack_from(">i", body)[0]
    document, plan = next(
        (group, row)
        for group in descriptors()["groups"]
        for row in group["items"]
        if row["action_id"] == action_id
    )
    from .item_set_assembly import assemble

    return assemble(
        store,
        account_id,
        generation,
        character_id,
        body,
        in_fight=in_fight,
        document=document,
        plan=plan,
        source_sha256=SOURCE_SHA256,
        policy=POLICY,
        authority_table="native_journal_part_item_actions",
        availability=_available_output,
        native_map_id=native_map_id,
    )
