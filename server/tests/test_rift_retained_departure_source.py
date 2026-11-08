"""A departed Rift caster may source its live retained effects only."""
import unittest
from copy import deepcopy
import json
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_adapter import (
    NativeActorAuthority,
    NativeServerRuntimeAdapter,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_native_actor_lookup import native_actor_population
from wakfu_server.combat_summon import RegisteredSummonAuthority


class RetainedDepartureSourceTests(unittest.TestCase):
    @staticmethod
    def actor(identity, team, cell, owner=None, controlled=False):
        actor = Actor(identity, team, cell, 100, 6, 3, 10, 230, owner, controlled)
        actor.effect_stats = {92: 0, 97: 0, 100: 0}
        actor.effect_maxima = {92: 0}
        actor.effect_minima = {}
        actor.effect_frozen = frozenset()
        actor.physical_radius = 0
        return actor

    @staticmethod
    def ordinary():
        class Ordinary:
            @staticmethod
            def __call__(fight, actor):
                return NativeActorAuthority(
                    targeting={
                        "dpr_id": actor.id,
                        "dpu_id": actor.id,
                        "baF": True,
                        "baG": False,
                        "baK": False,
                        "bcN": actor.team,
                        "is_eGj": True,
                    },
                    is_player=True,
                    deck_spell_ids=frozenset(),
                    excluded_deck_spell_ids=frozenset(),
                    is_carried=False,
                    breed_id=1,
                    summon_count=0,
                    summon_counts_by_breed={},
                    occupant_blocks=True,
                    native_controller_id=actor.id,
                )

            @staticmethod
            def properties(_fight, _actor):
                return frozenset()

            @staticmethod
            def world_properties(_fight, _actor):
                return frozenset()

        return Ordinary()

    def invocation(self, *, base_uid=462):
        # This retained class-330 effect was present in fight 390: actor 159
        # (departed) remains its caster for teammate 160.
        return EffectInvocation(
            reference=314779,
            level=12,
            caster_id=159,
            target_id=160,
            cell=(-6, 5, 0),
            base_uid=base_uid,
            state_uid=461,
            native_retained_container={
                "id": 223,
                "type": 3,
                "level": 230,
                "present": True,
                "is_spell": False,
                "native_kind": "effect_area",
            },
        )

    def fight_with_retained_effect(self):
        caster = self.actor(159, 0, (-1, 0, 0), 98, True)
        recipient = self.actor(160, 0, (0, 0, 0), 99, True)
        opponent = self.actor(-200, 1, (1, 0, 0))
        fight = Fight(
            390,
            [caster, recipient, opponent],
            {(-1, 0, 0), (0, 0, 0), (1, 0, 0)},
            {0: {(-1, 0, 0), (0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.native_retained_records = {
            462: {
                "uid": 462,
                "owner_uid": 461,
                "target_id": 160,
                "manager_id": 160,
                "container_id": 444858380,
                "effect_class": 330,
                "container_kind": "state",
                "container_type": 1,
                "generic_effect": 314779,
                "definition_type": 2,
                "container_present": True,
            }
        }
        fight.native_owned_group_effects = {
            462: {
                "uid": 462,
                "timer": None,
                "payload": "08ce0310ce03189b9b1320002a0f08fa",
                "variant": 0,
                "children": [314780],
                "state_uid": 461,
                "target_id": 160,
                "invocation": vars(self.invocation(base_uid=None)),
                "effect_class": 330,
                "execution_count": -1,
                "native_selector": {"mask": 1, "class": "fcE"},
            }
        }
        return fight

    def test_retained_effect_keeps_departed_caster_source_out_of_candidates(self):
        from wakfu_server.combat_retained_departure_source import (
            capture_departure_sources,
        )

        fight = self.fight_with_retained_effect()
        from native_combat_fixture import initialize_fixture_qi

        initialize_fixture_qi(fight)
        fight.phase = "active"
        authority = RegisteredSummonAuthority(self.ordinary())
        capture_departure_sources(fight, {159}, authority)
        from wakfu_server.combat_pve_departure import retire_pve_actor

        retire_pve_actor(fight, fight.actors[159], root_actor_id=159, owner_id=98)
        fight.actors[159].pve_withdrawn = True
        from wakfu_server.fight_checkpoint_store import snapshot

        checkpoint = json.loads(json.dumps(snapshot(fight)))
        self.assertIn("native_retained_departure_sources", checkpoint)
        restored = deepcopy(fight)
        restored.native_retained_departure_sources = checkpoint[
            "native_retained_departure_sources"
        ]

        self.assertNotIn(159, {actor.id for actor in native_actor_population(restored)})
        adapter = NativeServerRuntimeAdapter.__new__(NativeServerRuntimeAdapter)
        adapter.actor_authority = authority
        contexts = adapter.targets(restored, None, None, self.invocation())
        self.assertIn(160, contexts)
        # The source context is available to resolve the retained effect; the
        # actor remains absent from native target-candidate population.
        self.assertIn(159, contexts)
        from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents

        events = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
        events.adapter = adapter
        events.preview = restored
        events.plan = None
        self.assertTrue(
            events.executable({"effect_class": 330}, self.invocation(), None)
        )
        with self.assertRaisesRegex(
            ValueError, "Withdrawn PvE actor has no active summon authority"
        ):
            authority(restored, restored.actors[159])

    def test_retained_source_attestation_does_not_bleed_between_effect_uids(self):
        from wakfu_server.combat_condition_selection_scope import (
            condition_actor_selection_scope,
        )
        from wakfu_server.combat_retained_departure_source import (
            capture_departure_sources,
        )

        fight = self.fight_with_retained_effect()
        from native_combat_fixture import initialize_fixture_qi

        initialize_fixture_qi(fight)
        fight.phase = "active"
        authority = RegisteredSummonAuthority(self.ordinary())
        capture_departure_sources(fight, {159}, authority)
        from wakfu_server.combat_pve_departure import retire_pve_actor

        retire_pve_actor(fight, fight.actors[159], root_actor_id=159, owner_id=98)
        fight.actors[159].pve_withdrawn = True
        adapter = NativeServerRuntimeAdapter.__new__(NativeServerRuntimeAdapter)
        adapter.actor_authority = authority

        from wakfu_server import combat_table_condition_context

        with patch.object(
            combat_table_condition_context,
            "table_only_condition_context",
            side_effect=lambda preview, _effect, invocation, authority_for: (
                authority_for(preview.actors[invocation.caster_id])
            ),
        ), condition_actor_selection_scope():
            valid = adapter.condition(fight, None, None, self.invocation())
            self.assertEqual(valid.targeting["dpu_id"], 159)
            with self.assertRaisesRegex(
                ValueError, "Retained departure invocation lacks its original group"
            ):
                adapter.condition(fight, None, None, self.invocation(base_uid=999))

    def test_phase_allows_attested_caster_but_still_rejects_retired_recipient(self):
        from wakfu_server.combat_pve_departure import retire_pve_actor
        from wakfu_server.combat_retained_departure_source import (
            capture_departure_sources,
        )
        from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
        from native_combat_fixture import initialize_fixture_qi

        class ReachedDefinition(Exception):
            pass

        fight = self.fight_with_retained_effect()
        initialize_fixture_qi(fight)
        fight.phase = "active"
        authority = RegisteredSummonAuthority(self.ordinary())
        capture_departure_sources(fight, {159}, authority)
        retire_pve_actor(fight, fight.actors[159], root_actor_id=159, owner_id=98)
        fight.actors[159].pve_withdrawn = True
        adapter = NativeServerRuntimeAdapter.__new__(NativeServerRuntimeAdapter)
        adapter.actor_authority = authority
        events = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
        events.adapter, events.preview = adapter, fight
        events.definition = lambda *_args: (_ for _ in ()).throw(ReachedDefinition())
        with self.assertRaises(ReachedDefinition):
            events.phase(
                {"effect_class": 330},
                self.invocation(),
                uid=462,
                value=0,
                channel=1,
                _event_ids=(0,),
            )

        fight.actors[160].pve_withdrawn = True
        with self.assertRaisesRegex(
            ValueError, "Withdrawn PvE actor has no active summon authority"
        ):
            events.phase(
                {"effect_class": 330},
                self.invocation(),
                uid=462,
                value=0,
                channel=1,
                _event_ids=(0,),
            )


if __name__ == "__main__":
    unittest.main()
