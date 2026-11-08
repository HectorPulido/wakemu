from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.rift_artifact_recovery import (
    _iteration_team_roster,
    _native_iteration_rosters,
    eligible_representative,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_adapter import (
    NativeCastAuthority,
    NativeServerRuntimeAdapter,
)
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_condition_cell_batch import NativeConditionContextSource
from wakfu_server.combat_effect_dispatch import EffectDispatcher
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_static_catalogs import DefinitionOverlay, ImmutableCatalog


class RosterIterationTests(unittest.TestCase):
    def test_real_native_adapter_and_frozen_catalogs_admit_one_population(self):
        actors = (
            Actor(7, 0, (0, 0, 0), 10, 6, 3, 10, 1, owner_id=7, controlled=True),
            Actor(-200, 1, (1, 0, 0), 10, 6, 3, 5, 1),
        )
        fight = Fight(
            901, actors, {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        ordinary = OrdinaryActorAuthority(
            characters={},
            monsters={},
            decks={},
            excluded_decks={},
            catalog={},
            deck_caps={},
        )
        policy = lambda *args, **kwargs: None
        cast = NativeCastAuthority(*([policy] * 10))
        adapter = NativeServerRuntimeAdapter(actor_authority=ordinary, cast=cast)
        effects = DefinitionOverlay(ImmutableCatalog({}), {})
        context = NativeConditionContextSource(
            adapter.condition, fight, object(), effects
        )
        dispatcher = EffectDispatcher(
            effects,
            {},
            resolve=policy,
            condition_context=context,
            probability_accepts=policy,
            group_cells=policy,
            actor_position=policy,
        )
        events = NativeAreaEventRuntime(
            fight, dispatcher, definitions=DefinitionOverlay(ImmutableCatalog({}), {})
        )

        roster = _native_iteration_rosters(fight, events)
        self.assertIsNotNone(
            roster,
            repr(
                {
                    "fight_type": type(fight).__name__,
                    "fight_instance_override": "_in_play" in vars(fight),
                    "fight_method": Fight._in_play
                    is getattr(fight._in_play, "__func__", None),
                    "area_type": type(events).__name__,
                    "area_definitions": type(events.definitions).__name__,
                    "area_mapping_ok": __import__(
                        "wakfu_server.rift_artifact_recovery", fromlist=["_"]
                    )._native_readonly_effect_mapping(events.definitions),
                    "dispatcher_type": type(dispatcher).__name__,
                    "dispatcher_effects": type(dispatcher.effects).__name__,
                    "dispatcher_mapping_ok": __import__(
                        "wakfu_server.rift_artifact_recovery", fromlist=["_"]
                    )._native_readonly_effect_mapping(dispatcher.effects),
                    "context_type": type(context).__name__,
                    "context_callback": getattr(context.callback, "__func__", None)
                    is NativeServerRuntimeAdapter.condition,
                }
            ),
        )
        self.assertEqual(tuple(actor.id for actor in roster["actors"]), (7, -200))
        self.assertEqual(_iteration_team_roster(roster, 0), (actors[0],))
        self.assertEqual(_iteration_team_roster(roster, 1), (actors[1],))

        original = NativeServerRuntimeAdapter.condition
        try:
            NativeServerRuntimeAdapter.condition = lambda *args, **kwargs: None
            self.assertIsNone(_native_iteration_rosters(fight, events))
        finally:
            NativeServerRuntimeAdapter.condition = original

    def test_iteration_roster_preserves_native_id_order_and_live_area_checks(self):
        actors = (
            SimpleNamespace(id=-20, team=1),
            SimpleNamespace(id=9, team=0),
            SimpleNamespace(id=3, team=0),
        )
        cache = {"actors": actors, "summons": frozenset(), "by_team": {}}
        calls = []

        class Events:
            def artifact_assignment_eligible(self, area_uid, actor_id):
                calls.append((area_uid, actor_id))
                return actor_id == 9

        events = Events()
        self.assertEqual(_iteration_team_roster(cache, 0), (actors[2], actors[1]))
        self.assertEqual(
            eligible_representative(
                SimpleNamespace(),
                0,
                area_uid=101,
                area_events=events,
                _rosters=cache,
            ),
            9,
        )
        self.assertEqual(calls, [(101, 3), (101, 9)])

    def test_custom_provider_falls_back_and_rechecks_population_after_mutation(self):
        original = SimpleNamespace(id=1, team=0)
        replacement = SimpleNamespace(id=2, team=0)
        fight = SimpleNamespace(actors={1: original}, _in_play=lambda actor: True)
        events = SimpleNamespace(
            artifact_assignment_eligible=lambda _uid, actor_id: actor_id in fight.actors
        )
        self.assertIsNone(_native_iteration_rosters(fight, events))
        calls = []

        def current_population(owner):
            calls.append(owner)
            return tuple(owner.actors.values())

        with patch(
            "wakfu_server.combat_global_pv_read_view.in_play_actors",
            side_effect=current_population,
        ):
            self.assertEqual(
                eligible_representative(fight, 0, area_uid=101, area_events=events),
                1,
            )
            fight.actors.clear()
            fight.actors[2] = replacement
            events.artifact_assignment_eligible = (
                lambda _uid, actor_id: actor_id in fight.actors
            )
            self.assertEqual(
                eligible_representative(fight, 0, area_uid=102, area_events=events),
                2,
            )
        self.assertEqual(calls, [fight, fight])


if __name__ == "__main__":
    unittest.main()
