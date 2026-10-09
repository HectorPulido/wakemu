import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from wakfu_server.combat_collision_resource import NativeCollisionResourceExecutor
from wakfu_server.combat_resource_loss_handler import NativeResourceLossHandler
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server import native_catalog


def actor(uid, ap=6):
    return SimpleNamespace(
        id=uid,
        hp=60,
        max_hp=60,
        ap=ap,
        mp=3,
        max_ap=6,
        max_mp=3,
        position=(uid, 0, 0),
        effect_stats={1: 60, 2: ap, 3: 3, 86: 0},
        effect_minima={2: 0, 3: 0},
        effect_maxima={2: 6, 3: 3},
        effect_frozen=frozenset(),
    )


class CollisionResourceTests(unittest.TestCase):
    def setUp(self):
        self.definition = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1] / "protocol/collision-effect.json"
            )
        )
        self.fight = SimpleNamespace(
            id=100,
            phase="active",
            actors={7: actor(7), -7: actor(-7)},
            owned_stat_effects={},
        )
        self.packets = []
        self.phases = []
        self.states = []
        self.handler = NativeResourceLossHandler(
            self.fight,
            self.packets,
            action_id=200,
            allocate_uid=lambda: 901,
            context=lambda *a: StatExecutionContext(True, True, None, False, b"", None),
            rng=lambda: 0,
            properties=lambda a: frozenset(),
            secondary_state=lambda *a: self.states.append(a),
            event_lifecycle=SimpleNamespace(
                phase=lambda *a, **k: self.phases.append(k["channel"])
            ),
            delivery=lambda *a: None,
        )
        self.executor = NativeCollisionResourceExecutor(
            self.handler, self.definition, characteristic_present=lambda a, s: True
        )
        self.handler.delivery = self.executor.delivery

    def test_shared_lifecycle_secondary_and_signed_registration(self):
        self.assertTrue(self.executor(7, -7))
        self.assertEqual(self.fight.actors[-7].ap, 5)
        self.assertEqual(self.phases, [1, 2, 3, 4])
        self.assertEqual(self.states[0][5], (5227, 0, 10, 0, 100, 0))
        self.assertEqual(self.packets[0][0], 12613)
        self.assertFalse(self.fight.owned_stat_effects)
        self.assertFalse(self.handler.prepared)
        self.assertFalse(self.handler.runner_amounts)

    def test_absent_characteristic_skips_all_phases(self):
        self.executor.characteristic_present = lambda a, s: False
        self.assertFalse(self.executor(7, -7))
        self.assertEqual(self.phases, [])
        self.assertEqual(self.packets, [])

    def test_unknown_characteristic_is_not_a_skip(self):
        self.executor.characteristic_present = lambda a, s: None
        with self.assertRaisesRegex(ValueError, "AP presence"):
            self.executor(7, -7)
        self.assertEqual(self.phases, [])

    def test_guard_rejection_releases_prepared_runner(self):
        self.handler.context = lambda *a: StatExecutionContext(
            False, True, None, False, b"", None
        )
        self.assertFalse(self.executor(7, -7))
        self.assertEqual(self.phases, [1])
        self.assertEqual(self.packets, [])
        self.assertFalse(self.handler.runner_amounts)

    def test_l2_modifier_updates_actual_loss_beyond_c_one(self):
        def phase(effect, invocation, *, channel, runner_modifier, **kwargs):
            self.phases.append(channel)
            if channel == 2:
                runner_modifier.mutate(1, 3, True)

        self.handler.event_lifecycle = SimpleNamespace(phase=phase)
        self.assertTrue(self.executor(7, -7))
        self.assertEqual(self.fight.actors[-7].ap, 3)
        self.assertEqual(self.states[0][5], (5227, 0, 30, 0, 100, 0))
        from wakfu_server.combat_effect_removal import _identity_fields

        self.assertEqual(_identity_fields(self.packets[0][1][19:])[4], 3)
        self.assertEqual(self.phases, [1, 2, 3, 4])

    def test_registered_faw_receiver_can_skip_absent_ap_without_fake_actor(self):
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_fake_fighter import fake_fighter_constructor
        from wakfu_server.combat_state_ledger import StateLedger

        definition = native_effect_areas()["1034"]
        self.fight.native_effect_areas = {
            91: dict(
                uid=91,
                reference=1034,
                cell=(2, 0, 0),
                native_area_contract="faW",
                native_obstacle_id=2,
                native_obstacle_source="QI.f(QK)",
                native_faw_constructor=fake_fighter_constructor(definition),
                native_running_effect_manager=True,
                state_ledger=StateLedger(91),
            )
        }
        seen = []

        def presence(recipient, stat):
            seen.append((recipient.id, recipient.native_is_area, stat))
            return False

        self.executor.characteristic_present = presence
        self.assertFalse(self.executor(7, 91))
        self.assertEqual(seen, [(91, True, 2)])
        self.assertNotIn(91, self.fight.actors)
        self.assertEqual(self.phases, [])
        self.assertEqual(self.packets, [])

    def test_preparation_failure_releases_fresh_runner(self):
        self.handler.context = lambda *a: StatExecutionContext(
            True, False, None, False, b"", None
        )
        with self.assertRaisesRegex(ValueError, "timing/guard authority"):
            self.executor(7, -7)
        self.assertEqual(self.phases, [1])
        self.assertFalse(self.handler.runner_amounts)
        self.assertFalse(self.handler.prepared)
        self.assertEqual(self.fight.actors[-7].ap, 6)

    def test_synthetic_retention_rejects_before_resource_mutation(self):
        self.handler.context = lambda *a: StatExecutionContext(
            True, True, None, True, b"", None
        )
        with self.assertRaisesRegex(ValueError, "cannot retain"):
            self.executor(7, -7)
        self.assertEqual(self.fight.actors[-7].ap, 6)
        self.assertEqual(self.states, [])
        self.assertEqual(self.packets, [])
        self.assertFalse(self.handler.runner_amounts)


class CollisionSourceTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server.combat_collision_source import NativeCollisionSourceAuthority
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        self.authority = NativeCollisionSourceAuthority.from_native_catalog()
        self.effect = json.loads(
            native_catalog.read_text(
                Path(__file__).parents[1] / "protocol/collision-effect.json"
            )
        )
        self.inv = EffectInvocation(
            -13,
            0,
            7,
            -7,
            (1, 0, 0),
            base_uid=0,
            native_retained_container={"present": False},
            native_explicit_target=True,
        )

    def test_sealed_source_has_actual_null_container_and_zone_policy(self):
        from wakfu_server.combat_trigger_identifiers import source_identifiers

        result = source_identifiers(
            None, self.effect, self.inv, synthetic_authority=self.authority
        )
        self.assertEqual(result["native_container"], {"present": False})
        self.assertEqual(
            result["zone_trigger_policy"],
            {"definition_present": True, "zone_flag": False, "point_area": True},
        )
        self.assertEqual(result["effect_action_id"], 55)

    def test_negative_reference_alone_is_not_authority(self):
        from wakfu_server.combat_trigger_identifiers import source_identifiers

        with self.assertRaisesRegex(ValueError, "synthetic identifier authority"):
            source_identifiers(
                None, self.effect, self.inv, synthetic_authority=object()
            )

    def test_runtime2254_does_not_change_definition_masks(self):
        from wakfu_server.combat_ordinary_events import OrdinaryResourceLossEvents

        lifecycle = object.__new__(OrdinaryResourceLossEvents)
        lifecycle.synthetic_authority = self.authority
        self.assertEqual(
            lifecycle.events(self.effect, 1, None, self.inv), (0, 77, 2254)
        )
        self.assertEqual(self.effect["target_masks"], [None] * 7)

    def test_no_inherited_spell_container_or_trigger(self):
        from dataclasses import replace

        with self.assertRaisesRegex(ValueError, "eXD.q construction"):
            self.authority.definition(
                self.effect, replace(self.inv, native_trigger_context={"uid": 1})
            )

    def test_source_metadata_for_secondary_state_uses_actual_synthetic_runner(self):
        from wakfu_server.combat_ordinary_events import OrdinaryResourceLossEvents

        lifecycle = object.__new__(OrdinaryResourceLossEvents)
        lifecycle.synthetic_authority = self.authority
        lifecycle.retention = SimpleNamespace(
            container=lambda inv: ({"container_present": False}, None)
        )
        source = lifecycle.source(
            self.effect, self.inv, uid=901, value=0, channel=1, plan=None
        )
        self.assertEqual(source.generic_effect, -13)
        self.assertEqual(source.event_ids, (0, 77, 2254))
        self.assertEqual(source.native_container, {"present": False})
        self.assertIsNone(source.source_parent_uid)
        self.assertEqual(
            source.cost_source,
            {"runner_class": "other", "spell_context": {"present": False}},
        )

    def test_actual_local_phase_router_preserves2254_for_all_four_phases(self):
        from wakfu_server.combat_ordinary_events import OrdinaryResourceLossEvents
        from wakfu_server.combat_resource_loss import resolve_resource_loss

        lifecycle = object.__new__(OrdinaryResourceLossEvents)
        lifecycle.synthetic_authority = self.authority
        lifecycle.preview = SimpleNamespace(
            actors={7: actor(7), -7: actor(-7)}, native_owned_group_effects={}
        )
        lifecycle.adapter = SimpleNamespace(actor_authority=lambda p, a: None)
        lifecycle.retention = SimpleNamespace(
            container=lambda inv: ({"container_present": False}, None),
            view=lambda: SimpleNamespace(entries=[]),
        )
        lifecycle.authority = object()
        observed = []
        lifecycle.replay = lambda source, **kwargs: observed.append(source)
        plan = resolve_resource_loss(
            stat_id=2,
            requested=1,
            current=6,
            minimum=0,
            maximum=6,
            caster_willpower=0,
            target_willpower=0,
            same_actor=False,
            ignores_willpower=False,
            frozen=False,
            suppresses_loss_state=False,
            random_fraction=lambda: 0,
        )
        for channel in (1, 2, 3, 4):
            lifecycle.phase(
                self.effect,
                self.inv,
                uid=901,
                value=0 if channel == 1 else 1,
                channel=channel,
                plan=None if channel == 1 else plan,
            )
        self.assertEqual(
            [source.channel for source in observed], [10, 1, 20, 2, 30, 3, 40, 4]
        )
        self.assertTrue(all(2254 in source.event_ids for source in observed))
        self.assertTrue(all(source.generic_effect == -13 for source in observed))
        self.assertTrue(
            all(source.native_container == {"present": False} for source in observed)
        )
        self.assertEqual(self.effect["target_masks"], [None] * 7)
