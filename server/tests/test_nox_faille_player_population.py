"""Scoped DB reconstruction of original402197, preserving unrelated PV leaves."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from postgres_case import PostgresCase
import test_combat_effect_resolver as resolver_fixture


class NoxFaillePopulationTests(PostgresCase):
    def test_native_descriptor_scoped_admission_and_replay_boundaries(self):
        from wakfu_server import combat_encounter_group_selection as policy
        from wakfu_server import combat_encounter_roles as roles
        from wakfu_server import combat_encounter_area_activation as areas
        from wakfu_server.combat_effect_resolver import TriggerEligibility

        for module in (policy, roles, areas):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        f = resolver_fixture.NativeResolverTests()
        f.setUp()
        boss = f.actors[2]
        boss.id, boss.team = -200, 0
        f.native[-200] = f.native.pop(3)
        for actor in f.actors[:2]:
            actor.team, actor.controlled = 1, True
        boss.controlled = False
        assigned = roles.role_assignment(1435, [5664])
        fight = SimpleNamespace(
            phase="placement",
            actors={actor.id: actor for actor in f.actors},
            placement={
                1: {actor.position for actor in f.actors[:2]},
                0: {boss.position},
            },
        )
        roles.bind_roles(fight, assigned, player_ids=[1, 2], npc_ids=[-200])
        frozen = deepcopy(fight.native_encounter_group_population)
        self.assertEqual(
            frozen["effects"],
            [
                [
                    402197,
                    304,
                    140737488355344,
                    3,
                    'IsPlayer("target")',
                    [9028.0, 0.0, 1.0, 0.0, -1.0, 0.0],
                ]
            ],
        )
        fight.phase = "active"
        f.effect.update(
            effect_class=304,
            parameters=[9028.0, 0.0, 1.0, 0.0, -1.0, 0.0],
            parameter_count=3,
            criteria='IsPlayer("target")',
            area_class="anD",
            area_native="point",
            native_target_selector={"class": "fcE", "mask": 140737488355344},
        )
        f.resolver.direct_target_policies = {
            str(reference): [304, False, False] for reference in (402197, 999)
        }
        f.resolver.fresh_group_population = (
            lambda effect, invocation: policy.permits_fresh_group_population(
                fight, effect, invocation
            )
        )
        invocation = replace(
            f.invocation,
            reference=402197,
            level=1,
            caster_id=-200,
            target_id=-200,
            cell=boss.position,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
        )

        def selected(current=invocation, effect=f.effect):
            return [row.target_id for row in f.resolver(effect, current)]

        self.assertEqual(selected(), [1, 2])
        for changes in (
            dict(native_preselected_target=True),
            dict(wakemu_fresh_child_selection=False),
            dict(native_trigger_context={"caster_id": 1, "target_id": -200}),
        ):
            with self.subTest(contract=changes):
                self.assertEqual(selected(replace(invocation, **changes)), [-200])
        immediate = f.context
        f.context = replace(
            immediate,
            delivery="event",
            trigger=TriggerEligibility((1028,), 1, "standard", True),
        )
        self.assertEqual(
            selected(
                effect=dict(
                    f.effect, target_masks=[[1028], None, None, None, None, None, None]
                )
            ),
            [-200],
        )
        f.context = immediate
        self.assertEqual(selected(replace(invocation, reference=999)), [-200])
        for changes in (
            dict(criteria="True"),
            dict(parameters=[9028, 0, 2, 0, -1, 0]),
            dict(native_target_selector={"class": "fcE", "mask": 16}),
        ):
            with self.subTest(descriptor=changes), self.assertRaisesRegex(
                ValueError, "descriptor changed"
            ):
                policy.permits_fresh_group_population(
                    fight, dict(f.effect, **changes), invocation
                )
        with patch.object(
            roles,
            "frozen_roles",
            return_value=SimpleNamespace(map_id=1400, monster_references=(5500,)),
        ), self.assertRaisesRegex(ValueError, "scope"):
            selected()
        fight.native_encounter_group_population = dict(frozen, authority="forged")
        with self.assertRaisesRegex(ValueError, "drifted"):
            selected()
        fight.native_encounter_group_population = frozen
        absent = SimpleNamespace()
        self.assertFalse(
            policy.permits_fresh_group_population(absent, f.effect, invocation)
        )
        # Existing frozen fights retain authority after an active configuration change.
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM encounter_group_population_active WHERE map_id=1435"
            )
        self.assertIsNone(
            policy.freeze_group_population_policy(SimpleNamespace(), roles=assigned)
        )
        self.assertEqual(selected(), [1, 2])

    def test_migration_preserves_tal_inventory_and_rejects_area_or_negative_masks(self):
        with self.store.connection() as db:
            tal = db.execute(
                "SELECT effect_reference,selector_mask FROM encounter_group_population_effects "
                "WHERE policy='wakemu-tal-mirror-criterion-population-v1' ORDER BY effect_reference"
            ).fetchall()
        self.assertEqual(
            [(row["effect_reference"], row["selector_mask"]) for row in tal],
            [
                (379384, 0),
                (379386, 0),
                (379951, 0),
                (379954, 0),
                (394706, 0),
                (394707, 0),
            ],
        )
        for mask in (-1, 1, 17):
            with self.subTest(mask=mask), self.assertRaises(
                psycopg.Error
            ), self.store.connection() as db:
                identity = "test-unadmitted-mask-" + str(mask)
                db.execute(
                    "INSERT INTO encounter_group_population_versions VALUES "
                    "(%s,'test authority',1,ARRAY[1],ARRAY[999])",
                    (identity,),
                )
                db.execute(
                    "INSERT INTO encounter_group_population_effects VALUES "
                    "(%s,999,304,%s,0,'True',ARRAY[]::double precision[])",
                    (identity, mask),
                )
        with self.assertRaisesRegex(
            psycopg.Error, "immutable"
        ), self.store.connection() as db:
            db.execute(
                "UPDATE encounter_group_population_effects SET criterion='True' "
                "WHERE effect_reference=402197"
            )
