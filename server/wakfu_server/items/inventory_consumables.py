"""Native flat neutral self-healing foods, persisted with owned consumption.

Equipment/passive healing modifiers and conditional effects are not evaluated.
The caller must reject use during combat; the transaction checks current HP.
"""
from .paths import DATA_ROOT
import json
import struct
from pathlib import Path
from .inventory_items import _lease, decode_use
from . import health, health_store

CATALOG = {
    item["reference"]: item
    for item in json.loads((DATA_ROOT / "item-healing-rules.json").read_text())["items"]
}


def healing_plan(reference):
    item = CATALOG.get(reference)
    if item is None or item["use_action"] or item["use_criteria"]:
        raise ValueError("Unsupported native healing consumable or use criteria")
    heal = []
    emotes = []
    for effect in item["effects"]:
        if effect["effect_criteria"] or effect["target_mask"] != 0:
            raise ValueError("Conditional or targeted item effect is unsupported")
        if effect["generic"] == 25:
            # eXs.fOA: parameter0 quantity, parameter1 healing flags. Native
            # paired values contain a level increment; only flat food is used.
            if effect["parameter_count"] != 2 or effect["params"] != [
                effect["value_at_item_level"],
                0.0,
                2.0,
                0.0,
            ]:
                raise ValueError("Non-flat or modified neutral healing is unsupported")
            heal.append(effect["value_at_item_level"])
        elif effect["generic"] == 550:
            # eXH.C/c: emote ID, forced=true when there is a single parameter.
            if effect["parameter_count"] != 1 or effect["params"] != [20019.0, 0.0]:
                raise ValueError("Unsupported item emote effect")
            emotes.append(dict(emote_id=20019, forced=True, effect_id=effect["id"]))
        else:
            raise ValueError("Additional consumable effect is unsupported")
    if len(heal) != 1 or heal[0] <= 0 or len(emotes) != 1:
        raise ValueError("Unsupported native healing food effect composition")
    return dict(amount=heal[0], emotes=emotes)


def use(store, account_id, generation, character_id, body, *, expected_hp, in_fight):
    """12659 self use: consume one owned item and heal in one transaction.

    No resurrection is implied. Local policy rejects full-health waste and use
    while fighting. Metadata exposes the native emote, separate from HP state.
    """
    request = decode_use(body)
    if type(in_fight) is not bool or in_fight or request["position"] is not None:
        raise ValueError("Healing food requires an outside-combat self use")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        _lease(store, db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        if type(expected_hp) is not int or character["hp"] != expected_hp:
            raise ValueError("Stale consumable health snapshot")
        if not 0 < character["hp"] < character["max_hp"]:
            raise ValueError("Healing food requires a living wounded character")
        # Until equipment effects are authoritative, no item modifier is silently
        # ignored. Build equipment is native protobuf and unrelated to bags.
        from .wire import proto_fields

        if any(
            any(tag == 10 for tag, _ in proto_fields(bytes.fromhex(build["equipment"])))
            for build in character["builds"].values()
        ):
            raise ValueError("Equipped healing modifiers are not implemented")
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=? AND character_id=?",
            (request["uid"], character_id),
        ).fetchone()
        if item is None:
            raise ValueError("Used food unavailable or foreign")
        plan = healing_plan(item["reference"])
        hp = min(character["max_hp"], character["hp"] + plan["amount"])
        health_store.schema(db)
        state = db.execute(
            "SELECT coefficient FROM character_regeneration WHERE character_id=?",
            (character_id,),
        ).fetchone()
        coefficient = state["coefficient"] if state else 0
        now = int(store.clock() * 1000)
        db.execute(
            "UPDATE characters SET hp=? WHERE id=? AND account_id=? AND hp=?",
            (hp, character_id, account_id, expected_hp),
        )
        db.execute(
            "INSERT INTO character_regeneration VALUES(?,?,?,?,?) ON CONFLICT(character_id) DO UPDATE SET initial_hp=excluded.initial_hp,started_ms=excluded.started_ms,coefficient=excluded.coefficient,last_ms=excluded.last_ms",
            (character_id, hp, now, coefficient, now),
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=?", (item["uid"],))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=?",
                (item["uid"],),
            )
        return dict(
            character=store.character(account_id, character_id, db),
            packets=[
                (12470, struct.pack(">qh", item["uid"], -1)),
                (12436, health.packet(character_id, hp, coefficient)),
            ],
            emotes=plan["emotes"],
            healed=hp - expected_hp,
            applied=True,
        )
