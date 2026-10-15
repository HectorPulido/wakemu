import struct
import unittest
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_maximum_resource import NativeMaximumResourceHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server.combat_timed_expiration import prepare_timed_expiration


class MaximumResourceTests(unittest.TestCase):
    def setUp(self):
        actor = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        self.fight = Fight(
            8,
            [actor, npc],
            {actor.position, npc.position},
            {0: {actor.position}, 1: {npc.position}},
        )
        self.fight.ready(3)
        self.actor = actor
        actor.effect_stats = {2: 6, 3: 3, 4: 6}
        actor.effect_maxima = {2: 6, 3: 3, 4: 6}
        actor.effect_minima = {2: 0, 3: 0, 4: 0}
        actor.effect_base_minima = dict(actor.effect_minima)
        actor.effect_base_maxima = dict(actor.effect_maxima)
        actor.effect_percentages = {2: 0, 3: 0, 4: 0}
        actor.effect_frozen = frozenset()
        self.packets = []
        self.uid = 100

        def allocate():
            self.uid += 1
            return self.uid

        self.handler = NativeMaximumResourceHandler(
            self.fight,
            self.packets,
            action_id=1,
            allocate_uid=allocate,
            context=lambda *a: StatExecutionContext(
                True, True, None, True, None, StateTimer(7, 2, "start")
            ),
        )
        self.invocation = EffectInvocation(999, 1, 7, 7, (0, 0, 0))

    def apply(self, kind=41, amount=1, apply=1, remove=1, flags=()):
        return self.handler(
            dict(
                effect_class=kind,
                parameters=[amount, 0.0, apply, 0.0, remove, 0.0],
                native_effect_flags=list(flags),
            ),
            [],
            self.invocation,
        )

    def test_native_hp_maximum_and_current_restore_without_cap_metadata(self):
        actor = self.actor
        for name, value in (
            ("effect_stats", 60),
            ("effect_maxima", 60),
            ("effect_base_maxima", 60),
            ("effect_minima", 0),
            ("effect_base_minima", 0),
            ("effect_percentages", 0),
        ):
            getattr(actor, name)[1] = value
        self.handler(
            dict(effect_class=20, parameters=[25.0, 0.0, 1.0, 0.0, 1.0, 0.0]),
            [],
            self.invocation,
        )
        self.assertEqual((actor.hp, actor.max_hp), (85, 85))
        self.assertEqual((actor.effect_stats[1], actor.effect_maxima[1]), (85, 85))
        from wakfu_server.combat_maximum_resource import remove_maximum_resource

        remove_maximum_resource(self.handler, 101)
        self.assertEqual((actor.hp, actor.max_hp), (60, 60))
        self.assertEqual([p[0] for p in self.packets], [12613, 13560])

    def test_mp_boost_and_expiration(self):
        self.assertTrue(self.apply())
        self.assertEqual((self.actor.mp, self.actor.max_mp), (4, 4))
        preview, packets = prepare_timed_expiration(
            self.fight,
            actor_id=7,
            round_number=2,
            phase="start",
            action_id=2,
            registry={"effects": {}},
        )
        self.assertEqual((preview.actors[7].mp, preview.actors[7].max_mp), (3, 3))
        self.assertEqual(self.actor.mp, 4)
        self.assertEqual([op for op, _ in packets], [13560])

    def test_mp_gain_handler_snapshot_and_native_client_clamp_agree(self):
        from wakfu_server.combat_actor_snapshot import _int32
        from wakfu_server.combat_snapshot_wire import snapshot_characteristics
        from wakfu_server.combat_wire import actor_state, decode_actor_state
        from wakfu_server.combat_resource_pa_notifications import RAW_SOURCE

        identities = (1, 2, 3, 4, 35)
        definitions = {
            "characteristics": {
                str(identity): {"hard_minimum": 0, "hard_maximum": 100}
                for identity in identities
            }
        }
        copy_metadata = {
            "fresh_characteristics": {
                str(identity): {"over_max_current": False} for identity in identities
            }
        }
        actor = self.actor
        actor.effect_stats.update({1: actor.hp, 35: actor.initiative})
        actor.effect_minima.update({1: 0, 35: 0})
        actor.effect_maxima.update({1: actor.max_hp, 35: 100})
        actor.effect_base_minima = dict(actor.effect_minima)
        actor.effect_base_maxima.update({1: actor.max_hp, 35: 100})
        actor.effect_percentages.update({1: 0, 35: 0})
        actor.effect_resource_raw_currents = {2: actor.ap, 3: actor.mp}
        actor.native_resource_raw_current_source = RAW_SOURCE

        with patch(
            "wakfu_server.combat.combat_maximum_resource.native_actor_catalog",
            return_value=definitions,
        ), patch(
            "wakfu_server.combat.combat_actor_snapshot.native_actor_catalog",
            return_value=definitions,
        ), patch(
            "wakfu_server.combat.combat_character_copy_metadata.native_copy_characteristics",
            return_value=copy_metadata,
        ), patch(
            "wakfu_server.combat.combat_resource_pa_notifications.notify_resource_pa"
        ):
            self.apply(amount=2)
            payload = snapshot_characteristics(actor)
            envelope = decode_actor_state(
                12873, actor_state(12873, self.fight.id, actor.id, payload)
            )

        blob = envelope["state"]
        count = struct.unpack_from(">H", blob)[0]
        rows = {
            row[0]: row[1:]
            for row in (
                struct.unpack_from(">Biiii", blob, 2 + index * 17)
                for index in range(count)
            )
        }
        raw_current, raw_minimum, raw_maximum, percentage = rows[3]
        percent_product = _int32(raw_maximum * percentage)
        percent_adjustment = (
            abs(percent_product) // 100 * (1 if percent_product >= 0 else -1)
        )
        effective_maximum = min(100, max(0, _int32(raw_maximum + percent_adjustment)))
        effective_minimum = min(100, max(0, raw_minimum))

        # Native fff.aYS clamps raw current against aYU()/aYW().
        client_current = max(effective_minimum, min(effective_maximum, raw_current))
        self.assertEqual((actor.mp, actor.max_mp), (5, 5))
        self.assertEqual((raw_current, raw_maximum, percentage), (5, 5, 0))
        self.assertEqual(client_current, actor.mp)

    def test_hp_maximum_removal_preserves_one_hp_when_delta_exceeds_current(self):
        actor = self.actor
        for name, value in (
            ("effect_stats", 60),
            ("effect_maxima", 60),
            ("effect_base_maxima", 60),
            ("effect_minima", 0),
            ("effect_base_minima", 0),
            ("effect_percentages", 0),
        ):
            getattr(actor, name)[1] = value
        self.apply(kind=20, amount=25)
        actor.hp = actor.effect_stats[1] = 10
        from wakfu_server.combat_maximum_resource import remove_maximum_resource

        remove_maximum_resource(self.handler, 101)
        self.assertEqual((actor.hp, actor.effect_stats[1], actor.max_hp), (1, 1, 60))

    def test_hp_removal_equal_delta_uses_native_strict_greater_comparison(self):
        actor = self.actor
        for name, value in (
            ("effect_stats", 60),
            ("effect_maxima", 60),
            ("effect_base_maxima", 60),
            ("effect_minima", 0),
            ("effect_base_minima", 0),
            ("effect_percentages", 0),
        ):
            getattr(actor, name)[1] = value
        self.apply(kind=20, amount=25)
        actor.hp = actor.effect_stats[1] = 25
        from wakfu_server.combat_maximum_resource import remove_maximum_resource

        remove_maximum_resource(self.handler, 101)
        self.assertEqual((actor.hp, actor.max_hp), (0, 60))

    def test_native_cap_and_flag17(self):
        self.apply(amount=20)
        self.assertEqual((self.actor.mp, self.actor.max_mp), (8, 8))
        self.assertEqual(self.fight.owned_stat_effects[101]["actual"], 5)
        self.apply(amount=2, flags=[17])
        self.assertEqual((self.actor.mp, self.actor.max_mp), (10, 10))

    def test_apply_current_false_and_removal(self):
        self.apply(kind=31, amount=2, apply=0, remove=0)
        self.assertEqual((self.actor.ap, self.actor.max_ap), (6, 8))
        NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        ).remove(101)
        self.assertEqual((self.actor.ap, self.actor.max_ap), (6, 6))

    def test_wp_updates_snapshot_and_inconsistent_percent_rejects(self):
        self.apply(kind=191, amount=3)
        self.assertEqual(
            (self.actor.effect_stats[4], self.actor.effect_maxima[4]), (9, 9)
        )
        self.actor.effect_percentages[3] = 50
        with self.assertRaisesRegex(ValueError, "mismatch"):
            self.apply()
        self.assertEqual(self.uid, 101)

    def test_percent_raw_cap_and_overlapping_removal(self):
        self.actor.effect_percentages[3] = 50
        self.actor.mp = 4
        self.actor.max_mp = 4
        self.actor.effect_stats[3] = 4
        self.actor.effect_maxima[3] = 4
        self.apply(amount=1)
        self.assertEqual(
            (self.actor.mp, self.actor.max_mp, self.actor.effect_base_maxima[3]),
            (6, 6, 4),
        )
        self.apply(amount=1)
        self.assertEqual(
            (self.actor.mp, self.actor.max_mp, self.actor.effect_base_maxima[3]),
            (7, 7, 5),
        )
        remover = NativeStatHandler(
            self.fight,
            self.packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=None,
            context=None,
        )
        remover.remove(101)
        self.assertEqual(
            (self.actor.mp, self.actor.max_mp, self.actor.effect_base_maxima[3]),
            (6, 6, 4),
        )
        remover.remove(102)
        self.assertEqual(
            (self.actor.mp, self.actor.max_mp, self.actor.effect_base_maxima[3]),
            (4, 4, 3),
        )

    def test_native_percentage_integer_math(self):
        from wakfu_server.combat_maximum_resource import effective_maximum

        self.assertEqual(effective_maximum(3, 50, 0, 2147483647), 4)
        self.assertEqual(effective_maximum(3, -50, 0, 2147483647), 2)
        self.assertEqual(effective_maximum(2147483647, 100, 0, 2147483647), 2147483646)
