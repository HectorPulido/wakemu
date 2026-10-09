"""Actual factory eVI source, secondary state and replay integration."""
import random
import os
import json
from wakfu_server.paths import DATA_ROOT
import unittest
from unittest.mock import patch
import test_combat_displacement as fixtures
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_ordinary_authority import ordinary_cast_authority
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server import native_catalog


class CollisionResourceRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeDisplacementTests.setUpClass()

    def setUp(self):
        self.fixture = fixtures.NativeDisplacementTests()
        self.fixture.setUp()
        f = self.fixture
        self.preview = f.preview
        self.preview.actors[8].controlled = False
        native = json.loads(
            native_catalog.read_text(
                DATA_ROOT / "native-actor-characteristics.json", encoding="utf-8"
            )
        )["characteristics"]["86"]
        for actor in self.preview.actors.values():
            actor.effect_stats[86] = 0
            actor.effect_minima[86] = native["minimum"]
            actor.effect_maxima[86] = native["maximum"]
        self.build_runtime()

    def build_runtime(self, *, critical=False):
        f = self.fixture
        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=f.authority,
            cast=ordinary_cast_authority(
                actors=f.authority,
                timing=NativeEffectTimingProvider(f.fixture.states),
                rng=random.Random(1),
                critical=critical,
            ),
        )
        factory = NativeEffectRuntimeFactory(
            effects=f.effects,
            state_catalog=f.fixture.states,
            characteristic_registry=f.fixture.registry,
            action_id=1,
            contexts=self.adapter.contexts(),
            displacement_authority=f.authority,
        )
        self.dispatcher, self.packets = factory(
            self.preview, dict(spell_id=6266, evaluation_level=1)
        )
        self.executor = self.dispatcher.native_collision_resource_executor

    def test_factory_loss_executes_actual5227_and_runtime2254(self):
        seen = []
        original = type(self.dispatcher.replay_event).__call__

        def replay(instance, source, **kwargs):
            seen.append(source)
            return original(instance, source, **kwargs)

        with patch.object(type(self.dispatcher.replay_event), "__call__", replay):
            self.assertTrue(self.executor(7, -7))
        self.assertEqual(self.preview.actors[-7].ap, 5)
        synthetic = [source for source in seen if source.generic_effect == -13]
        self.assertEqual(
            [source.channel for source in synthetic], [10, 1, 20, 2, 30, 3, 40, 4]
        )
        self.assertTrue(all(2254 in source.event_ids for source in synthetic))
        self.assertTrue(
            all(source.native_container == {"present": False} for source in synthetic)
        )
        states = [
            entry
            for entry in self.preview.actors[-7].state_ledger.entries
            if entry.reference == 5227
        ]
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].level, 10)
        self.assertEqual(self.preview.actors[-7].effect_stats[86], 10)
        losses = [
            body
            for opcode, body in self.packets
            if opcode == 12613 and int.from_bytes(body[13:17], "big") == 55
        ]
        self.assertEqual(len(losses), 1)
        identity = _identity_fields(losses[0][19:])
        self.assertEqual(
            (identity[2], identity[3], identity[4], identity[6], identity[7]),
            (0, (-13) & ((1 << 64) - 1), 1, 7, (-7) & ((1 << 64) - 1)),
        )
        self.assertNotIn(identity[1], self.preview.owned_stat_effects)
        self.assertFalse(self.executor.handler.prepared)
        self.assertFalse(self.executor.handler.runner_amounts)
        # Actual retained state child retirement restores WP, not instant AP.
        self.dispatcher.native_state_handler.remove_state_children(states[0].uid)
        self.assertEqual(self.preview.actors[-7].effect_stats[86], 0)
        self.assertEqual(self.preview.actors[-7].ap, 5)
        self.assertFalse(
            any(
                row.get("state_uid") == states[0].uid
                for row in self.preview.owned_stat_effects.values()
            )
        )

    def test_actual_push_geometry_precedes_both_losses_and_asymmetric204(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        # Native351295 is variant1; exercise its authoritative critical cast.
        self.assertEqual(self.fixture.effects["351295"]["variant"], 1)
        self.build_runtime(critical=True)
        self.preview.actors[7].position = (0, 0, 0)
        self.preview.actors[-7].position = (1, 0, 0)
        self.preview.actors[8].position = (3, 0, 0)
        # Exact live statistic snapshot makes both C draws yield requested1.
        self.preview.actors[7].effect_stats[86] = 100
        slots = [None] * 127
        for slot, member in enumerate(self.preview.actors.values()):
            member.native_obstacle_id = slot
            slots[slot] = dict(
                identity=["actor", member.id],
                position=list(member.position[:2]),
                radius=0,
                indexed=True,
                movement_blocking=True,
            )
        self.preview.native_qi_snapshot = dict(
            x=0, y=0, width=8, height=1, cell_masks=[0] * 8
        )
        self.preview.native_qi_slots = slots
        self.preview.native_qi_touched_cells = []
        self.preview.native_qi_movement_override = False
        self.preview.native_qi_ignored_slots = []
        seen = []
        original = type(self.dispatcher.replay_event).__call__

        def replay(instance, source, **kwargs):
            seen.append((source, self.preview.actors[-7].position))
            return original(instance, source, **kwargs)

        # Original class push351295 has six cells, AP-loss flag and no criterion.
        effect = self.fixture.effects["351295"]
        self.assertEqual(effect["effect_class"], 300)
        self.assertEqual(effect["parameters"], [6, 0, 1, 0])
        with patch.object(type(self.dispatcher.replay_event), "__call__", replay):
            self.assertTrue(
                self.dispatcher.execute(
                    EffectInvocation(
                        351295, 1, 7, -7, (1, 0, 0), native_explicit_target=True
                    )
                )
            )
        self.assertEqual(self.preview.actors[-7].position, (2, 0, 0))
        for identity in (-7, 8):
            self.assertEqual(self.preview.actors[identity].ap, 5)
            self.assertEqual(self.preview.actors[identity].effect_stats[86], 10)
            self.assertEqual(
                [
                    entry.level
                    for entry in self.preview.actors[identity].state_ledger.entries
                    if entry.reference == 5227
                ],
                [10],
            )
        losses = [
            (source, position)
            for source, position in seen
            if source.generic_effect == -13
        ]
        self.assertEqual(len(losses), 16)
        self.assertTrue(
            all(
                position == (2, 0, 0) and 2254 in source.event_ids
                for source, position in losses
            )
        )
        collision = [source for source, position in seen if source.event_ids == (204,)]
        self.assertEqual(
            [
                (source.channel, source.manager_actor_id, source.target_id)
                for source in collision
            ],
            [(30, 7, -7), (3, -7, -7), (30, 7, 8), (3, 8, -7)],
        )
        self.assertEqual(collision[0].uid, collision[1].uid)
        self.assertEqual(collision[0].uid, collision[3].uid)
        self.assertNotEqual(collision[0].uid, collision[2].uid)
        first204 = next(
            index
            for index, (source, position) in enumerate(seen)
            if source.event_ids == (204,)
        )
        self.assertTrue(
            all(
                index < first204
                for index, (source, position) in enumerate(seen)
                if source.generic_effect == -13
            )
        )
        self.assertEqual(
            tuple(
                self.preview.native_qi_slots[
                    self.preview.actors[-7].native_obstacle_id
                ]["position"]
            ),
            (2, 0),
        )

    def test_actual_area_collision_skips_absent_ap_and_delivers_qf_event204(self):
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        self.preview.actors[7].position = (0, 0, 0)
        self.preview.actors[-7].position = (1, 0, 0)
        self.preview.actors[8].position = (7, 0, 0)
        self.preview.actors[7].direction = 1
        self.preview.actors[7].effect_stats[86] = 100
        slots = [None] * 127
        for slot, member in enumerate(self.preview.actors.values()):
            member.native_obstacle_id = slot
            slots[slot] = dict(
                identity=["actor", member.id],
                position=list(member.position[:2]),
                radius=0,
                indexed=True,
                movement_blocking=True,
            )
        self.preview.native_qi_snapshot = dict(
            x=0, y=0, width=8, height=1, cell_masks=[0, 0, 0, 256, 0, 0, 0, 0]
        )
        self.preview.native_qi_slots = slots
        self.preview.native_qi_touched_cells = []
        self.preview.native_qi_movement_override = False
        self.preview.native_qi_ignored_slots = []
        with patch.dict(os.environ, {"WAKFU_NATIVE_AREA_CALLBACKS": "1"}):
            self.build_runtime()
            # Original noncritical339 creates actual faW prototype1035.
            self.assertTrue(
                self.dispatcher.execute(EffectInvocation(174979, 1, 7, None, (3, 0, 0)))
            )
            area = next(
                row
                for row in self.preview.native_effect_areas.values()
                if row["reference"] == 1035
            )
            area_id = area["uid"]
            self.assertEqual(area["cell"], (3, 0, 0))
            self.assertNotIn(area_id, self.preview.actors)
            self.assertEqual(area["native_faw_constructor"]["characteristic_ids"], ())
            self.build_runtime(critical=True)
        seen = []
        original = type(self.dispatcher.replay_event).__call__

        def replay(instance, source, **kwargs):
            seen.append(source)
            return original(instance, source, **kwargs)

        with patch.object(type(self.dispatcher.replay_event), "__call__", replay):
            self.assertTrue(
                self.dispatcher.execute(
                    EffectInvocation(
                        351295, 1, 7, -7, (1, 0, 0), native_explicit_target=True
                    )
                )
            )
        self.assertEqual(self.preview.actors[-7].position, (2, 0, 0))
        self.assertEqual(self.preview.actors[-7].ap, 5)
        synthetic = [source for source in seen if source.generic_effect == -13]
        self.assertEqual(len(synthetic), 8)
        self.assertTrue(all(source.target_id == -7 for source in synthetic))
        collision = [source for source in seen if source.event_ids == (204,)]
        self.assertEqual(
            [
                (source.channel, source.manager_actor_id, source.target_id)
                for source in collision
            ],
            [(30, 7, -7), (3, -7, -7), (30, 7, area_id), (3, area_id, -7)],
        )
        self.assertNotIn(area_id, self.preview.actors)
        self.assertNotIn("effect_stats", area)
