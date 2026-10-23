"""DB-scoped fresh criterion populations preserve original chosen-PV replay."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from postgres_case import PostgresCase
import test_combat_effect_resolver as resolver_fixture


class EncounterGroupPopulationTests(PostgresCase):
    def test_admitted_policy_population_native_criteria_replay_and_frozen_guards(self):
        from wakfu_server import combat_encounter_group_selection as policy
        from wakfu_server import combat_encounter_roles as roles
        from wakfu_server import combat_encounter_area_activation as areas
        from wakfu_server.combat_conditions import (
            ConditionActor,
            ConditionContext,
            evaluate_condition,
        )

        for module in (policy, roles, areas):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        f = resolver_fixture.NativeResolverTests()
        f.setUp()
        f.actors[0].team, f.actors[1].team, f.actors[2].team = 1, 0, 0
        for actor in f.actors:
            actor.controlled = actor.id == 1
        assigned = roles.role_assignment(1400, [5500])
        fight = SimpleNamespace(
            phase="placement",
            actors={1: f.actors[0], 3: f.actors[2]},
            placement={1: {f.actors[0].position}, 0: {f.actors[2].position}},
        )
        # Exercise the production admission hook, not a direct fabricated record.
        roles.bind_roles(fight, assigned, player_ids=[1], npc_ids=[3])
        frozen = deepcopy(fight.native_encounter_group_population)
        self.assertIsNotNone(frozen)
        self.assertEqual(
            [rule[0] for rule in frozen["effects"]],
            [379384, 379386, 379951, 379954, 394706, 394707],
        )
        fight.actors[2] = f.actors[
            1
        ]  # Explicit mirror candidate premise, not a summon witness.
        fight.phase = "active"
        f.effect.update(
            effect_class=330,
            parameters=[],
            parameter_count=0,
            criteria='HasState(8237, "target")',
            area_class="anD",
            area_native="point",
            native_target_selector={"class": "fcE", "mask": 0},
        )
        f.resolver.direct_target_policies = {
            str(ref): [330, False, False] for ref in (379951, 379954)
        }
        f.resolver.fresh_group_population = (
            lambda effect, invocation: policy.permits_fresh_group_population(
                fight, effect, invocation
            )
        )
        invocation = replace(
            f.invocation,
            reference=379951,
            target_id=1,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )

        def selected(effect=f.effect, current=invocation):
            return [row.target_id for row in f.resolver(effect, current)]

        self.assertEqual(selected(), [1, 2, 3])
        # The original criterion, rather than a policy-created state or target,
        # chooses only the actual mirror-state holder from that population.
        contexts = {
            identity: ConditionActor(
                frozenset({8237}) if identity == 2 else frozenset()
            )
            for identity in (1, 2, 3)
        }
        accepted = [
            row.target_id
            for row in f.resolver(f.effect, invocation)
            if evaluate_condition(
                f.effect["criteria"],
                ConditionContext(
                    {"caster": contexts[1], "target": contexts[row.target_id]}
                ),
            )
        ]
        self.assertEqual(accepted, [2])
        self.assertEqual(
            selected(current=replace(invocation, reference=379954)), [1, 2, 3]
        )
        rule = next(row for row in frozen["effects"] if row[0] == 379384)
        reference, family, mask, count, criterion, parameters = rule
        native_leaf = dict(
            f.effect,
            effect_class=family,
            parameter_count=count,
            parameters=list(parameters),
            criteria=criterion,
            native_target_selector={"class": "fcE", "mask": mask},
        )
        leaf_invocation = replace(invocation, reference=reference)
        f.resolver.direct_target_policies[str(reference)] = [family, False, False]
        self.assertEqual(
            selected(effect=native_leaf, current=leaf_invocation), [1, 2, 3]
        )
        boss_contexts = {
            identity: ConditionActor(
                frozenset({8231}) if identity == 3 else frozenset()
            )
            for identity in (1, 2, 3)
        }
        self.assertEqual(
            [
                row.target_id
                for row in f.resolver(native_leaf, leaf_invocation)
                if evaluate_condition(
                    criterion,
                    ConditionContext(
                        {
                            "caster": boss_contexts[1],
                            "target": boss_contexts[row.target_id],
                        }
                    ),
                )
            ],
            [3],
        )
        for changes in (
            dict(wakemu_fresh_child_selection=False),
            dict(native_preselected_target=True),
            dict(native_trigger_context={"target_id": 1}),
        ):
            self.assertEqual(
                selected(
                    effect=native_leaf, current=replace(leaf_invocation, **changes)
                ),
                [1],
            )
        from wakfu_server.combat_effect_resolver import TriggerEligibility

        immediate = f.context
        f.context = replace(
            immediate,
            delivery="event",
            trigger=TriggerEligibility((1028,), 1, "standard", True),
        )
        for effect, current in ((f.effect, invocation), (native_leaf, leaf_invocation)):
            event_effect = dict(
                effect, target_masks=[[1028], None, None, None, None, None, None]
            )
            # Delivery mode itself must prevent reselection, even without an
            # invocation trigger dictionary in this already-verified event.
            self.assertIsNone(current.native_trigger_context)
            self.assertEqual(selected(effect=event_effect, current=current), [1])
        f.context = immediate
        f.resolver.direct_target_policies["999"] = [family, False, False]
        self.assertEqual(
            selected(
                effect=native_leaf, current=replace(leaf_invocation, reference=999)
            ),
            [1],
        )
        with self.assertRaisesRegex(ValueError, "descriptor changed"):
            policy.permits_fresh_group_population(
                fight,
                dict(native_leaf, parameters=[0] * len(parameters)),
                leaf_invocation,
            )
        for changes in (
            dict(wakemu_fresh_child_selection=False),
            dict(native_preselected_target=True),
            dict(native_trigger_context={"target_id": 1}),
        ):
            with self.subTest(changes=changes):
                self.assertEqual(selected(current=replace(invocation, **changes)), [1])
        leaf = dict(f.effect, effect_class=400)
        f.resolver.direct_target_policies["99"] = [400, False, False]
        self.assertEqual(
            selected(effect=leaf, current=replace(invocation, reference=99)), [1]
        )
        for changes in (
            dict(criteria="True"),
            dict(parameter_count=1, parameters=[0, 0]),
            dict(native_target_selector={"class": "fcE", "mask": 2}),
        ):
            with self.subTest(descriptor=changes), self.assertRaisesRegex(
                ValueError, "descriptor changed"
            ):
                # Call the policy directly too: selectors that bypass fresh-zero
                # population in the resolver must still fail closed as a descriptor.
                policy.permits_fresh_group_population(
                    fight, dict(f.effect, **changes), invocation
                )
        fight.native_encounter_group_population = dict(frozen, authority="forged")
        with self.assertRaisesRegex(ValueError, "drifted"):
            selected()
        fight.native_encounter_group_population = frozen
        other = SimpleNamespace(map_id=545, monster_references=(2430,))
        with patch.object(
            roles, "frozen_roles", return_value=other
        ), self.assertRaisesRegex(ValueError, "scope"):
            selected()
        absent = SimpleNamespace()
        self.assertIsNone(policy.freeze_group_population_policy(absent, roles=other))
        self.assertFalse(
            policy.permits_fresh_group_population(absent, f.effect, invocation)
        )
        with self.assertRaisesRegex(
            psycopg.Error, "immutable"
        ), self.store.connection() as db:
            db.execute("UPDATE encounter_group_population_effects SET criterion='True'")
        with self.assertRaisesRegex(
            psycopg.Error, "immutable"
        ), self.store.connection() as db:
            db.execute(
                "UPDATE encounter_group_population_versions SET authority='changed'"
            )
        with self.assertRaisesRegex(
            psycopg.Error, "immutable.*inventory"
        ), self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_group_population_effects VALUES "
                "(%s,999,330,0,0,'True',ARRAY[]::double precision[])",
                (frozen["policy"],),
            )
        # Active configuration is consulted only at admission, never per effect.
        with self.store.connection() as db:
            db.execute("DELETE FROM encounter_group_population_active")
        fresh = SimpleNamespace()
        self.assertIsNone(policy.freeze_group_population_policy(fresh, roles=assigned))
        with patch.object(
            policy, "_database", side_effect=AssertionError("Unexpected active lookup")
        ):
            self.assertEqual(selected(), [1, 2, 3])
            self.assertEqual(
                policy.freeze_group_population_policy(fight, roles=assigned).record(),
                frozen,
            )
