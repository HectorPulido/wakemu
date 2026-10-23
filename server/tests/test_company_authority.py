"""Original company rank intervals, absent authority and unchanged wire payload."""
from unittest import TestCase

from wakfu_server.company_authority import (
    CompanySnapshot,
    ranks,
    rank_for_score,
    rank_for_snapshot,
)
from wakfu_server.hero_wire import company


class CompanyAuthorityTests(TestCase):
    def test_all_original_intervals_boundaries_and_outside_fallback_match_jvm(self):
        rows = ranks()
        self.assertEqual(len(rows), 11)
        self.assertNotIn(11, {row["rank"] for row in rows})
        for row in rows:
            for score in (row["minimum_score"], row["maximum_score"]):
                self.assertEqual(rank_for_score(score), row["rank"])
        self.assertEqual(
            [
                rank_for_score(score)
                for score in (-1, 0, 1, 2, 100, 500, 1000, 2000, 10000)
            ],
            [12, 12, 1, 1, 1, 3, 5, 7, 12],
        )
        for invalid in (True, None, "1", 2**31, -(2**31) - 1):
            with self.assertRaises(ValueError):
                rank_for_score(invalid)

    def test_absent_company_is_distinct_from_registered_zero_and_ownership_is_explicit(
        self,
    ):
        snapshot = CompanySnapshot(7, 101, 0, 0, score=0, active=True)
        self.assertEqual(rank_for_snapshot(None), -1)
        self.assertEqual(rank_for_snapshot(snapshot), 12)
        self.assertIs(snapshot.require_owner(7), snapshot)
        with self.assertRaisesRegex(ValueError, "Foreign"):
            snapshot.require_owner(8)
        for value in ({}, 0, False):
            with self.assertRaises(ValueError):
                rank_for_snapshot(value)
        for kwargs in (
            dict(account_id=0),
            dict(chief_id=True),
            dict(active=1),
            dict(score=True),
        ):
            fields = dict(
                account_id=7,
                chief_id=101,
                nation_id=0,
                guild_id=0,
                score=1,
                active=True,
            )
            fields.update(kwargs)
            with self.assertRaises(ValueError):
                CompanySnapshot(**fields)

    def test_existing_published_company_bytes_are_unchanged(self):
        expected = bytes.fromhex(
            "0000000100000001000000000000000700000000000000650000001e00000000000001f4000000000000000101"
        )
        self.assertEqual(
            company(
                7,
                101,
                nation_id=30,
                guild_id=500,
                company_snapshot=CompanySnapshot(7, 101, 30, 500, score=1, active=True),
            ),
            (13873, expected),
        )
        self.assertEqual(
            CompanySnapshot(7, 101, 30, 500, score=1, active=True).packet(),
            (13873, expected),
        )
        with self.assertRaisesRegex(ValueError, "actual native company"):
            company(7, 101)
        with self.assertRaisesRegex(ValueError, "chief"):
            company(
                7,
                202,
                company_snapshot=CompanySnapshot(7, 101, 0, 0, score=1, active=True),
            )

    def test_all_sixteen_original_equipment_gates_use_owned_aggregate_rank(self):
        import ast
        from wakfu_server.equipment_conditions import catalog, evaluate
        from wakfu_server.combat_local_criteria import parse_local_criterion

        expressions = [
            row["EQUIP"]
            for row in catalog().values()
            if "GetCompanyRank(" in row.get("EQUIP", "")
        ]
        self.assertEqual(len(expressions), 16)
        for expression in expressions:
            required = next(
                node.value
                for node in ast.walk(parse_local_criterion(expression))
                if isinstance(node, ast.Constant) and type(node.value) is int
            )
            threshold = min(
                row["minimum_score"] for row in ranks() if row["rank"] >= required
            )
            for score, expected in ((threshold - 1, False), (threshold, True)):
                snapshot = CompanySnapshot(7, 101, 0, 0, score=score, active=True)
                context = dict(
                    actor_kind="player",
                    level=100,
                    account_id=7,
                    company_snapshot=snapshot.record(),
                )
                self.assertEqual(
                    evaluate(
                        expression,
                        item=dict(uid=1, reference=1),
                        selected=[],
                        owned={},
                        criterion_context=context,
                    ),
                    expected,
                )
        base = dict(actor_kind="player", level=100, account_id=7)
        with self.assertRaises(ValueError):
            evaluate(
                "GetCompanyRank() >= 1",
                item={},
                selected=[],
                owned={},
                criterion_context=base,
            )
        self.assertFalse(
            evaluate(
                "GetCompanyRank() >= 1",
                item={},
                selected=[],
                owned={},
                criterion_context=dict(base, company_snapshot=None),
            )
        )
        with self.assertRaisesRegex(ValueError, "Foreign"):
            evaluate(
                "GetCompanyRank() >= 1",
                item={},
                selected=[],
                owned={},
                criterion_context=dict(
                    base,
                    company_snapshot=CompanySnapshot(8, 102, 0, 0, 1000, True).record(),
                ),
            )

    def test_native_companion_company_uses_registered_account_without_player_components(
        self,
    ):
        from wakfu_server.companion_equipment import criterion_context
        from wakfu_server.equipment_conditions import evaluate

        owner = dict(
            id=101,
            account_id=7,
            level=245,
            breed=8,
            map_id=527,
            equipment_criterion_context=dict(
                company_snapshot=CompanySnapshot(7, 101, 0, 0, 181, True).record()
            ),
        )
        context = criterion_context(owner, 20)
        self.assertNotIn("breed_id", context)
        self.assertNotIn("profession_levels", context)
        self.assertNotIn("real_level", context)
        self.assertEqual(context["level"], 20)
        self.assertTrue(
            evaluate(
                "GetCompanyRank() >= 2",
                item={},
                selected=[],
                owned={},
                criterion_context=context,
            )
        )
        with self.assertRaisesRegex(ValueError, "Foreign"):
            criterion_context(dict(owner, account_id=8), 20)
        with self.assertRaises(ValueError):
            evaluate(
                "GetCompanyRank() >= 1",
                item={},
                selected=[],
                owned={},
                criterion_context=dict(
                    actor_kind="native_companion_npc", level=20, account_id=7
                ),
            )

    def test_native_companion_map_and_global_clock_require_real_projected_authority(
        self,
    ):
        from wakfu_server.equipment_conditions import evaluate

        context = dict(
            actor_kind="native_companion_npc",
            level=20,
            native_map_id=527,
            world_time_ms=0,
        )
        self.assertTrue(
            evaluate(
                "GetInstanceId() == 527",
                item={},
                selected=[],
                owned={},
                criterion_context=context,
            )
        )
        from wakfu_server.world_clock import daytime

        self.assertEqual(
            evaluate(
                "IsDay()", item={}, selected=[], owned={}, criterion_context=context
            ),
            daytime(0),
        )
        with self.assertRaises(ValueError):
            evaluate(
                "GetInstanceId() == 527",
                item={},
                selected=[],
                owned={},
                criterion_context=dict(actor_kind="native_companion_npc", level=20),
            )
