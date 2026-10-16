"""Hourly PvP events bind to consenting, durable friendly duels."""
from datetime import datetime, timezone
import json
import os
import unittest
from psycopg.types.json import Jsonb
from unittest.mock import patch

from wakfu_server.combat_shared import Session
from wakfu_server.objectives import pvp, repository


def _accept_native_duel(context, native_levels=(1, 1)):
    """Prepare the durable native actor evidence used by PvP eligibility."""
    context.challenge()

    def prepare(db, fight_id, _invitation, _source, _target):
        from wakfu_server.combat_state import Actor, Fight

        actors = [
            Actor(
                context.char_a["id"],
                0,
                (0, 0, 0),
                60,
                6,
                3,
                10,
                native_levels[0],
                context.account_a,
                True,
            ),
            Actor(
                context.char_b["id"],
                1,
                (2, 0, 0),
                60,
                6,
                3,
                9,
                native_levels[1],
                context.account_b,
                True,
            ),
        ]
        fight = Fight(
            fight_id,
            actors,
            {(0, 0, 0), (1, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(2, 0, 0)}},
        )
        return {"fight_id": fight_id, "fight": fight}, lambda: None

    return context.answer(True, prepare)


def _select_account_a(context, character_id):
    context.store.select_character(
        context.account_a, context.generation_a, character_id
    )
    context.char_a = context.store.character(context.account_a, character_id)
    context.session_a = Session(
        context.account_a, character_id, context.generation_a, 1134, 0
    )


class ObjectivesPvpLevelPolicyTests(unittest.TestCase):
    def test_relative_policy_includes_twenty_percent_boundary_only(self):
        policy = {"type": "relative", "maximum_percent": 20}
        self.assertTrue(pvp.compatible_levels(policy, 100, 120))
        self.assertFalse(pvp.compatible_levels(policy, 100, 121))
        self.assertTrue(pvp.compatible_levels(policy, 1, 1))
        self.assertFalse(pvp.compatible_levels(policy, 1, 2))
        self.assertTrue(pvp.compatible_levels(policy, 50, 60))
        self.assertFalse(pvp.compatible_levels(policy, 50, 61))
        self.assertFalse(pvp.compatible_levels(policy, 0, 1))
        self.assertFalse(pvp.compatible_levels(policy, True, 2))

    def test_absolute_ten_level_and_same_twenty_level_bracket_policies(self):
        absolute = {"type": "absolute", "maximum_difference": 10}
        self.assertTrue(pvp.compatible_levels(absolute, 80, 90))
        self.assertFalse(pvp.compatible_levels(absolute, 80, 91))
        bracket = {"type": "bracket", "size": 20}
        self.assertTrue(pvp.compatible_levels(bracket, 1, 20))
        self.assertFalse(pvp.compatible_levels(bracket, 20, 21))
        self.assertTrue(pvp.compatible_levels(bracket, 181, 200))

    def test_policy_rejects_boolean_or_out_of_range_thresholds(self):
        for policy in (
            {"type": "relative", "maximum_percent": True},
            {"type": "relative", "maximum_percent": 101},
            {"type": "absolute", "maximum_difference": -1},
            {"type": "bracket", "size": 0},
            {"type": "bracket", "size": 201},
        ):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                pvp.validate_level_policy(policy)

    def test_native_roster_requires_balanced_same_account_teams_and_compatible_levels(
        self,
    ):
        event = {
            "first_account_id": 1,
            "second_account_id": 2,
            "first_character_id": 10,
            "second_character_id": 20,
            "level_policy": {"type": "relative", "maximum_percent": 20},
        }
        balanced = [
            {"team": 0, "account_id": 1, "character_id": 10, "level": 60},
            {"team": 0, "account_id": 1, "character_id": 11, "level": 80},
            {"team": 1, "account_id": 2, "character_id": 20, "level": 62},
            {"team": 1, "account_id": 2, "character_id": 21, "level": 90},
        ]
        self.assertTrue(pvp._valid_roster(event, balanced))
        self.assertFalse(pvp._valid_roster(event, balanced[:-1]))
        mixed_owner = [dict(row) for row in balanced]
        mixed_owner[1]["account_id"] = 3
        self.assertFalse(pvp._valid_roster(event, mixed_owner))
        wrong_bracket = [dict(row) for row in balanced]
        wrong_bracket[3]["level"] = 150
        self.assertFalse(pvp._valid_roster(event, wrong_bracket))


class ObjectivesHourlyPvpPostgresTests(unittest.TestCase):
    def setUp(self):
        from test_friendly_duels import FriendlyDuelStoreTests

        self.context = FriendlyDuelStoreTests(
            methodName="test_duel_settlement_accepts_valid_registered_controlled_summon"
        )
        self.context.setUp()
        self.addCleanup(self.context.doCleanups)
        # Use a live clock: PvP snapshots and actions validate PostgreSQL's
        # current lease expiry, while the legacy duel fixture pins its clock.
        self.context.store.clock = lambda: datetime.now(timezone.utc).timestamp()
        self.context.generation_a = self.context.store.begin_session(
            self.context.account_a, ttl=7200
        )
        self.context.generation_b = self.context.store.begin_session(
            self.context.account_b, ttl=7200
        )
        self.context.store.select_character(
            self.context.account_a, self.context.generation_a, self.context.char_a["id"]
        )
        self.context.store.select_character(
            self.context.account_b, self.context.generation_b, self.context.char_b["id"]
        )
        self.context.session_a = Session(
            self.context.account_a,
            self.context.char_a["id"],
            self.context.generation_a,
            1134,
            0,
        )
        self.context.session_b = Session(
            self.context.account_b,
            self.context.char_b["id"],
            self.context.generation_b,
            1134,
            0,
        )

    def test_bogota_hour_boundary_and_connected_matchmaking_restart_are_stable(self):
        before, _, _ = pvp.hour(datetime(2026, 10, 16, 4, 59, tzinfo=timezone.utc))
        after, _, _ = pvp.hour(datetime(2026, 10, 16, 5, 0, tzinfo=timezone.utc))
        self.assertEqual(before, "2026-10-15T23")
        self.assertEqual(after, "2026-10-16T00")

        context = self.context
        now = datetime.fromtimestamp(context.store.clock(), tz=timezone.utc)
        with context.store.connection() as db:
            db.execute(
                "UPDATE sessions SET expires_at=%s WHERE account_id=%s",
                (now.replace(microsecond=0), context.account_b),
            )
        with context.store.connection() as db, patch.dict(
            os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False
        ):
            self.assertIsNone(pvp.tick(db, now))

        context.generation_b = context.store.begin_session(context.account_b)
        context.store.select_character(
            context.account_b, context.generation_b, context.char_b["id"]
        )
        with context.store.connection() as db, patch.dict(
            os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False
        ):
            first = pvp.tick(db, now)
            replay = pvp.tick(db, now.replace(minute=45))
            count = db.execute(
                "SELECT count(*) n FROM objectives_pvp_events"
            ).fetchone()["n"]
        self.assertIsNotNone(first)
        self.assertEqual(first["status"], "open")
        self.assertEqual(replay["id"], first["id"])
        self.assertNotEqual(first["first_account_id"], first["second_account_id"])
        self.assertEqual(
            {first["first_account_id"], first["second_account_id"]},
            {context.account_a, context.account_b},
        )
        self.assertEqual(
            {first["first_generation"], first["second_generation"]},
            {context.generation_a, context.generation_b},
        )
        self.assertEqual(count, 1)

    def test_matchmaking_requires_two_selected_live_accounts_and_never_backfills(self):
        context = self.context
        now = datetime.fromtimestamp(context.store.clock(), tz=timezone.utc)
        with context.store.connection() as db:
            db.execute(
                "DELETE FROM sessions WHERE account_id = ANY(%s)",
                ([context.account_a, context.account_b],),
            )
        with patch.dict(os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False):
            with context.store.connection() as db:
                self.assertIsNone(pvp.tick(db, now))
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) n FROM objectives_pvp_events"
                    ).fetchone()["n"],
                    0,
                )

            context.generation_a = context.store.begin_session(
                context.account_a, ttl=7200
            )
            context.store.select_character(
                context.account_a, context.generation_a, context.char_a["id"]
            )
            with context.store.connection() as db:
                self.assertIsNone(pvp.tick(db, now))
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) n FROM objectives_pvp_events"
                    ).fetchone()["n"],
                    0,
                )

            # The second account returns in the next hour; only that live
            # period can be created, with no synthetic event for the missed one.
            next_hour = now.replace(minute=0, second=0, microsecond=0).replace(
                hour=(now.hour + 1) % 24
            )
            if next_hour <= now:
                from datetime import timedelta

                next_hour += timedelta(days=1)
            context.generation_b = context.store.begin_session(
                context.account_b, ttl=7200
            )
            context.store.select_character(
                context.account_b, context.generation_b, context.char_b["id"]
            )
            with context.store.connection() as db:
                event = pvp.tick(db, next_hour)
                keys = db.execute(
                    "SELECT period_key FROM objectives_pvp_events"
                ).fetchall()
        self.assertIsNotNone(event)
        self.assertEqual(event["period_key"], pvp.hour(next_hour)[0])
        self.assertEqual([row["period_key"] for row in keys], [pvp.hour(next_hour)[0]])

    def test_matchmaking_skips_incompatible_levels_and_selects_a_compatible_pair(self):
        context = self.context
        third_account = context.store.register(
            "duel-hourly-level-check", "local-password"
        )["id"]
        third_character = context.store.create_character(third_account, "Level Check")[
            "id"
        ]
        third_generation = context.store.begin_session(third_account, ttl=7200)
        context.store.select_character(third_account, third_generation, third_character)
        now = datetime.fromtimestamp(context.store.clock(), tz=timezone.utc)
        with context.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=60 WHERE id=%s", (context.char_a["id"],)
            )
            db.execute(
                "UPDATE characters SET level=130 WHERE id=%s", (context.char_b["id"],)
            )
            db.execute(
                "UPDATE characters SET level=160 WHERE id=%s", (third_character,)
            )
            db.execute(
                "UPDATE settings SET value=%s WHERE name='objectives_pvp_level_policy'",
                (Jsonb({"type": "relative", "maximum_percent": 20}),),
            )
        with context.store.connection() as db, patch.dict(
            os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False
        ):
            self.assertIsNone(pvp.tick(db, now))

        with context.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=150 WHERE id=%s", (third_character,)
            )
        with context.store.connection() as db, patch.dict(
            os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False
        ):
            event = pvp.tick(db, now)
        self.assertIsNotNone(event)
        self.assertEqual(
            {event["first_account_id"], event["second_account_id"]},
            {context.account_b, third_account},
        )
        self.assertTrue(
            pvp.compatible_levels(
                event["level_policy"], event["first_level"], event["second_level"]
            )
        )

    def test_duel_eligibility_uses_native_effective_levels_not_character_rows(self):
        context = self.context
        now = datetime.fromtimestamp(context.store.clock(), tz=timezone.utc)
        with context.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=100 WHERE id=ANY(%s)",
                ([context.char_a["id"], context.char_b["id"]],),
            )
        with patch.dict(os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False):
            with context.store.connection() as db:
                event = pvp.tick(db, now)
            self.assertEqual((event["first_level"], event["second_level"]), (100, 100))

            # PostgreSQL character rows look compatible (100/100), but the
            # native actor evidence is modulated to incompatible 50/100.
            accepted = _accept_native_duel(context, native_levels=(50, 100))
            self.assertTrue(accepted["accepted"])
            with context.store.connection() as db:
                saved = db.execute(
                    "SELECT status,fight_id FROM objectives_pvp_events WHERE id=%s",
                    (event["id"],),
                ).fetchone()
                roster_count = db.execute(
                    "SELECT count(*) n FROM objectives_pvp_fight_roster WHERE event_id=%s",
                    (event["id"],),
                ).fetchone()["n"]
        self.assertEqual(saved["status"], "expired")
        self.assertIsNone(saved["fight_id"])
        self.assertEqual(roster_count, 0)

    def test_open_hourly_pair_tracks_selected_hero_and_freezes_native_roster(self):
        context = self.context
        now = datetime.fromtimestamp(context.store.clock(), tz=timezone.utc)
        hero = context.store.create_character(context.account_a, "Hourly Selected Hero")
        too_high = context.store.create_character(
            context.account_a, "Hourly Incompatible Hero"
        )
        with context.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=100 WHERE id=ANY(%s)",
                ([context.char_a["id"], context.char_b["id"]],),
            )
            db.execute("UPDATE characters SET level=110 WHERE id=%s", (hero["id"],))
            db.execute("UPDATE characters SET level=200 WHERE id=%s", (too_high["id"],))

        with patch.dict(os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False):
            with context.store.connection() as db:
                event = pvp.tick(db, now)
            self.assertIsNotNone(event)
            original_id = event["id"]

            _select_account_a(context, too_high["id"])
            with context.store.connection() as db:
                incompatible = pvp.actions(
                    db,
                    {
                        "account_id": context.account_a,
                        "character_id": too_high["id"],
                        "generation": context.generation_a,
                    },
                )
            self.assertEqual(incompatible, [])

            _select_account_a(context, hero["id"])
            identity = {
                "account_id": context.account_a,
                "character_id": hero["id"],
                "generation": context.generation_a,
            }
            with context.store.connection() as db:
                compatible = pvp.actions(db, identity)
            self.assertEqual(
                [row["key"] for row in compatible], [f"pvp.meet.{original_id}"]
            )
            self.assertEqual(
                compatible[0]["target"]["opponent_character_id"], context.char_b["id"]
            )
            accepted = _accept_native_duel(context, native_levels=(110, 100))
            self.assertTrue(accepted["accepted"])
            with context.store.connection() as db:
                frozen = db.execute(
                    "SELECT id,status,first_account_id,first_character_id,first_level,"
                    "second_account_id,second_character_id,second_level FROM objectives_pvp_events WHERE id=%s",
                    (original_id,),
                ).fetchone()
                roster = db.execute(
                    "SELECT account_id,character_id,team,level FROM objectives_pvp_fight_roster WHERE event_id=%s ORDER BY team",
                    (original_id,),
                ).fetchall()

        self.assertEqual(frozen["id"], original_id)
        self.assertEqual(frozen["status"], "in_fight")
        self.assertEqual(
            {frozen["first_character_id"], frozen["second_character_id"]},
            {hero["id"], context.char_b["id"]},
        )
        self.assertEqual({frozen["first_level"], frozen["second_level"]}, {100, 110})
        self.assertEqual(
            {(row["account_id"], row["character_id"], row["level"]) for row in roster},
            {
                (context.account_a, hero["id"], 110),
                (context.account_b, context.char_b["id"], 100),
            },
        )

    def test_only_durable_defeat_outcome_binds_and_awards_both_accounts_once(self):
        context = self.context
        now = datetime.fromtimestamp(context.store.clock(), tz=timezone.utc)
        from wakfu_server.friendly_duels import settle
        from wakfu_server.objectives import reward_policies

        with patch.dict(os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False):
            # A reusable account-level event follows the currently selected
            # hero. A level-200 hero is out of range; selecting the level-110
            # hero restores the same event and current opponent action.
            selected_hero = context.store.create_character(
                context.account_a, "Hourly Account Hero"
            )
            incompatible_hero = context.store.create_character(
                context.account_a, "Hourly Out Of Range"
            )
            with context.store.connection() as db:
                db.execute(
                    "UPDATE characters SET level=100 WHERE id=ANY(%s)",
                    ([context.char_a["id"], context.char_b["id"]],),
                )
                db.execute(
                    "UPDATE characters SET level=110 WHERE id=%s",
                    (selected_hero["id"],),
                )
                db.execute(
                    "UPDATE characters SET level=200 WHERE id=%s",
                    (incompatible_hero["id"],),
                )
            with context.store.connection() as db:
                event = pvp.tick(db, now)
            self.assertIsNotNone(event)
            original_event_id = event["id"]

            _select_account_a(context, incompatible_hero["id"])
            with context.store.connection() as db:
                actions = pvp.actions(
                    db,
                    {
                        "account_id": context.account_a,
                        "character_id": incompatible_hero["id"],
                        "generation": context.generation_a,
                    },
                )
            self.assertEqual(actions, [])

            _select_account_a(context, selected_hero["id"])
            with context.store.connection() as db:
                actions = pvp.actions(
                    db,
                    {
                        "account_id": context.account_a,
                        "character_id": selected_hero["id"],
                        "generation": context.generation_a,
                    },
                )
            self.assertEqual(
                [row["key"] for row in actions], [f"pvp.meet.{original_event_id}"]
            )
            accepted = _accept_native_duel(context, native_levels=(110, 100))
            self.assertTrue(accepted["accepted"])
            with context.store.connection() as db:
                bound = db.execute(
                    "SELECT id,status,fight_id,first_account_id,first_character_id,first_level,"
                    "second_account_id,second_character_id,second_level FROM objectives_pvp_events WHERE id=%s",
                    (original_event_id,),
                ).fetchone()
                roster_at_start = db.execute(
                    "SELECT account_id,character_id,level FROM objectives_pvp_fight_roster WHERE event_id=%s",
                    (original_event_id,),
                ).fetchall()
            self.assertEqual(
                (bound["id"], bound["status"], bound["fight_id"]),
                (original_event_id, "in_fight", accepted["fight_id"]),
            )
            self.assertEqual(
                {bound["first_character_id"], bound["second_character_id"]},
                {selected_hero["id"], context.char_b["id"]},
            )
            self.assertEqual({bound["first_level"], bound["second_level"]}, {100, 110})
            self.assertEqual(
                {
                    (row["account_id"], row["character_id"], row["level"])
                    for row in roster_at_start
                },
                {
                    (context.account_a, selected_hero["id"], 110),
                    (context.account_b, context.char_b["id"], 100),
                },
            )

            fight = context._finished_duel_with_registered_summon(accepted["fight_id"])
            fight.actors[selected_hero["id"]].effective_level = 110
            fight.actors[context.char_b["id"]].effective_level = 100
            with context.store.connection() as db:
                with self.assertRaisesRegex(ValueError, "durable duel outcome"):
                    pvp.record_result(
                        db,
                        accepted["fight_id"],
                        context.char_a["id"],
                        context.char_b["id"],
                        "defeat",
                    )
                # A private definition edit after announcement must not change
                # the scaled prize frozen into this hourly event.
                for key in ("hourly-pvp-participation", "hourly-pvp-winner"):
                    current = db.execute(
                        "SELECT definition,revision FROM objectives_definitions WHERE key=%s",
                        (key,),
                    ).fetchone()
                    edited = {
                        **current["definition"],
                        "rewards": [{"kind": "kamas", "amount": 999999}],
                    }
                    repository.put_definition(db, edited, current["revision"])

            def expand_frozen_policy(db, policy_row, level):
                from wakfu_server.objectives.pvp import POLICIES

                kind = next(
                    kind for kind, key in POLICIES.items() if key == policy_row["key"]
                )
                frozen = event["reward_snapshot"][kind]
                self.assertEqual(policy_row["revision"], frozen["revision"])
                self.assertEqual(policy_row["policy"], frozen["policy"])
                self.assertIn(level, {100, 110})
                return [{"kind": "kamas", "amount": 100}]

            # Reward-pool expansion is isolated here; the test still exercises
            # the production entitlement outbox and its transaction boundary.
            with patch.object(
                reward_policies, "expand", side_effect=expand_frozen_policy
            ), patch("wakfu_server.combat.fight_store._write_terminal_checkpoint"):
                first_result = settle(
                    context.store,
                    context.account_a,
                    context.generation_a,
                    context.char_a["id"],
                    fight,
                )
                replay_result = settle(
                    context.store,
                    context.account_a,
                    context.generation_a,
                    context.char_a["id"],
                    fight,
                )
            self.assertTrue(first_result["outcome"])
            self.assertTrue(replay_result["outcome"])

            with context.store.connection() as db:
                saved = db.execute(
                    "SELECT * FROM objectives_pvp_events WHERE id=%s", (event["id"],)
                ).fetchone()
                outcome = db.execute(
                    "SELECT winner_character_id,loser_character_id,reason FROM friendly_duel_outcomes WHERE fight_id=%s",
                    (accepted["fight_id"],),
                ).fetchone()
                rewards = db.execute(
                    "SELECT character_id,definition_key,period_key,payload FROM objectives_rewards WHERE definition_key LIKE 'hourly-pvp-%' ORDER BY character_id,definition_key"
                ).fetchall()
                progress = db.execute(
                    "SELECT character_id,definition_key,period_key,completed_at FROM objectives_progress WHERE definition_key LIKE 'hourly-pvp-%' ORDER BY character_id,definition_key"
                ).fetchall()
                account_progress = db.execute(
                    "SELECT account_id,definition_key,period_key,counters FROM objectives_account_progress WHERE definition_key LIKE 'hourly-pvp-%' ORDER BY account_id,definition_key"
                ).fetchall()
                event_count = db.execute(
                    "SELECT count(*) n FROM objectives_pvp_events WHERE period_key=%s",
                    (event["period_key"],),
                ).fetchone()["n"]
                view = pvp.snapshot(
                    db,
                    {
                        "account_id": context.account_a,
                        "character_id": context.char_a["id"],
                        "generation": context.generation_a,
                    },
                )
            self.assertEqual(
                (saved["status"], saved["rewards_reserved"]), ("completed", True)
            )
            self.assertEqual(outcome["reason"], "defeat")
            self.assertEqual(len(rewards), 3)
            self.assertTrue(
                all(
                    row["payload"] == {"kind": "kamas", "amount": 100}
                    for row in rewards
                )
            )
            self.assertEqual(len(progress), 3)
            self.assertEqual(len(account_progress), 3)
            self.assertEqual(
                {row["account_id"] for row in account_progress},
                {context.account_a, context.account_b},
            )
            self.assertEqual(
                sum(
                    1
                    for row in account_progress
                    if row["definition_key"] == "hourly-pvp-participation"
                ),
                2,
            )
            self.assertEqual(
                sum(
                    1
                    for row in account_progress
                    if row["definition_key"] == "hourly-pvp-winner"
                ),
                1,
            )
            self.assertEqual(event_count, 1)
            self.assertIsNone(view["current"])
            self.assertEqual(view["history"][0]["status"], "completed")
            self.assertEqual(len(view["history"]), 1)
            self.assertEqual(
                sum(
                    1 for row in rewards if row["definition_key"] == "hourly-pvp-winner"
                ),
                1,
            )
            per_character = {}
            for row in rewards:
                per_character.setdefault(row["character_id"], []).append(
                    row["definition_key"]
                )
            winner = outcome["winner_character_id"]
            loser = outcome["loser_character_id"]
            self.assertEqual(
                set(per_character[winner]),
                {"hourly-pvp-participation", "hourly-pvp-winner"},
            )
            self.assertEqual(per_character[loser], ["hourly-pvp-participation"])
            self.assertEqual(
                {row["period_key"] for row in rewards}, {event["period_key"]}
            )
            self.assertTrue(all(row["completed_at"] is not None for row in progress))

    def test_hourly_event_exposes_meet_watch_and_active_result_to_player_view(self):
        context = self.context
        now = datetime.fromtimestamp(context.store.clock(), tz=timezone.utc)
        from wakfu_server.friendly_duels import settle
        from wakfu_server.objectives import player_views, reward_policies

        with patch.dict(os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False):
            with context.store.connection() as db:
                event = pvp.tick(db, now)
                participant_actions = pvp.actions(
                    db,
                    {
                        "account_id": context.account_a,
                        "character_id": context.char_a["id"],
                        "generation": context.generation_a,
                    },
                )
            self.assertEqual(
                [action["key"] for action in participant_actions],
                [f"pvp.meet.{event['id']}"],
            )

            third_account = context.store.register(
                "duel-hourly-watcher", "local-password"
            )["id"]
            third_character = context.store.create_character(
                third_account, "Hourly Watcher"
            )["id"]
            third_generation = context.store.begin_session(third_account)
            context.store.select_character(
                third_account, third_generation, third_character
            )
            accepted = _accept_native_duel(context)
            with context.store.connection() as db:
                watcher = pvp.actions(
                    db,
                    {
                        "account_id": third_account,
                        "character_id": third_character,
                        "generation": third_generation,
                    },
                )
            self.assertEqual(
                [action["key"] for action in watcher], [f"pvp.watch.{event['id']}"]
            )

            # Public view exposes current encounter state and server-owned
            # actions, and identifies the real currently selected actor.
            with context.store.connection() as db, patch(
                "wakfu_server.objectives.player_travel.actions", return_value=[]
            ):
                view = player_views.snapshot(
                    db,
                    {
                        "account_id": context.account_a,
                        "character_id": context.char_a["id"],
                        "generation": context.generation_a,
                    },
                )
            self.assertEqual(view["actor"]["id"], context.char_a["id"])
            self.assertEqual(view["pvp"]["current"]["status"], "in_fight")
            self.assertEqual(
                [action["key"] for action in view["pvp"]["current"]["actions"]],
                [f"pvp.watch.{event['id']}"],
            )

            fight = context._finished_duel_with_registered_summon(accepted["fight_id"])
            with patch.object(
                reward_policies,
                "expand",
                return_value=[{"kind": "kamas", "amount": 100}],
            ), patch("wakfu_server.combat.fight_store._write_terminal_checkpoint"):
                settle(
                    context.store,
                    context.account_a,
                    context.generation_a,
                    context.char_a["id"],
                    fight,
                )
            with context.store.connection() as db, patch(
                "wakfu_server.objectives.player_travel.actions", return_value=[]
            ):
                completed = player_views.snapshot(
                    db,
                    {
                        "account_id": context.account_a,
                        "character_id": context.char_a["id"],
                        "generation": context.generation_a,
                    },
                )
            self.assertIsNone(completed["pvp"]["current"])
            history = completed["pvp"]["history"]
            self.assertEqual(len(history), 1)
            self.assertIsNotNone(history[0]["winner"])
            self.assertEqual(history[0]["winner"]["account_id"], context.account_a)


if __name__ == "__main__":
    unittest.main()
