"""PostgreSQL migration, pinning and room-formation checks for Tofulailler v3."""
import json
import unittest
from pathlib import Path

from postgres_case import PostgresCase
from wakfu_server import combat_group_store, dungeon_physical_doors
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.maps import (
    dungeon_progression,
    dungeon_runtime,
    dungeon_runtime_config,
)
from wakfu_server.maps.dungeon_encounters import enemy_formation, reachable_cells


ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "docs/reports/dungeons/TOFU-RUNTIME-V3.json"


class TofuPhysicalDungeonPostgresTests(PostgresCase):
    from test_dungeon_instances import DungeonInstanceTests as Fixture

    player = Fixture.player
    party = Fixture.party

    def setUp(self):
        super().setUp()
        self.config = json.loads(CONFIG_PATH.read_text(encoding="utf8"))
        self.groups = combat_group_store.PersistentGroups(self.store)
        with self.store.connection() as db:
            self.installed = dungeon_runtime_config.active_configuration(
                db, "native_dungeon_27"
            )
        self.members, self.party_id = self.party(2)
        self.instance_id = self._create_instance()
        self.geometry = map_geometry(1087)

    def _create_instance(self):
        route = self.config["route"]
        with self.store.connection() as db:
            party = db.execute(
                "SELECT leader_id,revision FROM player_parties WHERE id=%s",
                (self.party_id,),
            ).fetchone()
            instance = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,"
                "template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,"
                "start_map_id,context_route_key,context_policy_version) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING instance_id",
                (
                    self.party_id,
                    party["revision"],
                    party["leader_id"],
                    route["template_id"],
                    route["definition_id"],
                    route["entry_map_id"],
                    route["entry_object_id"],
                    route["destination_id"],
                    route["start_map_id"],
                    route["key"],
                    self.installed["version"],
                ),
            ).fetchone()
            instance_id = instance["instance_id"]
            for member in self.members:
                character_id = member["character"]["id"]
                db.execute(
                    "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,"
                    "session_generation,party_revision,role) VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        instance_id,
                        self.party_id,
                        character_id,
                        member["generation"],
                        party["revision"],
                        "leader" if character_id == party["leader_id"] else "member",
                    ),
                )
                db.execute(
                    "UPDATE characters SET map_id=1087,instance_id=%s,x=16,y=-37,z=-8 "
                    "WHERE id=%s",
                    (instance_id, character_id),
                )
            plan = dungeon_runtime_config.plan_from_configuration(self.installed)
            dungeon_progression.initialize_run(db, instance_id, self.party_id, plan)
        return instance_id

    def test_migration_seeds_valid_immutable_v3_and_active_pointer(self):
        self.assertEqual(3, self.installed["version"])
        self.assertEqual("native_dungeon_27", self.installed["route"]["key"])
        self.assertEqual(
            "native_physical_door_victory_policy", self.installed["topology"]["policy"]
        )
        self.assertEqual(
            dungeon_runtime_config.canonical_hash(self.config["compiled_plan"]),
            self.installed["evidence_hashes"]["plan"],
        )
        self.assertEqual(
            dungeon_runtime_config.canonical_hash(self.config["topology"]),
            self.installed["evidence_hashes"]["topology"],
        )
        changed = dungeon_runtime_config.prepare_configuration(
            self.installed["compiled_plan"],
            self.installed["topology"],
            self.installed["route"],
            version=3,
            provenance="attempted replacement of frozen ToFu v3",
        )
        with self.assertRaisesRegex(ValueError, "immutable"):
            with self.store.connection() as db:
                dungeon_runtime_config.install_configuration(db, changed)
        with self.store.connection() as db:
            self.assertEqual(
                self.installed,
                dungeon_runtime_config.pinned_configuration(
                    db,
                    "native_dungeon_27",
                    3,
                    expected_plan_hash=self.installed["compiled_plan"][
                        "document_sha256"
                    ],
                ),
            )
            context = db.execute(
                "SELECT policy_version,template_id,definition_id,provenance "
                "FROM dungeon_context_policy_versions WHERE route_key=%s",
                ("native_dungeon_27",),
            ).fetchone()
        self.assertEqual(
            (3, 29, 27),
            (
                context["policy_version"],
                context["template_id"],
                context["definition_id"],
            ),
        )

    def test_frozen_current_run_spawns_all_three_native_rooms_with_separated_party_slots(
        self,
    ):
        expected_rooms = self.installed["topology"]["rooms"]
        self.assertEqual([1, 2, 3], [room["order"] for room in expected_rooms])
        observed = []
        for order, room in enumerate(expected_rooms, 1):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE dungeon_room_runs SET current_room=%s WHERE instance_id=%s",
                    (order, self.instance_id),
                )
                run, pinned = dungeon_runtime.configuration_for_instance(
                    db, self.instance_id
                )
                self.assertEqual(
                    ("native_dungeon_27", 3),
                    (run["context_route_key"], run["context_policy_version"]),
                )
                self.assertEqual(self.installed, pinned)
                spawned = dungeon_runtime.ensure_current_room(
                    db, self.groups, self.instance_id, self.geometry
                )
                self.assertFalse(spawned["replay"])

            anchor = tuple(room["anchor"])
            room_cells = set(map(tuple, room["cells"]))
            room_geometry = {
                "map_id": 1087,
                "cells": sorted(room_cells),
                "edges": sorted(
                    (tuple(start), tuple(end))
                    for start, end in self.geometry["edges"]
                    if tuple(start) in room_cells and tuple(end) in room_cells
                ),
            }
            members = tuple(spawned["members"])
            positions = {(m["x"], m["y"], m["z"]) for m in members}
            self.assertEqual(8, len(members))
            self.assertEqual(8, len(positions))
            self.assertTrue(positions <= room_cells)
            self.assertTrue(
                all(
                    m["map_id"] == 1087 and m["instance_id"] == self.instance_id
                    for m in members
                )
            )
            expected = set(enemy_formation(room_geometry, anchor, 8, player_slots=6))
            self.assertEqual(expected, positions)

            first_neighbor = next(
                tuple(end)
                for start, end in room_geometry["edges"]
                if tuple(start) == anchor and tuple(end) != anchor
            )
            from wakfu_server.combat_arena_selection import bounded_arena

            safe = bounded_arena(room_geometry, anchor, [first_neighbor], radius=89)
            player_positions = {anchor, *reachable_cells(safe, anchor, 5)}
            self.assertEqual(6, len(player_positions))
            self.assertFalse(player_positions & positions)
            if order == 3:
                self.assertEqual(1, sum(member["ref"] == 1259 for member in members))
            else:
                self.assertFalse(any(member["ref"] == 1259 for member in members))
            observed.append(spawned["group_id"])

        self.assertEqual(3, len(set(observed)))
        with self.store.connection() as db:
            receipts = db.execute(
                "SELECT room_order,asset_map_id FROM dungeon_room_spawn_receipts "
                "WHERE instance_id=%s ORDER BY room_order",
                (self.instance_id,),
            ).fetchall()
        self.assertEqual(
            [(1, 1087), (2, 1087), (3, 1087)],
            [(row["room_order"], row["asset_map_id"]) for row in receipts],
        )

    def test_first_spawn_is_reachable_from_native_arrival_before_either_gate_opens(
        self,
    ):
        """Tie the PG-owned first formation to the native arrival path witness."""
        witness = json.loads(
            (
                ROOT / "docs/reports/dungeons/TOFU-FIRST-GROUP-REACHABILITY.json"
            ).read_text()
        )
        room = self.installed["topology"]["rooms"][0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_room_runs SET current_room=1 WHERE instance_id=%s",
                (self.instance_id,),
            )
            spawned = dungeon_runtime.ensure_current_room(
                db, self.groups, self.instance_id, self.geometry
            )

        actual_monsters = {(m["x"], m["y"], m["z"]) for m in spawned["members"]}
        expected_monsters = set(map(tuple, witness["monster_positions"]))
        self.assertEqual(actual_monsters, expected_monsters)
        self.assertFalse(any(m["ref"] == 1259 for m in spawned["members"]))

        native = self.installed["topology"]["exploration_geometry"]
        directed_edges = {(tuple(a), tuple(b)) for a, b in native["edges"]}
        path = list(map(tuple, witness["path"]))
        self.assertEqual(path[0], tuple(witness["entry"]))
        self.assertEqual(path[-1], tuple(witness["approach"]))
        self.assertTrue(all((a, b) in directed_edges for a, b in zip(path, path[1:])))
        self.assertTrue(set(path).issubset(set(map(tuple, room["cells"]))))
        gate_cells = {
            tuple(door["position"])
            for door in self.installed["topology"]["physical_doors"]
        }
        self.assertFalse(set(path) & gate_cells)
        self.assertFalse(set(path) & actual_monsters)
        target = tuple(witness["engagement_target"])
        approach = path[-1]
        self.assertIn(target, actual_monsters)
        self.assertEqual(abs(target[0] - approach[0]) + abs(target[1] - approach[1]), 1)
        self.assertEqual(target[2], approach[2])

        closed = dungeon_physical_doors.packets(
            self.installed["topology"],
            map_id=1087,
            instance_id=self.instance_id,
            unlocked_room=1,
        )
        states = {
            int.from_bytes(body[:8], "big", signed=True): int.from_bytes(
                body[17:19], "big", signed=True
            )
            for _, body in closed
        }
        self.assertEqual(
            {26874: 1, 26875: 1}, {key: states[key] for key in (26874, 26875)}
        )


if __name__ == "__main__":
    unittest.main()
