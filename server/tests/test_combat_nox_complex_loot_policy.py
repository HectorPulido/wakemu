"""DB-owned eligibility/accounting premises; paid victory is qualified separately."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.combat_nox_complex_loot_policy import (
    earned,
    load_policy,
    permission,
    terminal_drop_context,
    validate_native_rows,
)
from wakfu_server.combat_drops import plan_player_drops


class NoxComplexLootPolicyTests(PostgresCase):
    def fixtures(self):
        with self.store.connection() as db:
            policy = load_policy(db)
        rows = json.loads(
            (Path(__file__).parent / "fixtures/nox_complex_loot_rows.json").read_text()
        )
        self.assertEqual(len(policy.item_references), 51)
        return policy, rows

    def test_db_whitelist_preserves_native_chances_draws_quantities_and_other_guards(
        self,
    ):
        policy, rows = self.fixtures()
        native_rows = deepcopy(rows)
        native_rows.append(dict(rows[0], reference_id=999999))
        # Actual item32473 also has independent ordinary Stele rows.
        native_rows.append(
            dict(
                rows[0],
                complex_criteria=False,
                conditions=[dict(id=5, value=-1, native_enum="CAN_BE_LOOTED_IN_STELE")],
            )
        )
        catalog = dict(source_sha256="a" * 64, monsters={5664: native_rows, 5306: rows})
        control_rows = deepcopy(rows)
        for row in control_rows:
            row["complex_criteria"] = False
        draws, control_draws = [], []

        def draw(log):
            def choose(upper):
                log.append(upper)
                return upper - 1

            return choose

        args = dict(
            monsters=[dict(actor_id=-200, reference=5664)],
            character_id=7,
            prospecting_bonus=100,
            can_loot=True,
        )
        control = plan_player_drops(
            **args,
            catalog=dict(source_sha256="b" * 64, monsters={5664: control_rows}),
            fight_context=dict(score=3000000, boss_score_drop_rate_bp=13000),
            rng=draw(control_draws)
        )
        context = dict(
            score=3000000,
            boss_score_drop_rate_bp=13000,
            nox_complex_loot=permission(policy),
        )
        with patch(
            "wakfu_server.combat_drops.protocol_catalog.release",
            return_value=policy.catalog_revision,
        ):
            selected = plan_player_drops(
                **args, catalog=catalog, fight_context=context, rng=draw(draws)
            )

            def no_draw(_upper):
                self.fail("Foreign or unauthorized complex row consumed RNG")

            self.assertEqual(
                plan_player_drops(
                    monsters=[dict(actor_id=-200, reference=5306)],
                    character_id=7,
                    prospecting_bonus=0,
                    can_loot=True,
                    catalog=catalog,
                    fight_context=context,
                    rng=no_draw,
                ),
                (),
            )
        self.assertEqual(len(selected), 51)
        self.assertEqual(selected, control)
        self.assertEqual(draws, control_draws)
        self.assertEqual(
            plan_player_drops(
                **args,
                catalog=catalog,
                fight_context={},
                rng=lambda _upper: self.fail("No permission consumed RNG")
            ),
            (),
        )

    def test_unearned_foreign_changed_rows_and_policy_drift_fail_closed(self):
        policy, rows = self.fixtures()
        terminal = dict(
            eligible=True,
            boss_defeated=True,
            survived=True,
            encounter_controller=policy.encounter_controller,
            score=policy.minimum_score,
        )
        self.assertTrue(earned(policy, terminal))
        for fields in (
            dict(score=2999999),
            dict(eligible=False),
            dict(boss_defeated=False),
            dict(survived=False),
            dict(encounter_controller="wakemu-rushu-score-v1"),
        ):
            with self.subTest(fields=fields), self.store.connection() as db:
                self.assertIsNone(terminal_drop_context(db, dict(terminal, **fields)))
        for field, value in (
            ("probability", 0.999),
            ("quantity_max", 77),
            ("conditions", [dict(native_enum="MIN_SCORE", value=3000000)]),
        ):
            changed = deepcopy(rows)
            changed[0][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_native_rows(policy, policy.catalog_revision, changed)
        with self.assertRaises(ValueError):
            validate_native_rows(policy, "unreviewed", rows)
        with self.assertRaises(ValueError):
            plan_player_drops(
                monsters=[dict(actor_id=-200, reference=5664)],
                character_id=7,
                prospecting_bonus=0,
                can_loot=True,
                catalog=dict(source_sha256="a" * 64, monsters={5664: rows}),
                fight_context=dict(score=2999999, nox_complex_loot=permission(policy)),
                rng=lambda _upper: self.fail("Unearned permission consumed RNG"),
            )
        with self.assertRaisesRegex(ValueError, "scope"), self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_complex_loot_policy_items(version,item_reference) VALUES(%s,999999)",
                (policy.version,),
            )
            load_policy(db)
        with self.store.connection() as db:
            self.assertEqual(load_policy(db), policy)
