import unittest
import gzip
import json
from types import SimpleNamespace
from wakfu_server.combat_native_los_ray import (
    DATA_ROOT,
    static_ray,
    cast_rays,
    topology_columns,
)
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_actor_snapshot import build_npc_snapshot, native_actor_catalog
from wakfu_server.fight_checkpoint_store import snapshot


class NativeGenericLOSTests(unittest.TestCase):
    def test_topology_columns_preserve_native_order_values_and_shared_aliases(self):
        path = DATA_ROOT / "native-los-topology" / "1134.json.gz"
        with gzip.open(path, "rt") as stream:
            native = json.load(stream)

        columns = topology_columns(1134)
        expected = {
            (x, y): tuple(tuple(surface) for surface in values)
            for x, y, values in native["columns"]
        }
        self.assertEqual(list(columns.items()), list(expected.items()))
        self.assertEqual(columns, expected)
        self.assertTrue(all(type(surfaces) is tuple for surfaces in columns.values()))
        self.assertTrue(
            all(
                type(surface) is tuple
                for surfaces in columns.values()
                for surface in surfaces
            )
        )

        canonical = {}
        found_alias = False
        for surfaces in columns.values():
            if surfaces in canonical:
                self.assertIs(surfaces, canonical[surfaces])
                found_alias = True
            else:
                canonical[surfaces] = surfaces
        self.assertTrue(found_alias)

    def test_reported_gui_endpoints_use_native_cast_height(self):
        source = (-15, -3, 0)
        for target in ((-14, -4, 0), (-15, -5, -1), source):
            rays = cast_rays(1134, source, target, source_height=6, target_height=6)
            self.assertTrue(any(visible for visible, _ in rays))

    def test_height_unknown_rejects_instead_of_inventing_zero(self):
        with self.assertRaises(ValueError):
            cast_rays(
                1134, (-15, -3, 0), (-15, -5, -1), source_height=None, target_height=6
            )

    def test_dynamic_blocker_and_footprints_remain_live(self):
        source, target = (-14, -10, -1), (-11, -10, -1)
        fight = SimpleNamespace(
            actors={
                1: SimpleNamespace(
                    id=1,
                    hp=10,
                    position=source,
                    native_los_height=6,
                    native_obstacle_id=None,
                    team=0,
                ),
                2: SimpleNamespace(
                    id=2,
                    hp=10,
                    position=target,
                    native_los_height=6,
                    native_obstacle_id=None,
                    team=1,
                ),
                3: SimpleNamespace(
                    id=3,
                    hp=10,
                    position=(-13, -10, -1),
                    native_los_height=6,
                    native_obstacle_id=None,
                    team=1,
                ),
            },
            walkable={(x, -10, -1) for x in range(-14, -10)},
        )
        footprints = {1: {source[:2]}, 2: {target[:2]}, 3: {(-13, -10)}}
        self.assertFalse(
            authoritative_visible(
                1134, source, target, fight, blocking_footprints=footprints
            )
        )
        footprints[3] = set()
        self.assertTrue(
            authoritative_visible(
                1134, source, target, fight, blocking_footprints=footprints
            )
        )
        fight.actors[1].native_los_height = None
        with self.assertRaises(ValueError):
            authoritative_visible(
                1134, source, target, fight, blocking_footprints=footprints
            )

    def test_npc_height_comes_from_profile_and_survives_checkpoint(self):
        npc = Actor(-7, 1, (1, 0, 0), 12, 6, 3, 0, 1)
        build_npc_snapshot(
            dict(id=-7, ref=5525), npc, wp_current=0, wp_maximum=0, running_effects=()
        ).install(npc)
        self.assertEqual(npc.native_los_height, 4)  # Original aMb.css -> blj.bcK.
        self.assertEqual(native_actor_catalog()["default_actor_los_height"], 6)
        pc = Actor(7, 0, (0, 0, 0), 10, 6, 3, 0, 1, 3, True)
        fight = Fight(
            1,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        self.assertEqual(snapshot(fight)["actors"]["-7"]["native_los_height"], 4)
