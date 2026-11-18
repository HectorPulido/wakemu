"""Source-bound quest supplies through the ordinary native chest occupation.

Outputs are explicitly reviewed associations, never inferred from a chest name.
Successful openings are once per character and original source, across instances.
Held native tools are checked twice and are never charged by this adapter.
"""

from datetime import datetime, timedelta
import hashlib
import json
import struct
import uuid

from psycopg.types.json import Jsonb

SCHEMA = "quest-chest-supply-rule-v1"
TICKET = "quest-chest-supply:occupation"


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def validate(rule):
    positives = (
        "version",
        "map_id",
        "object_id",
        "native_definition",
        "quest_id",
        "objective_id",
        "variable_id",
        "threshold",
        "output_reference",
        "output_quantity",
        "duration_ms",
    )
    if (
        not isinstance(rule, dict)
        or rule.get("schema") != SCHEMA
        or any(type(rule.get(k)) is not int or rule[k] <= 0 for k in positives)
        or rule.get("occupation_type") != 13
        or rule.get("scene_scope") not in ("public", "owned_story")
        or rule["duration_ms"] != 1000
        or rule["output_quantity"] != 1
        or rule.get("source_stage") != f"IsAchievementRunning({rule['quest_id']})"
        or rule.get("output_authority") != "reviewed_native_quest_guide_join"
        or not rule.get("authority")
        or not rule.get("id")
        or not isinstance(rule.get("approaches"), list)
        or not rule["approaches"]
        or any(
            not isinstance(p, list) or len(p) != 3 or any(type(v) is not int for v in p)
            for p in [rule.get("position")] + rule["approaches"]
        )
        or len({tuple(p) for p in rule["approaches"]}) != len(rule["approaches"])
        or any(
            not isinstance(rule.get(k), str)
            or len(rule[k]) != 64
            or any(c not in "0123456789abcdef" for c in rule[k])
            for k in ("catalog_revision", "geometry_sha256", "physical_sha256")
        )
    ):
        raise ValueError("Unqualified reviewed quest chest supply")
    entry = rule.get("owned_entry")
    if rule["scene_scope"] == "owned_story" and (
        not isinstance(entry, dict)
        or set(entry) != {"map_id", "object_id", "destination_id"}
        or any(type(v) is not int or v <= 0 for v in entry.values())
    ):
        raise ValueError("Quest supply lacks its authentic private entry source")
    if rule["scene_scope"] == "public" and entry is not None:
        raise ValueError("Public quest supply cannot claim a private entry")
    prototype = rule.get("native_prototype", {})
    tool, quantity = rule.get("held_tool_reference"), rule.get("held_tool_quantity")
    if (
        type(tool) is not int
        or type(quantity) is not int
        or tool < 0
        or quantity < 0
        or (tool == 0) != (quantity == 0)
        or (
            prototype.get("p"),
            prototype.get("emb"),
            prototype.get("emc"),
            prototype.get("ema"),
        )
        != (rule["native_definition"], tool, quantity, 0)
        or prototype.get("ehu")
        not in (
            "",
            rule["source_stage"],
            f"!IsAchievementObjectiveComplete({rule['objective_id']})",
        )
        or tool == rule["output_reference"]
    ):
        raise ValueError("Quest supply differs from the original held-tool contract")
    if "native_poi" in rule:
        poi, source = rule["native_poi"], rule.get("poi_source", {})
        if (
            not isinstance(poi, dict)
            or poi.get("chj") != rule["object_id"]
            or [poi.get(k) for k in ("bbn", "bbo", "bbl")] != rule["position"]
            or not any(
                row.get("chn") == rule["source_stage"] for row in poi.get("chl", ())
            )
            or source.get("native_entry") != f"poi/{rule['map_id']}/map.poi"
            or source.get("native_reader") != "aIm.b(aoG.dx(bytes),false)"
            or not isinstance(source.get("native_entry_sha256"), str)
            or len(source["native_entry_sha256"]) != 64
        ):
            raise ValueError(
                "Quest supply POI evidence differs from its original source/stage"
            )
    return rule


def _rule(db, map_id, object_id):
    row = db.execute(
        "SELECT rule,sha256,sealed FROM quest_chest_supply_rules "
        "WHERE map_id=%s AND object_id=%s",
        (map_id, object_id),
    ).fetchone()
    if row is None:
        return None
    rule = validate(row["rule"])
    if not row["sealed"] or digest(rule) != row["sha256"]:
        raise ValueError("Quest chest supply publication changed")
    return rule


def definition(store, map_id, object_id):
    with store.connection() as db:
        return _rule(db, map_id, object_id)


def _key(rule):
    return f"quest-chest-supply:{rule['map_id']}:{rule['object_id']}"


def _state(rule, value):
    from wakfu_server.environment_interactions import _packet

    return _packet(
        dict(
            object_id=rule["object_id"],
            state_payload_hex=rule["native_state_payload_hex"],
        ),
        value,
    )


def _source(db, rule):
    from wakfu_server.treasure_chests import _native_authority

    _native_authority(
        rule["catalog_revision"],
        rule["map_id"],
        rule["object_id"],
        rule["payload_hex"],
        rule["native_state_payload_hex"],
        rule["geometry_sha256"],
        tuple(rule["position"]),
    )
    original = db.execute(
        "SELECT * FROM native_loot_chest_prototypes WHERE p=%s",
        (rule["native_definition"],),
    ).fetchone()
    if original is None or dict(original) != rule["native_prototype"]:
        raise ValueError("Quest chest native prototype changed")


def _quantity(db, character, reference):
    from wakfu_server.combat_inventory_date_conditions import (
        complete_owned_item_quantity,
    )

    return complete_owned_item_quantity(character, (reference,))


def _guard(db, store, character, rule, *, is_hero):
    from wakfu_server.achievements import storage
    from wakfu_server.simple_item_actions import _idle

    if (
        is_hero is not False
        or character["map_id"] != rule["map_id"]
        or [character[k] for k in ("x", "y", "z")] not in rule["approaches"]
    ):
        raise ValueError("Quest chest requires its selected main and native approach")
    roster = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s",
        (character["account_id"],),
    ).fetchone()
    if roster is not None and roster["leader_id"] != character["id"]:
        raise ValueError("Quest chest cannot supply an inactive hero")
    _idle(db, character["id"], store.now())
    if rule["scene_scope"] == "public" and character.get("instance_id", 0) != 0:
        raise ValueError("Quest chest requires its original public scene")
    if rule["scene_scope"] == "owned_story":
        from wakfu_server import owned_story_controller

        if not character.get("instance_id", 0):
            raise ValueError("Quest chest requires its genuine private entry")
        selected, _ = owned_story_controller._scope(db, store, character)
        entry = db.execute(
            "SELECT entry_map_id,entry_object_id,entry_destination_id FROM dungeon_instances "
            "WHERE instance_id=%s",
            (character["instance_id"],),
        ).fetchone()
        if (
            selected["map_id"] != rule["map_id"]
            or entry is None
            or {
                "map_id": entry["entry_map_id"],
                "object_id": entry["entry_object_id"],
                "destination_id": entry["entry_destination_id"],
            }
            != rule["owned_entry"]
        ):
            raise ValueError("Quest chest escaped its genuine owned scene membership")
    state = storage.load_locked(db, character["id"])
    if (
        rule["quest_id"] not in state["running"]
        or rule["quest_id"] in state["completed"]
        or rule["objective_id"] in state["objectives"]
    ):
        raise ValueError("Quest chest supply stage is not running")
    if (
        rule["held_tool_reference"]
        and _quantity(db, character, rule["held_tool_reference"])
        < rule["held_tool_quantity"]
    ):
        raise ValueError("Quest chest requires its original held tool")
    if db.execute(
        "SELECT 1 FROM environment_interaction_tickets WHERE character_id=%s "
        "AND state='active'",
        (character["id"],),
    ).fetchone():
        raise ValueError("Another native occupation is active")
    _source(db, rule)


def _counter(db, rule):
    from wakfu_server.achievements import counter_missions, mission_toolkit

    rows = db.execute(
        "SELECT DISTINCT i.profile_id,i.version FROM mission_toolkit_event_index i "
        "JOIN mission_toolkit_active a USING(profile_id,version) "
        "WHERE i.kind='chest_loot' AND i.reference=%s",
        (rule["output_reference"],),
    ).fetchall()
    matching = []
    for row in rows:
        profile = mission_toolkit.get_profile(db, row["profile_id"], row["version"])
        native = mission_toolkit.definitions(db, profile)
        if (
            rule["quest_id"],
            rule["objective_id"],
            rule["variable_id"],
            rule["threshold"],
        ) not in counter_missions.bindings(list(native.values())).get(
            rule["variable_id"], ()
        ):
            continue
        matching.extend(
            b
            for b in profile["bindings"]
            if (
                b.get("quest_id"),
                b.get("objective_id"),
                b.get("variable_id"),
                b.get("event"),
                b.get("count"),
            )
            == (
                rule["quest_id"],
                rule["objective_id"],
                rule["variable_id"],
                dict(kind="chest_loot", reference=rule["output_reference"]),
                "quantity",
            )
            and rule["map_id"] in b.get("maps", ())
        )
    if len(matching) != 1:
        raise ValueError("Quest chest lacks its published physical acquisition counter")


def _ticket(db, character_id, *, lock=True):
    row = db.execute(
        "SELECT payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s" + (" FOR UPDATE" if lock else ""),
        (character_id, TICKET),
    ).fetchone()
    return None if row is None else dict(row["payload"])


def _write_ticket(db, character_id, ticket):
    db.execute(
        "INSERT INTO character_achievement_events(character_id,event_key,signature,payload) "
        "VALUES(%s,%s,%s,%s) ON CONFLICT(character_id,event_key) "
        "DO UPDATE SET signature=EXCLUDED.signature,payload=EXCLUDED.payload",
        (character_id, TICKET, digest(ticket), Jsonb(ticket)),
    )


def require_no_active(db, store, character_id, generation):
    """Keep legacy paid attempts exclusive with the shared quest occupation."""
    ticket = _ticket(db, character_id)
    if (
        ticket is not None
        and ticket["state"] == "active"
        and ticket["generation"] == generation
        and datetime.fromisoformat(ticket["expires_at"]) > store.now()
    ):
        raise ValueError("Another quest chest occupation is active")


def _result(character, rule, *, token=None, state="active", replay=False, packets=()):
    return dict(
        character=character,
        token=token,
        state=state,
        replay=replay,
        personal_state=True,
        location=(character["map_id"], character.get("instance_id", 0)),
        packets=list(packets),
    )


def begin(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    loaded=False,
    blocked=False,
    is_hero=None,
    **unused,
):
    from wakfu_server import paid_containers

    if type(body) is not bytes or len(body) != 12 or not loaded or blocked:
        raise ValueError("Quest chest requires its authenticated loaded action")
    object_id, action, parameter = struct.unpack(">qHH", body)
    if (action, parameter) != (22, 0):
        raise ValueError("Quest chest requires its original action22")
    with store.connection() as db:
        paid_containers._leased_owner(store, db, account_id, generation, character)
        actual = store.character(account_id, character["id"], db)
        if any(
            actual.get(k, 0) != character.get(k, 0)
            for k in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Quest chest actor moved before occupation")
        rule = _rule(db, actual["map_id"], object_id)
        if rule is None:
            raise ValueError("Unknown source-bound quest chest")
        _guard(db, store, actual, rule, is_hero=is_hero)
        _counter(db, rule)
        previous = _ticket(db, actual["id"])
        now = store.now()
        active = (
            previous
            and previous["state"] == "active"
            and previous["generation"] == generation
            and datetime.fromisoformat(previous["expires_at"]) > now
        )
        if active and (
            previous["object_id"],
            previous["map_id"],
            previous["instance_id"],
            previous["position"],
            previous["rule_sha256"],
        ) != (
            object_id,
            actual["map_id"],
            actual.get("instance_id", 0),
            [actual[k] for k in ("x", "y", "z")],
            digest(rule),
        ):
            raise ValueError("Another quest chest occupation is active")
        if db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s "
            "AND event_key=%s",
            (actual["id"], _key(rule)),
        ).fetchone():
            return _result(
                actual, rule, state="completed", replay=True, packets=[_state(rule, 0)]
            )
        if active:
            ticket = previous
        else:
            if db.execute(
                "SELECT 1 FROM paid_container_attempts WHERE character_id=%s "
                "AND state='active' AND expires_at>%s",
                (actual["id"], now),
            ).fetchone():
                raise ValueError("Another paid chest occupation is active")
            ticket = dict(
                token=str(uuid.uuid4()),
                state="active",
                account_id=account_id,
                generation=generation,
                map_id=actual["map_id"],
                object_id=object_id,
                instance_id=actual.get("instance_id", 0),
                position=[actual[k] for k in ("x", "y", "z")],
                rule_sha256=digest(rule),
                due_at=(now + timedelta(milliseconds=rule["duration_ms"])).isoformat(),
                expires_at=(now + timedelta(minutes=2)).isoformat(),
            )
            _write_ticket(db, actual["id"], ticket)
        token = dict(kind="quest_chest_supply", token=ticket["token"])
        start = 13905, struct.pack(
            ">bhqqq",
            1,
            rule["occupation_type"],
            actual["id"],
            object_id,
            rule["duration_ms"],
        )
        return _result(
            actual,
            rule,
            token=token,
            replay=ticket is previous,
            packets=[_state(rule, 3), start],
        )


def handles(token):
    return (
        isinstance(token, dict)
        and set(token) == {"kind", "token"}
        and token["kind"] == "quest_chest_supply"
        and isinstance(token["token"], str)
    )


def finish(
    store,
    account_id,
    generation,
    character,
    token,
    body,
    *,
    loaded=False,
    blocked=False,
    is_hero=None,
):
    from wakfu_server import paid_containers
    from wakfu_server.achievements import mission_toolkit, storage
    from wakfu_server.harvest_inventory import grant_products

    if (
        not handles(token)
        or type(body) is not bytes
        or len(body) != 3
        or not loaded
        or blocked
    ):
        raise ValueError("Missing connection-owned quest chest occupation")
    status, kind = struct.unpack(">bh", body)
    if status not in (2, 3) or kind != 13:
        raise ValueError("Foreign native quest chest occupation result")
    with store.connection() as db:
        paid_containers._leased_owner(store, db, account_id, generation, character)
        ticket = _ticket(db, character["id"])
        if ticket is None or (
            ticket["token"],
            ticket["account_id"],
            ticket["generation"],
        ) != (token["token"], account_id, generation):
            raise ValueError("Quest chest occupation belongs to another lease")
        rule = _rule(db, ticket["map_id"], ticket["object_id"])
        if rule is None or digest(rule) != ticket["rule_sha256"]:
            raise ValueError("Quest chest occupation source changed")
        actual = store.character(account_id, character["id"], db)
        if ticket["state"] != "active":
            return _result(
                actual,
                rule,
                state=ticket["state"],
                replay=True,
                packets=[_state(rule, 0 if ticket["state"] == "completed" else 1)],
            )
        if status == 3 or store.now() >= datetime.fromisoformat(ticket["expires_at"]):
            ticket["state"] = "canceled"
            _write_ticket(db, character["id"], ticket)
            return _result(actual, rule, state="canceled", packets=[_state(rule, 1)])
        if store.now() < datetime.fromisoformat(ticket["due_at"]):
            raise ValueError("Quest chest occupation finished too early")
        if (
            actual["map_id"],
            actual.get("instance_id", 0),
            [actual[k] for k in ("x", "y", "z")],
        ) != (ticket["map_id"], ticket["instance_id"], ticket["position"]):
            raise ValueError("Quest chest actor moved during occupation")
        _guard(db, store, actual, rule, is_hero=is_hero)
        _counter(db, rule)
        payload = dict(
            rule_sha256=digest(rule),
            object_id=rule["object_id"],
            map_id=rule["map_id"],
            item_reference=rule["output_reference"],
            quantity=rule["output_quantity"],
            session_generation=generation,
        )
        fresh = storage.record_event(db, actual["id"], _key(rule), payload)
        packets = []
        if fresh:
            granted = grant_products(
                db, actual, {rule["output_reference"]: rule["output_quantity"]}
            )
            packets.extend(granted["packets"])
            actual = store.character(account_id, character["id"], db)
            packets.extend(
                mission_toolkit.settle(
                    db,
                    store,
                    actual,
                    _key(rule),
                    "chest_loot",
                    rule["output_reference"],
                    rule["output_quantity"],
                )
            )
        ticket["state"] = "completed"
        _write_ticket(db, actual["id"], ticket)
        actual = store.character(account_id, character["id"], db)
        packets.append(_state(rule, 0))
        return _result(
            actual, rule, state="completed", replay=not fresh, packets=packets
        )


def cancel(store, account_id, generation, character, token):
    return finish(
        store,
        account_id,
        generation,
        character,
        token,
        struct.pack(">bh", 3, 13),
        loaded=True,
    )


def snapshots(store, account_id, map_id, *, character_id):
    with store.connection() as db:
        owner = db.execute(
            "SELECT c.map_id,c.instance_id,s.generation FROM characters c "
            "LEFT JOIN sessions s ON s.account_id=c.account_id AND s.character_id=c.id "
            "AND s.expires_at>%s WHERE c.account_id=%s AND c.id=%s",
            (store.now(), account_id, character_id),
        ).fetchone()
        if owner is None or owner["map_id"] != map_id:
            return ()
        rows = db.execute(
            "SELECT object_id FROM quest_chest_supply_rules WHERE map_id=%s "
            "AND sealed ORDER BY object_id",
            (map_id,),
        ).fetchall()
        if not rows:
            return ()
        rules = [_rule(db, map_id, r["object_id"]) for r in rows]
        claimed = {
            r["event_key"]
            for r in db.execute(
                "SELECT event_key FROM character_achievement_events WHERE character_id=%s "
                "AND event_key=ANY(%s)",
                (character_id, [_key(rule) for rule in rules]),
            ).fetchall()
        }
        ticket = _ticket(db, character_id, lock=False)
        active = (
            ticket is not None
            and ticket["state"] == "active"
            and ticket["generation"] == owner["generation"]
            and ticket["map_id"] == map_id
            and ticket["instance_id"] == owner["instance_id"]
            and datetime.fromisoformat(ticket["expires_at"]) > store.now()
        )
        return tuple(
            _state(
                rule,
                (
                    0
                    if _key(rule) in claimed
                    else 3
                    if active and ticket["object_id"] == rule["object_id"]
                    else 1
                ),
            )
            for rule in rules
        )
