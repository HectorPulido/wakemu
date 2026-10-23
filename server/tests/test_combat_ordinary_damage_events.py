import unittest
from unittest.mock import patch
from random import Random
from copy import deepcopy
from dataclasses import replace
import test_combat_event_replay as native_fixture
from wakfu_server.combat_ordinary_authority import (
    OrdinaryActorAuthority,
    ordinary_cast_authority,
)
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_removal import _identity_fields


class OrdinaryDamageEventsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixture.NativeEventReplayTests.setUpClass()

    def setUp(self):
        f = native_fixture.NativeEventReplayTests()
        f.setUp()
        self.f = f
        self.fight = f.fight
        for actor in self.fight.actors.values():
            actor.effect_stats = {identity: 0 for identity in range(300)}
            actor.effect_stats[1] = actor.hp
            actor.effect_maxima = {identity: 0 for identity in range(300)}
            actor.effect_maxima[1] = actor.max_hp
            actor.effect_minima = {identity: 0 for identity in range(300)}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
            actor.direction = 0 if actor.id == 7 else 3
        target = self.fight.actors[-7]
        target.hp = target.max_hp = 12000
        target.effect_stats[1] = target.effect_maxima[1] = 12000
        actors = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=15, level=1, map_id=1134)},
            monsters={-7: dict(id=-7, ref=5525, map_id=1134)},
            decks={7: [6266]},
            excluded_decks={7: []},
        )
        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=actors,
            cast=ordinary_cast_authority(
                actors=actors,
                timing=NativeEffectTimingProvider({}),
                rng=Random(7),
                critical=False,
            ),
        )
        self.factory = NativeEffectRuntimeFactory(
            effects=f.effects,
            state_catalog={"effects": {}, "states": []},
            characteristic_registry={"effects": {"400": {"runner": "eXE"}}},
            action_id=1,
            contexts=self.adapter.contexts(),
        )
        with patch(
            "wakfu_server.combat_retained_runtime.native_retained_metadata",
            return_value=f.fixture["retained_metadata"],
        ):
            self.dispatcher, self.packets = self.factory(
                self.fight, dict(spell_id=6266, evaluation_level=1)
            )
        self.source = f.fixture["damage_source"]
        self.inv = EffectInvocation(self.source, 1, 7, -7, (1, 0, 0))

    def test_factory_produces_native_damage_events_automatically(self):
        seen = []
        original = self.dispatcher.replay_event.__class__.__call__

        def capture(replay, source, **kwargs):
            seen.append(
                (
                    source.channel,
                    source.value,
                    source.event_ids,
                    self.fight.actors[-7].hp,
                )
            )
            return original(replay, source, **kwargs)

        with patch.object(type(self.dispatcher.replay_event), "__call__", capture):
            self.assertTrue(self.dispatcher.execute(self.inv))
        self.assertEqual([s[0] for s in seen], [10, 1, 20, 2, 30, 3, 40, 4])
        self.assertEqual(
            [s[1] for s in seen], [0, 0, 10000, 10000, 10000, 10000, 10000, 10000]
        )
        self.assertEqual([s[3] for s in seen], [12000] * 4 + [2000] * 4)
        self.assertTrue(all(s[2] == (0, 2) for s in seen))
        fields = _identity_fields(self.packets[0][1][19:])
        self.assertEqual(
            (fields[1], fields[2], fields[3], fields[4]), (901, 901, self.source, 10000)
        )
        self.assertEqual(self.fight.native_effect_uid_next, 902)

    def test_damage_probability_rejection_has_only_phase1_and_fresh_uid(self):
        seen = []
        self.dispatcher.probability_accepts = lambda *args: False
        with patch.object(
            type(self.dispatcher.replay_event),
            "__call__",
            lambda _, source, **kwargs: seen.append(source.channel),
        ):
            self.assertFalse(self.dispatcher.execute(self.inv))
        self.assertEqual(seen, [10, 1])
        self.assertEqual(self.packets, [])
        self.assertEqual(self.fight.actors[-7].hp, 12000)
        self.assertEqual(self.fight.native_effect_uid_next, 902)

    def test_block_rng_follows_arithmetic_rounding_before_probability(self):
        calls = []

        def random():
            calls.append("round")
            return 0.5

        def block(*args):
            calls.append("block")
            return False

        handler = NativeDamageHandler(
            self.fight,
            [],
            action_id=1,
            allocate_uid=lambda: 800,
            context=lambda *args: DamageExecutionContext(
                False, True, None, True, 11, False, "FRONT"
            ),
            rng=random,
            block_after_calculation=block,
        )
        target = self.fight.actors[-7]
        target.hp = 99
        effect = dict(
            effect_class=1,
            parameters=[1, 0, 0, 0, 5, 0],
            native_effect_flags=[],
            native_localization_enabled=False,
        )
        handler(effect, {}, self.inv)
        self.assertEqual(calls, ["round", "block"])

    def test_actual_back_event_is_emitted_when_arithmetic_localization_is_disabled(
        self,
    ):
        self.fight.actors[
            -7
        ].direction = 1  # actual native BACK relative to source at0,0
        seen = []
        with patch.object(
            type(self.dispatcher.replay_event),
            "__call__",
            lambda _, source, **kwargs: seen.append((source.channel, source.event_ids)),
        ):
            self.dispatcher.execute(self.inv)
        self.assertEqual(seen[-2:], [(40, (0, 2, 29)), (4, (0, 2, 29))])
