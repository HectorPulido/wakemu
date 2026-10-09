import unittest
from types import SimpleNamespace
from wakfu_server.combat_fight_property import (
    NativeFightPropertyHandler,
    remove_fight_property,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation

TIME = bytes.fromhex("08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01")


class Authority:
    def __call__(self, fight, actor):
        return SimpleNamespace(targeting={"is_eGj": True})

    def property_counts(self, fight, actor):
        return dict(getattr(actor, "native_fight_property_counts", {}))


class NativeFightPropertyTests(unittest.TestCase):
    def fixture(self):
        actor = SimpleNamespace(
            id=-7, ap=6, mp=3, effect_minima={2: 0, 3: 0}, effect_stats={2: 6, 3: 3}
        )
        fight = SimpleNamespace(
            id=12, phase="active", actors={-7: actor}, owned_stat_effects={}
        )
        packets = []
        uids = iter(range(903, 910))
        handler = NativeFightPropertyHandler(
            fight,
            packets,
            action_id=3,
            allocate_uid=lambda: next(uids),
            context=lambda *args: StatExecutionContext(True, True, None, True, TIME),
            authority=Authority(),
        )
        return fight, actor, packets, handler

    def apply(self, handler, prop):
        return handler(
            {"effect_class": 447},
            {"parameters": [prop]},
            EffectInvocation(348444, 1, 7, -7, (0, 0, 0)),
        )

    def test_overlap_retirement_does_not_clear_other_owner(self):
        f, a, p, h = self.fixture()
        self.assertTrue(self.apply(h, 11))
        self.assertTrue(self.apply(h, 11))
        self.assertEqual(a.native_fight_property_counts, {11: 2})
        remove_fight_property(SimpleNamespace(fight=f, action_id=3, packets=p), 903)
        self.assertEqual(a.native_fight_property_counts, {11: 1})
        self.assertIn(11, a.native_fight_properties)
        remove_fight_property(SimpleNamespace(fight=f, action_id=3, packets=p), 904)
        self.assertEqual(a.native_fight_property_counts, {})
        self.assertEqual([o for o, _ in p], [12613, 12613, 13560, 13560])
        self.assertEqual(p[0][1][19:], p[2][1][18:-16])

    def test_pa_minimum_is_one_time_assignment_not_freeze_or_restore(self):
        for prop, stat, name in ((31, 2, "ap"), (34, 3, "mp")):
            f, a, p, h = self.fixture()
            self.apply(h, prop)
            self.assertEqual(getattr(a, name), 0)
            setattr(a, name, 4)
            a.effect_stats[stat] = 4
            remove_fight_property(SimpleNamespace(fight=f, action_id=3, packets=p), 903)
            self.assertEqual(getattr(a, name), 4)

    def test_unknown_special_callbacks_reject_before_any_mutation(self):
        for prop in (5, 18, 10, 25, 37):
            f, a, p, h = self.fixture()
            with self.assertRaises(ValueError):
                self.apply(h, prop)
            self.assertEqual(f.owned_stat_effects, {})
            self.assertFalse(hasattr(a, "native_fight_property_counts"))
            self.assertEqual(p, [])

    def test_native_invalid_enum_fails_without_property_or_packet(self):
        f, a, p, h = self.fixture()
        self.assertFalse(self.apply(h, 127))
        self.assertEqual(p, [])

    def test_feq_haste_noop_and_extra_turn_reset_with_real_fsm(self):
        from test_combat_state import FightStateTests
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority

        class TimelineAuthority(Authority):
            property_side_effect = OrdinaryActorAuthority.property_side_effect

        fight = FightStateTests().fight()
        fight.ready(1)
        actor = fight.actors[100]
        actor.effect_stats = {2: actor.ap, 3: actor.mp}
        actor.effect_minima = {2: 0, 3: 0}
        packets = []
        uids = iter(range(901, 910))
        h = NativeFightPropertyHandler(
            fight,
            packets,
            action_id=3,
            allocate_uid=lambda: next(uids),
            context=lambda *args: StatExecutionContext(True, True, None, True, TIME),
            authority=TimelineAuthority(),
        )

        def apply(prop):
            return h(
                {"effect_class": 447},
                {"parameters": [prop]},
                EffectInvocation(348444, 1, 100, 100, (0, 0, 0)),
            )

        initial = list(fight.order)
        apply(10)
        self.assertEqual(fight.order, initial)
        apply(37)
        self.assertEqual(fight.order, [100, 100, 200])
        fight.end_turn(1, 100, fight.turn_id)
        self.assertEqual(fight.current.id, 100)
        fight.end_turn(1, 100, fight.turn_id)
        self.assertEqual(fight.current.id, 200)
        fight.end_server_turn(200, fight.turn_id)
        self.assertEqual(fight.current.id, 100)
        self.assertEqual(fight.order, initial)
        self.assertIsNone(fight.native_base_turn_order)

    def test_visibility_uses_qi_affiliation_and_current_removal_position(self):
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
        from wakfu_server.wire import proto_fields

        class VisibilityAuthority(Authority):
            property_side_effect = OrdinaryActorAuthority.property_side_effect

            def __call__(self, f, a):
                return SimpleNamespace(targeting={"is_eGj": True, "bcN": a.team})

        f, a, p, h = self.fixture()
        h.authority = VisibilityAuthority()
        f.native_los_ignored_affiliations = frozenset()
        f.native_walk_ignored_affiliations = frozenset({1})
        a.team = 1
        a.position = (2, -3, 4)
        a.direction = 3
        self.apply(h, 5)
        self.assertEqual(f.native_los_ignored_affiliations, frozenset({1}))
        self.assertEqual(f.native_walk_ignored_affiliations, frozenset({1}))
        extra = dict(proto_fields(p[0][1][19:]))[66]
        self.assertEqual(extra.hex(), "7a0f080210fdffffffffffffffff011804800103880201")
        a.position = (3, -3, 4)
        remove_fight_property(SimpleNamespace(fight=f, action_id=3, packets=p), 903)
        self.assertEqual(a.position, (3, -3, 4))
        latest = dict(proto_fields(p[1][1][18:-16]))[66]
        self.assertEqual(dict(proto_fields(dict(proto_fields(latest))[122]))[8], 3)
        self.assertEqual(f.native_los_ignored_affiliations, frozenset())
        self.assertEqual(f.native_walk_ignored_affiliations, frozenset())

    def test_wp_notifications_do_not_reset_resource_and_require_known_listeners(self):
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority

        class NotifyAuthority(Authority):
            property_side_effect = OrdinaryActorAuthority.property_side_effect

            def __call__(self, f, a):
                return SimpleNamespace(targeting={"is_eGj": True}, is_player=True)

        f, a, p, h = self.fixture()
        h.authority = NotifyAuthority()
        a.native_resource_numeric_observers = {4: ()}
        a.effect_stats[4] = 6
        events = []
        f._event = lambda *args, **kw: events.append((args, kw))
        self.assertTrue(self.apply(h, 25))
        self.assertEqual(a.effect_stats[4], 6)
        self.assertEqual(len(events), 1)
        a.native_resource_numeric_observers = {4: ("eXb",)}
        before = dict(a.native_fight_property_counts)
        with self.assertRaises(ValueError):
            self.apply(h, 25)
        self.assertEqual(a.native_fight_property_counts, before)
        self.assertEqual(len(p), 1)
