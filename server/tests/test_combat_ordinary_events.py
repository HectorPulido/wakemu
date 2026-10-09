import unittest
from copy import deepcopy
from random import Random
from dataclasses import replace
import test_combat_event_replay as native_fixture
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    ordinary_cast_authority,
)
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
from wakfu_server.combat_healing_handler import NativeHealingHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation


class OrdinaryHealingEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixture.NativeEventReplayTests.setUpClass()

    def setUp(self):
        fixture = native_fixture.NativeEventReplayTests()
        fixture.setUp()
        self.f = fixture
        self.fight = fixture.fight
        for actor in self.fight.actors.values():
            actor.effect_stats = {1: actor.hp, 92: 0, 97: 0, 100: 0, 32: 0}
            actor.effect_maxima = {1: actor.max_hp, 92: 0, 32: 1000}
            actor.effect_minima = {32: 0}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        actors = OrdinaryActorAuthority(
            characters={
                7: dict(
                    id=7,
                    breed=15,
                    level=self.fight.actors[7].effective_level,
                )
            },
            monsters={-7: dict(id=-7, ref=5525)},
            decks={7: [6266]},
            excluded_decks={7: []},
        )
        timing = NativeEffectTimingProvider({})
        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=actors,
            cast=ordinary_cast_authority(
                actors=actors, timing=timing, rng=Random(7), critical=False
            ),
        )
        self.events = OrdinaryHealingEvents(
            adapter=self.adapter,
            preview=self.fight,
            plan={},
            replay=fixture.replay,
            retention=fixture.retention,
        )
        self.handler = NativeHealingHandler(
            self.fight,
            fixture.packets,
            action_id=1,
            allocate_uid=self.fight.allocate_effect_uid,
            context=lambda e, i: self.adapter.cast.healing(self.fight, {}, e, i),
            rng=lambda: 0.99,
        )
        self.handler.event_lifecycle = self.events
        self.effect = fixture.effects[str(fixture.fixture["source"])]
        self.inv = EffectInvocation(fixture.fixture["source"], 1, 7, 7, (0, 0, 0))
        fixture.dispatcher.handlers[25] = self.handler
        fixture.dispatcher.condition_context = lambda i: self.adapter.condition(
            self.fight, {}, fixture.effects[str(i.reference)], i
        )
        fixture.dispatcher.prepare_effect = (
            lambda e, v, i: self.handler.prepare(e, v, i)
            if e["effect_class"] == 25
            else i
        )

    def assert_unsubscribed_owned_child_uses_cvx(self, packets, retention):
        from wakfu_server.combat_effect_removal import _identity_fields
        from wakfu_server.combat_native_timing_context import native_definition_timing

        child = next(iter(self.fight.owned_stat_effects.values()))
        child_effect = self.f.effects["308267"]
        child_invocation = EffectInvocation(308267, 1, 7, 7, (0, 0, 0))
        metadata = retention.definition(child_effect, child_invocation)
        self.assertIs(metadata["subscription"], False)
        native = native_definition_timing(child_effect, child_invocation.level)
        self.assertIs(native["retained"], True)  # Native Ty: eVy duration is nonzero.
        self.assertIs(native["delay"], False)

        # Native aTR cannot observe this persistent, unsubscribed eXE runner;
        # Qf therefore keeps the evaluated payload through cvX/eIK=false.
        child_identity = _identity_fields(
            bytes.fromhex(child["payload"]), integer_fields=(1, 3)
        )
        self.assertEqual(child_identity[3], 308267)
        deliveries = [
            data
            for opcode, data in packets
            if opcode == 12613
            and len(data) >= 19
            and int.from_bytes(data[13:17], "big", signed=True) == 400
        ]
        self.assertEqual(len(deliveries), 1)
        delivered_identity = _identity_fields(deliveries[0][19:], integer_fields=(1, 3))
        self.assertEqual(
            (delivered_identity[1], delivered_identity[3]),
            (child_identity[1], 308267),
        )

    def test_real_healing_executes_listener_and_removes_it_automatically(self):
        target = self.fight.actors[7]
        target.hp = 50
        target.effect_stats[1] = 50
        self.assertTrue(self.f.dispatcher.execute(self.inv))
        self.assertEqual(target.hp, 60)
        self.assertEqual(self.fight.native_owned_group_effects, {})
        child = next(iter(self.fight.owned_stat_effects.values()))
        from wakfu_server.combat_effect_removal import _identity_fields

        self.assertEqual(_identity_fields(bytes.fromhex(child["payload"]))[3], 308267)
        self.assert_unsubscribed_owned_child_uses_cvx(self.f.packets, self.f.retention)
        self.assertEqual(
            [opcode for opcode, _ in self.f.packets], [13497, 12613, 12613, 13560]
        )
        self.assertEqual(self.fight.native_effect_uid_next, 904)

    def test_native_phases_have_initial_requested_and_consumed_values(self):
        seen = []

        class Capture:
            def phase(_, effect, invocation, **data):
                seen.append((data["channel"], data["value"], self.fight.actors[7].hp))

        self.handler.event_lifecycle = Capture()
        self.fight.actors[7].hp = 50
        self.f.dispatcher.execute(self.inv)
        self.assertEqual(seen, [(1, 0, 50), (2, 1000, 50), (3, 10, 60), (4, 10, 60)])

    def test_local_recipient_channel_order_matches_Qe_L(self):
        seen = []
        self.events.replay = lambda source, **kwargs: seen.append(
            (source.channel, source.manager_actor_id)
        )
        self.events.phase(self.effect, self.inv, uid=800, value=1, channel=3)
        self.assertEqual(seen, [(30, 7), (3, 7)])

    def test_changed_relationships_reject_before_replay(self):
        self.fight.actors[7].native_carrier_id = -7
        with self.assertRaisesRegex(ValueError, "relationships"):
            self.f.dispatcher.execute(self.inv)
        self.assertEqual(self.fight.actors[7].hp, 60)
        self.assertEqual(self.fight.owned_stat_effects, {})

    def test_factory_binds_ordinary_events_without_manual_emitter(self):
        from unittest.mock import patch
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory

        metadata = self.f.fixture["retained_metadata"]
        factory = NativeEffectRuntimeFactory(
            effects=self.f.effects,
            state_catalog={"effects": {}, "states": []},
            characteristic_registry={"effects": {"400": {"runner": "eXE"}}},
            action_id=1,
            contexts=self.adapter.contexts(),
        )
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_metadata",
            return_value=metadata,
        ):
            dispatcher, packets = factory(
                self.fight, dict(spell_id=6266, evaluation_level=1)
            )
            self.fight.actors[7].hp = 50
            self.fight.actors[7].effect_stats[1] = 50
            self.assertTrue(dispatcher.execute(self.inv))
        self.assertEqual(self.fight.native_owned_group_effects, {})
        self.assertEqual(len(self.fight.owned_stat_effects), 1)
        self.assert_unsubscribed_owned_child_uses_cvx(
            packets, dispatcher.group_retention
        )
        self.assertEqual([kind for kind, _ in packets], [12613, 12613, 13560])

    def test_clone_original_area_uses_registered_bag_guard_provenance(self):
        from unittest.mock import patch

        listener = self.fight.native_owned_group_effects[900]
        listener["invocation"]["target_id"] = 91
        invocation = replace(self.inv, target_id=91, base_uid=900)
        definitions = {
            "111": dict(type="GLYPH", native_area_properties=[], entry_masks=[])
        }

        def area(removed=False, source="Qq.constructor"):
            return dict(
                uid=91,
                reference=111,
                cell=(2, 3, 0),
                native_area_contract="faY",
                native_running_effect_manager=False,
                native_qq_bhi=removed,
                native_qq_guard_source=source,
            )

        self.fight.native_effect_areas = {91: area()}
        with patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=definitions,
        ), patch(
            "wakfu_server.combat_ordinary_death.corpse_gate_bypassed",
            return_value=False,
        ):
            self.assertTrue(self.events.executable(self.effect, invocation, None))
            self.fight.native_effect_areas[91] = area(True, "Qq.b")
            self.assertFalse(self.events.executable(self.effect, invocation, None))
            self.fight.native_effect_areas[91] = area()
            self.fight.native_effect_areas[91].pop("native_qq_bhi")
            self.fight.native_effect_areas[91].pop("native_qq_guard_source")
            with self.assertRaisesRegex(ValueError, "guard provenance"):
                self.events.executable(self.effect, invocation, None)

    def test_undead_bbw_suppresses_all_healing_events_even_with_bypass33(self):
        self.fight.actors[7].native_fight_properties = {20}
        seen = []
        self.events.replay = lambda source, **kwargs: seen.append(source.event_ids)
        effect = dict(self.effect, native_effect_flags=[17, 33])
        self.events.phase(effect, self.inv, uid=800, value=10, channel=3)
        self.assertEqual(seen, [(), ()])
