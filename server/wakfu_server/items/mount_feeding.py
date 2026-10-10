"""Transactional pet/mount feeding domain; dispatcher integration is separate.

The installed native mount catalog supplies allowed meal references, XP per
meal, levels, health and meal interval. Food effect class and heal amount come
from the per-model native export loaded by migration 064. Missing model/item
policy entries fail closed; no food effect is inferred from its name.
"""
from hashlib import sha256
from datetime import datetime, timezone
import math

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from . import mount_feeding_wire


def feed(store, account_id, generation, character_id, body, *, in_fight):
    """Apply one native 12767 request inside one owner-locked transaction.

    The request carries no nonce, so duplicate suppression is necessarily a
    bounded local debounce policy. An identical deliberate request inside
    that configured window is indistinguishable from a transport retry.
    """
    request = mount_feeding_wire.decode_request(body)
    if type(in_fight) is not bool or in_fight:
        raise ValueError("Pet feeding is unavailable during combat")
    if type(account_id) is not int or type(character_id) is not int:
        raise ValueError("Invalid feeding owner")
    if type(generation) is not str or not generation:
        raise ValueError("Invalid feeding lease")
    if request["food_uid"] == request["pet_uid"]:
        raise ValueError("Food and pet must be distinct inventory items")

    request_hash = sha256(body).digest()
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        if db.info.transaction_status != TransactionStatus.INTRANS:
            raise ValueError("Feeding requires the owned transaction")
        active = db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f "
            "ON f.id=p.fight_id WHERE p.account_id=%s AND p.character_id=%s "
            "AND f.status IN ('placement','active') LIMIT 1",
            (account_id, character_id),
        ).fetchone()
        if active is not None:
            raise ValueError("Pet feeding is unavailable during combat")

        # Lock the persistent pet first. A replay must be recognized even if
        # its first successful request consumed/deleted the whole food stack.
        pet_row = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (request["pet_uid"], character_id),
        ).fetchone()
        if pet_row is None:
            raise ValueError("Pet item is unavailable or foreign")
        pet_item = dict(pet_row)
        if pet_item["quantity"] != 1:
            raise ValueError("Pet item must be an unstacked unit")

        mount = db.execute(
            "SELECT m.*,model.reference AS model_reference,model.maximum_health,"
            "model.xp_per_level,model.maximum_level,model.meal_item_refs,"
            "model.xp_per_meal,model.meal_min_interval_seconds "
            "FROM inventory_mounts m JOIN mount_models model USING(model_id) "
            "WHERE m.uid=%s FOR UPDATE OF m",
            (pet_item["uid"],),
        ).fetchone()
        if mount is None or pet_item["reference"] != mount["model_reference"]:
            raise ValueError("Pet item has no matching authoritative mount state")
        now = store.now()
        if now.tzinfo is None:
            raise ValueError("Feeding clock must be timezone-aware")
        now_ms = int(now.timestamp()) * 1000
        if now_ms <= 0:
            raise ValueError("Invalid feeding clock")
        current_revision = mount["revision"]
        previous = db.execute(
            "SELECT * FROM mount_feeding_receipts WHERE pet_uid=%s "
            "AND request_sha256=%s ORDER BY after_revision DESC LIMIT 1",
            (pet_item["uid"], request_hash),
        ).fetchone()
        if (
            previous is not None
            and previous["after_revision"] == current_revision
            and mount["last_meal_date"] == previous["applied_at_ms"]
            and type(previous["replay_window_ms"]) is int
            and 0 <= now_ms - previous["applied_at_ms"] < previous["replay_window_ms"]
        ):
            character = store.character(account_id, character_id, db)
            return dict(
                character=character,
                packets=[],
                applied=False,
                replayed=True,
                receipt=dict(previous),
                xp_delta=previous["xp_delta"],
                health_delta=previous["health_delta"],
            )

        food_row = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (request["food_uid"], character_id),
        ).fetchone()
        if food_row is None:
            raise ValueError("Food item is unavailable or foreign")
        food = dict(food_row)
        if food["quantity"] < request["quantity"]:
            raise ValueError("Requested food quantity exceeds the owned stack")
        effect = db.execute(
            "SELECT * FROM mount_feeding_food_policy WHERE model_id=%s AND item_reference=%s",
            (mount["model_id"], food["reference"]),
        ).fetchone()
        if effect is None:
            raise ValueError("Food reference has no native effect for this mount model")
        if (
            effect["effect_kind"] not in ("xp", "heal")
            or type(effect["version"]) is not int
            or effect["version"] <= 0
            or type(effect["health_per_item"]) is not int
            or type(effect["replay_window_ms"]) is not int
            or not 0 <= effect["replay_window_ms"] <= 10000
            or type(effect["reset_hungry_clock"]) is not bool
            or (effect["effect_kind"] == "xp" and effect["health_per_item"] != 0)
            or (effect["effect_kind"] == "heal" and effect["health_per_item"] <= 0)
        ):
            raise ValueError("Invalid pet food policy")

        from .mount_inventory import daily_limit_enabled

        enforce_daily_limit = daily_limit_enabled(db)
        if mount["sleep_item_ref"] > 0 or mount["sleep_date"] > 0:
            raise ValueError("Feeding a sleeping pet is unsupported")
        if (
            enforce_daily_limit
            and effect["effect_kind"] == "xp"
            and mount["last_meal_date"] > 0
            and datetime.fromtimestamp(
                mount["last_meal_date"] / 1000, timezone.utc
            ).date()
            == now.astimezone(timezone.utc).date()
        ):
            raise ValueError("Pet XP food is limited to once per UTC calendar day")

        before_xp = mount["xp"]
        before_health = mount["health"]
        xp_delta = 0
        health_delta = 0
        after_xp = before_xp
        after_health = before_health
        if effect["effect_kind"] == "xp":
            # Verified fvN.mb clamps to max(0,xp), then min(current,
            # fwr.csW() * fwr.aWa()). This is an exact catalog-derived cap.
            max_xp = mount["xp_per_level"] * mount["maximum_level"]
            if before_xp >= max_xp:
                raise ValueError("Pet is already at maximum XP")
            after_xp = min(
                max_xp, before_xp + mount["xp_per_meal"] * request["quantity"]
            )
            xp_delta = after_xp - before_xp
            if xp_delta <= 0:
                raise ValueError("Pet food has no supported XP effect")
        else:
            heal = effect["health_per_item"]
            if heal <= 0 or before_health >= mount["maximum_health"]:
                raise ValueError("Pet health food has no applicable effect")
            missing = mount["maximum_health"] - before_health
            max_useful_quantity = math.ceil(missing / heal)
            if request["quantity"] > max_useful_quantity:
                raise ValueError(
                    "Requested health-food quantity exceeds missing health"
                )
            after_health = min(
                mount["maximum_health"], before_health + heal * request["quantity"]
            )
            health_delta = after_health - before_health
            if health_delta <= 0:
                raise ValueError("Pet food has no supported health effect")

        after_revision = current_revision + 1
        after_hungry_date = (
            now_ms if effect["reset_hungry_clock"] else mount["last_hungry_date"]
        )
        db.execute(
            "UPDATE inventory_mounts SET xp=%s,health=%s,last_meal_date=%s,"
            "last_hungry_date=%s,revision=%s WHERE uid=%s",
            (
                after_xp,
                after_health,
                now_ms,
                after_hungry_date,
                after_revision,
                pet_item["uid"],
            ),
        )
        after_food_quantity = food["quantity"] - request["quantity"]
        if after_food_quantity == 0:
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (food["uid"],))
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=%s WHERE uid=%s",
                (after_food_quantity, food["uid"]),
            )
        character = store.character(account_id, character_id, db)
        updated_pet = next(
            (
                item
                for item in character["inventory_items"]
                if item["uid"] == pet_item["uid"]
            ),
            None,
        )
        if (
            updated_pet is None
            or updated_pet.get("mount", {}).get("revision") != after_revision
        ):
            raise ValueError("Invalid refreshed pet item")
        packets = mount_feeding_wire.publication_packets(
            food, updated_pet, request["quantity"]
        )
        # Equipped pet panels resolve a separate rich item registry. Physical
        # bag replacement alone leaves that registry's ProtoPet stale.
        from .inventory_items import equipment_inventory

        packets.append(equipment_inventory(character))
        snapshot = dict(
            pet_uid=pet_item["uid"],
            food_uid=food["uid"],
            food_reference=food["reference"],
            quantity=request["quantity"],
            replay_window_ms=effect["replay_window_ms"],
            effect_kind=effect["effect_kind"],
            effect_policy_version=effect["version"],
            before_revision=current_revision,
            after_revision=after_revision,
            before_xp=before_xp,
            after_xp=after_xp,
            before_health=before_health,
            after_health=after_health,
            last_meal_date=now_ms,
            last_hungry_date=after_hungry_date,
            packets=[dict(opcode=op, body=packet.hex()) for op, packet in packets],
        )
        receipt = dict(
            db.execute(
                "INSERT INTO mount_feeding_receipts(account_id,character_id,generation,"
                "pet_uid,food_uid,quantity,replay_window_ms,request_sha256,before_revision,after_revision,"
                "applied_at_ms,effect_kind,xp_delta,health_delta,snapshot) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    account_id,
                    character_id,
                    generation,
                    pet_item["uid"],
                    food["uid"],
                    request["quantity"],
                    effect["replay_window_ms"],
                    request_hash,
                    current_revision,
                    after_revision,
                    now_ms,
                    effect["effect_kind"],
                    xp_delta,
                    health_delta,
                    Jsonb(snapshot),
                ),
            ).fetchone()
        )
        return dict(
            character=character,
            packets=packets,
            applied=True,
            replayed=False,
            receipt=receipt,
            xp_delta=xp_delta,
            health_delta=health_delta,
        )
