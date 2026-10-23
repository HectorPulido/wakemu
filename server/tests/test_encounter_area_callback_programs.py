"""Isolated immutable DROP manifest contracts, without a combat/catalog reload."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from postgres_case import PostgresCase


class EncounterAreaCallbackProgramTests(PostgresCase):
    def scene(self):
        from wakfu_server import combat_encounter_area_callback_programs as policy
        from wakfu_server import combat_encounter_roles as roles

        for module in (policy, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        assigned = roles.role_assignment(1332, [5306])
        fight = SimpleNamespace(
            phase="placement", actors={}, native_encounter_roles=assigned.record()
        )
        return policy, roles, assigned, fight

    def test_all_original_drop_programs_parameters_and_checkpoint_are_isolated(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        policy, roles, assigned, fight = self.scene()
        frozen = policy.freeze_encounter_area_callback_programs(fight, roles=assigned)
        native = json.loads(
            (
                Path(__file__).parent
                / "fixtures/rushu_drop_callback_programs_native.json"
            ).read_text()
        )
        self.assertEqual(frozen["catalog_revision"], native["catalog_revision"])
        self.assertEqual(frozen["programs"], native["programs"])
        self.assertEqual(len(frozen["programs"]), 16)
        self.assertEqual(sum(len(p["steps"]) for p in frozen["programs"]), 64)
        self.assertEqual(
            sum(
                p["getter_parameter_count"]
                + sum(s["parameter_count"] for s in p["steps"])
                for p in frozen["programs"]
            ),
            256,
        )
        self.assertEqual(
            snapshot(fight)["native_encounter_area_callback_programs"], frozen
        )
        published = policy.encounter_area_callback_programs(fight)
        self.assertEqual(list(published), native["programs"])
        for program in published:
            with self.subTest(area=program["area_reference"]):
                self.assertEqual(
                    [s["role"] for s in program["steps"]],
                    ["constructor", "event", "state", "lock_removal"],
                )
                self.assertEqual(program["steps"][1]["emitted_events"], [2172])
                self.assertEqual(program["steps"][2]["parameters"][0], 7001)
        frozen["programs"][0]["steps"][0]["parameters"][0] = -1
        published[0]["getter_parameters"][0] = -1
        self.assertEqual(
            list(policy.encounter_area_callback_programs(fight)), native["programs"]
        )

    def test_immutable_inventory_scope_catalog_and_absence_survive_pointer_changes(
        self,
    ):
        from wakfu_server import native_catalog
        from wakfu_server.fight_checkpoint_store import snapshot

        policy, roles, assigned, fight = self.scene()
        frozen = policy.freeze_encounter_area_callback_programs(fight, roles=assigned)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM encounter_area_callback_program_active WHERE map_id=1332"
            )
        fight.phase, fight.native_start_event_delivered = "active", True
        self.assertEqual(
            policy.freeze_encounter_area_callback_programs(fight, roles=assigned),
            frozen,
        )
        absent = SimpleNamespace(phase="placement", actors={})
        self.assertIsNone(
            policy.freeze_encounter_area_callback_programs(absent, roles=assigned)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_area_callback_program_active VALUES (%s,%s,%s)",
                (1332, [5306], frozen["policy"]),
            )
        absent.phase, absent.native_start_event_delivered = "active", True
        self.assertIsNone(
            policy.freeze_encounter_area_callback_programs(absent, roles=assigned)
        )
        self.assertIsNone(snapshot(absent)["native_encounter_area_callback_programs"])
        self.assertEqual(policy.encounter_area_callback_programs(absent), ())
        with patch.object(
            policy, "_database", side_effect=AssertionError("Unscoped query")
        ):
            unscoped = SimpleNamespace(phase="placement")
            self.assertIsNone(
                policy.freeze_encounter_area_callback_programs(
                    unscoped, roles=roles.assigned_roles(unscoped)
                )
            )
        for field, value in (
            ("authority", "forged"),
            ("map_id", 1),
            ("catalog_revision", "0" * 64),
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "manifest changed"
            ):
                policy.callback_program_policy_from_record(
                    dict(frozen, **{field: value})
                )
        tampered = deepcopy(frozen)
        tampered["programs"][0]["steps"][2]["parameters"][0] = 1
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            policy.callback_program_policy_from_record(tampered)
        with patch.object(
            native_catalog, "release", return_value="0" * 64
        ), self.assertRaisesRegex(ValueError, "admission or catalog"):
            policy.freeze_encounter_area_callback_programs(fight, roles=assigned)
        with patch.object(
            roles,
            "frozen_roles",
            return_value=SimpleNamespace(map_id=1332, monster_references=(1,)),
        ), self.assertRaisesRegex(ValueError, "escaped frozen"):
            policy.encounter_area_callback_programs(fight)
        with self.assertRaisesRegex(ValueError, "pre1003"):
            policy.freeze_encounter_area_callback_programs(
                SimpleNamespace(phase="active", native_start_event_delivered=True),
                roles=assigned,
            )
        for table in (
            "encounter_area_callback_program_versions",
            "encounter_area_callback_programs",
            "encounter_area_callback_program_steps",
            "encounter_area_callback_program_parameters",
        ):
            with self.subTest(table=table), self.assertRaisesRegex(
                psycopg.Error, "immutable"
            ), self.store.connection() as db:
                db.execute("DELETE FROM " + table)
        with self.assertRaisesRegex(
            psycopg.Error, "outside.*callback effect"
        ), self.store.connection() as db:
            first = frozen["programs"][0]
            db.execute(
                "INSERT INTO encounter_area_callback_program_parameters VALUES (%s,%s,%s,%s,%s,%s)",
                (
                    frozen["policy"],
                    first["area_reference"],
                    first["drop_getter_reference"],
                    999,
                    0,
                    0,
                ),
            )
