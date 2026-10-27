"""Native geometry and preallocated-ID provider remain pure during previews."""
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from test_rift_runtime import policy
from wakfu_server.rift_dispatch_lifecycle import next_roster, resolve_destination


def geometry():
    cells = tuple((i, 0, 0) for i in range(10))
    edges = tuple((a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1)
    return dict(cells=cells, edges=edges)


class RiftDispatchLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.catalog = dict(
            wave_id=3,
            map_id=1314,
            type="INFINITE_WAVE",
            species_refs=[1],
            objects=[
                dict(
                    id=5,
                    type="GenericActivableInteractiveElement",
                    map_id=1314,
                    x=0,
                    y=0,
                    z=0,
                )
            ],
        )

    def test_arrival_uses_verified_reachable_native_floor(self):
        dest = resolve_destination(None, self.catalog, [1, 2, 3, 4], geometry())
        self.assertEqual(dest, dict(map_id=1314, x=0, y=0, z=0))
        with self.assertRaises(ValueError):
            resolve_destination(None, self.catalog, [1, 2], dict(cells=(), edges=()))

    def fight(self):
        player = SimpleNamespace(id=1, team=0, position=(0, 0, 0), hp=1)
        return SimpleNamespace(
            rift_wave_state=dict(
                catalog=self.catalog,
                policy=policy(),
                seed="test",
                instance_id=99,
                actor_id_pool=[-(2**50 + i) for i in range(8)],
            ),
            actors={1: player},
            walkable=set(geometry()["cells"]),
            edges=set(geometry()["edges"]),
            _in_play=lambda a: a.hp > 0,
        )

    def test_pure_provider_consumes_fresh_exact_ids_and_free_cells(self):
        fight = self.fight()
        fake = SimpleNamespace(
            reference=lambda ref: {"min_level": 21},
            owned_instance=lambda ref, level, uid, **kwargs: dict(
                ref=ref, level=level, id=uid, **kwargs
            ),
        )
        # This unit isolates reservation/species handling. Physical placement
        # has a separate native-QI lifecycle component, rather than a fallback
        # for this deliberately incomplete source fixture.
        with patch.dict(sys.modules, {"wakfu_server.monsters": fake}), patch(
            "wakfu_server.rift_reinforcement_placement.select_positions",
            return_value=tuple((i, 0, 0) for i in range(1, 5)),
        ):
            members = next_roster(fight, dict(completed_wave=1))
        self.assertEqual(len(members), 4)
        self.assertEqual(len(fight.rift_wave_state["actor_id_pool"]), 4)
        self.assertTrue(
            all(m["x"] > 0 and m["ref"] == 1 and m["level"] == 21 for m in members)
        )
        self.assertEqual(len({m["id"] for m in members}), 4)

    def test_insufficient_or_reused_reservation_fails_without_consumption(self):
        fight = self.fight()
        fight.rift_wave_state["actor_id_pool"] = [-1]
        fake = SimpleNamespace(
            reference=lambda *a: None, owned_instance=lambda *a: None
        )
        with patch.dict(sys.modules, {"wakfu_server.monsters": fake}):
            with self.assertRaisesRegex(ValueError, "replenishment"):
                next_roster(fight, dict(completed_wave=1))
        self.assertEqual(fight.rift_wave_state["actor_id_pool"], [-1])
