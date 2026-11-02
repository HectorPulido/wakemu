"""eWx1013 handles actual area PVs without inventing absent PA state.

Fixtures use the native area constructor and catalog. The armor lifecycle
observer is a focused test seam for checking Qe retention and release.
"""
from types import SimpleNamespace
import unittest

from wakfu_server import combat_armor
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import NativeStatHandler, StatExecutionContext
from wakfu_server.combat_state_timing import StateTimer

import test_combat_maximum_reduction_area as area_fixture
import test_combat_fake_fighter_area as area_constructor_fixture


class NativeArmorAreaCharacteristicsTests(unittest.TestCase):
    def _fixture(self):
        fixture = area_fixture.MaximumReductionAreaTests()
        fight, creator, allocated, packets = fixture.create(reference=1688)
        source = fight.actors[7]
        source.hp = source.max_hp = 1000
        source.effect_stats = {1: 1000, 97: 0, 120: 0, 121: 0}
        source.effect_maxima = {1: 1000, 97: 0}
        source.effect_minima = {97: 0}
        source.effect_frozen = frozenset()
        source.physical_radius = 0
        fight.phase = "active"
        fight.current = source
        fight.owned_stat_effects = {}
        packets.clear()
        calls = []
        rng_calls = []
        context = StatExecutionContext(
            True, True, None, True, b"", StateTimer(7, 2, "end")
        )
        handler = combat_armor.NativeArmorHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=creator.allocate_uid,
            context=lambda *_args: context,
            authority=lambda *_args: SimpleNamespace(is_player=False),
            rng=lambda: rng_calls.append("rng") or 0.5,
        )
        invocation = EffectInvocation(293112, 200, 7, 901, (2, 3, 0))
        effect = dict(
            effect_class=1013,
            parameters=[200, 0],
            variant=0,
            native_effect_flags=[],
            target_masks=[None] * 7,
        )

        class Lifecycle:
            def phase(self, _effect, _invocation, *, channel, value, **_kwargs):
                calls.append((channel, value))

            def register_applied(self, _effect, _invocation, uid):
                calls.append(("registered", uid))

        handler.event_lifecycle = Lifecycle()
        return (
            fixture,
            fight,
            creator,
            allocated,
            packets,
            handler,
            invocation,
            effect,
            calls,
            rng_calls,
        )

    def _stat_remover(self, fight, creator, packets):
        return NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=2,
            allocate_uid=creator.allocate_uid,
            context=lambda *_args: StatExecutionContext(
                True, True, None, True, b"", StateTimer(7, 2, "end")
            ),
        )

    def test_registered_faw_missing97_uses_partial_snapshot_and_retains_qe(self):
        (
            fixture,
            fight,
            creator,
            allocated,
            packets,
            handler,
            invocation,
            effect,
            calls,
            rng_calls,
        ) = self._fixture()
        row = fight.native_effect_areas[901]
        before = fixture.snapshot(row)
        invocation = handler.prepare(effect, {}, invocation)
        uid = invocation.native_running_uid
        # The native constructor allocates 901 for the area and 902 for its
        # created effect; eWx1013 then receives 903 from that same allocator.
        self.assertEqual(uid, 903)
        self.assertEqual(
            handler.prepared[uid][1], {"requested": 200, "room": (1 << 31) - 1}
        )
        self.assertEqual(allocated, [901, 902, 903])

        self.assertTrue(handler(effect, {}, invocation))
        entry = fight.owned_stat_effects[uid]
        self.assertEqual(entry["actual"], 200)
        self.assertEqual(
            (
                entry["target_id"],
                entry["effect_class"],
                entry["family"],
                entry["stat_id"],
            ),
            (901, 1013, "eWQ", 97),
        )
        self.assertIs(entry["native_absent_characteristic"], True)
        self.assertEqual(
            calls, [(1, 0), (2, 200), ("registered", uid), (3, 200), (4, 200)]
        )
        self.assertEqual(packets, [])  # No PA write or PR application packet.
        self.assertEqual(fixture.snapshot(row), before)
        self.assertNotIn(901, fight.actors)  # No fabricated Actor promotion.
        self.assertEqual(rng_calls, [])

        remover = self._stat_remover(fight, creator, packets)
        remover.remove(uid)
        self.assertFalse(fight.owned_stat_effects)
        self.assertEqual([opcode for opcode, _packet in packets], [13560])
        self.assertEqual(fixture.snapshot(row), before)
        self.assertEqual(rng_calls, [])

    def test_l3_removal_does_not_recreate_or_reaccess_released_qe(self):
        (
            fixture,
            fight,
            creator,
            allocated,
            packets,
            handler,
            invocation,
            effect,
            calls,
            rng_calls,
        ) = self._fixture()
        row = fight.native_effect_areas[901]
        before = fixture.snapshot(row)
        remover = self._stat_remover(fight, creator, packets)
        uid_box = []

        class RemovingLifecycle:
            def phase(self, _effect, _invocation, *, channel, value, **_kwargs):
                calls.append((channel, value))
                if channel == 3:
                    remover.remove(uid_box[0])

            def register_applied(self, _effect, _invocation, uid):
                uid_box.append(uid)

        handler.event_lifecycle = RemovingLifecycle()
        invocation = handler.prepare(effect, {}, invocation)
        uid_box.append(invocation.native_running_uid)
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(calls, [(1, 0), (2, 200), (3, 200), (4, 200)])
        self.assertFalse(fight.owned_stat_effects)
        self.assertEqual([opcode for opcode, _packet in packets], [13560])
        self.assertEqual(fixture.snapshot(row), before)
        self.assertEqual(rng_calls, [])

    def test_missing_or_tampered_area_authority_fails_closed_before_uid(self):
        (
            _,
            fight,
            _creator,
            allocated,
            packets,
            handler,
            invocation,
            effect,
            _calls,
            _rng,
        ) = self._fixture()
        initial_allocations = list(allocated)
        del fight.native_effect_areas[901]
        with self.assertRaisesRegex(ValueError, "actual native armor target PV"):
            handler(effect, {}, invocation)
        self.assertEqual(allocated, initial_allocations)
        self.assertEqual((fight.owned_stat_effects, packets), ({}, []))

        (
            _,
            fight,
            _creator,
            allocated,
            packets,
            handler,
            invocation,
            effect,
            _calls,
            _rng,
        ) = self._fixture()
        row = fight.native_effect_areas[901]
        row["native_faw_constructor"]["characteristic_ids"] = (1, 97)
        initial_allocations = list(allocated)
        with self.assertRaises(ValueError):
            handler(effect, {}, invocation)
        self.assertEqual(allocated, initial_allocations)
        self.assertEqual((fight.owned_stat_effects, packets), ({}, []))

        (
            _,
            fight,
            _creator,
            allocated,
            packets,
            handler,
            invocation,
            effect,
            _calls,
            _rng,
        ) = self._fixture()
        row = fight.native_effect_areas[901]
        row["native_area_contract"] = "unknown"
        initial_allocations = list(allocated)
        with self.assertRaises(ValueError):
            handler(effect, {}, invocation)
        self.assertEqual(allocated, initial_allocations)
        self.assertEqual((fight.owned_stat_effects, packets), ({}, []))

    def test_wall_trap_and_plain_areas_follow_native_qf_retention(self):
        from wakfu_server.combat_effect_area import native_effect_areas

        cases = (
            (1605, "fbd", True),  # Actual native wall, mandatory Qf.
            (1000, "fbc", False),  # Actual native trap without property-12 Qf.
            (314, "fbb", False),  # Actual native SIMPLE/plain area, no Qf.
        )
        for reference, contract, qf in cases:
            with self.subTest(reference=reference, contract=contract):
                fixture = area_fixture.MaximumReductionAreaTests()
                (
                    fight,
                    area_creator,
                    allocated,
                    area_packets,
                ) = area_constructor_fixture.NativeFakeFighterAreaTests().create()
                definition = native_effect_areas()[str(reference)]
                self.assertTrue(
                    area_creator(
                        {"effect_class": 339},
                        {"parameters": [reference]},
                        EffectInvocation(323843, 1, 7, None, (2, 3, 0)),
                    )
                )
                row = fight.native_effect_areas[901]
                self.assertEqual(row["native_area_contract"], contract)
                self.assertEqual(row["native_running_effect_manager"], qf)
                self.assertEqual(
                    definition["type"],
                    {"fbd": "WALL", "fbc": "TRAP", "fbb": "SIMPLE"}[contract],
                )
                before = fixture.snapshot(row)

                source = fight.actors[7]
                source.hp = source.max_hp = 1000
                source.effect_stats = {1: 1000, 97: 0, 120: 0, 121: 0}
                source.effect_maxima = {1: 1000, 97: 0}
                source.effect_minima = {97: 0}
                source.effect_frozen = frozenset()
                source.physical_radius = 0
                fight.phase = "active"
                fight.current = source
                fight.owned_stat_effects = {}
                area_packets.clear()
                packets = []
                context = StatExecutionContext(
                    True, True, None, True, b"", StateTimer(7, 2, "end")
                )
                armor = combat_armor.NativeArmorHandler(
                    fight,
                    packets,
                    action_id=2,
                    allocate_uid=area_creator.allocate_uid,
                    context=lambda *_args: context,
                    authority=lambda *_args: SimpleNamespace(is_player=False),
                    rng=lambda: 0.5,
                )
                calls = []

                class Lifecycle:
                    def phase(self, _effect, _invocation, *, channel, value, **_kwargs):
                        calls.append((channel, value))

                armor.event_lifecycle = Lifecycle()
                invocation = EffectInvocation(324818, 200, 7, 901, (2, 3, 0))
                effect = dict(
                    effect_class=1013,
                    parameters=[200, 0],
                    variant=0,
                    native_effect_flags=[],
                    target_masks=[None] * 7,
                )
                prepared = armor.prepare(effect, {}, invocation)
                uid = prepared.native_running_uid
                self.assertEqual(uid, 903)
                self.assertTrue(armor(effect, {}, prepared))
                self.assertEqual(fixture.snapshot(row), before)
                self.assertNotIn(901, fight.actors)
                self.assertEqual(packets, [])  # Missing PA mutes PR and PA writes.
                self.assertEqual(calls, [(1, 0), (2, 200), (3, 200), (4, 200)])
                if qf:
                    entry = fight.owned_stat_effects[uid]
                    self.assertEqual(entry["actual"], 200)
                    self.assertIs(entry["native_absent_characteristic"], True)
                    remover = self._stat_remover(fight, area_creator, packets)
                    remover.remove(uid)
                    self.assertFalse(fight.owned_stat_effects)
                    self.assertEqual([opcode for opcode, _ in packets], [13560])
                    self.assertEqual(fixture.snapshot(row), before)
                else:
                    self.assertFalse(fight.owned_stat_effects)


if __name__ == "__main__":
    unittest.main()
