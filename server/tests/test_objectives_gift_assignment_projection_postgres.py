"""Native Gifts and the browser board share assigned account objectives."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.custom_tasks import external
from wakfu_server.objectives import (
    assignments,
    player_views,
    points,
    repository,
    schedules,
)


class ObjectivesGiftAssignmentProjectionPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.at = datetime.now(timezone.utc)
        self.account = self.store.register(
            "gift-assignment-projection", "local-password"
        )["id"]
        self.main = self.store.create_character(self.account, "Assignment Main")["id"]
        self.hero = self.store.create_character(self.account, "Assignment Hero")["id"]
        self.generation = self.store.begin_session(self.account, ttl=7200)
        self.store.select_character(self.account, self.generation, self.main)
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=20 WHERE id=%s", (self.main,))
            db.execute("UPDATE characters SET level=120 WHERE id=%s", (self.hero,))
            db.execute(
                "UPDATE settings SET value=%s WHERE name='objectives_assignment_counts'",
                (Jsonb({"daily": 0, "weekly": 0, "mission": 0}),),
            )

        self.daily = self._put("daily", "daily", "daily")
        self.weekly = self._put("weekly", "task", "weekly")
        self.mission = self._put("mission", "mission", "once")
        self.unassigned = self._put("unassigned", "daily", "daily")
        self.daily_period = schedules.period_key(self.daily["schedule"], self.at)
        self.weekly_period = schedules.period_key(self.weekly["schedule"], self.at)

        with self.store.connection() as db:
            # The assignment-period level is the reward-preview authority for
            # every character on this account, even after selecting a level-120 hero.
            db.execute(
                "INSERT INTO objectives_assignment_periods(account_id,group_key,period_key,character_id,level) "
                "VALUES(%s,'daily',%s,%s,20),(%s,'weekly',%s,%s,20),(%s,'mission','once',%s,20)",
                (
                    self.account,
                    self.daily_period,
                    self.main,
                    self.account,
                    self.weekly_period,
                    self.main,
                    self.account,
                    self.main,
                ),
            )
            for group, period, definition in (
                ("daily", self.daily_period, self.daily),
                ("weekly", self.weekly_period, self.weekly),
                ("mission", "once", self.mission),
            ):
                db.execute(
                    "INSERT INTO objectives_assignments(account_id,group_key,period_key,definition_key) "
                    "VALUES(%s,%s,%s,%s)",
                    (self.account, group, period, definition["key"]),
                )

    def _put(self, suffix, kind, schedule_type):
        schedule = {"type": schedule_type, "timezone": "America/Bogota"}
        definition = {
            "key": f"test.gifts.{suffix}",
            "title": f"Matched {suffix.title()}",
            "description": "Shared assigned objective.",
            "kind": kind,
            "enabled": True,
            "objectives": [
                {
                    "key": "complete",
                    "event": "test.gift_assignment",
                    "filters": {},
                    "target": 1,
                }
            ],
            "schedule": schedule,
            "rewards": [{"kind": "scaled", "policy_key": "content-v1.daily"}],
        }
        with self.store.connection() as db:
            return repository.put_definition(db, definition, 0)["definition"]

    def _web(self, db):
        identity = {
            "account_id": self.account,
            "character_id": self.main,
            "generation": self.generation,
        }
        with patch("wakfu_server.objectives.player_travel.actions", return_value=[]):
            return player_views.snapshot(db, identity)

    def test_gifts_and_web_share_assignment_keys_and_frozen_reward_level_across_heroes(
        self,
    ):
        with self.store.connection() as db:
            native_main = external.snapshot(db, self.main, now=self.at)
            web_main = self._web(db)

        native_keys = {card["key"] for card in native_main}
        web_cards = [card for cards in web_main["sections"].values() for card in cards]
        web_keys = {card["key"] for card in web_cards}
        expected = {self.daily["key"], self.weekly["key"], self.mission["key"]}
        fixture_keys = expected | {self.unassigned["key"]}
        self.assertEqual(native_keys & fixture_keys, expected)
        self.assertEqual(web_keys & fixture_keys, expected)
        self.assertNotIn(self.unassigned["key"], native_keys)
        self.assertNotIn(self.unassigned["key"], web_keys)

        main_web = {card["key"]: card for card in web_cards}
        self.assertTrue(all(main_web[key]["reward_level"] == 20 for key in expected))
        with self.store.connection() as db:
            band = next(
                row
                for row in db.execute(
                    "SELECT policy FROM objectives_reward_policies WHERE key='content-v1.daily'"
                ).fetchone()["policy"]["bands"]
                if row["minimum"] <= 20 <= row["maximum"]
            )
        kamas = next(
            reward["amount"]
            for reward in band["rewards"]
            if reward.get("kind") == "kamas"
        )
        native_daily = next(
            card for card in native_main if card["key"] == self.daily["key"]
        )
        self.assertIn(f"{kamas:,} kamas", native_daily["description"])
        self.assertIn(
            {"kind": "kamas", "amount": kamas}, main_web[self.daily["key"]]["rewards"]
        )

        # The same durable assignment remains visible on the level-120 hero.
        self.store.select_character(self.account, self.generation, self.hero)
        with self.store.connection() as db:
            native_hero = external.snapshot(db, self.hero, now=self.at)
            web_hero = self._web(db)
        hero_native = {card["key"]: card for card in native_hero}
        hero_web = {
            card["key"]: card
            for cards in web_hero["sections"].values()
            for card in cards
        }
        self.assertEqual(set(hero_native) & fixture_keys, expected)
        self.assertTrue(all(hero_web[key]["reward_level"] == 20 for key in expected))
        self.assertIn(f"{kamas:,} kamas", hero_native[self.daily["key"]]["description"])
        self.assertEqual(
            hero_web[self.daily["key"]]["rewards"],
            main_web[self.daily["key"]]["rewards"],
        )

    def test_completed_once_assignment_hides_from_both_and_weekly_view_uses_points(
        self,
    ):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO objectives_account_progress(account_id,definition_key,period_key,definition_revision,"
                "counters,completed_at,reward_character_id) VALUES(%s,%s,'once',1,'{\"complete\":1}'::jsonb,%s,%s)",
                (self.account, self.mission["key"], self.at, self.main),
            )
            points.award_points(
                db,
                self.account,
                "gift-board:daily",
                17,
                category="daily",
                character_id=self.main,
                occurred_at=self.at,
            )
            points.award_points(
                db,
                self.account,
                "gift-board:weekly",
                25,
                category="weekly",
                character_id=self.hero,
                occurred_at=self.at,
            )

            native = external.snapshot(db, self.main, now=self.at)
            web = self._web(db)
            weekly = external.snapshot(db, self.main, now=self.at, section="weekly")

        native_keys = {card["key"] for card in native}
        web_keys = {card["key"] for cards in web["sections"].values() for card in cards}
        self.assertNotIn(self.mission["key"], native_keys)
        self.assertNotIn(self.mission["key"], web_keys)
        ranking = next(
            card for card in weekly if card["key"] == "objectives.weekly.ranking"
        )
        self.assertIn("42 points", ranking["description"])
        self.assertNotIn("!challenge weekly", ranking["description"])
        self.assertNotIn("best performance", ranking["description"].lower())
        self.assertTrue(any(card["key"] == self.weekly["key"] for card in weekly))


if __name__ == "__main__":
    unittest.main()
