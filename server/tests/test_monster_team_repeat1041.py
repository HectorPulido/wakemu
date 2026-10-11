"""eXM/eXN native team membership and target-preserving script dispatch."""
import json
from pathlib import Path
import unittest
from dataclasses import replace
import test_combat_repeated_group as repeated
from wakfu_server.combat_repeated_group import execute_repeated_group, NativePtResult
from wakfu_server.combat_team_repeat import (
    native_team_repeat_count,
    team_repeat_specification,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
    unregister_global_fighter,
)
from wakfu_server.combat_controller_registry import (
    initialize_controller_registry,
    register_native_controller,
    set_native_current_team,
)


class TeamRepeat1041Tests(unittest.TestCase):
    def fight(self, count=3):
        actors = [Actor(i + 1, 0, (i, 0, 0), 100, 6, 3, 10, 20) for i in range(count)]
        actors.append(Actor(-1, 1, (-1, 0, 0), 100, 6, 3, 10, 20))
        fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {team: {a.position for a in actors if a.team == team} for team in (0, 1)},
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        initialize_controller_registry(fight)
        for actor in actors:
            register_native_controller(
                fight, actor.id, team=actor.team, controller_id=actor.id
            )
        return fight

    def test_installed_eXN_loop_cap_and_fdZ_status_independence(self):
        rows = json.loads(
            (
                Path(__file__).parent / "fixtures/monster_team_repeat1041_native.json"
            ).read_text()
        )
        for row in rows:
            if "input" in row:
                seen = []
                _, iterations = execute_repeated_group(
                    team_repeat_specification(min(12, row["input"])),
                    [7, 8],
                    lambda child: seen.append(child) or NativePtResult(True, 0, False),
                )
                self.assertEqual(len(iterations), row["iterations"])
                self.assertEqual(seen, [7, 8] * row["iterations"])
            else:
                self.assertEqual(row["matches_zero"], row["team"] == 0)

    def test_current_team_registered_dead_and_explicit_retirement(self):
        fight = self.fight()
        self.assertEqual(native_team_repeat_count(fight, 1), 2)
        fight.actors[2].hp = 0
        set_global_fighter_status(fight, 2, "OFF_PLAY")
        self.assertEqual(native_team_repeat_count(fight, 1), 2)
        set_native_current_team(fight, 2, 1)
        self.assertEqual(native_team_repeat_count(fight, 1), 1)
        set_native_current_team(fight, 2, 0)
        unregister_global_fighter(fight, 2)
        self.assertEqual(native_team_repeat_count(fight, 1), 1)
        self.assertEqual(native_team_repeat_count(self.fight(16), 1), 12)
        del fight.native_controller_registry
        with self.assertRaisesRegex(ValueError, "registration producer"):
            native_team_repeat_count(fight, 1)

    def test_actual_area_caster_uses_captured_team_after_owner_team_change(self):
        import test_combat_fake_fighter_area as area_fixture

        fight, creator, _, _ = area_fixture.NativeFakeFighterAreaTests().create()
        fight.actors.update(
            {i: Actor(i, 0, (i, 0, 0), 100, 6, 3, 10, 20) for i in (8, 9)}
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        initialize_controller_registry(fight)
        for identity in fight.actors:
            register_native_controller(fight, identity, team=0, controller_id=identity)
        area_fixture.NativeFakeFighterAreaTests().invoke(creator)
        self.assertEqual(native_team_repeat_count(fight, 901), 2)
        set_native_current_team(fight, 7, 1)
        self.assertEqual(native_team_repeat_count(fight, 901), 1)
        self.assertEqual(native_team_repeat_count(fight, 7), 0)
        del fight.native_effect_areas[901]["native_fight_affiliation_source"]
        with self.assertRaisesRegex(ValueError, "captured team authority"):
            native_team_repeat_count(fight, 901)

    def test_target_actor_cell_and_context_preserved_without_stop_on_empty_pt(self):
        counter = {"applied": 0}
        dispatcher = repeated.DispatcherPtTests().dispatcher(counter)
        dispatcher.effects["90"]["effect_class"] = 1041
        dispatcher.effects["90"]["parameters"] = []
        dispatcher.effects["90"]["parameter_count"] = 0
        dispatcher.team_repeat_count = lambda inv: 3
        seen = []
        dispatcher.handlers[400] = lambda e, v, i: seen.append(i) or False
        dispatcher.actor_position = lambda identity: (identity, 2, 3)
        dispatcher.execute(EffectInvocation(90, 1, 7, 8, (0, 0, 0)))
        self.assertEqual(len(seen), 3)
        self.assertTrue(
            all(
                (i.target_id, i.cell, i.native_explicit_target, i.native_context_hex)
                == (8, (8, 2, 3), True, "")
                for i in seen
            )
        )
        dispatcher.team_repeat_count = None
        with self.assertRaisesRegex(ValueError, "actual fdt team producer"):
            dispatcher.execute(EffectInvocation(90, 1, 7, 8, (0, 0, 0)))

    def test_registered_team_provider_drives_actual_dispatcher_script_iterations(self):
        fight = self.fight(4)
        set_global_fighter_status(fight, 3, "OFF_PLAY")
        fight.actors[3].hp = 0
        counter = {"applied": 0}
        dispatcher = repeated.DispatcherPtTests().dispatcher(counter)
        dispatcher.effects["90"]["effect_class"] = 1041
        dispatcher.effects["90"]["parameters"] = []
        dispatcher.effects["90"]["parameter_count"] = 0
        dispatcher.team_repeat_count = lambda invocation: native_team_repeat_count(
            fight, invocation.caster_id
        )
        dispatched = []
        dispatcher.handlers[400] = (
            lambda definition, values, invocation: dispatched.append(
                invocation.target_id
            )
            or True
        )
        dispatcher.actor_position = lambda identity: fight.actors[identity].position
        self.assertTrue(dispatcher.execute(EffectInvocation(90, 1, 1, 2, (0, 0, 0))))
        self.assertEqual(dispatched, [2, 2, 2])
        dispatched.clear()
        set_native_current_team(fight, 4, 1)
        self.assertTrue(dispatcher.execute(EffectInvocation(90, 1, 1, 2, (0, 0, 0))))
        self.assertEqual(dispatched, [2, 2])
        dispatched.clear()
        del fight.native_controller_registry
        with self.assertRaisesRegex(ValueError, "registration producer"):
            dispatcher.execute(EffectInvocation(90, 1, 1, 2, (0, 0, 0)))
        self.assertEqual(dispatched, [])

    def test_zero_count_still_finishes_owned_parent_without_child(self):
        counter = {"applied": 0}
        dispatcher = repeated.DispatcherPtTests().dispatcher(counter)
        dispatcher.effects["90"]["effect_class"] = 1041
        dispatcher.team_repeat_count = lambda inv: 0
        finished = []
        dispatcher.group_retention.finish_group = lambda pending: finished.append(
            pending
        )
        self.assertFalse(dispatcher.execute(EffectInvocation(90, 1, 7, 8, (0, 0, 0))))
        self.assertEqual(counter["applied"], 0)
        self.assertEqual(len(finished), 1)
