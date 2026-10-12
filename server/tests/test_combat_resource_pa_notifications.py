import copy
import unittest
from types import SimpleNamespace

from wakfu_server.combat_resource_pa_notifications import (
    attach_ap_listener,
    detach_ap_listener,
    notify_resource_pa,
    RAW_SOURCE,
    set_resource_current,
    set_resource_maximum,
    shift_resource_current,
)
from wakfu_server import native_catalog


class ResourcePANotificationTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(
            id=7,
            ap=6,
            max_ap=6,
            mp=3,
            max_mp=3,
            effect_stats={2: 6, 3: 3},
            effect_maxima={2: 6, 3: 3},
            effect_base_maxima={2: 6, 3: 3},
            effect_minima={2: 0, 3: 0},
            effect_base_minima={2: 0, 3: 0},
            effect_percentages={2: 0, 3: 0},
            effect_frozen=frozenset(),
            effect_resource_raw_currents={2: 6, 3: 3},
            native_resource_raw_current_source=RAW_SOURCE,
        )
        fight = SimpleNamespace(actors={7: actor})
        return fight, actor

    def test_current_loss_then_maximum_change_preserves_exact_listener_deltas(self):
        fight, actor = self.fixture()
        attach_ap_listener(fight, actor, 99)
        set_resource_current(fight, actor, 2, 4)
        self.assertEqual((actor.mp, actor.max_mp), (1, 3))
        set_resource_maximum(fight, actor, 2, 8)
        self.assertEqual((actor.mp, actor.max_mp), (1, 5))
        self.assertEqual(detach_ap_listener(fight, actor, 99), 2)
        set_resource_current(fight, actor, 2, 2)
        self.assertEqual(actor.mp, 1)

    def test_non_overmax_ap_assignment_does_not_leak_into_preview_maximum_growth(self):
        fight, actor = self.fixture()
        attach_ap_listener(fight, actor, 99)
        candidate = copy.deepcopy(fight)
        target = candidate.actors[7]
        set_resource_current(candidate, target, 2, 8)
        set_resource_maximum(candidate, target, 2, 8)
        self.assertEqual((target.mp, target.max_mp), (3, 5))
        self.assertEqual((actor.mp, actor.max_mp), (3, 3))
        self.assertEqual(fight.native_resource_pa_listeners[7][0]["rBg"], 0)

    def test_no_current_change_does_not_fire_and_malformed_listener_rejects(self):
        fight, actor = self.fixture()
        attach_ap_listener(fight, actor, 99)
        before = copy.deepcopy(fight.native_resource_pa_listeners)
        notify_resource_pa(fight, actor, 2, before_current=6)
        self.assertEqual(fight.native_resource_pa_listeners, before)
        fight.native_resource_pa_listeners[7][0]["source"] = "unproved"
        with self.assertRaisesRegex(ValueError, "listener authority"):
            notify_resource_pa(fight, actor, 2, before_current=6)

    def test_actual_handler_installs_property_listener_and_removal_restores_maximum(
        self,
    ):
        from wakfu_server.combat_ap_as_mp import NativeAPAsMPHandler, remove_ap_as_mp
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext, _write

        fight, actor = self.fixture()
        fight.id, fight.phase, fight.owned_stat_effects = 8, "active", {}
        actor.native_fight_property_counts = {}
        packets = []
        handler = NativeAPAsMPHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 99,
            rng=lambda: 0.5,
            context=lambda *_: StatExecutionContext(True, True, None, True, None),
            authority=SimpleNamespace(
                property_counts=lambda *_: actor.native_fight_property_counts
            ),
        )
        invocation = EffectInvocation(999, 1, 7, 7, (0, 0, 0))
        self.assertTrue(handler({"effect_class": 808}, [], invocation))
        # cvY/aTR observes a runner without calling eWq.c(). The retained
        # cvX/aVo branch must execute the decoded MP/property/listener mutation.
        self.assertEqual(packets[-1][0], 12613)
        self.assertEqual(packets[-1][1][12], 0)
        # eWq uses PA.or directly, bypassing eWN's MP-family PC.aZt cap8.
        self.assertEqual(
            (actor.mp, actor.max_mp, actor.effect_base_maxima[3]), (9, 9, 9)
        )
        self.assertEqual(actor.native_fight_property_counts[50], 1)
        _write(fight, 7, actor, 2, 4)
        self.assertEqual(actor.mp, 7)
        remove_ap_as_mp(handler, 99)
        self.assertEqual((actor.mp, actor.max_mp), (3, 3))
        self.assertNotIn(50, actor.native_fight_properties)
        self.assertEqual(packets[-1][0], 13560)
        # Removing the form detaches the client/server AP observer; subsequent
        # AP spending must no longer consume the restored human-form MP.
        set_resource_current(fight, actor, 2, 2)
        self.assertEqual((actor.mp, actor.max_mp), (3, 3))

    def test_expandable_mp_without_fzb_clamps_on_and_or_to_effective_maximum(self):
        fight, actor = self.fixture()
        set_resource_current(fight, actor, 3, 7)
        self.assertEqual((actor.mp, actor.effect_resource_raw_currents[3]), (3, 3))
        set_resource_maximum(fight, actor, 3, 5)
        self.assertEqual((actor.mp, actor.effect_resource_raw_currents[3]), (3, 3))
        shift_resource_current(fight, actor, 3, 1, subtract=True)
        self.assertEqual((actor.mp, actor.effect_resource_raw_currents[3]), (2, 2))
        set_resource_maximum(fight, actor, 3, 8)
        self.assertEqual(actor.mp, 2)

    def test_frozen_current_stays_raw_while_maximum_changes_effective_value(self):
        fight, actor = self.fixture()
        actor.effect_frozen = frozenset({3})
        set_resource_current(fight, actor, 3, 1)
        self.assertEqual(actor.effect_resource_raw_currents[3], 3)
        set_resource_maximum(fight, actor, 3, 2)
        self.assertEqual((actor.mp, actor.effect_resource_raw_currents[3]), (2, 3))
        set_resource_maximum(fight, actor, 3, 5)
        self.assertEqual(actor.mp, 3)

    def test_native_ap_assignment950_uses_constructor_setter_operand_for_raw_current(
        self,
    ):
        import json
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_force_characteristic import (
            NativeForcedCharacteristicHandler,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext

        fight, actor = self.fixture()
        fight.id, fight.phase, fight.owned_stat_effects = 8, "active", {}
        events = []
        fight._event = lambda kind, **fields: events.append((kind, fields))
        actor.ap = actor.max_ap = 0
        actor.effect_stats[2] = actor.effect_maxima[2] = 0
        actor.effect_base_maxima[2] = actor.effect_resource_raw_currents[2] = 0
        registry = json.loads(
            native_catalog.read_text(DATA_ROOT / "effect-characteristic-registry.json")
        )
        handler = NativeForcedCharacteristicHandler(
            fight,
            [],
            registry,
            action_id=1,
            allocate_uid=lambda: 101,
            rng=lambda: 0.5,
            context=lambda *_: StatExecutionContext(True, True, None, True, None),
        )
        self.assertTrue(
            handler(
                {"effect_class": 950, "parameters": [4.0, 0.0, 1.0, 0.0]},
                [],
                EffectInvocation(999, 1, 7, 7, (0, 0, 0)),
            )
        )
        self.assertEqual(
            (actor.ap, actor.max_ap, actor.effect_resource_raw_currents[2]), (4, 4, 4)
        )
        self.assertEqual(events[-1][1]["actual"], 4)
