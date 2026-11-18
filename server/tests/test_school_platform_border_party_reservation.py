"""School platform placement keeps its six native party slots off faW909."""

import os
from contextlib import nullcontext
from copy import deepcopy
import unittest
from types import SimpleNamespace
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_DATABASE_URL"), "requires read-only native map catalogs"
)
class SchoolPlatformBorderReservationTests(unittest.TestCase):
    def test_actual_origins_freeze_after_border_reservation_and_reject_tampering(self):
        import json
        from pathlib import Path

        from wakfu_server.postgres import Database
        from wakfu_server.combat_actor_snapshot import native_actor_catalog
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_encounter_scene_policy import (
            prepare_scene,
            arena_scene,
        )
        from wakfu_server.combat_placement_policy import freeze
        from wakfu_server.combat_encounter_roles import role_assignment
        from wakfu_server.combat_placement_policy import _party_reserved_cells

        database = Database(
            os.environ["WAKFU_DATABASE_URL"],
            password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"],
        )
        with database.connection() as db:
            with db.transaction():
                db.execute("SET TRANSACTION READ ONLY")
                instance = db.execute(
                    "SELECT i.instance_id,c.configuration FROM dungeon_instances i "
                    "JOIN dungeon_runtime_configurations c ON c.route_key=i.context_route_key "
                    "AND c.policy_version=i.context_policy_version WHERE i.start_map_id=1030 "
                    "ORDER BY i.instance_id DESC LIMIT 1"
                ).fetchone()
        self.assertIsNotNone(instance)
        configuration = instance["configuration"]
        topology = configuration["topology"]
        room = topology["rooms"][0]
        descriptor = room["encounter_scene"]
        members = [
            dict(
                id=-100 - index,
                ref=entry["reference"],
                map_id=1030,
                instance_id=instance["instance_id"],
                **dict(zip(("x", "y", "z"), entry["cell"]))
            )
            for index, entry in enumerate(descriptor["fixed_actor_placements"])
        ]
        catalog = native_actor_catalog()
        radii = tuple(
            catalog["npc_profiles"][str(member["ref"])]["physical_radius"]
            for member in members
        )
        record = prepare_scene(
            descriptor,
            scope=dict(
                map_id=1030,
                instance_id=instance["instance_id"],
                group_id=1,
                room_order=1,
                policy_version=configuration["version"],
                route_key=configuration["route"]["key"],
                evidence_hashes=configuration["evidence_hashes"],
            ),
            room_cells=room["cells"],
        )
        member_cells = [
            tuple(member[axis] for axis in ("x", "y", "z")) for member in members
        ]
        roles = role_assignment(1030, [member["ref"] for member in members])

        class FakeDb:
            def __init__(self):
                self.saved_layout = None
                self.writes = 0

            def execute(self, sql, params=()):
                if "SELECT status FROM combat_fights" in sql:
                    row = {"status": "placement"}
                elif "FROM combat_fight_participants" in sql:
                    row = {"admitted": 1}
                elif (
                    "SELECT map_id,instance_id,layout FROM fight_placement_layouts"
                    in sql
                ):
                    row = None
                elif "SELECT value FROM settings" in sql:
                    row = {
                        "value": {
                            "version": 1,
                            "slots_per_team": 6,
                            "variation_enabled": False,
                        }
                    }
                elif "INSERT INTO fight_placement_layouts" in sql:
                    self.writes += 1
                    self.saved_layout = params[-1].obj
                    row = None
                else:
                    row = None
                return SimpleNamespace(fetchone=lambda: row)

        class FakeStore:
            def __init__(self, db):
                self.db = db

            def connection(self):
                return nullcontext(self.db)

            def lock_character(self, *_args):
                return None

        def prepare(origin, scene_record=record):
            character = dict(
                id=369,
                map_id=1030,
                instance_id=instance["instance_id"],
                **dict(zip(("x", "y", "z"), origin))
            )
            selected = local_arena(
                1030,
                instance["instance_id"],
                origin,
                member_cells,
                allowed_cells=room["cells"],
                full_room_scope=True,
                fixed_member_positions={
                    i: tuple(entry["cell"])
                    for i, entry in enumerate(descriptor["fixed_actor_placements"])
                },
                member_radii=radii,
                player_radius=catalog["default_actor_radius"],
                ordinary_npc_placement=True,
                ordinary_generated_placement=True,
            )
            return (
                character,
                selected,
                arena_scene(scene_record, selected, character, members),
            )

        for fight_id, origin in enumerate(((128, -15, 0), (125, -15, 0)), 1):
            character, base_arena, selected = prepare(origin)
            self.assertEqual(
                selected["native_border_policy"],
                "wakemu.reconstructed-native-cardinal-perimeter-v1",
            )
            reserved = _party_reserved_cells(
                selected,
                selected["validated_cells"],
                selected["placement_cells"],
                roles.player_team,
            )
            self.assertEqual(len(reserved), 6)
            self.assertIn(origin, reserved)
            self.assertFalse(reserved & set(selected["native_border_cells"]))
            self.assertFalse(
                reserved & set(map(tuple, selected["native_party_npc_cells"]))
            )

            fake_db = FakeDb()
            seeds = {0: [origin], 1: member_cells}
            with patch(
                "wakfu_server.combat_placement_policy.reserve_topology",
                return_value=4321,
            ), patch("wakfu_server.combat_border_policy.choose", return_value=None):
                frozen = freeze(
                    FakeStore(fake_db),
                    account_id=1,
                    generation=1,
                    character_id=369,
                    fight_id=fight_id,
                    map_id=1030,
                    instance_id=instance["instance_id"],
                    selected_arena=selected,
                    seeds=seeds,
                )
            self.assertEqual(fake_db.writes, 1)
            self.assertEqual(
                set(map(tuple, fake_db.saved_layout["native_party_reserved_cells"])),
                reserved,
            )
            self.assertEqual(
                set(frozen["placement_cells"][roles.player_team])
                & set(frozen["placement_cells"][roles.npc_team]),
                set(),
            )
            self.assertEqual(
                frozen["participant_positions"], selected["participant_positions"]
            )

            # Without the authored 909 border, preserve the original generated
            # reservation and player zone exactly.
            borderless_descriptor = dict(
                schema_version=1,
                full_room_scope=True,
                policy_id="wakemu.test.native-scene-no-border.v1",
                authority="test scene without a border declaration",
                source_uri="native geometry fixture",
            )
            borderless_record = prepare_scene(
                borderless_descriptor,
                scope=record["scope"],
                room_cells=room["cells"],
            )
            borderless = arena_scene(borderless_record, base_arena, character, members)
            self.assertEqual(
                borderless["native_party_reserved_cells"],
                base_arena["native_party_reserved_cells"],
            )
            self.assertEqual(
                borderless["placement_cells"], base_arena["placement_cells"]
            )

        # The policy must reject a native arena whose generated player zone no
        # longer has all six reserved positions, before it can be frozen.
        character, _, selected = prepare((128, -15, 0))
        insufficient = deepcopy(selected)
        insufficient["placement_cells"] = dict(selected["placement_cells"])
        insufficient["placement_cells"][roles.player_team] = sorted(
            insufficient["placement_cells"][roles.player_team]
        )[:5]
        fake_db = FakeDb()
        with patch(
            "wakfu_server.combat_placement_policy.reserve_topology", return_value=4321
        ), patch(
            "wakfu_server.combat_border_policy.choose", return_value=None
        ), self.assertRaises(
            ValueError
        ):
            freeze(
                FakeStore(fake_db),
                account_id=1,
                generation=1,
                character_id=369,
                fight_id=10,
                map_id=1030,
                instance_id=instance["instance_id"],
                selected_arena=insufficient,
                seeds={0: [(128, -15, 0)], 1: member_cells},
            )
        self.assertEqual(fake_db.writes, 0)

        character, _, selected = prepare((128, -15, 0))
        damaged = dict(selected)
        damaged["native_party_reserved_cells"] = [
            list(cell) for cell in selected["native_party_reserved_cells"]
        ]
        damaged["native_party_reserved_cells"][0] = list(
            next(iter(selected["native_border_cells"]))
        )
        fake_db = FakeDb()
        with patch(
            "wakfu_server.combat_placement_policy.reserve_topology", return_value=4321
        ), patch(
            "wakfu_server.combat_border_policy.choose", return_value=None
        ), self.assertRaises(
            ValueError
        ):
            freeze(
                FakeStore(fake_db),
                account_id=1,
                generation=1,
                character_id=369,
                fight_id=9,
                map_id=1030,
                instance_id=instance["instance_id"],
                selected_arena=damaged,
                seeds={0: [(128, -15, 0)], 1: member_cells},
            )
        self.assertEqual(fake_db.writes, 0)


if __name__ == "__main__":
    unittest.main()
