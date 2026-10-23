"""Frozen DB manifest contracts; original program execution is qualified separately."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from postgres_case import PostgresCase


class EncounterSeedProgramTests(PostgresCase):
    def scene(self):
        from wakfu_server import combat_encounter_seed_programs as policy
        from wakfu_server import combat_encounter_roles as roles

        for module in (policy, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        assigned = roles.role_assignment(1332, [5306])
        fight = SimpleNamespace(
            phase="active",
            native_start_event_delivered=False,
            native_encounter_roles=assigned.record(),
        )
        return policy, roles, assigned, fight

    def test_complete_native_program_inventory_and_reconstructed_level_are_frozen(self):
        from wakfu_server.combat_rushu_encounter_setup import initial_vestige_plan
        from wakfu_server.combat_parameters import parameter_value

        policy, roles, assigned, fight = self.scene()
        record = policy.freeze_encounter_seed_program_policy(fight, roles=assigned)
        native = json.loads(
            (
                Path(__file__).parent / "fixtures/rushu_seed_programs_native.json"
            ).read_text()
        )
        self.assertEqual(record["catalog_revision"], native["catalog_revision"])
        self.assertEqual(record["programs"], native["programs"])
        self.assertEqual(
            (
                record["initial_level"],
                record["boss_reference"],
                record["boss_constructor_state"],
            ),
            (1, 5306, 7000),
        )
        programs = policy.encounter_seed_programs(fight, boss_reference=5306)
        self.assertEqual(len(programs), 16)
        for row in programs:
            with self.subTest(area=row["area_reference"]):
                parent = native["effects"][str(row["program_reference"])]
                creator = native["effects"][str(row["creator_reference"])]
                companion = native["effects"][str(row["state_effect_reference"])]
                self.assertEqual(parent["effect_class"], 349)
                self.assertEqual(
                    parent["children"],
                    [row["creator_reference"], row["state_effect_reference"]],
                )
                self.assertEqual(creator["effect_class"], 315)
                self.assertEqual(
                    parameter_value(creator["parameters"], 0, row["level"]),
                    row["area_reference"],
                )
                self.assertEqual(companion["effect_class"], 304)
                self.assertEqual(
                    [
                        parameter_value(companion["parameters"], i, row["level"])
                        for i in (0, 1)
                    ],
                    [row["state_reference"], row["level"]],
                )
        layout = dict(
            map_id=1332,
            policy="unit-source-manifest-layout",
            glyph_cells=[(index * 2, 0, 0) for index in range(16)],
        )
        seeds, provenance = initial_vestige_plan(layout, seed=78, programs=programs)
        again, _ = initial_vestige_plan(layout, seed=78, programs=programs)
        self.assertEqual(seeds, again)
        self.assertEqual(
            {row.program_reference for row in seeds},
            {row["program_reference"] for row in programs},
        )
        self.assertEqual(provenance["initial_levels"], [1])
        self.assertFalse(provenance["state_damage_cost_or_event_overrides"])
        record["programs"][0]["creator_reference"] = 1
        programs[0]["state_reference"] = 1
        self.assertEqual(
            policy.encounter_seed_programs(fight, boss_reference=5306)[0][
                "state_reference"
            ],
            7001,
        )

    def test_immutable_scope_absence_and_existing_setup_version_survive_pointer_changes(
        self,
    ):
        policy, roles, assigned, fight = self.scene()
        frozen = policy.freeze_encounter_seed_program_policy(fight, roles=assigned)
        self.assertEqual(policy.encounter_seed_programs(fight, boss_reference=5664), ())
        with self.store.connection() as db:
            db.execute("DELETE FROM encounter_seed_program_active WHERE map_id=1332")
        fight.native_start_event_delivered = True
        self.assertEqual(
            policy.freeze_encounter_seed_program_policy(fight, roles=assigned), frozen
        )
        self.assertEqual(
            len(policy.encounter_seed_programs(fight, boss_reference=5306)), 16
        )
        absent = SimpleNamespace(phase="active", native_start_event_delivered=False)
        self.assertIsNone(
            policy.freeze_encounter_seed_program_policy(absent, roles=assigned)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_seed_program_active VALUES "
                "(1332,ARRAY[5306],'wakemu-rushu-initial-vestige-programs-v1')"
            )
        absent.native_start_event_delivered = True
        self.assertIsNone(
            policy.freeze_encounter_seed_program_policy(absent, roles=assigned)
        )
        self.assertEqual(
            policy.encounter_seed_programs(absent, boss_reference=5306), ()
        )
        unscoped = SimpleNamespace(phase="placement")
        with patch.object(
            policy,
            "_database",
            side_effect=AssertionError("Unscoped fight queried content"),
        ):
            self.assertIsNone(
                policy.freeze_encounter_seed_program_policy(
                    unscoped, roles=roles.assigned_roles(unscoped)
                )
            )
        for mutation in (
            dict(initial_level=2),
            dict(authority="forged"),
            dict(map_id=1435),
        ):
            with self.subTest(record=mutation), self.assertRaisesRegex(
                ValueError, "manifest changed"
            ):
                policy.seed_program_policy_from_record(dict(frozen, **mutation))
        with patch.object(
            roles,
            "frozen_roles",
            return_value=SimpleNamespace(map_id=1332, monster_references=(1,)),
        ), self.assertRaisesRegex(ValueError, "escaped frozen scope"):
            policy.encounter_seed_programs(fight, boss_reference=5306)
        fresh_after_start = SimpleNamespace(
            phase="active", native_start_event_delivered=True
        )
        with self.assertRaisesRegex(ValueError, "pre1003"):
            policy.freeze_encounter_seed_program_policy(
                fresh_after_start, roles=assigned
            )
        for table in ("encounter_seed_program_versions", "encounter_seed_program_rows"):
            with self.subTest(table=table), self.assertRaisesRegex(
                psycopg.Error, "immutable"
            ), self.store.connection() as db:
                db.execute("DELETE FROM " + table)
        with self.assertRaisesRegex(
            psycopg.Error, "outside.*inventory"
        ), self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_seed_program_rows VALUES "
                "('wakemu-rushu-initial-vestige-programs-v1',999,999,998,7001,1000)"
            )
