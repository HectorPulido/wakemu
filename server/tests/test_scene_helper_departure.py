"""Declared helper departure composes the actual HP-preserving934 runner."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_encounter_scene_helpers import (
    bind_scene_helper_controls,
    helper_actor_ids_for_departing,
    retire_departing_scene_helpers,
)


class SceneHelperDepartureTests(unittest.TestCase):
    def test_only_departing_principal_helpers_retire_with_real934_and_keep_floor(self):
        from test_encounter_scene_helpers import EncounterSceneHelperTests
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
            current_registry,
        )
        from wakfu_server.combat_global_pv_collections import global_fighter_guards
        from wakfu_server.combat_controller_registry import current_native_controller
        from wakfu_server.combat_forced_retirement_handler import (
            NativeForcedRetirementHandler,
        )
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_stat_handler import (
            NativeStatHandler,
            StatExecutionContext,
        )
        from wakfu_server.combat_execution_context import constructed_execution_context
        from dataclasses import replace

        fight, char, members, manifest = EncounterSceneHelperTests().fight()
        helper_ids = tuple(row["actor_id"] for row in manifest["source"]["helpers"])
        for actor in fight.actors.values():
            actor.physical_radius = 0
            actor.native_fight_property_counts = {}
            actor.native_controlled_by_ai = not actor.controlled
            actor.effect_stats = {1: actor.hp, 2: actor.ap, 3: actor.mp, 7: 0, 8: 0}
            actor.effect_minima = {1: 1 if actor.id in helper_ids else 0}
            actor.effect_maxima = {1: actor.max_hp}
            actor.effect_frozen = frozenset()
        fight.native_npc_initialization_receipts = {
            row["actor_id"]: dict(
                ref=row["reference"],
                initialized=True,
                descriptor_level=fight.actors[row["actor_id"]].effective_level,
            )
            for row in manifest["source"]["helpers"]
        }
        bind_scene_helper_controls(
            fight,
            source_policy=manifest["source"]["policy"],
            source_digest=manifest["source_digest"],
        )
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=7, height=4, cell_masks=[0] * 28
        )
        slots = prepare_fresh_actor_slots(
            fight, physical_radii={identity: 0 for identity in fight.actors}
        )
        install_fresh_actor_slots(fight, slots)
        fight.ready(char["account_id"])
        fight.native_effect_uid_next = 900
        initial_hp = {identity: fight.actors[identity].hp for identity in helper_ids}
        self.assertEqual(helper_actor_ids_for_departing(fight, {-200}), ())
        self.assertEqual(
            helper_actor_ids_for_departing(fight, {char["id"]}), helper_ids
        )
        calls = []

        def factory(candidate, plan):
            calls.append(candidate)
            outbox = []
            retention = NativeRetainedRuntime(
                candidate,
                outbox,
                plan=plan,
                state_catalog={},
                action_id=5,
                timing=None,
                metadata={},
            )
            context = lambda *args: StatExecutionContext(True, True, None, False, b"")
            retention.stat_handler = NativeStatHandler(
                candidate,
                outbox,
                {"effects": {}},
                action_id=5,
                allocate_uid=candidate.allocate_effect_uid,
                context=context,
                rng=lambda: 0,
            )
            runner = NativeForcedRetirementHandler(
                candidate,
                outbox,
                action_id=5,
                allocate_uid=candidate.allocate_effect_uid,
                context=context,
                retention=retention,
                rng=lambda: 0,
            )
            # Prototype shape is a component fixture; the real dispatcher source
            # publication is checked in encounter qualification separately.
            effect = dict(
                effect_class=934,
                parameter_count=0,
                parameters=[],
                children=[],
                criteria="",
                target_masks=[[] for _ in range(7)],
            )

            def execute(invocation):
                invocation = replace(
                    invocation,
                    native_context_hex=constructed_execution_context().payload().hex(),
                )
                return runner(effect, {}, invocation)

            return (
                SimpleNamespace(
                    native_retention=retention,
                    effects={"117993": effect},
                    execute=execute,
                ),
                outbox,
            )

        packets = []
        retired = retire_departing_scene_helpers(fight, {char["id"]}, factory, packets)
        self.assertEqual(retired, helper_ids)
        self.assertEqual(len(calls), 1)
        self.assertEqual(sum(opcode == 13497 for opcode, _ in packets), 2)
        for identity in helper_ids:
            actor = fight.actors[identity]
            self.assertEqual(
                (actor.hp, actor.effect_minima[1]), (initial_hp[identity], 1)
            )
            self.assertEqual(
                global_fighter_guards(fight, identity),
                dict(baF=False, baG=False, baK=True),
            )
            self.assertEqual(current_native_controller(fight, identity), identity)
            self.assertNotIn(identity, fight.order)
            self.assertEqual(actor.native_obstacle_id, -1)
        self.assertTrue(global_fighter_guards(fight, -200)["baF"])
        current_registry(fight)
        from wakfu_server.combat_encounter_scene_helpers import (
            scene_helper_controller_records,
        )

        self.assertEqual(scene_helper_controller_records(fight), ())
        self.assertEqual(
            retire_departing_scene_helpers(fight, {char["id"]}, factory, packets), ()
        )
        self.assertEqual(len(calls), 1)
        self.assertFalse(any(event["kind"] == "death" for event in fight.events))


if __name__ == "__main__":
    unittest.main()
