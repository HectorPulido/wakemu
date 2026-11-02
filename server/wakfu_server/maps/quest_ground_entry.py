"""Qualified native scene trigger aliases to their exact co-located teleporter.

This source-bound reconstruction never searches nearby portals. Verified
dungeon entrance hubs use the server's entrance policy; other destinations
retain native quest criteria. All travel uses the normal owned transition.
"""
import struct
from contextlib import contextmanager
from wakfu_server.achievements import storage, conversation
from wakfu_server.achievements.service import _owner
from wakfu_server import generic_transports, dungeon_criteria, native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.dungeon_achievement_authority import queries_from_snapshot
from wakfu_server.ecology_feedback import information
from wakfu_server.quest_npc import SETTING, publication


def _criterion_evaluator(store, db, character, destination, authority):
    """Use entrance policy only for a hub in the validated dungeon registry.

    Keep all reads in the caller's locked transaction. Other quest transports
    retain their original achievement authority and native criteria.
    """
    from wakfu_server import dungeon_entry_access, dungeon_instances

    dungeon_hub = bool(dungeon_instances.entry_object_ids(destination["map_id"]))

    class TransactionStore:
        @contextmanager
        def connection(self):
            yield db

        def clock(self):
            return store.clock()

    transactional_store = TransactionStore()

    def allowed(criterion, actor, destination_map_id):
        if (
            actor["id"] != character["id"]
            or actor["account_id"] != character["account_id"]
            or destination_map_id != destination["map_id"]
        ):
            raise ValueError(
                "Ground entrance criterion belongs to another owner or destination"
            )
        if dungeon_hub:
            return dungeon_entry_access.evaluate(
                transactional_store,
                criterion,
                character=actor,
                destination_map_id=destination_map_id,
            )
        return dungeon_criteria.evaluate(
            transactional_store,
            criterion,
            character=actor,
            queries=authority,
        )

    return allowed


def handle(store, account_id, generation, character, body, *, blocked):
    if len(body) != 12:
        return None
    identity, action, parameter = struct.unpack(">qHH", body)
    with store.connection() as db:
        published = publication(db)
        if published is None:
            return None
        entry = next(
            (
                e
                for e in published[0].get("ground_entries", [])
                if (e["map_id"], e["object_id"]) == (character["map_id"], identity)
            ),
            None,
        )
        if entry is None:
            return None
        if blocked or (action, parameter) != (entry["action"], entry["parameter"]):
            raise ValueError("Native quest entrance action is unavailable")
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character["id"], selected=True)
        _owner(db, character)
        current = store.character(account_id, character["id"], db)
        if (
            current["instance_id"] != 0
            or [current[k] for k in ("x", "y", "z")] != entry["position"]
        ):
            raise ValueError("Native quest entrance requires its actual walked cell")
        source = native_catalog.record(
            DATA_ROOT / "native-map-objects.json", "$", str(identity)
        )
        if (
            source is None
            or source["map_id"] != current["map_id"]
            or source["type"] != "PositionTrigger"
            or source["payload_hex"] != entry["native_payload_hex"]
            or [int(source[k]) for k in ("x", "y", "z")] != entry["position"]
        ):
            raise ValueError("Quest entrance trigger differs from its native source")
        teleporter = generic_transports.source(
            current["map_id"], entry["teleporter_id"]
        )
        if (
            teleporter is None
            or [int(teleporter[k]) for k in ("x", "y", "z")] != entry["position"]
        ):
            raise ValueError(
                "Quest entrance is not co-located with its native teleporter"
            )
        state = storage.load_locked(db, current["id"])
        authority = queries_from_snapshot(
            {k: state[k] for k in ("running", "completed", "objectives")}
        )
        destination = next(
            d
            for d in teleporter["destinations"]
            if d["destination_id"] == entry["destination_id"]
        )
        criterion_allowed = _criterion_evaluator(
            store, db, current, destination, authority
        )
        if not criterion_allowed(
            destination["criterion"], current, destination["map_id"]
        ):
            return dict(
                packets=[information(entry["incomplete_feedback"])],
                blocked_by_quest=True,
            )
        request = struct.pack(
            ">qiBi", entry["teleporter_id"], entry["destination_id"], 0, 2
        )
        resolved = generic_transports.resolve(
            current,
            request,
            source_allowed=lambda actor, target: actor["id"] == current["id"]
            and target["id"] == teleporter["id"],
            criterion_evaluator=criterion_allowed,
        )
        saved = store.transition_map_in_transaction(
            db, account_id, generation, current["id"], current, resolved["destination"]
        )
        return dict(packets=[], saved=saved, transport=resolved, blocked_by_quest=False)
