"""The reviewed initial group remains fixed outside combat, with native facing."""
import gzip
import json
from pathlib import Path
from postgres_case import PostgresCase
from unittest.mock import patch

from test_monster_wander import FixedRng


class PohlFixedWorldWanderTests(PostgresCase):
    def test_authored_group_does_not_consume_wander_rng_or_move(self):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.combat_monster_world import world_actor
        from wakfu_server.dungeon_encounters import room_members
        from wakfu_server.dungeon_runtime_config import level_selector
        from wakfu_server.monster_wander import wander_location

        config = json.loads(
            gzip.decompress(
                (
                    Path(__file__).parent
                    / "fixtures/pohl-fixed-placement/configuration184v7.json.gz"
                ).read_bytes()
            )
        )
        room = config["topology"]["rooms"][1]
        compiled = config["compiled_plan"]["rooms"][1]
        cells = set(map(tuple, room["cells"]))
        geometry = map_geometry(1369)
        geometry = dict(
            geometry,
            cells=cells,
            edges=[
                (a, b)
                for a, b in geometry["edges"]
                if tuple(a) in cells and tuple(b) in cells
            ],
        )
        roster = [
            dict(
                ref_id=r["ref_id"],
                count=r["count"],
                min_level=r["native_min_level"],
                max_level=r["native_max_level"],
                role=r["role"],
            )
            for r in compiled["monsters"]
        ]
        instance = (1 << 57) + 1369
        members = room_members(
            dict(
                status="active",
                current_room=2,
                instance_id=instance,
                rooms=[dict(order=2, monsters=roster)],
            ),
            asset_map_id=1369,
            anchor=tuple(room["anchor"]),
            geometry=geometry,
            group_id=991184,
            select_level=level_selector(config, room_order=2),
            player_slots=6,
            fixed_actor_placements=room["encounter_scene"]["fixed_actor_placements"],
        )
        groups = PersistentGroups(self.store)
        key = groups.register(1369, instance, 991184, members)
        player = dict(map_id=1369, instance_id=instance, x=-5, y=-55, z=-15)
        rng = FixedRng(rolls=(0,) * 100, steps=1)
        packets = []
        moved = wander_location(
            groups,
            1369,
            instance,
            [player],
            geometry["edges"],
            lambda *p: packets.append(p),
            rng=rng,
            move_probability=1,
            min_steps=1,
            max_steps=1,
            radius=100,
        )
        self.assertEqual(moved, [])
        self.assertEqual(rng.random_calls, 0)
        self.assertEqual(groups.available(1369, instance)[0]["members"], members)
        self.assertEqual(packets, [])
        boss = next(m for m in members if m["ref"] == 5376)
        self.assertEqual(boss["fixed_actor_placement"]["direction"], 3)
        # Initial native world facing must follow source metadata even when the
        # caller's ordinary group-facing default differs.
        self.assertEqual(
            world_actor(boss, group_id=991184, direction=7),
            world_actor(boss, group_id=991184, direction=3),
        )
        from wakfu_server.combat_fixed_actor_placement import native_member_fields
        from wakfu_server.monster_corpses import defeated_members
        from types import SimpleNamespace

        dead = SimpleNamespace(
            phase="finished",
            actors={m["id"]: SimpleNamespace(controlled=False, hp=0) for m in members},
        )
        self.assertEqual(defeated_members(dead, members), members)
        forged = dict(boss, hp=boss["hp"] + 1)
        with self.assertRaises(ValueError):
            world_actor(forged, group_id=991184)
        changed = dict(boss, x=boss["x"] + 1)
        with self.assertRaises(ValueError):
            native_member_fields(changed)
        ordinary = PersistentGroups(self.store)
        ordinary_members = [
            dict(native_member_fields(m), instance_id=instance + 1) for m in members
        ]
        ordinary_key = ordinary.register(1369, instance + 1, 991185, ordinary_members)
        rng = FixedRng(rolls=(0,) * 100, steps=1)
        ordinary_moved = wander_location(
            ordinary,
            1369,
            instance + 1,
            [dict(player, instance_id=instance + 1)],
            geometry["edges"],
            lambda *p: None,
            rng=rng,
            move_probability=1,
            min_steps=1,
            max_steps=1,
            radius=100,
        )
        self.assertGreater(rng.random_calls, 0)
        self.assertEqual(ordinary_moved, [ordinary_key])
