"""Owned native inventory actions. Destruction is supported; use effects are explicit."""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import json
import struct
from pathlib import Path
from .inventory_items import _lease, decode_use
from .wire import proto_fields

RULES = {
    entry["reference"]: entry
    for entry in protocol_catalog.load(DATA_ROOT / "item-action-rules.json")["items"]
}


def destroy(store, account_id, generation, character_id, body):
    """cpM12490 destroys the entire owned stack; cwZ12470 subtracts it."""
    if len(body) != 8:
        raise ValueError("Invalid native destroy request length")
    uid = struct.unpack(">q", body)[0]
    if uid <= 0:
        raise ValueError("Invalid destroyed item UID")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s",
            (uid, character_id),
        ).fetchone()
        if item is None:
            raise ValueError("Destroyed item unavailable or foreign")
        rule = RULES.get(item["reference"])
        if rule is None or rule["destroy_has_criteria"]:
            raise ValueError(
                "Native destruction criteria are not implemented for this item"
            )
        character = store.character(account_id, character_id, db)
        for build in character["builds"].values():
            for tag, value in proto_fields(bytes.fromhex(build["equipment"])):
                if tag == 10 and dict(proto_fields(value)).get(8) == uid:
                    raise ValueError(
                        "Desequip the selected owned unit before destruction"
                    )
        db.execute(
            "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
            (uid, character_id),
        )
        return dict(
            character=store.character(account_id, character_id, db),
            packets=[(12470, struct.pack(">qh", uid, -item["quantity"]))],
            applied=True,
        )


def use_request(store, account_id, generation, character_id, body):
    """Return verified native use metadata without inventing item effects."""
    request = decode_use(body)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s",
            (request["uid"], character_id),
        ).fetchone()
        if item is None:
            raise ValueError("Used item unavailable or foreign")
        rule = RULES.get(item["reference"])
        if rule is None:
            raise ValueError("Unknown native item action template")
        return dict(request=request, item=dict(item), rule=rule)
