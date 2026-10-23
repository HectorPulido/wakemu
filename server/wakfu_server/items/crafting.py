"""Lease-scoped ordinary crafting authority.

World lookup is intentionally an input contract: the caller must supply the
currently registered station context, including the native reachability check.
This module owns request validation, durable occupation/version state and the
atomic inventory + profession reward transaction. It does not handle artisan
crafting or native criteria expressions whose semantics are not implemented.
"""
from __future__ import annotations

import hashlib
import re
import struct
import uuid
from collections import defaultdict

from psycopg.types.json import Jsonb

from . import craft_wire
from .craft_planner import plan
from .inventory_items import _lease, insertion


def _positive(value):
    return type(value) is int and value > 0


def craft_duration_ms(raw_duration, batch_count, craft_speed_modifier=0):
    """Return the native adjusted per-recipe timer for a whole batch.

    ``raw_duration`` is scaled by the native CRAFT_SPEED percentage and rounded
    with Java ``Math.round`` semantics. Crafting a batch is serialized by the
    server, so this emulator keeps the occupation open for one adjusted recipe
    duration per requested batch entry. The modifier itself must come from the
    trusted actor/world layer; zero is the neutral fallback.
    """
    if (
        type(raw_duration) is not int
        or raw_duration <= 0
        or type(batch_count) is not int
        or not 1 <= batch_count <= 32767
        or type(craft_speed_modifier) is not int
        or craft_speed_modifier <= -100
    ):
        raise ValueError("Invalid native crafting duration inputs")
    denominator = 100 + craft_speed_modifier
    # Math.round(raw_duration / (1 + modifier/100))
    # == floor((2 * raw_duration * 100 + denominator) / (2 * denominator)).
    per_recipe_ms = (200 * raw_duration + denominator) // (2 * denominator)
    duration_ms = per_recipe_ms * batch_count
    if not 1 <= per_recipe_ms or duration_ms > 2**31 - 1:
        raise ValueError("Adjusted crafting duration is out of range")
    return duration_ms


def _station(catalog, character, table_id, station):
    required = (
        "table_uid",
        "map_id",
        "instance_id",
        "definition_id",
        "profession_id",
        "in_range",
    )
    if not isinstance(station, dict) or any(key not in station for key in required):
        raise ValueError("Missing verified crafting station context")
    if (
        station["table_uid"] != table_id
        or not _positive(station["table_uid"])
        or type(station["map_id"]) is not int
        or station["map_id"] <= 0
        or type(station["instance_id"]) is not int
        or station["instance_id"] < 0
        or not _positive(station["definition_id"])
        or not _positive(station["profession_id"])
        or station["in_range"] is not True
    ):
        raise ValueError("Invalid or unreachable crafting station")
    if (
        station["map_id"] != character["map_id"]
        or station["instance_id"] != character["instance_id"]
    ):
        raise ValueError("Crafting station is in another map instance")
    if station.get("haven_bag") is True:
        # The world adapter resolves a deployed, owned portable table from the
        # fresh bag snapshot; recipe membership remains native catalog policy.
        definition = catalog.definitions.get(station["definition_id"])
        if definition is not None:
            definition = {**definition, "status": "resolved"}
    else:
        definition = catalog.resolve_table(station["map_id"], table_id)
    if (
        not isinstance(definition, dict)
        or definition.get("status") != "resolved"
        or definition.get("definition_id") != station["definition_id"]
        or definition.get("profession_id") != station["profession_id"]
    ):
        raise ValueError("Unknown or mismatched native crafting station")
    return definition


def _recipe(catalog, definition, recipe_id, *, db=None, account_id=None):
    if not catalog.authorize_recipe(definition["definition_id"], recipe_id):
        raise ValueError("Recipe is not allowed at this native station")
    recipe = catalog.recipes.get(recipe_id)
    if not isinstance(recipe, dict) or recipe.get("recipe_id") != recipe_id:
        raise ValueError("Unknown native crafting recipe")
    ordinary = (
        recipe.get("raw_clT") == ""
        and recipe.get("raw_cvc") == ""
        and recipe.get("raw_cvd") is False
        and recipe.get("raw_ckE") == []
    )
    if not ordinary:
        # Native eOh checks the account's eTo learned-recipe collection;
        # eTy.SECRET(0) uses that same fact to authorize discovery. Other
        # expressions and AUTO_CONSUME_ITEM(1) require separate contracts.
        expression = recipe.get("raw_clT")
        known = (
            re.fullmatch(
                r"IsKnownRecipe\(\s*([0-9]+)\s*,\s*([0-9]+)\s*\)",
                expression.strip(),
            )
            if isinstance(expression, str)
            else None
        )
        if (
            known is None
            or recipe.get("raw_cvc") != ""
            or recipe.get("raw_cvd") is not False
            or recipe.get("raw_ckE") != [0]
            or tuple(map(int, known.groups()))
            != (recipe.get("profession_id"), recipe_id)
        ):
            raise ValueError("Unsupported native crafting recipe criterion or flags")
        if db is None or type(account_id) is not int or account_id <= 0:
            raise ValueError("Secret recipe requires authoritative account knowledge")
        profession = db.execute(
            "SELECT actions FROM account_professions WHERE account_id=%s AND profession_id=%s",
            (account_id, recipe["profession_id"]),
        ).fetchone()
        if profession is None or recipe_id not in profession["actions"]:
            raise ValueError("The native secret recipe has not been learned")
    if (
        type(recipe.get("minimum_level")) is not int
        or recipe["minimum_level"] < 0
        or type(recipe.get("profession_id")) is not int
        or recipe["profession_id"] <= 0
        or type(recipe.get("raw_duration")) is not int
        or not 1 <= recipe["raw_duration"] <= 2**31 - 1
    ):
        raise ValueError("Invalid native crafting recipe data")
    return recipe


def _batch(opcode, request, recipe):
    if opcode == 12231:
        if request["recipe_id"] != recipe["recipe_id"]:
            raise ValueError("Mismatched crafting recipe request")
        return request["quantity"], 0
    if opcode != 13382:
        raise ValueError("Unsupported crafting request mode")
    if request["recipe_id"] != recipe["recipe_id"] or request["mode"] != 0:
        raise ValueError("Unsupported native crafting occupation mode")
    required = defaultdict(int)
    for ingredient in recipe["ingredients"]:
        required[ingredient["item_id"]] += ingredient["quantity"]
    supplied = request["components"]
    if not required or not supplied or set(required) != set(supplied):
        raise ValueError("Crafting component list does not match recipe")
    counts = set()
    for item_id, amount in required.items():
        total = supplied[item_id]
        if total % amount:
            raise ValueError("Crafting component quantity is not a whole batch")
        counts.add(total // amount)
    if len(counts) != 1:
        raise ValueError("Crafting component batch counts disagree")
    count = counts.pop()
    if not 1 <= count <= 32767:
        raise ValueError("Invalid crafting batch quantity")
    return count, 0


def _combat_guard(db, character_id):
    if (
        db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
            "WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
            (character_id,),
        ).fetchone()
        is not None
    ):
        raise ValueError("Crafting is unavailable during combat")


def _lock_inventory(db, character_id):
    db.execute(
        "SELECT uid FROM inventory_items WHERE character_id=%s ORDER BY uid FOR UPDATE",
        (character_id,),
    ).fetchall()


def _offered_uids(db, character_id):
    return {
        row["uid"]
        for row in db.execute(
            "SELECT i.uid FROM player_exchange_items i JOIN player_exchange_members m "
            "ON m.exchange_id=i.exchange_id AND m.character_id=i.character_id "
            "JOIN player_exchanges e ON e.id=i.exchange_id "
            "WHERE i.character_id=%s AND e.state IN ('invitation','active')",
            (character_id,),
        )
    }


def _plan(store, db, account_id, character_id, catalog, recipe, batch_count):
    from wakfu_server.inventory_uids import allocate

    _lock_inventory(db, character_id)
    character = store.character(account_id, character_id, db)
    _annotate_product_metadata(db, character["inventory_items"])
    protected = _offered_uids(db, character_id)
    from .craft_upgrade_policy import protected_ingredients

    protected.update(protected_ingredients(db, recipe, character))
    material_plan = plan(
        catalog,
        recipe["recipe_id"],
        batch_count,
        character_id=character_id,
        items=character["inventory_items"],
        containers=character["inventory_containers"],
        builds=character["builds"],
        protected_uids=protected,
    )
    if protected.intersection(row["uid"] for row in material_plan["consumed"]):
        raise ValueError("Crafting cannot consume an offered item")
    from .craft_upgrade_policy import prepare

    preserved = prepare(db, recipe, batch_count, character, material_plan)
    if preserved:
        material_plan = plan(
            catalog,
            recipe["recipe_id"],
            batch_count,
            character_id=character_id,
            items=character["inventory_items"],
            containers=character["inventory_containers"],
            builds=character["builds"],
            protected_uids=protected,
            singleton_products={
                reference: len(states) for reference, states in preserved.items()
            },
        )
    material_plan["preserved_products"] = preserved
    return character, material_plan


def _annotate_product_metadata(db, items):
    """Expose nondefault persisted unit state to the product merge guard.

    Ingredient consumption is unchanged. Metadata equal to a new product's
    native defaults remains compatible; marked or unknown units stay distinct.
    """
    from wakfu_server.exchange_rules import ITEMS
    from wakfu_server.recycling import CATALOG

    by_uid = {item["uid"]: item for item in items}
    if not by_uid:
        return
    for row in db.execute(
        "SELECT uid,bound,template_reference FROM inventory_item_bindings WHERE uid=ANY(%s)",
        (list(by_uid),),
    ):
        item = by_uid[row["uid"]]
        expected = (
            ITEMS.get(str(item["reference"]), {})
            .get("binding_template", {})
            .get("default_eKo")
        )
        if (
            type(expected) is not bool
            or row["template_reference"] != item["reference"]
            or type(row["bound"]) is not bool
            or (row["bound"] or expected) != expected
        ):
            item["native_craft_binding_state"] = dict(row)
    for row in db.execute(
        "SELECT uid,unidentified,socketed FROM inventory_item_recycling_state WHERE uid=ANY(%s)",
        (list(by_uid),),
    ):
        item = by_uid[row["uid"]]
        expected = CATALOG.get(str(item["reference"]), {}).get("template_gjv")
        if (
            type(expected) is not bool
            or row["unidentified"] is not None
            and row["unidentified"] is not expected
            or row["socketed"] not in (None, False)
        ):
            item["native_craft_recycling_state"] = dict(row)
    for row in db.execute(
        "SELECT source_uid,next_use FROM random_item_use_counters WHERE source_uid=ANY(%s)",
        (list(by_uid),),
    ):
        # New craft products must not acquire the resident UID's draw cursor.
        # The planner already keeps metadata-bearing targets separate.
        by_uid[row["source_uid"]]["native_craft_random_state"] = dict(row)


def _request(opcode, body):
    if opcode == 12231:
        return craft_wire.request(opcode, body)
    if opcode == 13382:
        return craft_wire.occupation_request(body)
    raise ValueError("Unsupported crafting request mode")


def begin(
    store,
    catalog,
    account_id,
    generation,
    character_id,
    opcode,
    body,
    *,
    station,
    craft_speed_modifier=0,
    location_resolver=None,
):
    """Validate and persist one occupation; no materials are consumed here.

    ``station`` must be resolved by the trusted world layer for this actor and
    request. A duplicate request while the same occupation is active returns
    its existing token/event. The native protocol contains no client nonce, so
    completed-request deduplication beyond this occupation token is impossible.
    """
    request = _request(opcode, body)
    table_id = request["table_id"]
    now = store.now()
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        if location_resolver is not None:
            character = location_resolver(character)
            from .craft_station import resolve_current

            station = resolve_current(character, table_id)
        definition = _station(catalog, character, table_id, station)
        recipe = _recipe(
            catalog, definition, request["recipe_id"], db=db, account_id=account_id
        )
        batch_count, mode = _batch(opcode, request, recipe)
        from wakfu_server.profession_store import stored_level

        table_level = stored_level(db, account_id, definition["profession_id"])
        recipe_level = stored_level(db, account_id, recipe["profession_id"])
        if table_level is None or recipe_level is None:
            raise ValueError("Required crafting profession is not learned")
        if recipe_level < recipe["minimum_level"]:
            raise ValueError("Crafting profession level is too low")
        _combat_guard(db, character_id)
        active = db.execute(
            "SELECT * FROM craft_occupations WHERE character_id=%s AND state='active' FOR UPDATE",
            (character_id,),
        ).fetchone()
        fingerprint = hashlib.sha256(struct.pack(">i", opcode) + body).digest()
        if active is not None and active["generation"] != generation:
            db.execute(
                "UPDATE craft_occupations SET state='canceled',version=version+1,"
                "finished_at=%s,terminal_reason='lease_replaced' "
                "WHERE token=%s AND state='active'",
                (now, active["token"]),
            )
            active = None
        if active is not None:
            if (
                active["account_id"] == account_id
                and active["generation"] == generation
                and active["request_hash"] == fingerprint
                and active["table_uid"] == table_id
                and active["map_id"] == station["map_id"]
                and active["instance_id"] == station["instance_id"]
                and active["definition_id"] == definition["definition_id"]
                and active["recipe_id"] == recipe["recipe_id"]
                and active["mode"] == mode
                and active["batch_count"] == batch_count
            ):
                return dict(
                    token=active["token"],
                    version=active["version"],
                    duration_ms=active["duration_ms"],
                    duplicate=True,
                    packets=[
                        craft_wire.occupation_started(
                            table_id, recipe["recipe_id"], mode, active["duration_ms"]
                        )
                    ],
                )
            raise ValueError("Character already has an active crafting occupation")

        character, material_plan = _plan(
            store, db, account_id, character_id, catalog, recipe, batch_count
        )
        from wakfu_server.profession_consumable_modifiers import modifiers
        from wakfu_server.native_world_context import is_battleground

        consumable_speed = modifiers(
            store,
            db,
            character_id,
            recipe["profession_id"],
            generation=generation,
            is_battleground=is_battleground(character["map_id"]),
        )["craft_speed"]
        craft_speed_modifier += consumable_speed
        duration_ms = craft_duration_ms(
            recipe["raw_duration"], batch_count, craft_speed_modifier
        )
        token = uuid.uuid4()
        from .craft_upgrade_policy import fingerprint as preservation_fingerprint

        snapshot = dict(
            consumed=material_plan["consumed"],
            preserved_products_sha256=preservation_fingerprint(
                material_plan["preserved_products"]
            ),
            batch_count=batch_count,
            craft_speed_modifier=craft_speed_modifier,
            duration_policy="native_craft_speed_sequential_batch_v1",
            request_opcode=opcode,
            request_body=body.hex(),
        )
        db.execute(
            "INSERT INTO craft_occupations(token,account_id,generation,character_id,"
            "table_uid,map_id,instance_id,definition_id,profession_id,recipe_id,request_opcode,"
            "mode,batch_count,request_hash,inventory_snapshot,duration_ms,started_at,due_at) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                token,
                account_id,
                generation,
                character_id,
                table_id,
                station["map_id"],
                station["instance_id"],
                definition["definition_id"],
                recipe["profession_id"],
                recipe["recipe_id"],
                opcode,
                mode,
                batch_count,
                fingerprint,
                Jsonb(snapshot),
                duration_ms,
                now,
                store.now(duration_ms / 1000),
            ),
        )
        return dict(
            token=token,
            version=1,
            duration_ms=duration_ms,
            duplicate=False,
            packets=[
                craft_wire.occupation_started(
                    table_id, recipe["recipe_id"], mode, duration_ms
                )
            ],
        )


def _occupation(store, db, account_id, generation, character_id, token):
    _lease(store, db, account_id, generation, character_id)
    row = db.execute(
        "SELECT * FROM craft_occupations WHERE token=%s FOR UPDATE", (token,)
    ).fetchone()
    if (
        row is None
        or row["account_id"] != account_id
        or row["character_id"] != character_id
        or (row["state"] != "completed" and row["generation"] != generation)
    ):
        raise ValueError("Crafting occupation does not belong to this lease")
    return dict(row)


def current(store, account_id, generation, character_id):
    """Return the lease's active operation so a dispatcher can restore its token."""
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        row = db.execute(
            "SELECT token,version,table_uid,recipe_id,mode,duration_ms,started_at,due_at "
            "FROM craft_occupations WHERE account_id=%s AND generation=%s "
            "AND character_id=%s AND state='active'",
            (account_id, generation, character_id),
        ).fetchone()
        return None if row is None else dict(row)


def completion_target(store, account_id, generation, character_id):
    """Resolve the active job or latest completed job for tokenless 13429.

    Native completion/cancel messages carry only result and occupation kind,
    not the durable token. A duplicate completion with no newer active job can
    therefore be recognized safely and answered as a replay. Active work is
    always preferred; the protocol cannot distinguish a delayed old request
    from completion of a newer active job.
    """
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        row = db.execute(
            "SELECT token,version,table_uid,recipe_id,mode,duration_ms,started_at,due_at,state "
            "FROM craft_occupations WHERE account_id=%s "
            "AND character_id=%s AND (state='completed' OR "
            "(state='active' AND generation=%s)) "
            "ORDER BY CASE WHEN state='active' THEN 0 ELSE 1 END,started_at DESC LIMIT 1",
            (account_id, character_id, generation),
        ).fetchone()
        return None if row is None else dict(row)


def cancel(store, account_id, generation, character_id, token, version, body):
    """Cancel only the lease's current version; client packet carries no token."""
    craft_wire.cancellation(body)
    if not isinstance(token, uuid.UUID) or type(version) is not int or version <= 0:
        raise ValueError("Invalid crafting occupation version")
    with store.connection() as db:
        row = _occupation(store, db, account_id, generation, character_id, token)
        if row["state"] == "canceled":
            return dict(token=token, version=row["version"], replay=True, packets=[])
        if row["state"] != "active" or row["version"] != version:
            raise ValueError("Stale crafting cancellation")
        _combat_guard(db, character_id)
        db.execute(
            "UPDATE craft_occupations SET state='canceled',version=version+1,finished_at=%s,"
            "terminal_reason='client_cancel' WHERE token=%s AND version=%s AND state='active'",
            (store.now(), token, version),
        )
        return dict(token=token, version=version + 1, replay=False, packets=[])


def _apply_inventory(db, character_id, character, material_plan):
    from wakfu_server.inventory_elements import create, save
    from wakfu_server.inventory_uids import allocate

    original = {row["uid"]: row for row in character["inventory_items"]}
    final = {row["uid"]: row for row in material_plan["final_items"]}
    packets = []
    for uid, item in sorted(original.items()):
        target = final.get(uid)
        if target is None:
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                (uid, character_id),
            )
            packets.append((12470, struct.pack(">qh", uid, -item["quantity"])))
        elif target["quantity"] != item["quantity"]:
            delta = target["quantity"] - item["quantity"]
            db.execute(
                "UPDATE inventory_items SET quantity=%s WHERE uid=%s AND character_id=%s",
                (target["quantity"], uid, character_id),
            )
            packets.append((12470, struct.pack(">qh", uid, delta)))
    for placement in material_plan["product_placements"]:
        if placement["merge_uid"] is not None:
            # The final quantity diff above already publishes the net delta;
            # emitting this placement again would duplicate a merged product.
            continue
        uid = allocate(db)
        item = dict(
            uid=uid,
            character_id=character_id,
            reference=placement["reference"],
            quantity=placement["quantity"],
            container=placement["container"],
            slot=placement["slot"],
        )
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            tuple(
                item[key]
                for key in (
                    "uid",
                    "character_id",
                    "reference",
                    "quantity",
                    "container",
                    "slot",
                )
            ),
        )
        selected = create(item["reference"])
        if selected is not None:
            save(db, uid, selected)
            item.update(selected)
        preservation_index = placement.get("preservation_index")
        if preservation_index is not None:
            preservation = material_plan["preserved_products"][item["reference"]][
                preservation_index
            ]
            from .craft_upgrade_policy import apply

            apply(db, item, preservation)
            from wakfu_server.combat_drop_delivery import _item_proto

            proto = _item_proto(item)
            packets.append(
                (
                    12471,
                    struct.pack(">qhI", item["container"], item["slot"], len(proto))
                    + proto
                    + b"\x01",
                )
            )
        else:
            packets.append(insertion(item, notification=True))
    return packets


def complete(
    store,
    catalog,
    account_id,
    generation,
    character_id,
    token,
    version,
    body,
    *,
    station,
    location_resolver=None,
):
    """Atomically apply one finished native craft occupation."""
    craft_wire.completion_request(body)
    if not isinstance(token, uuid.UUID) or type(version) is not int or version <= 0:
        raise ValueError("Invalid crafting occupation version")
    with store.connection() as db:
        row = _occupation(store, db, account_id, generation, character_id, token)
        if row["state"] == "completed":
            return dict(token=token, version=row["version"], replay=True, packets=[])
        if row["state"] != "active" or row["version"] != version:
            raise ValueError("Stale crafting completion")
        if store.now() < row["due_at"]:
            raise ValueError("Crafting occupation completed before its duration")
        character = store.character(account_id, character_id, db)
        if location_resolver is not None:
            character = location_resolver(character)
            from .craft_station import resolve_current

            station = resolve_current(character, row["table_uid"])
        definition = _station(catalog, character, row["table_uid"], station)
        if (
            definition["definition_id"] != row["definition_id"]
            or station["map_id"] != row["map_id"]
            or station["instance_id"] != row["instance_id"]
        ):
            raise ValueError("Crafting station changed during occupation")
        recipe = _recipe(
            catalog, definition, row["recipe_id"], db=db, account_id=account_id
        )
        from wakfu_server.profession_store import stored_level, award

        level = stored_level(db, account_id, recipe["profession_id"])
        if level is None or level < recipe["minimum_level"]:
            raise ValueError("Crafting profession changed during occupation")
        _combat_guard(db, character_id)
        character, material_plan = _plan(
            store, db, account_id, character_id, catalog, recipe, row["batch_count"]
        )
        if material_plan["consumed"] != row["inventory_snapshot"]["consumed"]:
            raise ValueError("Crafting ingredients changed during occupation")
        from .craft_upgrade_policy import fingerprint as preservation_fingerprint

        expected = row["inventory_snapshot"].get(
            "preserved_products_sha256", preservation_fingerprint({})
        )
        if preservation_fingerprint(material_plan["preserved_products"]) != expected:
            raise ValueError("Crafting precursor state changed during occupation")
        packets = _apply_inventory(db, character_id, character, material_plan)
        from wakfu_server.profession_rewards import base_xp

        # The local recipe policy rewards distinct ingredient slots per
        # produced batch. Quantities within an ingredient slot are material
        # amounts, not extra recipe slots; the requested batch count repeats
        # the same slot-based award once per recipe.
        recipe_slots = len({item["item_id"] for item in recipe["ingredients"]})
        per_recipe_reward = base_xp(db, "recipe", recipe_slots=recipe_slots)
        base_reward = per_recipe_reward * row["batch_count"]
        reward = award(
            store,
            db,
            account_id,
            generation,
            character_id,
            recipe["profession_id"],
            base_xp=base_reward,
            operation=f"craft:{token}",
            action_category="recipe",
            native_map_id=character["map_id"],
        )
        result_packet = craft_wire.result(0, 0, row["batch_count"])
        packets.append(result_packet)
        packets.extend(reward["packets"])
        consumed = material_plan["consumed"]
        products = material_plan["product_placements"]
        db.execute(
            "UPDATE craft_occupations SET state='completed',version=version+1,finished_at=%s,"
            "terminal_reason='completed',consumed_items=%s,products=%s,applied_xp=%s "
            "WHERE token=%s AND version=%s AND state='active'",
            (
                store.now(),
                Jsonb(consumed),
                Jsonb(products),
                reward["xp"],
                token,
                version,
            ),
        )
        from wakfu_server.guild_daily_quests import settle_craft

        packets.extend(
            settle_craft(db, store, character, token, profession_level=level)
        )
        return dict(
            token=token,
            version=version + 1,
            replay=False,
            consumed=consumed,
            products=products,
            applied_xp=reward["xp"],
            packets=packets,
        )
