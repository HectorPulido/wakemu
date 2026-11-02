"""Original bIg item-to-ground request; unknown native ground rules stay closed."""
from contextlib import ExitStack
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct
from psycopg.errors import LockNotAvailable


@lru_cache(maxsize=1)
def rules():
    return json.loads(
        Path(__file__).with_name("dungeon_optional_ground_rules.json").read_text()
    )["rules"]


def scene_enabled(map_id):
    return any(
        r.get("enabled") is True
        and isinstance(r.get("ground_authority"), dict)
        and r["ground_authority"].get("map_id") == map_id
        for r in rules()
    )


def decode(body):
    if not isinstance(body, bytes) or len(body) != 20:
        raise ValueError("Invalid native bIg ground request")
    action, uid, x, y = struct.unpack(">iqii", body)
    if action <= 0 or uid <= 0:
        raise ValueError("Invalid native bIg source identity")
    return dict(action_id=action, source_uid=uid, x=x, y=y)


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 4:
        return None
    if struct.unpack_from(">i", body)[0] not in {r["action_id"] for r in rules()}:
        return None
    decode(body)
    return "bIg"


def use_criterion(rule):
    original = rule.get("native_use_criterion", rule.get("use_criterion", ""))
    effective = rule.get("use_criterion", "")
    if effective != original and not (
        rule.get("action_id") == 7952
        and rule.get("item_reference") == 11387
        and original == "GetCraftLevel(64) >= 35"
        and effective == ""
        and rule.get("reviewed_server_policy", {}).get("use_criterion_override")
    ):
        raise ValueError("Unreviewed native item USE criterion override")
    return effective


def qualified_rule(action):
    matches = [r for r in rules() if r["action_id"] == action]
    if len(matches) != 1:
        raise ValueError("Unknown or ambiguous native ground action")
    rule = matches[0]
    ground = rule.get("ground_authority")
    if (
        rule.get("enabled") is not True
        or rule.get("native_class") != "bIg"
        or rule.get("native_action_type") != 34
        or not isinstance(ground, dict)
        or not ground.get("source_sha256")
        or not ground.get("targets")
        or not rule.get("qualified_native_release")
        or rule.get("reviewed_server_policy", {}).get("consume_units") != 1
        or rule["reviewed_server_policy"].get("optional_slots_per_instance") != 1
    ):
        raise ValueError("Native optional ground access is not yet qualified")
    use_criterion(rule)
    from wakfu_server import native_catalog

    if native_catalog.release() != rule["qualified_native_release"]:
        raise ValueError("Optional ground source publication changed")
    return rule


def target_for(rule, request, character, topology):
    ground = rule["ground_authority"]
    if (
        ground.get("map_id") != character["map_id"]
        or character["map_id"] != topology["asset_map_id"]
    ):
        raise ValueError("Native ground action uses another map")
    matches = [
        r
        for r in ground["targets"]
        if r["position"][:2] == [request["x"], request["y"]]
    ]
    if len(matches) != 1 or not matches[0].get("source_sha256"):
        raise ValueError("Native target ground is not qualified")
    target = matches[0]
    position = [character[k] for k in ("x", "y", "z")]
    if position not in target.get("approach_cells", ()):
        raise ValueError("Native ground approach is not qualified")
    cells = {tuple(c) for r in topology["rooms"] for c in r["cells"]}
    if tuple(target["position"]) not in cells or tuple(position) not in cells:
        raise ValueError("Native ground action leaves reviewed terrain")
    return target["position"]


def use(
    store,
    groups,
    account_id,
    generation,
    character_id,
    body,
    *,
    in_fight=False,
    positions=None
):
    request = decode(body)
    return activate(
        store,
        groups,
        account_id,
        generation,
        character_id,
        request,
        rule=qualified_rule(request["action_id"]),
        activation_method="native_inventory_action",
        in_fight=in_fight,
        positions=positions,
    )


def step_on_target(
    store,
    groups,
    account_id,
    generation,
    character_id,
    position,
    *,
    in_fight=False,
    positions=None
):
    """Activate only an actual accepted endpoint, never a forged item request."""
    matches = [
        r
        for r in rules()
        if r.get("enabled") is True
        and "step_on_target" in r.get("activation_methods", ())
        and r.get("ground_authority", {}).get("map_id") == position.get("map_id")
        and [position.get(k) for k in ("x", "y", "z")]
        in [t["position"] for t in r.get("ground_authority", {}).get("targets", ())]
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError("Ambiguous reviewed ground step activation")
    rule = qualified_rule(matches[0]["action_id"])
    request = dict(
        action_id=rule["action_id"], source_uid=None, x=position["x"], y=position["y"]
    )
    return activate(
        store,
        groups,
        account_id,
        generation,
        character_id,
        request,
        rule=rule,
        activation_method="step_on_target",
        in_fight=in_fight,
        positions=positions,
    )


def activate(*args, **kwargs):
    try:
        return _activate(*args, **kwargs)
    except LockNotAvailable as error:
        raise ValueError(
            "Dungeon ownership is busy; retry this ground action"
        ) from error


def _activate(
    store,
    groups,
    account_id,
    generation,
    character_id,
    request,
    *,
    rule,
    activation_method,
    in_fight=False,
    positions=None
):
    if activation_method not in rule.get("activation_methods", ()):
        raise ValueError("Ground activation method is not reviewed")
    if in_fight:
        raise ValueError("Leave combat before using this ground item")
    from wakfu_server.inventory_owner import lock_inventory_character
    from wakfu_server.simple_item_actions import _criterion, _equipped, _idle
    from wakfu_server import dungeon_runtime, dungeon_runtime_config
    from wakfu_server.combat_terrain import map_geometry
    from wakfu_server.dungeon_encounters import roster_members
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.haven_bag_furniture_knowledge import _rules
    from psycopg.types.json import Jsonb

    with ExitStack() as ownership, store.connection() as db:
        # Discover the target without acquiring account/session/item locks.
        preflight = db.execute(
            "SELECT c.instance_id,EXISTS(SELECT 1 FROM inventory_items item "
            "WHERE item.character_id=c.id AND item.reference=%s AND item.quantity>0 "
            "AND (%s::bigint IS NULL OR item.uid=%s)) AS owned_seed,"
            "EXISTS(SELECT 1 FROM dungeon_optional_access paid WHERE paid.instance_id=c.instance_id "
            "AND paid.account_id=c.account_id AND paid.character_id=c.id) AS paid_access "
            "FROM characters c JOIN sessions s ON s.account_id=c.account_id "
            "WHERE c.id=%s AND c.account_id=%s AND c.deleted_at IS NULL "
            "AND s.generation=%s AND s.expires_at>%s",
            (
                rule["item_reference"],
                request["source_uid"],
                request["source_uid"],
                character_id,
                account_id,
                generation,
                store.now(),
            ),
        ).fetchone()
        if preflight is None or preflight["instance_id"] <= 0:
            raise ValueError("Optional access requires a live owned dungeon location")
        if not preflight["owned_seed"] and not preflight["paid_access"]:
            raise ValueError("Native optional seed is unavailable")
        instance_id = preflight["instance_id"]
        # Combat rewards hold this run before accounts/items/population/groups.
        run = db.execute(
            "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
            (instance_id,),
        ).fetchone()
        if run is None or run["status"] != "completed":
            raise ValueError("Optional access requires completed main progression")
        if positions is not None:
            # Never wait for a transition already holding the opposite ownership
            # order. The entire transaction rolls back with no seed/group write.
            from wakfu_server.position_buffer import PositionOwnerBusy

            try:
                ownership.enter_context(
                    positions.account_barrier(account_id, blocking=False)
                )
            except PositionOwnerBusy as error:
                raise ValueError(
                    "Dungeon position is busy; retry this ground action"
                ) from error
            positions.flush(account_id=account_id)
        for sql in (
            "SELECT id FROM accounts WHERE id=%s FOR UPDATE NOWAIT",
            "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE NOWAIT",
        ):
            db.execute(sql, (account_id,)).fetchone()
        db.execute(
            "SELECT id FROM characters WHERE id=%s FOR UPDATE NOWAIT", (character_id,)
        ).fetchone()
        lock_inventory_character(store, db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        _idle(db, character_id, store.now())
        instance = db.execute(
            "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE NOWAIT",
            (instance_id,),
        ).fetchone()
        if (
            character.get("instance_id") != instance_id
            or instance is None
            or instance["status"] != "active"
        ):
            raise ValueError(
                "Optional dungeon location changed during ownership acquisition"
            )
        member = db.execute(
            "SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND party_id=%s "
            "AND character_id=%s AND status='active' AND session_generation=%s",
            (instance_id, run["party_id"], character_id, generation),
        ).fetchone()
        if member is None:
            raise ValueError("Optional access requires active dungeon membership")
        _, config = dungeon_runtime.configuration_for_instance(db, instance_id)
        if config["route"]["key"] != rule["route_key"]:
            raise ValueError("Ground item belongs to another dungeon route")
        accesses = (
            config["topology"].get("optional_room_policy", {}).get("optional_rooms", ())
        )
        accesses = [r for r in accesses if r["source_order"] == rule["source_order"]]
        if (
            len(accesses) != 1
            or accesses[0]["access"].get("status") != "qualified_native_ground_item"
            or accesses[0]["access"].get("rule_key") != rule["key"]
        ):
            raise ValueError(
                "Pinned dungeon does not authorize this optional ground action"
            )
        if activation_method == "step_on_target":
            target = [character[k] for k in ("x", "y", "z")]
            if (
                target[:2] != [request["x"], request["y"]]
                or target
                not in [t["position"] for t in rule["ground_authority"]["targets"]]
                or character["map_id"] != rule["ground_authority"]["map_id"]
            ):
                raise ValueError(
                    "Ground step does not match the actual owned soil location"
                )
        else:
            target = target_for(rule, request, character, config["topology"])
        digest = hashlib.sha256(
            json.dumps(rule, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        prior = db.execute(
            "SELECT * FROM dungeon_optional_access WHERE instance_id=%s FOR UPDATE",
            (instance_id,),
        ).fetchone()
        if prior is not None:
            if any(
                prior[k] != v
                for k, v in (
                    ("account_id", account_id),
                    ("character_id", character_id),
                    ("target", target),
                    ("rule_sha256", digest),
                    ("catalog_hash", run["catalog_hash"]),
                )
            ) or (
                request["source_uid"] is not None
                and prior["source_uid"] != request["source_uid"]
            ):
                raise ValueError(
                    "Optional slot already belongs to a different access receipt"
                )
            return dict(
                character=character,
                packets=[],
                consumed=0,
                instance_id=instance_id,
                replay=True,
            )
        if activation_method == "step_on_target":
            item = db.execute(
                "SELECT * FROM inventory_items WHERE character_id=%s AND reference=%s AND quantity>0 ORDER BY uid LIMIT 1 FOR UPDATE",
                (character_id, rule["item_reference"]),
            ).fetchone()
        else:
            item = db.execute(
                "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
                (request["source_uid"], character_id),
            ).fetchone()
        if (
            item is None
            or item["reference"] != rule["item_reference"]
            or item["quantity"] < 1
            or _equipped(character, item["uid"])
        ):
            raise ValueError("Native optional seed is unavailable or equipped")
        published = _rules().get(item["reference"], {})
        if (
            published.get("use_action_id") != rule["action_id"]
            or published.get("use_action_class") != "bIg"
        ):
            raise ValueError("Native ground item action catalog changed")
        if not _criterion(
            store, db, account_id, character, use_criterion(rule), character["map_id"]
        ) or not _criterion(
            store,
            db,
            account_id,
            character,
            rule["action_criterion"],
            character["map_id"],
        ):
            raise ValueError("Original ground item USE criterion is not satisfied")
        order = accesses[0]["order"]
        from wakfu_server.dungeon_optional_group import create

        create(
            db,
            groups,
            run,
            config,
            character,
            room_order=order,
            source_order=rule["source_order"],
            anchor=target,
            activation=dict(
                source_uid=item["uid"],
                source_reference=item["reference"],
                action_id=rule["action_id"],
                activation_method=activation_method,
            ),
            rule_sha256=digest,
        )
        if item["quantity"] == 1:
            db.execute(
                "DELETE FROM inventory_items WHERE uid=%s AND character_id=%s",
                (item["uid"], character_id),
            )
        else:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s AND character_id=%s",
                (item["uid"], character_id),
            )
        return dict(
            character=store.character(account_id, character_id, db),
            packets=[(12470, struct.pack(">qh", item["uid"], -1))],
            consumed=1,
            instance_id=instance_id,
            replay=False,
        )
