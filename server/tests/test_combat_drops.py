from decimal import Decimal, ROUND_CEILING
import unittest

from postgres_case import PostgresCase

from wakfu_server.combat_drops import (
    DRAW_DENOMINATOR,
    delivery_items,
    native_drop_catalog,
    native_prospection_bonus,
    plan_player_drops,
    report_loots,
    resolve,
)


def drop_row(
    probability,
    *,
    roll_count=-1,
    quantity_min=1,
    quantity_max=1,
    conditions=None,
    complex_criteria=False,
    is_loot_table=False,
    native_csE=-1,
    native_csF=0,
    reference_id=2026,
):
    return {
        "reference_id": reference_id,
        "probability": probability,
        "roll_count": roll_count,
        "quantity_min": quantity_min,
        "quantity_max": quantity_max,
        "is_loot_table": is_loot_table,
        "complex_criteria": complex_criteria,
        "native_csE": native_csE,
        "native_csF": native_csF,
        "conditions": conditions or [],
    }


def catalog_for(*rows):
    return {"source_sha256": "a" * 64, "monsters": {1: list(rows)}}


class Draws:
    def __init__(self, *values):
        self.values = list(values)
        self.bounds = []

    def __call__(self, upper):
        self.bounds.append(upper)
        value = self.values.pop(0)
        if not 0 <= value < upper:
            raise AssertionError((value, upper))
        return value


class CombatDropMathTests(unittest.TestCase):
    def test_native_wakfu_catalog_keeps_exact_jalato_hat_probability_and_rows(self):
        catalog = native_drop_catalog()
        matches = []
        for reference, rows in catalog["monsters"].items():
            for index, row in enumerate(rows):
                if row["reference_id"] == 2026:
                    matches.append((reference, index, row))
        self.assertEqual([reference for reference, _, _ in matches], [1, 2, 3, 39, 41])
        self.assertTrue(
            all(
                Decimal(str(row["probability"])) == Decimal("0.008")
                for _, _, row in matches
            )
        )
        self.assertTrue(
            all(
                row["roll_count"] == -1
                and row["quantity_min"] == row["quantity_max"] == 1
                for _, _, row in matches
            )
        )

    def test_probability_zero_and_one_follow_strict_draw_comparison(self):
        common = dict(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            catalog=catalog_for(drop_row(0)),
        )
        self.assertFalse(plan_player_drops(**common, rng=Draws(0))[0].success)
        common["catalog"] = catalog_for(drop_row(1))
        guaranteed = plan_player_drops(**common, rng=Draws(DRAW_DENOMINATOR - 1, 0))[0]
        self.assertTrue(guaranteed.success)
        self.assertEqual(guaranteed.effective_probability, Decimal(1))

    def test_native_point_eight_percent_is_decimal_exact_with_dofus_baseline_factors(
        self,
    ):
        rng = Draws(0, 0)
        result = plan_player_drops(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            catalog=catalog_for(drop_row("0.008")),
            rng=rng,
        )[0]
        # Dofus Fight.java's challenge setup floors a missing challenge bonus
        # to 1 before adding it as percent, so the reference baseline is 1.01.
        self.assertEqual(result.base_probability, Decimal("0.008"))
        self.assertEqual(result.raw_probability, Decimal("0.00808"))
        boundary = int(
            (result.raw_probability * DRAW_DENOMINATOR).to_integral_value(
                rounding=ROUND_CEILING
            )
        )
        below = plan_player_drops(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            catalog=catalog_for(drop_row("0.008")),
            rng=Draws(boundary - 1, 0),
        )[0]
        at = plan_player_drops(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            catalog=catalog_for(drop_row("0.008")),
            rng=Draws(boundary),
        )[0]
        self.assertTrue(below.success)
        self.assertFalse(at.success)

    def test_player_rolls_are_independent_and_prospection_bonus_uses_native_zero_baseline(
        self,
    ):
        args = dict(
            monsters=[{"actor_id": -11, "reference": 1}],
            can_loot=True,
            fight_context={},
            catalog=catalog_for(drop_row("0.008")),
        )
        first = plan_player_drops(
            **args, character_id=7, prospecting_bonus=0, rng=Draws(0, 0)
        )[0]
        second = plan_player_drops(
            **args, character_id=8, prospecting_bonus=50, rng=Draws(0, 0)
        )[0]
        self.assertEqual(first.raw_probability, Decimal("0.00808"))
        self.assertEqual(second.raw_probability, Decimal("0.01212"))
        self.assertTrue(first.success)
        self.assertTrue(second.success)
        below_baseline = plan_player_drops(
            **args, character_id=9, prospecting_bonus=-50, rng=Draws(0, 0)
        )[0]
        self.assertEqual(below_baseline.raw_probability, Decimal("0.00808"))

    def test_native_prospection_input_requires_actor_stat_snapshot(self):
        class Actor:
            effect_stats = {33: 75}

        self.assertEqual(native_prospection_bonus(Actor()), 75)

        class MissingStat:
            effect_stats = {}

        with self.assertRaisesRegex(ValueError, "authoritative Wakfu prospection"):
            native_prospection_bonus(MissingStat())

    def test_chance_above_one_is_capped_only_for_comparison_without_truncation(self):
        result = plan_player_drops(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=1000,
            can_loot=True,
            fight_context={},
            challenge_drop_percent=100,
            star_bonus_percent=100,
            drop_rate_bp=1000000,
            catalog=catalog_for(drop_row("0.5")),
            rng=Draws(DRAW_DENOMINATOR - 1, 0),
        )[0]
        self.assertGreater(result.raw_probability, Decimal(1))
        self.assertEqual(result.effective_probability, Decimal(1))
        self.assertTrue(result.success)

    def test_drop_multiplier_above_100x_and_at_max_stays_decimal_and_bounded(self):
        above_100x = plan_player_drops(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            drop_rate_bp=1_000_001,
            catalog=catalog_for(drop_row("0.01")),
            rng=Draws(0, 0),
        )[0]
        self.assertEqual(above_100x.raw_probability, Decimal("1.01000101"))
        self.assertEqual(above_100x.effective_probability, Decimal(1))
        self.assertTrue(above_100x.success)

        maximum_rate = 99_999_999_999
        draws = Draws(DRAW_DENOMINATOR - 1, 0)
        at_maximum = plan_player_drops(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            drop_rate_bp=maximum_rate,
            catalog=catalog_for(drop_row("0.5")),
            rng=draws,
        )[0]
        self.assertEqual(at_maximum.raw_probability, Decimal("5049999.9999495"))
        self.assertEqual(at_maximum.effective_probability, Decimal(1))
        self.assertTrue(at_maximum.success)
        self.assertEqual(draws.bounds, [DRAW_DENOMINATOR, 1])
        with self.assertRaisesRegex(ValueError, "Invalid drop rate"):
            plan_player_drops(
                monsters=[{"actor_id": -11, "reference": 1}],
                character_id=7,
                prospecting_bonus=0,
                can_loot=True,
                fight_context={},
                drop_rate_bp=maximum_rate + 1,
                catalog=catalog_for(drop_row("0.5")),
                rng=Draws(0, 0),
            )

    def test_conditions_fail_closed_and_supported_context_is_evaluated(self):
        row = drop_row(
            "0.008",
            conditions=[{"id": 3, "value": 3, "native_enum": "MIN_STASIS_LEVEL"}],
        )
        base = dict(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            catalog=catalog_for(row),
            rng=Draws(0, 0),
        )
        self.assertEqual(plan_player_drops(**base, fight_context={}), ())
        eligible = plan_player_drops(**base, fight_context={"stasis_level": 3})
        self.assertEqual(len(eligible), 1)
        complex_row = drop_row("1", complex_criteria=True)
        external = drop_row("1", is_loot_table=True)
        self.assertEqual(
            plan_player_drops(
                **{**base, "catalog": catalog_for(complex_row, external)},
                fight_context={},
            ),
            (),
        )

    def test_complex_flag_still_fails_closed_when_simple_conditions_are_also_exported(
        self,
    ):
        row = drop_row(
            "1",
            complex_criteria=True,
            conditions=[
                {
                    "id": 3,
                    "value": 3,
                    "native_enum": "MIN_STASIS_LEVEL",
                }
            ],
        )
        result = plan_player_drops(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={"stasis_level": 3},
            catalog=catalog_for(row),
            rng=Draws(0, 0),
        )
        self.assertEqual(result, ())

    def test_row_identity_roll_count_quantity_range_and_loot_report_are_preserved(self):
        catalog = catalog_for(
            drop_row("1", roll_count=2, quantity_min=2, quantity_max=4),
            drop_row("1", quantity_min=1, quantity_max=1),
        )
        rng = Draws(
            DRAW_DENOMINATOR - 1, 2, DRAW_DENOMINATOR - 1, 0, DRAW_DENOMINATOR - 1, 0
        )
        planned = plan_player_drops(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            catalog=catalog,
            rng=rng,
        )
        self.assertEqual(
            [
                (item.drop_row_index, item.attempt_index, item.quantity)
                for item in planned
            ],
            [(0, 0, 4), (0, 1, 2), (1, 0, 1)],
        )
        from wakfu_server.combat_drops import AwardBatch

        batch = AwardBatch(9, 7, 1, {}, "b" * 64, planned, False)
        self.assertEqual(
            report_loots(batch),
            [
                {
                    "reference": 2026,
                    "quantity": 4,
                    "is_purse_loot": False,
                    "is_pvp_loot": False,
                },
                {
                    "reference": 2026,
                    "quantity": 2,
                    "is_purse_loot": False,
                    "is_pvp_loot": False,
                },
                {
                    "reference": 2026,
                    "quantity": 1,
                    "is_purse_loot": False,
                    "is_pvp_loot": False,
                },
            ],
        )
        self.assertEqual(len(delivery_items(batch)), 3)

    def test_identical_native_rows_keep_distinct_raw_indices_and_roll_per_player(self):
        row = drop_row("1")
        args = dict(
            monsters=[{"actor_id": -11, "reference": 1}],
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            catalog=catalog_for(row, dict(row)),
        )
        first = plan_player_drops(**args, character_id=7, rng=Draws(0, 0, 0, 0))
        second = plan_player_drops(**args, character_id=8, rng=Draws(0, 0, 0, 0))
        self.assertEqual(
            [(d.drop_row_index, d.attempt_index, d.success) for d in first],
            [(0, 0, True), (1, 0, True)],
        )
        self.assertEqual(
            [(d.drop_row_index, d.attempt_index, d.success) for d in second],
            [(0, 0, True), (1, 0, True)],
        )
        self.assertEqual([d.quantity for d in first], [1, 1])

    def test_native_roll_max_is_preserved_but_does_not_override_displayed_roll_count(
        self,
    ):
        row = drop_row("1", roll_count=2, native_csE=1)
        planned = plan_player_drops(
            monsters=[{"actor_id": -11, "reference": 1}],
            character_id=7,
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            catalog=catalog_for(row),
            rng=Draws(0, 0, 0, 0),
        )
        self.assertEqual(len(planned), 2)
        self.assertEqual([decision.roll_count for decision in planned], [2, 2])
        self.assertEqual([decision.native_roll_max for decision in planned], [1, 1])

    def test_non_monster_fight_has_no_drops(self):
        self.assertEqual(
            plan_player_drops(
                monsters=[],
                character_id=7,
                prospecting_bonus=0,
                can_loot=True,
                fight_context={},
                catalog=catalog_for(drop_row("1")),
                rng=Draws(),
            ),
            (),
        )

    def test_invalid_probability_and_random_draw_are_rejected(self):
        for value in (-0.1, 1.1, "NaN", True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                plan_player_drops(
                    monsters=[{"actor_id": -11, "reference": 1}],
                    character_id=7,
                    prospecting_bonus=0,
                    can_loot=True,
                    fight_context={},
                    catalog=catalog_for(drop_row(value)),
                    rng=Draws(0),
                )
        with self.assertRaises(ValueError):
            plan_player_drops(
                monsters=[{"actor_id": -11, "reference": 1}],
                character_id=7,
                prospecting_bonus=0,
                can_loot=True,
                fight_context={},
                catalog=catalog_for(drop_row("1")),
                rng=lambda upper: upper,
            )


class CombatDropPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account_id = self.store.register("combat-drop", "local-password")["id"]
        self.character = self.store.create_character(self.account_id, "DropWinner")
        self.generation = self.store.begin_session(self.account_id)
        self.store.select_character(
            self.account_id, self.generation, self.character["id"]
        )
        with self.store.connection() as db:
            self.fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (self.fight_id, self.character["id"], self.account_id),
            )
            db.execute(
                "INSERT INTO fight_rewards(generation,fight_id,character_id,account_id,xp,kamas,created_at,"
                "start_xp,end_xp,start_level,end_level) VALUES(%s,%s,%s,%s,0,0,CURRENT_TIMESTAMP,0,0,1,1)",
                (self.generation, self.fight_id, self.character["id"], self.account_id),
            )

    def _resolve(self, db, *, rng):
        return resolve(
            self.store,
            db,
            account_id=self.account_id,
            generation=self.generation,
            character_id=self.character["id"],
            fight_id=self.fight_id,
            monsters=[{"actor_id": -123456, "reference": 1}],
            prospecting_bonus=0,
            can_loot=True,
            fight_context={},
            rng=rng,
        )

    def test_ordinary_company_resolves_all_three_pcs_under_one_main_session(self):
        from wakfu_server.characters import heroes

        company = [self.character]
        for index in range(2):
            hero = self.store.create_character(
                self.account_id, ("DropHero One", "DropHero Two")[index]
            )
            heroes.add(
                self.store,
                self.account_id,
                self.generation,
                self.character["id"],
                hero["id"],
            )
            company.append(hero)
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation=%s "
                "WHERE fight_id=%s",
                (self.generation, self.fight_id),
            )
            for hero in company[1:]:
                db.execute(
                    "INSERT INTO combat_fight_participants"
                    "(fight_id,character_id,account_id,team,session_generation) "
                    "VALUES(%s,%s,%s,0,%s)",
                    (self.fight_id, hero["id"], self.account_id, self.generation),
                )
                db.execute(
                    "INSERT INTO fight_rewards"
                    "(generation,fight_id,character_id,account_id,xp,kamas,created_at,"
                    "start_xp,end_xp,start_level,end_level) "
                    "VALUES(%s,%s,%s,%s,0,0,CURRENT_TIMESTAMP,0,0,1,1)",
                    (self.generation, self.fight_id, hero["id"], self.account_id),
                )
            for member in company:
                batch = resolve(
                    self.store,
                    db,
                    account_id=self.account_id,
                    generation=self.generation,
                    character_id=member["id"],
                    fight_id=self.fight_id,
                    monsters=[{"actor_id": -123456, "reference": 1}],
                    prospecting_bonus=0,
                    can_loot=True,
                    fight_context={},
                    rng=lambda upper: 0,
                )
                self.assertFalse(batch.replayed)
                self.assertTrue(batch.decisions)
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT character_id) AS n "
                    "FROM fight_drop_awards WHERE fight_id=%s",
                    (self.fight_id,),
                ).fetchone()["n"],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT character_id FROM sessions WHERE account_id=%s",
                    (self.account_id,),
                ).fetchone()["character_id"],
                self.character["id"],
            )
            db.execute(
                "DELETE FROM account_hero_slots WHERE account_id=%s AND character_id=%s",
                (self.account_id, company[-1]["id"]),
            )
            with self.assertRaisesRegex(ValueError, "frozen owned hero"):
                resolve(
                    self.store,
                    db,
                    account_id=self.account_id,
                    generation=self.generation,
                    character_id=company[-1]["id"],
                    fight_id=self.fight_id,
                    monsters=[{"actor_id": -123456, "reference": 1}],
                    prospecting_bonus=0,
                    can_loot=True,
                    fight_context={},
                    rng=lambda upper: 0,
                )

    def test_receipt_and_multiplier_are_versioned_replayed_and_atomic(self):
        with self.store.connection() as db:
            first = self._resolve(db, rng=lambda upper: 0)
            self.assertFalse(first.replayed)
            self.assertEqual(first.policy_version, 1)
            self.assertEqual(first.snapshot["modifiers"]["drop_rate_bp"], 10000)
            self.assertTrue(first.decisions)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_drop_attempt_receipts"
                ).fetchone()["n"],
                len(first.decisions),
            )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_drop_policy_versions(version,drop_rate_bp) VALUES(2,0)"
            )
            db.execute(
                "UPDATE combat_drop_policy_active SET version=2 WHERE singleton=true"
            )
        with self.store.connection() as db:
            replay = self._resolve(db, rng=lambda upper: upper - 1)
            self.assertTrue(replay.replayed)
            self.assertEqual(replay.policy_version, 1)
            self.assertEqual(replay.snapshot_sha256, first.snapshot_sha256)
            self.assertEqual(replay.decisions, first.decisions)
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_drop_awards").fetchone()[
                    "n"
                ],
                1,
            )

    def test_missing_reward_receipt_and_failed_transaction_cannot_leave_drops(self):
        with self.store.connection() as db:
            db.execute("DELETE FROM fight_rewards WHERE fight_id=%s", (self.fight_id,))
            with self.assertRaises(ValueError):
                self._resolve(db, rng=lambda upper: 0)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_drop_awards").fetchone()[
                    "n"
                ],
                0,
            )
