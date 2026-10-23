"""Bounded captain-map assembly using an explicitly documented Wakemu policy.

The native criterion requires all sixteen maps and its callback says to destroy
maps and add an encyclopedia. One26729 per set is supported inference from the
unique native treasure-map encyclopedia, not a recovered server reward edge.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct


SOURCE_SHA256 = "6240cc1fec285cb885c95bd40a145b93b63bca617c084179b8019ce781d59a18"
POLICY = "supported_inference_wakemu_one_encyclopedia_per_set"


@lru_cache(maxsize=1)
def descriptors():
    raw = Path(__file__).with_name("native_captain_map_items.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting native captain-map descriptors")
    return json.loads(raw)


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid captain-map action header")
    action_id, uid = struct.unpack_from(">iq", body)
    if not any(row["action_id"] == action_id for row in descriptors()["items"]):
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid captain-map action grammar")
    return "bIn"


def _available_output(db):
    """Qualify the real reusable book and its typed acquisition route first."""
    from .haven_bag_furniture_knowledge import _rules
    from .inventory_move import ACQUISITION_STACKS
    from .book_item_actions import SOURCE_SHA256 as BOOK_SHA256
    from wakfu_server.combat_drop_delivery import _template_binding

    active = _rules().get(26729, {})
    stack = ACQUISITION_STACKS.get(26729, {})
    book = db.execute(
        "SELECT * FROM native_book_item_actions WHERE item_ref=26729"
    ).fetchone()
    if (
        active.get("use_action_class") != "bHU"
        or active.get("use_action_id") != 10916
        or stack.get("maximum") != 1
        or _template_binding(26729) != ("BOUND_ON_PICKUP_TO_ACCOUNT", 4, True)
        or book is None
        or book["action_id"] != 10916
        or book["source_sha256"] != BOOK_SHA256
        or book["consumes_source"] is not False
        or book["background_id"] <= 0
    ):
        raise ValueError("The qualified treasure-map encyclopedia is unavailable")


def use(
    store, account_id, generation, character_id, body, *, in_fight, native_map_id=None
):
    """Assemble one complete physical set using the shared atomic engine."""
    if action_class(body) != "bIn":
        raise ValueError("Unsupported captain-map action")
    action_id = struct.unpack_from(">i", body)[0]
    document = descriptors()
    plan = next(row for row in document["items"] if row["action_id"] == action_id)
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
        authority_table="native_captain_map_item_actions",
        availability=lambda db, unused: _available_output(db),
        native_map_id=native_map_id,
    )
