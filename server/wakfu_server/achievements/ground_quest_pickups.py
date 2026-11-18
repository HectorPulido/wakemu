"""Authenticated, source-qualified quest pickups with owned durable receipts.

Profiles connect typed native deterministic loot to its authored quest objective.
The server validates the actual world action, session, position and active quest;
items, objective progress and the receipt commit together. Shared ground objects
remain available to other players. Replays never grant a second item, including
when the first item has subsequently been handed in or removed.
"""

from functools import lru_cache
import json
from pathlib import Path
import struct

from . import mission_progress, mission_dependencies, rewards, storage

PROFILE = Path(__file__).with_name("ground_pickup_profiles") / "astrub-books.json"


def validate(document):
    if (
        type(document) is not dict
        or set(document) != {"schema", "native_revision", "bindings"}
        or document["schema"] != "native-quest-ground-pickups-v1"
        or type(document["native_revision"]) is not str
        or len(document["native_revision"]) != 64
        or any(c not in "0123456789abcdef" for c in document["native_revision"])
        or not isinstance(document["bindings"], list)
        or not document["bindings"]
    ):
        raise ValueError("Invalid native ground pickup profile")
    seen = set()
    positive = (
        "map_id",
        "object_id",
        "descriptor_id",
        "native_action_id",
        "quest_id",
        "objective_id",
        "item_reference",
        "quantity",
        "loot_list_id",
        "loot_entry_id",
        "success_script",
        "unavailable_script",
        "max_distance",
    )
    keys = set(positive) | {
        "object_type",
        "position",
        "native_payload_hex",
        "action",
        "parameter",
        "evidence",
    }
    for row in document["bindings"]:
        if (
            type(row) is not dict
            or set(row) != keys
            or any(
                type(row[k]) is not int or not 0 < row[k] < 2**31 for k in positive
            )
            or any(
                type(row[k]) is not int or not 0 <= row[k] < 65536
                for k in ("action", "parameter")
            )
            or row["object_type"] != "GenericActivableInteractiveElement"
            or type(row["position"]) is not list
            or len(row["position"]) != 3
            or any(
                type(v) is not int or not -(2**31) <= v < 2**31
                for v in row["position"]
            )
            or type(row["evidence"]) is not str
            or not row["evidence"].strip()
            or type(row["native_payload_hex"]) is not str
            or (row["map_id"], row["object_id"]) in seen
        ):
            raise ValueError("Invalid native ground pickup binding")
        try:
            payload = bytes.fromhex(row["native_payload_hex"])
        except ValueError as error:
            raise ValueError("Invalid native ground pickup payload") from error
        if not payload or row["max_distance"] > 2 or row["quantity"] > 32767:
            raise ValueError("Unqualified native ground pickup range or quantity")
        seen.add((row["map_id"], row["object_id"]))
    return document


@lru_cache(maxsize=1)
def profile():
    return validate(json.loads(PROFILE.read_text()))


def recognizes(map_id, body):
    if type(body) is not bytes or len(body) != 12:
        return False
    identity = struct.unpack_from(">q", body)[0]
    return any(
        (r["map_id"], r["object_id"]) == (map_id, identity)
        for r in profile()["bindings"]
    )


def _source(rule):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    original = native_catalog.record(
        DATA_ROOT / "native-map-objects.json", "$", str(rule["object_id"])
    )
    if (
        original is None
        or original.get("map_id") != rule["map_id"]
        or original.get("type") != rule["object_type"]
        or [original.get(k) for k in ("x", "y", "z")] != rule["position"]
        or original.get("payload_hex") != rule["native_payload_hex"]
    ):
        raise ValueError("Ground pickup differs from its native world source")


def interact(store, account_id, generation, location, body, *, loaded, blocked):
    from wakfu_server import world_static
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard
    from wakfu_server.simple_item_actions import _idle
    from .interactive_missions import _visual
    from wakfu_server.items import quest_inventory

    if not loaded or blocked or not recognizes(location["map_id"], body):
        raise ValueError("Ground quest pickup requires its loaded authenticated action")
    identity, action, parameter = struct.unpack(">qHH", body)
    document = profile()
    rule = next(
        r
        for r in document["bindings"]
        if (r["map_id"], r["object_id"]) == (location["map_id"], identity)
    )
    if (action, parameter) != (rule["action"], rule["parameter"]):
        raise ValueError("Ground quest pickup action differs from native descriptor")
    _source(rule)
    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, location)
        _guard(db, location["id"])
        current = store.character(account_id, location["id"], db)
        _idle(db, current["id"], store.now())
        if any(
            current.get(k, 0) != location.get(k, 0)
            for k in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Ground quest pickup requires the current owned position")
        actual = world_static.interaction(current, body)
        x, y, z = rule["position"]
        if (
            actual["type"] != rule["object_type"]
            or [actual[k] for k in ("x", "y", "z")] != rule["position"]
            or abs(current["z"] - z) > 1
            or abs(current["x"] - x) + abs(current["y"] - y) > rule["max_distance"]
            or db.execute(
                "SELECT 1 FROM environment_interaction_tickets WHERE character_id=%s AND state='active'",
                (current["id"],),
            ).fetchone()
        ):
            raise ValueError("Ground quest pickup is unavailable or out of range")
        if rule["item_reference"] not in quest_inventory.REFERENCES:
            raise ValueError(
                "Ground quest pickup requires a native personal QUEST item"
            )
        row = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
            (document["native_revision"], rule["quest_id"]),
        ).fetchone()
        if row is None:
            raise ValueError("Missing source-qualified ground pickup quest")
        definition = row["data"]["native"]
        before = storage.load_locked(db, current["id"])
        key = (
            f"quest-ground-pickup:{rule['quest_id']}:{rule['objective_id']}:{identity}"
        )
        existing = db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (current["id"], key),
        ).fetchone()
        available = (
            rule["quest_id"] in before["running"]
            and rule["objective_id"] not in before["objectives"]
            and not any(
                item["reference"] == rule["item_reference"] and item["quantity"] > 0
                for item in current.get("quest_items", ())
            )
            and existing is None
        )
        if not available:
            return dict(
                applied=False,
                handled=True,
                character=current,
                completed=[],
                packets=_visual(current["id"], identity, rule["unavailable_script"]),
            )
        fact = dict(
            kind="native_quest_ground_pickup_v1",
            map_id=rule["map_id"],
            object_id=identity,
            descriptor_id=rule["descriptor_id"],
            quest_id=rule["quest_id"],
            objective_id=rule["objective_id"],
            item_reference=rule["item_reference"],
            quantity=rule["quantity"],
            loot_list_id=rule["loot_list_id"],
            loot_entry_id=rule["loot_entry_id"],
            revision=document["native_revision"],
        )
        if not storage.record_event(db, current["id"], key, fact):
            raise ValueError("Ground quest pickup receipt changed during settlement")
        packets = rewards.grant(
            db,
            store,
            current,
            dict(aeV=5, ckl=[rule["item_reference"], rule["quantity"]]),
        )
        current = store.character(account_id, current["id"], db)
        now_ms = int(store.now().timestamp() * 1000)
        planned = mission_progress.advance_objective(
            before,
            definition,
            rule["objective_id"],
            character=current,
            store=store,
            now_ms=now_ms,
        )
        result = mission_dependencies.settle(
            db,
            store,
            current,
            before,
            planned,
            {rule["quest_id"]: definition},
            (),
            now_ms=now_ms,
        )
        packets.extend(result["packets"])
        packets.extend(_visual(current["id"], identity, rule["success_script"]))
        return dict(
            applied=True,
            handled=True,
            character=current,
            completed=result["completed"],
            packets=packets,
        )
