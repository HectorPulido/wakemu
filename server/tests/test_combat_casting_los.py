"""Native QI.h masks, registered slot visibility and live property policy."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_casting_los import native_qi_h, native_actor_visibility
from wakfu_server import native_catalog


class NativeCastingLOSTests(unittest.TestCase):
    def terrain(self, masks=None):
        return SimpleNamespace(
            x=0, y=0, width=2, masks=[0, 0, 0, 0] if masks is None else masks
        )

    def h(self, terrain, x=0, y=0, z=0, slots=(), visible=None, ignored=frozenset()):
        return native_qi_h(
            terrain,
            x,
            y,
            z,
            ordered_slots=lambda x, y: slots,
            visibility=lambda slot: visible[slot],
            ignored=ignored,
        )

    def test_mask256_and_index_bounds_precede_obstacle_lookup(self):
        self.assertTrue(self.h(self.terrain([256, 0, 0, 0])))
        self.assertTrue(self.h(self.terrain(), x=-1))
        self.assertTrue(self.h(self.terrain(), y=2))
        self.assertFalse(self.h(self.terrain(), x=2))
        self.assertTrue(self.h(self.terrain([0, 0, 256, 0]), x=2))

    def test_actual_slot_blocking_exclusions_and_unused_z(self):
        for z in (-32768, 0, 32767):
            self.assertTrue(self.h(self.terrain(), z=z, slots=(2,), visible={2: True}))
            self.assertFalse(
                self.h(
                    self.terrain(),
                    z=z,
                    slots=(2,),
                    visible={2: True},
                    ignored=frozenset({2}),
                )
            )
            self.assertFalse(
                self.h(self.terrain(), z=z, slots=(2,), visible={2: False})
            )

    def test_actual_null_slot_preserves_native_iteration_short_circuit(self):
        self.assertFalse(
            self.h(self.terrain(), slots=(1, 2), visible={1: None, 2: True})
        )
        self.assertTrue(
            self.h(self.terrain(), slots=(2, 1), visible={1: None, 2: True})
        )

    def test_ray_diagnostics_identify_actual_intermediate_actor_without_extra_queries(
        self,
    ):
        from unittest.mock import patch
        from wakfu_server.combat_casting_los import native_casting_ray

        blocker = SimpleNamespace(id=42)
        row = dict(identity=["actor", 42], position=[1, 0, 0], radius=1)
        registry = SimpleNamespace(
            slots={2: row},
            snapshot=lambda: self.terrain(),
            ordered_U=lambda x, y: (2,),
        )
        calls = []
        authority = SimpleNamespace(
            properties=lambda fight, actor: calls.append(actor.id) or ()
        )
        detail = {}
        with patch(
            "wakfu_server.combat_qi_fight.current_registry", return_value=registry
        ), patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, ((1, 0),)),),
        ):
            result = native_casting_ray(
                SimpleNamespace(actors={42: blocker}),
                authority,
                1086,
                (0, 0, 0),
                (2, 0, 0),
                source_height=6,
                target_height=6,
                ignored_slots=(),
                diagnostic=detail,
            )
        self.assertFalse(result)
        self.assertEqual(calls, [42])
        self.assertEqual(detail["rays"][0]["blocked_probe"], [1, 0])
        self.assertEqual(
            detail["rays"][0]["evaluated_slots"],
            [
                dict(
                    slot=2,
                    identity=["actor", 42],
                    position=[1, 0, 0],
                    radius=1,
                    blocks_los=True,
                )
            ],
        )
        self.assertFalse(detail["result"])

    def test_fight_visibility_properties(self):
        self.assertTrue(native_actor_visibility(frozenset()))
        self.assertFalse(native_actor_visibility(frozenset({5})))
        self.assertTrue(native_actor_visibility(frozenset({5, 6})))
        self.assertFalse(native_actor_visibility(frozenset({18, 6})))
        self.assertFalse(native_actor_visibility(frozenset({54, 6})))

    def test_map1086_beacon_cell_blocks_the_actual_casting_ray_when_native_visible(
        self,
    ):
        import json
        from pathlib import Path
        from wakfu_server.combat_native_los_ray import cast_rays

        source = (
            Path(__file__).resolve().parents[1]
            / "protocol/native-class-summon-initial-states.json"
        )
        profile = json.loads(native_catalog.read_text(source))["profiles"]["3798"]
        properties = frozenset(profile["fight_properties"])
        self.assertEqual(profile["initial_state_triples"][:3], [7781, -1, 1])
        # The sourced profile has none of eGj.bcQ's invisible/revealed,
        # superior-invisible or DONT_BLOCK_LOS properties.
        self.assertTrue(native_actor_visibility(properties))

        rays = cast_rays(
            1086,
            (7, -163, 0),
            (3, -163, 0),
            source_height=6,
            target_height=0,
        )
        self.assertEqual(len(rays), 2)
        for static_clear, probes in rays:
            self.assertTrue(static_clear)
            self.assertIn((4, -163), probes)
            terrain = SimpleNamespace(x=4, y=-163, width=1, masks=[0])
            self.assertTrue(
                native_qi_h(
                    terrain,
                    4,
                    -163,
                    999,
                    ordered_slots=lambda _x, _y: (2,),
                    visibility=lambda _slot: native_actor_visibility(properties),
                    ignored=frozenset(),
                )
            )
            self.assertFalse(
                native_qi_h(
                    terrain,
                    4,
                    -163,
                    999,
                    ordered_slots=lambda _x, _y: (2,),
                    visibility=lambda _slot: native_actor_visibility(properties | {5}),
                    ignored=frozenset(),
                )
            )
