import copy
import unittest
from types import SimpleNamespace

from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
)
from wakfu_server.combat_native_actor_lookup import native_actor_population
from wakfu_server.combat_event_replay import (
    NativeCloneAuthority,
    NativeEventReplay,
    NativeEventSource,
)
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_runtime_adapter import (
    NativeActorAuthority,
    NativeCastAuthority,
    NativeServerRuntimeAdapter,
)
from wakfu_server.combat_effect_resolver import (
    NativeEffectResolver,
    UnknownEffectResolution,
)
from wakfu_server.combat_state import Actor, Fight


class RetiredRetainedSourceTests(unittest.TestCase):
    def setUp(self):
        self.caster = Actor(130, 0, (0, 0, 0), 1, 6, 3, 10, 31)
        self.caster.hp = 0  # Raw native death transition; no actor reconstruction.
        self.target = Actor(209, 1, (1, 0, 0), 50, 6, 3, 8, 20)
        self.other = Actor(100, 0, (2, 0, 0), 50, 6, 3, 9, 20)
        self.actors = (self.caster, self.target, self.other)
        self.fight = Fight(
            12403,
            self.actors,
            {(0, 0, 0), (1, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0), (2, 0, 0)}, 1: {(1, 0, 0)}},
        )
        for actor in self.actors:
            actor.effect_stats = {92: 0, 97: 0, 100: 0}
            actor.effect_maxima = {92: 100}
            actor.effect_minima = {}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        initialize_global_pv_collections(self.fight, (130, 209, 100))
        set_global_fighter_status(self.fight, 130, "OUT_OF_PLAY")
        set_global_fighter_status(self.fight, 100, "OUT_OF_PLAY")

        self.authorities = {
            actor.id: NativeActorAuthority(
                targeting={"actor": actor.id},
                is_player=False,
                deck_spell_ids=frozenset(),
                excluded_deck_spell_ids=frozenset(),
                is_carried=False,
                breed_id=330,
                summon_count=0,
                summon_counts_by_breed={},
                occupant_blocks=False,
            )
            for actor in self.actors
        }
        policies = [lambda *args: None for _ in range(10)]
        self.adapter = NativeServerRuntimeAdapter(
            actor_authority=lambda _fight, actor: self.authorities[actor.id],
            cast=NativeCastAuthority(*policies),
        )

    def test_retained_event_source_context_does_not_restore_retired_caster_to_population(
        self,
    ):
        # The retained 327061 activation belongs to owner 130 and targets the
        # still-live Gobgob 209 after the owner's native OUT_OF_PLAY transition.
        before = copy.deepcopy(self.fight.native_global_pv_collections)
        invocation = EffectInvocation(327061, 31, 130, 209, self.target.position)

        contexts = self.adapter.targets(self.fight, {}, {}, invocation)

        self.assertEqual(set(contexts), {130, 209})
        self.assertNotIn(100, contexts)
        self.assertEqual(contexts[130], {"actor": 130})
        self.assertEqual(contexts[209], {"actor": 209})
        self.assertEqual(
            tuple(actor.id for actor in native_actor_population(self.fight)), (209,)
        )
        self.assertEqual(self.fight.native_global_pv_collections, before)
        self.assertEqual(self.target.hp, 50)

    def test_unknown_retained_caster_is_not_fabricated_as_a_target_context(self):
        invocation = EffectInvocation(327061, 31, 999, 209, self.target.position)

        contexts = self.adapter.targets(self.fight, {}, {}, invocation)

        self.assertEqual(set(contexts), {209})
        self.assertNotIn(999, contexts)
        self.assertEqual(
            tuple(a.id for a in native_actor_population(self.fight)), (209,)
        )

        resolver = NativeEffectResolver(
            actors=lambda _effect, _invocation: native_actor_population(self.fight),
            native_context=lambda *_args: {},
            context=lambda *_args: None,
        )
        with self.assertRaisesRegex(UnknownEffectResolution, "Missing caster"):
            resolver.candidate_invocations({}, invocation)

    def test_retained_event_replay_rebinds_retired_source_without_readding_it(self):
        entry = RetainedEffect(
            uid=900,
            target_id=209,
            effect_class=400,
            generic_effect=327061,
            manager_id=209,
            container_present=False,
        )
        row = {
            "invocation": {
                "reference": 327061,
                "level": 31,
                "caster_id": 209,
                "target_id": 209,
                "cell": self.target.position,
                "base_uid": 900,
            },
            "native_subscription_masks": [None, None, None, None, None, [1003], None],
            "native_effect_flags": [],
            "execution_count": -1,
        }
        self.fight.native_owned_group_effects = {900: row}
        definition = {
            "event_global_subscription": False,
            "event_reverse_subscription": False,
            "event_priority": 0,
            "event_target_code": 5,
            "event_caster_code": 4,
        }

        class Retention:
            def __init__(inner_self):
                inner_self.fight = self.fight
                inner_self.metadata = {"effects": {"327061": definition}}

            def view(inner_self):
                return SimpleNamespace(entries=(entry,))

            @staticmethod
            def replay_container(*_args):
                return None

        observations = []

        class Dispatcher:
            effects = {"327061": definition}

            def execute_activation(_self, invocation, **_kwargs):
                observations.append(invocation)
                contexts = self.adapter.targets(self.fight, {}, {}, invocation)
                self.assertEqual(contexts[130], {"actor": 130})
                self.assertEqual(contexts[209], {"actor": 209})
                self.assertNotIn(100, contexts)
                return True

        source = NativeEventSource(
            uid=42,
            generic_effect=327061,
            value=0,
            caster_id=130,
            target_id=209,
            cell=self.target.position,
            event_ids=(1003,),
            channel=6,
            manager_actor_id=209,
            source_parent_uid=None,
            suppresses_level_one=False,
            suppresses_all=False,
            suppressed=False,
            native_events_verified=True,
        )
        replay = NativeEventReplay(Dispatcher(), Retention())
        authority = NativeCloneAuthority(lambda *_args: True, lambda *_args: None)

        before = copy.deepcopy(self.fight.native_global_pv_collections)
        self.assertEqual(replay(source, authority=authority), (True,))

        self.assertEqual(len(observations), 1)
        self.assertEqual(
            (observations[0].caster_id, observations[0].target_id), (130, 209)
        )
        self.assertEqual(
            tuple(a.id for a in native_actor_population(self.fight)), (209,)
        )
        self.assertEqual(self.fight.native_global_pv_collections, before)

    def test_missing_authority_for_retired_source_fails_closed(self):
        self.authorities.pop(130)
        invocation = EffectInvocation(327061, 31, 130, 209, self.target.position)

        with self.assertRaises(KeyError):
            self.adapter.targets(self.fight, {}, {}, invocation)

        self.assertEqual(
            tuple(a.id for a in native_actor_population(self.fight)), (209,)
        )
        self.assertEqual(self.target.hp, 50)


if __name__ == "__main__":
    unittest.main()
