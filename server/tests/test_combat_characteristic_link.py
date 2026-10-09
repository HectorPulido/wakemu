import copy
import json
import unittest
from types import SimpleNamespace
from wakfu_server.combat_characteristic_link import (
    NativeCharacteristicLinkHandler,
    ObservableCharacteristicStats,
    link_contribution,
    remove_characteristic_link,
    bind_characteristic_stats,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext, _write
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server import native_catalog


class NativeCharacteristicLinkTests(unittest.TestCase):
    def fixture(self):
        actors = {
            identity: SimpleNamespace(
                id=identity,
                effect_stats={7: value, 8: value, 103: 10, 104: 10},
                effect_minima={7: -1000, 8: -1000, 103: -1000, 104: -1000},
                effect_maxima={7: 1000, 8: 1000, 103: 1000, 104: 1000},
                effect_frozen=frozenset(),
            )
            for identity, value in ((7, 20), (9, 60))
        }
        fight = SimpleNamespace(
            id=8, actors=actors, owned_stat_effects={}, phase="active"
        )
        packets = []
        count = iter(range(101, 200))
        handler = NativeCharacteristicLinkHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: next(count),
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
        )
        invocation = EffectInvocation(999, 40, 7, 9, (0, 0, 0))
        return fight, handler, packets, invocation

    def effect(self, params=(7, 103, 0, 50)):
        return dict(
            effect_class=1038, parameters=[v for value in params for v in (value, 0)]
        )

    def test_real_source_changes_replace_previous_contribution_and_detach(self):
        fight, handler, packets, invocation = self.fixture()
        self.assertTrue(handler(self.effect(), [], invocation))
        self.assertEqual(fight.actors[7].effect_stats[103], 40)
        _write(fight, 7, fight.actors[9], 7, 80)
        self.assertEqual(fight.actors[7].effect_stats[103], 50)
        _write(fight, 7, fight.actors[9], 7, 20)
        self.assertEqual(fight.actors[7].effect_stats[103], 20)
        remove_characteristic_link(handler, 101)
        self.assertEqual(fight.actors[7].effect_stats[103], 10)
        fight.actors[9].effect_stats[7] = 80
        self.assertEqual(fight.actors[7].effect_stats[103], 10)
        self.assertEqual([packet[0] for packet in packets], [13497, 13560])

    def test_reverse_upper_lower_and_level_parameter(self):
        fight, handler, packets, invocation = self.fixture()
        self.assertTrue(handler(self.effect((7, 103, 1, 50, 5, 8)), [], invocation))
        self.assertEqual(fight.actors[9].effect_stats[103], 18)
        self.assertEqual(fight.actors[7].effect_stats[103], 10)
        fight.actors[7].effect_stats.update({7: 100})
        self.assertEqual(fight.actors[9].effect_stats[103], 18)

    def test_clamped_actual_contribution_and_cancel_preserve_other_changes(self):
        fight, handler, packets, invocation = self.fixture()
        fight.actors[7].effect_maxima[103] = 25
        handler(self.effect(), [], invocation)
        self.assertEqual(fight.native_characteristic_links[101]["actual"], 15)
        fight.actors[7].effect_stats[103] = 20
        remove_characteristic_link(handler, 101)
        self.assertEqual(fight.actors[7].effect_stats[103], 5)

    def test_transaction_deepcopy_rebinds_observers_and_plain_snapshot(self):
        fight, handler, packets, invocation = self.fixture()
        handler(self.effect(), [], invocation)
        clone = copy.deepcopy(fight)
        self.assertIs(clone.actors[9].effect_stats._fight, clone)
        clone.actors[9].effect_stats[7] = 80
        self.assertEqual(clone.actors[7].effect_stats[103], 50)
        self.assertEqual(fight.actors[7].effect_stats[103], 40)
        plain = json.loads(json.dumps(snapshot(clone)))
        self.assertEqual(plain["actors"]["7"]["effect_stats"]["103"], 50)
        self.assertEqual(plain["native_characteristic_links"]["101"]["actual"], 40)
        self.assertNotIn("_fight", plain["actors"]["7"]["effect_stats"])

    def test_missing_or_stale_listener_registration_and_cycles_reject(self):
        fight, handler, packets, invocation = self.fixture()
        handler(self.effect(), [], invocation)
        reverse = EffectInvocation(1000, 40, 9, 7, (0, 0, 0))
        with self.assertRaisesRegex(ValueError, "Cyclic"):
            handler(self.effect((103, 7)), [], reverse)
        fight.actors[9].effect_stats = dict(fight.actors[9].effect_stats)
        with self.assertRaisesRegex(ValueError, "pre-mutation"):
            bind_characteristic_stats(fight)

    def test_signed_int_overflow_and_truncation(self):
        self.assertEqual(link_contribution(-3, 50), -1)
        self.assertEqual(link_contribution(2147483647, 100), -1)
        self.assertEqual(link_contribution(50, 100, 20, 30), 30)

    def test_frozen_and_resource_contracts(self):
        fight, handler, packets, invocation = self.fixture()
        fight.actors[7].effect_frozen = frozenset({103})
        handler(self.effect(), [], invocation)
        self.assertEqual(fight.native_characteristic_links[101]["actual"], 0)
        self.assertEqual(fight.actors[7].effect_stats[103], 10)
        with self.assertRaisesRegex(ValueError, "Resource PA"):
            handler(self.effect((1, 103)), [], invocation)

    def test_real_stat_handler_gain_revert_and_link_removal_routing(self):
        from wakfu_server.combat_stat_handler import NativeStatHandler
        from wakfu_server.paths import DATA_ROOT

        fight, handler, packets, invocation = self.fixture()
        for actor in fight.actors.values():
            actor.hp = actor.max_hp = 10
            actor.max_ap = actor.max_mp = 6
        fight.current = fight.actors[7]
        fight._event = lambda *args, **kwargs: None
        handler(self.effect(), [], invocation)
        registry = json.loads(
            native_catalog.read_text(DATA_ROOT / "effect-characteristic-registry.json")
        )
        stat = NativeStatHandler(
            fight,
            packets,
            registry,
            action_id=1,
            allocate_uid=lambda: 102,
            context=lambda *args: StatExecutionContext(
                True, True, None, True, b"", None
            ),
        )
        self.assertTrue(
            stat(dict(effect_class=173, parameters=[20, 0]), {}, invocation)
        )
        self.assertEqual(fight.actors[7].effect_stats[103], 50)
        stat.remove(102)
        self.assertEqual(fight.actors[7].effect_stats[103], 40)
        stat.remove(101)
        self.assertEqual(fight.actors[7].effect_stats[103], 10)
        self.assertIsInstance(packets[-1][1], bytes)
        self.assertEqual(packets[-1][0], 13560)
