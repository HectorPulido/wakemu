"""Native flat neutral self-healing foods, persisted with owned consumption.

The accepted food effect uses native coefficient mask 2: target healing
resistance applies, source mastery/final bonuses do not. Conditional food
effects remain separate. The transaction checks current HP and ownership.
"""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import json
import random
import struct
from pathlib import Path
from .inventory_items import _lease, decode_use
from . import health, health_store, health_policy

CATALOG = {
    item["reference"]: item
    for item in protocol_catalog.load(DATA_ROOT / "item-healing-rules.json")["items"]
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


def food_healing_amount(character, amount, *, rng=None):
    """Use eXs.fOA -> fat.fSy arithmetic for the accepted neutral food effect.

    healing_plan verifies parameter1=2. Native fat reads mastery/final bonuses
    only for bit1 and healing resistance (characteristic32) for bit2. Evaluate
    the selected equipment/aptitude sheet, never an inactive saved build.
    """
    from wakfu_server.equipment_stats import bonuses
    from wakfu_server.combat.combat_damage_healing import healing_amount

    stats = bonuses(character, include_consumable_buffs=True)["stats"]
    return healing_amount(
        amount,
        1,
        stats,
        stats,
        critical=False,
        single_target=False,
        area=False,
        melee=False,
        ranged=False,
        berserk=False,
        coefficient_mask=2,
        additional_mastery=0,
        additional_final=0,
        rng=random.random if rng is None else rng,
    )


def use(store, account_id, generation, character_id, body, *, expected_hp, in_fight):
    """12659 self use: consume one owned item and heal in one transaction.

    No resurrection is implied. Local policy rejects full-health waste and use
    while fighting. Metadata exposes the native emote, separate from HP state.
    """
    request = decode_use(body)
    if type(in_fight) is not bool or in_fight or request["position"] is not None:
        raise ValueError("Healing food requires an outside-combat self use")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        if type(expected_hp) is not int or character["hp"] != expected_hp:
            raise ValueError("Stale consumable health snapshot")
        if not 0 < character["hp"] < character["max_hp"]:
            raise ValueError("Healing food requires a living wounded character")
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s",
            (request["uid"], character_id),
        ).fetchone()
        if item is None:
            raise ValueError("Used food unavailable or foreign")
        plan = healing_plan(item["reference"])
        amount = food_healing_amount(character, plan["amount"])
        hp = min(character["max_hp"], character["hp"] + amount)
        state = db.execute(
            "SELECT coefficient FROM character_regeneration WHERE character_id=%s",
            (character_id,),
        ).fetchone()
        coefficient = state["coefficient"] if state else 0
        now = store.now()
        hp = health_policy.apply(db, character, hp)
        db.execute(
            "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET initial_hp=excluded.initial_hp,started_at=excluded.started_at,coefficient=excluded.coefficient,last_at=excluded.last_at",
            (character_id, hp, now, coefficient, now),
        )
        if item["quantity"] == 1:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (item["uid"],))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
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
