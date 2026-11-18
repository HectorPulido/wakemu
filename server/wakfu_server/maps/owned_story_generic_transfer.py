"""Atomic source-qualified GenericActivable travel between owned stories."""

import struct

SCHEMA = "owned-generic-transfer-v1"


def declarations(selected):
    rows = selected.get("generic_transfers", [])
    if not isinstance(rows, list):
        raise ValueError("Owned generic transfers require explicit declarations")
    steps = {step["id"] for step in selected["steps"]}
    seen = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row)
            != {
                "schema",
                "source_id",
                "effect_reference",
                "target_route_key",
                "requires",
                "evidence",
            }
            or row["schema"] != SCHEMA
            or any(
                type(row[key]) is not int or row[key] <= 0
                for key in ("source_id", "effect_reference")
            )
            or not isinstance(row["target_route_key"], str)
            or not row["target_route_key"]
            or not isinstance(row["requires"], list)
            or len(set(row["requires"])) != len(row["requires"])
            or not set(row["requires"]) <= steps
            or not row["evidence"]
            or row["source_id"] in seen
        ):
            raise ValueError("Invalid source-qualified owned generic transfer")
        seen.add(row["source_id"])
    return rows


def selection(configuration, body):
    selected = configuration.get("topology", {}).get("owned_story_controller")
    if selected is None or not selected.get("generic_transfers"):
        return None
    if not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Malformed original owned generic transfer action")
    source, action, parameter = struct.unpack(">qHH", body)
    matches = [row for row in declarations(selected) if row["source_id"] == source]
    if matches and (action != 0 or parameter != 0):
        raise ValueError("Owned generic transfer lost its native action")
    return matches[0] if matches else None


def enter(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    loaded,
    blocked,
    allowed_position_accounts,
    initialize_instance=None,
    resolve_destination=None
):
    from wakfu_server import dungeon_runtime, dungeon_exit, companions
    from wakfu_server import owned_story_controller as controller
    from wakfu_server import owned_story_mechanics as mechanics
    from wakfu_server import owned_story_generic_entry as entry
    from wakfu_server.simple_item_actions import _idle

    if (
        not loaded
        or blocked
        or allowed_position_accounts is None
        or account_id not in allowed_position_accounts
    ):
        raise ValueError("Owned generic transfer requires its loaded position fence")
    with store.connection() as db:
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        actual = store.character(account_id, character["id"], db)
        _idle(db, actual["id"], store.now())
        if actual["instance_id"] <= 0 or any(
            actual[key] != character[key]
            for key in ("map_id", "instance_id", "x", "y", "z")
        ):
            raise ValueError("Owned generic transfer lost its original private pose")
        run, configuration = dungeon_runtime.configuration_for_instance(
            db, actual["instance_id"]
        )
        declared = selection(configuration, body)
        if declared is None:
            raise ValueError("No pinned owned generic transfer at this source")
        selected, completed = controller._scope(db, store, actual)
        if (
            not set(declared["requires"]) <= completed
            or controller.pending_scene(db, store, actual, selected, completed)
            is not None
        ):
            raise ValueError(
                "Owned generic transfer is waiting for its genuine source steps"
            )
        db.execute(
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE", (run["party_id"],)
        )
        members = db.execute(
            "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
            (run["party_id"],),
        ).fetchall()
        if members != [dict(character_id=actual["id"])] or companions.controlled_count(
            db, [actual["id"]]
        ):
            raise ValueError("Owned generic transfer requires its actual solo company")
        target = entry.configuration(db, actual["map_id"], declared["source_id"])
        if target is None or target["route"]["key"] != declared["target_route_key"]:
            raise ValueError(
                "Owned generic transfer target is not independently published"
            )
        source, _, _, effect, destination, _ = entry.validate_route(target["route"])
        native = mechanics.sources(selected)
        if (
            native["programs"].get(str(source["id"]))
            != target["route"]["native_generic_entry"]["program"]
            or effect["action_reference"] != declared["effect_reference"]
            or destination["map_id"] == actual["map_id"]
        ):
            raise ValueError(
                "Owned generic transfer differs from its original native program"
            )
        source_outcome = controller.interact(
            db, store, actual, body, apply_effects=mechanics.executor(selected)
        )
        origin = {key: actual[key] for key in ("map_id", "instance_id", "x", "y", "z")}
        # Normal departure and admission share this transaction. The public
        # source used internally for admission is never exposed or committed.
        dungeon_exit._leave(
            store,
            account_id,
            generation,
            actual["id"],
            in_fight=lambda _identity: False,
            destination_for=lambda *_: {
                key: origin[key] for key in ("map_id", "x", "y", "z")
            },
            _db=db,
        )
        public = store.character(account_id, actual["id"], db)
        result = entry.enter(
            store,
            account_id,
            generation,
            public,
            body,
            loaded=loaded,
            blocked=blocked,
            allowed_position_accounts=allowed_position_accounts,
            initialize_instance=initialize_instance,
            resolve_destination=resolve_destination,
            _db=db,
        )
        db.execute(
            "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s WHERE instance_id=%s AND character_id=%s AND status='pending'",
            (store.now(), origin["instance_id"], actual["id"]),
        )
        db.execute(
            "UPDATE dungeon_transition_outbox SET source_instance_id=%s WHERE instance_id=%s AND character_id=%s AND session_generation=%s AND status='pending'",
            (origin["instance_id"], result["instance_id"], actual["id"], generation),
        )
        result["source_packets"] = source_outcome["packets"]
        return result
