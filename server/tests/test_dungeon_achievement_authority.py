import unittest

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server.maps import dungeon_achievement_authority


class AchievementSnapshotTests(unittest.TestCase):
    def test_empty_initialized_snapshot_has_false_predicates(self):
        queries = dungeon_achievement_authority.queries_from_snapshot(
            {"running": [], "completed": [], "objectives": []}
        )
        self.assertFalse(queries["IsAchievementRunning"](5568))
        self.assertFalse(queries["IsAchievementComplete"](5568))
        self.assertFalse(queries["IsAchievementObjectiveComplete"](11515))

    def test_unknown_or_malformed_snapshot_fails_closed(self):
        for snapshot in (
            None,
            {"running": [], "completed": []},
            {"running": [], "completed": [], "objectives": [], "extra": []},
        ):
            with self.subTest(snapshot=snapshot), self.assertRaisesRegex(
                ValueError, "Missing or malformed"
            ):
                dungeon_achievement_authority.queries_from_snapshot(snapshot)

    def test_malformed_identifiers_and_overlapping_states_are_rejected(self):
        for value in (0, -1, True, "5568"):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "identifiers"
            ):
                dungeon_achievement_authority.queries_from_snapshot(
                    {"running": [value], "completed": [], "objectives": []}
                )
        with self.assertRaisesRegex(ValueError, "running and completed"):
            dungeon_achievement_authority.queries_from_snapshot(
                {"running": [5568], "completed": [5568], "objectives": []}
            )

    def test_running_completed_and_objective_predicates_are_disjoint(self):
        queries = dungeon_achievement_authority.queries_from_snapshot(
            {"running": [5568], "completed": [7000], "objectives": [11513]}
        )
        self.assertTrue(queries["IsAchievementRunning"](5568))
        self.assertFalse(queries["IsAchievementComplete"](5568))
        self.assertTrue(queries["IsAchievementComplete"](7000))
        self.assertFalse(queries["IsAchievementRunning"](7000))
        self.assertTrue(queries["IsAchievementObjectiveComplete"](11513))
        self.assertFalse(queries["IsAchievementObjectiveComplete"](11515))

    def test_miabuelita_negated_native_expression_uses_objective_11515(self):
        criterion = (
            "not (IsAchievementRunning(5568) and "
            "IsAchievementObjectiveComplete(11513) and "
            "not IsAchievementObjectiveComplete(11515))"
        )
        from test_dungeon_criteria import _Store

        settings = _Store({"version": 1, "is_neo_server": False})

        def evaluate(snapshot):
            queries = dungeon_achievement_authority.queries_from_snapshot(snapshot)
            from wakfu_server.maps import dungeon_criteria

            return dungeon_criteria.evaluate(settings, criterion, queries=queries)

        self.assertTrue(evaluate({"running": [], "completed": [], "objectives": []}))
        self.assertTrue(
            evaluate({"running": [5568], "completed": [], "objectives": []})
        )
        self.assertFalse(
            evaluate({"running": [5568], "completed": [], "objectives": [11513]})
        )
        self.assertTrue(
            evaluate({"running": [5568], "completed": [], "objectives": [11515]})
        )


class AchievementAuthorityPostgresTests(PostgresCase):
    def make_character(self):
        with self.store.connection() as db:
            account = db.execute(
                "INSERT INTO accounts(username,username_key,salt,password_hash) "
                "VALUES(%s,%s,%s,%s) RETURNING id",
                ("AchievementOwner", "achievementowner", bytes(16), b"test-hash"),
            ).fetchone()["id"]
            return db.execute(
                "INSERT INTO characters(account_id,name,name_key,breed,sex,face,hair,colors,appearance,hp,max_hp) "
                "VALUES(%s,'Achievement Owner','achievement owner',8,false,0,0,'[]','{}',20,60) "
                "RETURNING id",
                (account,),
            ).fetchone()["id"]

    def test_new_character_is_initialized_and_snapshot_roundtrips(self):
        character_id = self.make_character()
        self.assertFalse(
            dungeon_achievement_authority.queries(self.store, character_id)[
                "IsAchievementRunning"
            ](5568)
        )
        snapshot = {"running": [5568], "completed": [7000], "objectives": [11515]}
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_achievement_authority SET snapshot=%s "
                "WHERE character_id=%s",
                (Jsonb(snapshot), character_id),
            )
        predicates = dungeon_achievement_authority.queries(self.store, character_id)
        self.assertTrue(predicates["IsAchievementRunning"](5568))
        self.assertTrue(predicates["IsAchievementComplete"](7000))
        self.assertTrue(predicates["IsAchievementObjectiveComplete"](11515))

    def test_absent_authority_row_fails_closed_even_for_negated_criterion(self):
        character_id = self.make_character()
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM character_achievement_authority WHERE character_id=%s",
                (character_id,),
            )
        with self.assertRaisesRegex(ValueError, "achievement authority"):
            dungeon_achievement_authority.evaluate(
                self.store,
                "not IsAchievementRunning(5568)",
                character={"id": character_id},
            )


if __name__ == "__main__":
    unittest.main()
