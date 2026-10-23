"""Atomic inventory use of descriptor-backed native foods and boosts."""
import random
import struct

from .inventory_items import decode_use
from .inventory_owner import lock_item_owner
from .simple_item_actions import _equipped, _idle


def percentage_healing(maximum, percentage, *, rng=None):
    """eYE.a/rJY: Java int multiplication, float division, then UP.bt."""
    from wakfu_server.equipment_damage import _float
    from wakfu_server.combat_resource_loss import stochastic_native_round

    if (
        type(maximum) is not int
        or maximum <= 0
        or type(percentage) is not int
        or percentage <= 0
    ):
        raise ValueError("Invalid native percentage healing")
    product = (maximum * percentage + 2**31) % 2**32 - 2**31
    return stochastic_native_round(
        _float(_float(product) / _float(100)), random.random if rng is None else rng
    )


def use(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    expected_hp,
    in_fight,
    native_map_id=None
):
    """12659 self-use; a failed plan cannot consume the source or grant a buff."""
    from .consumable_catalog import load_plan
    from .consumable_buffs import (
        active_states,
        apply_states,
        retire_states,
        emit_events,
    )
    from .consumable_characteristics import reconcile_health
    from .consumable_criteria import evaluate
    from . import health, health_policy

    request = decode_use(body)
    if type(in_fight) is not bool or in_fight or request["position"] is not None:
        raise ValueError("Utiliza este consumible sobre ti fuera del combate")
    legacy = False
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        owner_id = lock_item_owner(
            store, db, account_id, generation, character_id, (request["uid"],)
        )
        _idle(db, owner_id, store.now())
        item = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (request["uid"], owner_id),
        ).fetchone()
        if item is None:
            raise ValueError("El consumible ya no está disponible")
        plan = load_plan(db, item["reference"])
        if plan is None:
            legacy = True
        else:
            character = store.character(account_id, owner_id, db)
            character["consumable_states"] = active_states(
                store, db, owner_id, generation=generation
            )
            character = reconcile_health(db, character)
            if character["health_dead"] or character["hp"] <= 0:
                raise ValueError("Este consumible requiere un personaje vivo")
            if _equipped(character, item["uid"]):
                raise ValueError("Desequipa el objeto antes de utilizarlo")
            if not evaluate(
                plan.get("criterion", ""), character, native_map_id=native_map_id
            ):
                raise ValueError("No cumples las condiciones del consumible")
            # Validate exact original visual roots before any state or source
            # mutation. World publication may then safely retain their HMIs.
            from .consumable_visual_effects import select as visual_effects

            visual_orders = [
                state.get("metadata", {}).get("native_visual_applied_at_ms", 0)
                for state in character["consumable_states"]
            ]
            if any(
                type(order) is not int or not 0 <= order < 2**63 - 1
                for order in visual_orders
            ):
                raise ValueError("Invalid native consumable visual application order")
            previous_visual_order = max(visual_orders, default=0)
            visual_order = max(int(store.clock() * 1000), previous_visual_order + 1)
            if not 0 <= visual_order < 2**63:
                raise ValueError("Invalid native consumable visual application clock")
            for state in plan["states"]:
                if visual_effects(character, state):
                    # The retained native appearance stack must replay in the
                    # original application order, including same-clock renewals.
                    state["metadata"]["native_visual_applied_at_ms"] = visual_order
            before = dict(character)
            states = active_states(store, db, owner_id, generation=generation)
            before["consumable_states"] = states
            emit_events(
                store,
                db,
                owner_id,
                plan.get("emitted_event_details", ()),
                generation=generation,
            )
            retire_states(
                store,
                db,
                owner_id,
                state_ids=plan.get("remove_states", ()),
            )
            if plan["states"]:
                apply_states(
                    store,
                    db,
                    owner_id,
                    plan["states"],
                    source_item_ref=item["reference"],
                    source_item_uid=item["uid"],
                    generation=generation,
                )
            if plan.get("reduce_states"):
                from .consumable_state_reduction import reduce_states

                reduce_states(
                    store, db, owner_id, plan["reduce_states"], generation=generation
                )
            character = store.character(account_id, owner_id, db)
            character = reconcile_health(db, character)
            healed = 0
            heal = plan.get("heal")
            if heal is not None:
                if (
                    owner_id != character_id
                    or type(expected_hp) is not int
                    or before["hp"] != expected_hp
                ):
                    raise ValueError("Stale consumable health snapshot")
                if not 0 < character["hp"] < character["max_hp"]:
                    raise ValueError("Healing food requires a living wounded character")
                values = heal.get("values")
                if (
                    not isinstance(values, list)
                    or len(values) != 3
                    or values[1:] != [2, 4]
                ):
                    raise ValueError("Unsupported native percentage healing plan")
                from .inventory_consumables import food_healing_amount

                amount = food_healing_amount(
                    character, percentage_healing(character["max_hp"], values[0])
                )
                hp = min(character["max_hp"], character["hp"] + amount)
                healed = hp - character["hp"]
                hp = health_policy.apply(db, character, hp)
                now = store.now()
                db.execute(
                    "UPDATE character_regeneration SET initial_hp=%s,started_at=%s,last_at=%s WHERE character_id=%s",
                    (hp, now, now, owner_id),
                )
            if item["quantity"] == 1:
                db.execute(
                    "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                    (item["uid"], owner_id),
                )
            else:
                db.execute(
                    "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                    (item["uid"], owner_id),
                )
            saved = store.character(account_id, owner_id, db)
            coefficient = db.execute(
                "SELECT coefficient FROM character_regeneration WHERE character_id=%s",
                (owner_id,),
            ).fetchone()
            return dict(
                character=saved,
                previous_character=before,
                packets=[
                    (12470, struct.pack(">qh", item["uid"], -1)),
                    (
                        12436,
                        health.packet(
                            owner_id,
                            saved["hp"],
                            coefficient["coefficient"] if coefficient else 0,
                        ),
                    ),
                ],
                emotes=plan.get("emotes", ()),
                healed=healed,
                applied=True,
                native_consumable=True,
            )
    if legacy:
        from .inventory_consumables import use as use_healing

        return use_healing(
            store,
            account_id,
            generation,
            character_id,
            body,
            expected_hp=expected_hp,
            in_fight=in_fight,
        )
