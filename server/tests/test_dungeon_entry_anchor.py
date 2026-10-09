"""PostgreSQL checks for pinned room-anchor dungeon entry transitions."""

from dataclasses import asdict
import struct
import unittest

from postgres_case import PostgresCase
import test_dungeon_instances
from wakfu_server import dungeon_transport
from wakfu_server.maps import (
    dungeon_progression,
    dungeon_runtime,
    dungeon_runtime_config,
)
from wakfu_server import dungeon_instances


def native_route_payload(route):
    payload = asdict(route)
    if payload.get("native_template_id") is None:
        payload.pop("native_template_id", None)
    return payload


class DungeonEntryAnchorPostgresTests(PostgresCase):
    player = test_dungeon_instances.DungeonInstanceTests.player
    party = test_dungeon_instances.DungeonInstanceTests.party

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        route = native_route_payload(dungeon_instances.route("jalato_normal"))
        monster = {
            "name": "Synthetic native roster member",
            "ref_id": 1,
            "count": 1,
            "role": "monster",
            "native_min_level": 1,
            "native_max_level": 5,
            "guide_min_level": None,
            "guide_max_level": None,
        }
        plan = {
            "slug": "entry-anchor-fixture",
            "source_url": "https://example.invalid/entry-anchor-fixture",
            "source_sha256": "a" * 64,
            "document_sha256": "d" * 64,
            "definition_id": route["definition_id"],
            "template_id": route["template_id"],
            "asset_map_id": route["start_map_id"],
            "diagnostics": [],
            "roster_ready": True,
            "rooms": [
                {"order": order, "diagnostics": [], "monsters": [monster]}
                for order in (1, 2)
            ],
        }
        self.anchors = {1: (10, -5, 0), 2: (20, -5, 0)}
        topology = {
            "asset_map_id": route["start_map_id"],
            "policy": "local_accessible_anchor_policy",
            "rooms": [
                {"order": order, "anchor": list(anchor), "cells": [list(anchor)]}
                for order, anchor in self.anchors.items()
            ],
            "doors": [],
            "auto_edges": [
                {
                    "source_room": 1,
                    "destination_room": 2,
                    "anchor": list(self.anchors[2]),
                }
            ],
        }
        self.config = dungeon_runtime_config.prepare_configuration(
            plan,
            topology,
            route,
            version=1,
            provenance="isolated PostgreSQL entry-anchor fixture",
        )
        with self.store.connection() as db:
            dungeon_runtime_config.install_configuration(db, self.config)
        self.members, self.party_id = self.party(2)

    def initialize_run(self, db, session):
        config = dungeon_runtime_config.pinned_configuration(
            db, "jalato_normal", session["context_policy_version"]
        )
        plan = dungeon_runtime_config.plan_from_configuration(config)
        return dungeon_progression.initialize_run(
            db, session["instance_id"], session["party_id"], plan
        )

    def enter(self, *, resolver=dungeon_runtime.entry_destination, initialize=True):
        return dungeon_transport.enter(
            self.store,
            self.members[0]["account"],
            self.members[0]["generation"],
            self.members[0]["character"]["id"],
            527,
            struct.pack(">qiBi", 26842, 2504, 0, 2),
            criterion_allowed=lambda _character, _criterion: True,
            source_allowed=lambda _character, _source: True,
            initialize_instance=self.initialize_run if initialize else None,
            resolve_destination=resolver,
        )

    def locations(self):
        ids = [member["character"]["id"] for member in self.members]
        with self.store.connection() as db:
            return db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s) "
                "ORDER BY id",
                (ids,),
            ).fetchall()

    def outbox(self, instance_id):
        with self.store.connection() as db:
            return db.execute(
                "SELECT character_id,transition_revision,destination_map_id,"
                "destination_instance_id,destination_x,destination_y,destination_z,status "
                "FROM dungeon_transition_outbox WHERE instance_id=%s "
                "AND transition_kind='enter' ORDER BY event_id",
                (instance_id,),
            ).fetchall()

    def test_all_members_and_entry_outbox_use_resolved_room_anchor(self):
        result = self.enter()
        instance_id = result["instance_id"]
        anchor = self.anchors[1]
        self.assertEqual(
            {
                "map_id": 1086,
                "x": anchor[0],
                "y": anchor[1],
                "z": anchor[2],
                "direction": 7,
                "instance_id": instance_id,
            },
            result["destination"],
        )
        self.assertEqual(
            {(1086, instance_id, *anchor)},
            {
                (row["map_id"], row["instance_id"], row["x"], row["y"], row["z"])
                for row in self.locations()
            },
        )
        events = self.outbox(instance_id)
        self.assertEqual(2, len(events))
        self.assertEqual(
            {(1086, instance_id, *anchor, "pending")},
            {
                (
                    event["destination_map_id"],
                    event["destination_instance_id"],
                    event["destination_x"],
                    event["destination_y"],
                    event["destination_z"],
                    event["status"],
                )
                for event in events
            },
        )

    def test_entry_replay_does_not_duplicate_outbox_or_reset_room(self):
        first = self.enter()
        instance_id = first["instance_id"]
        replay = self.enter()
        self.assertTrue(replay["reused"])
        self.assertTrue(replay["transition"]["already_entered"])
        self.assertEqual(first["destination"], replay["destination"])
        self.assertEqual(2, len(self.outbox(instance_id)))
        with self.store.connection() as db:
            run = db.execute(
                "SELECT current_room,revision FROM dungeon_room_runs WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()
        self.assertEqual((1, 1), (run["current_room"], run["revision"]))

    def test_reentry_resolves_pinned_current_room_instead_of_resetting_to_room_one(
        self,
    ):
        first = self.enter()
        instance_id = first["instance_id"]
        for member in self.members:
            events = dungeon_instances.pending_transitions(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
            )
            self.assertEqual(1, len(events))
            self.assertTrue(
                dungeon_instances.acknowledge_transition(
                    self.store,
                    member["account"],
                    member["generation"],
                    member["character"]["id"],
                    events[0]["event_id"],
                )
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_room_runs SET current_room=2,revision=revision+1 "
                "WHERE instance_id=%s",
                (instance_id,),
            )
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-245,y=-90,z=2 "
                "WHERE id=ANY(%s)",
                ([member["character"]["id"] for member in self.members],),
            )
        reentry = self.enter()
        anchor = self.anchors[2]
        self.assertTrue(reentry["reused"])
        self.assertEqual(
            {
                "map_id": 1086,
                "x": anchor[0],
                "y": anchor[1],
                "z": anchor[2],
                "direction": 7,
                "instance_id": instance_id,
            },
            reentry["destination"],
        )
        self.assertEqual(
            {(1086, instance_id, *anchor)},
            {
                (row["map_id"], row["instance_id"], row["x"], row["y"], row["z"])
                for row in self.locations()
            },
        )
        with self.store.connection() as db:
            current_room = db.execute(
                "SELECT current_room FROM dungeon_room_runs WHERE instance_id=%s",
                (instance_id,),
            ).fetchone()["current_room"]
        self.assertEqual(2, current_room)
        events = self.outbox(instance_id)
        pending = [event for event in events if event["status"] == "pending"]
        self.assertEqual(2, len(pending))
        self.assertEqual(
            {(1086, instance_id, *anchor)},
            {
                (
                    event["destination_map_id"],
                    event["destination_instance_id"],
                    event["destination_x"],
                    event["destination_y"],
                    event["destination_z"],
                )
                for event in pending
            },
        )

    def test_destination_resolver_failure_rolls_back_new_instance_party_and_outbox(
        self,
    ):
        before = self.locations()

        def fail(_db, _session, _native_destination):
            raise ValueError("pinned room anchor unavailable")

        with self.assertRaisesRegex(ValueError, "pinned room anchor unavailable"):
            self.enter(resolver=fail)
        self.assertEqual(before, self.locations())
        with self.store.connection() as db:
            for table in (
                "dungeon_instances",
                "dungeon_instance_members",
                "dungeon_transition_outbox",
                "dungeon_room_runs",
            ):
                self.assertEqual(
                    0,
                    db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"],
                    table,
                )


if __name__ == "__main__":
    unittest.main()
