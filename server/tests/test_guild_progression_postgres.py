"""Focused PostgreSQL qualification for native guild progression lifecycle."""

import os
from datetime import datetime, timedelta, timezone
import uuid
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
import test_guild_service_postgres as _guild_fixture
from wakfu_server.characters import guild_economy, guild_progression
from wakfu_server.characters.guild_native_validators import (
    encode_blazon,
    permission_bits,
    validate_rank_mask,
)
from wakfu_server.characters.guild_service import GuildService


class GuildProgressionPostgresTests(PostgresCase):
    """Exercise actual purchase, native clock completion, and reward outbox."""

    def setUp(self):
        if os.environ.get("WAKFU_RUN_GUILD_POSTGRES_TESTS") != "1":
            self.skipTest(
                "Set WAKFU_RUN_GUILD_POSTGRES_TESTS=1 for isolated guild DB tests"
            )
        super().setUp()
        self.service = GuildService(self.store)
        self.blazon = encode_blazon(
            emblem_id=1, background_id=2, background_color=3, emblem_color=4
        )
        bits = permission_bits()
        self.base_policy = {
            "enabled": True,
            "native_sync_enabled": True,
            "moderation_bonus_learning_factor": 0.0,
            "owner_id_semantics": "account",
            "creation_kamas": 10000,
            "creation_item": 16942,
            "max_members": 20,
            "max_ranks": 15,
            "name_pattern": r"[A-Za-z][A-Za-z0-9 ]{2,30}",
            "name_normalization": "NFKC_CASEFOLD",
            "allowed_blazons": [self.blazon],
            "leader_permissions": validate_rank_mask(268435454, highest=True),
            "member_permissions": validate_rank_mask(0, lowest=True),
            "permissions": {
                "invite": bits["ADD_MEMBER"],
                "rank_create": bits["EDIT_RANK"],
                "rank_edit": bits["EDIT_RANK"],
                "rank_remove": bits["EDIT_RANK"],
                "rank_move": bits["EDIT_RANK"],
                "member_rank": bits["CHANGE_MEMBER_RANK"],
                "kick": bits["REMOVE_MEMBER"],
                "description": bits["CHANGE_GUILD_DESCRIPTION"],
                "message": bits["CHANGE_GUILD_MESSAGE"],
            },
            "invitation_seconds": 3600,
            "description_max_bytes": 500,
            "message_max_bytes": 500,
            "weekly_points_limit": 7500,
            "earned_points_limit": 0,
            "last_earning_point_week": 0,
            "economy": {"treasury_enabled": True},
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.base_policy),),
            )
        self.owner = _guild_fixture.GuildServicePostgresTests._player(
            self, "Progression Owner"
        )
        self.guild_id = _guild_fixture.GuildServicePostgresTests._create(
            self, self.owner, "Guild Progression"
        )["guild"]["id"]
        self.policy = guild_progression.progression_policy(
            self.base_policy, enabled=True
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
            db.execute(
                "UPDATE guilds SET current_points=300 WHERE id=%s",
                (self.guild_id,),
            )
            # The simulated native learning clock spans several days; keep
            # the real selected session valid throughout that deterministic run.
            db.execute(
                "UPDATE sessions SET expires_at=CURRENT_TIMESTAMP + interval '400 days' "
                "WHERE account_id=%s AND generation=%s",
                (self.owner["account"], self.owner["generation"]),
            )

    def _bonus(self, identity, *, activate=False, key):
        return guild_economy.bonus_operation(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
            self.guild_id,
            identity,
            activate=activate,
            operation_key=key,
        )

    def _guild_row(self):
        with self.store.connection() as db:
            return dict(
                db.execute(
                    "SELECT * FROM guilds WHERE id=%s", (self.guild_id,)
                ).fetchone()
            )

    def test_native_bonus_gates_costs_clock_activation_and_compartment_snapshot(self):
        base_time = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        with patch.object(self.store, "now", return_value=base_time):
            with self.assertRaisesRegex(ValueError, "higher guild level"):
                self._bonus(11, key="too-early-level")
            with self.assertRaisesRegex(ValueError, "points"):
                self._bonus(75, key="insufficient-points")
            self.assertEqual(300, self._guild_row()["current_points"])
            with self.store.connection() as db:
                db.execute(
                    "UPDATE guilds SET current_points=100000 WHERE id=%s",
                    (self.guild_id,),
                )
            first = self._bonus(75, key="learn-level-two")
            self.assertEqual(100000 - 400, first["points"])
            self.assertEqual(
                2 * 60 * 60 * 1000,
                first["bonus"]["learned_at_ms"] - first["bonus"]["purchased_at_ms"],
            )
            with self.assertRaisesRegex(ValueError, "not finished learning"):
                self._bonus(75, activate=True, key="early-level-two")
            self.assertEqual(first, self._bonus(75, key="learn-level-two"))

        compartment_cases = (
            (11, 4, 3000, 16, 0),
            (33, 6, 5000, 48, 1),
            (50, 8, 10000, 96, 2),
            (69, 10, 20000, 168, 3),
        )
        now = base_time
        now = datetime.fromtimestamp(
            (first["bonus"]["learned_at_ms"] + 1) / 1000, timezone.utc
        )
        with patch.object(self.store, "now", return_value=now):
            guild_progression.tick(self.store)
        self.assertEqual(2, self._guild_row()["level"])
        for identity, level, cost, hours, compartment in compartment_cases:
            with self.subTest(bonus=identity):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE guilds SET level=%s WHERE id=%s", (level, self.guild_id)
                    )
                    before_points = db.execute(
                        "SELECT current_points FROM guilds WHERE id=%s",
                        (self.guild_id,),
                    ).fetchone()["current_points"]
                with patch.object(self.store, "now", return_value=now):
                    pending = self._bonus(identity, key=f"learn-{identity}")
                    self.assertEqual(before_points - cost, pending["points"])
                    self.assertEqual(
                        hours * 60 * 60 * 1000,
                        pending["bonus"]["learned_at_ms"]
                        - pending["bonus"]["purchased_at_ms"],
                    )
                    with self.assertRaisesRegex(ValueError, "not finished learning"):
                        self._bonus(identity, activate=True, key=f"early-{identity}")
                    if identity == 11:
                        with self.store.connection() as db:
                            db.execute(
                                "UPDATE guilds SET level=6 WHERE id=%s",
                                (self.guild_id,),
                            )
                        with self.assertRaisesRegex(
                            ValueError, "maximum simultaneous learning"
                        ):
                            self._bonus(33, key="concurrent-33")
                now = datetime.fromtimestamp(
                    (pending["bonus"]["learned_at_ms"] + 1) / 1000, timezone.utc
                )
                with patch.object(self.store, "now", return_value=now):
                    completed = guild_progression.tick(self.store)
                    self.assertIn(
                        self.guild_id, {guild_id for guild_id, _ in completed}
                    )
                    self.assertEqual((), guild_progression.tick(self.store))
                    snapshot = self.service.snapshot(
                        self.owner["account"],
                        self.owner["generation"],
                        self.owner["character"],
                    )
                self.assertIn(compartment, self._guild_row()["unlocked_compartments"])
                self.assertIn(
                    identity, {row["bonus_id"] for row in snapshot["bonuses"]}
                )
                if identity == 11:
                    self.assertEqual(
                        before_points - cost, self._guild_row()["current_points"]
                    )

    def test_native_quest_reward_outbox_uses_exact_earned_payload_once(self):
        from wakfu_server.achievements import service as achievement_service
        from wakfu_server.achievements import storage as achievement_storage

        native = guild_progression.catalog()["point_quests"]["1389"]
        reward = dict(native["rewards"][0])
        completion_ms = int(self.store.now().timestamp() * 1000)
        anchor = native["native"]["efu"]
        period_ms = native["native"]["efv"] * 1000
        cycle = str((completion_ms - anchor) // period_ms)
        reward.update(_guild_id=self.guild_id, _guild_completion_date_ms=completion_ms)
        with self.store.connection() as db:
            state = achievement_storage.load_locked(db, self.owner["character"])
            state["completed"] = [1389]
            state["completion_dates"] = {"1389": completion_ms}
            achievement_storage.store(db, self.owner["character"], state)
            achievement_storage.claim_reward(
                db,
                self.owner["character"],
                1389,
                "guild-daily:" + cycle,
                reward["d"],
                reward,
            )
            db.execute(
                "INSERT INTO character_guild_daily_quests "
                "(character_id,definition_id,cycle_index,activation_guild_id,earned_guild_id,"
                "activated_at_ms,completed_at_ms,progress) VALUES (%s,1389,%s,%s,%s,%s,%s,10)",
                (
                    self.owner["character"],
                    int(cycle),
                    self.guild_id,
                    self.guild_id,
                    completion_ms,
                    completion_ms,
                ),
            )
            character = self.store.character(
                self.owner["account"], self.owner["character"], db
            )
            achievement_service.drain_rewards(db, self.store, character)
        after = self.service.snapshot(
            self.owner["account"], self.owner["generation"], self.owner["character"]
        )
        self.assertEqual(315, after["guild"]["current_points"])
        with self.store.connection() as db:
            self.assertEqual(
                [], achievement_storage.pending_rewards(db, self.owner["character"])
            )
            character = self.store.character(
                self.owner["account"], self.owner["character"], db
            )
            self.assertEqual(
                [], achievement_service.drain_rewards(db, self.store, character)
            )
        self.assertEqual(
            315,
            self.service.snapshot(
                self.owner["account"], self.owner["generation"], self.owner["character"]
            )["guild"]["current_points"],
        )

    def test_pending_quest_reward_waits_for_its_original_cycle_ledger(self):
        from wakfu_server.achievements import service as achievement_service
        from wakfu_server.achievements import storage as achievement_storage

        native = guild_progression.catalog()["point_quests"]["1389"]
        reward = dict(native["rewards"][0])
        completion_ms = int(self.store.now().timestamp() * 1000)
        anchor = native["native"]["efu"]
        period_ms = native["native"]["efv"] * 1000
        cycle_index = (completion_ms - anchor) // period_ms
        cycle_key = f"guild-daily:{cycle_index}"
        reward.update(_guild_id=self.guild_id, _guild_completion_date_ms=completion_ms)
        with self.store.connection() as db:
            state = achievement_storage.load_locked(db, self.owner["character"])
            state["completed"] = [1389]
            state["completion_dates"] = {"1389": completion_ms}
            achievement_storage.store(db, self.owner["character"], state)
            achievement_storage.claim_reward(
                db, self.owner["character"], 1389, cycle_key, reward["d"], reward
            )
            db.execute(
                "INSERT INTO character_guild_daily_quests "
                "(character_id,definition_id,cycle_index,activation_guild_id,earned_guild_id,"
                "activated_at_ms,completed_at_ms,progress) VALUES (%s,1389,%s,%s,%s,%s,%s,10)",
                (
                    self.owner["character"],
                    cycle_index,
                    self.guild_id,
                    self.guild_id,
                    completion_ms,
                    completion_ms,
                ),
            )
            # The current achievement journal may be reset for a newer cycle;
            # the exact historical daily-cycle ledger remains the authority
            # for this already-earned pending reward.
            state["completed"] = []
            state["completion_dates"] = {}
            achievement_storage.store(db, self.owner["character"], state)
            character = self.store.character(
                self.owner["account"], self.owner["character"], db
            )
            self.assertEqual(
                [], achievement_service.drain_rewards(db, self.store, character)
            )
            self.assertEqual(
                [], achievement_storage.pending_rewards(db, self.owner["character"])
            )
        snapshot = self.service.snapshot(
            self.owner["account"], self.owner["generation"], self.owner["character"]
        )
        self.assertEqual(315, snapshot["guild"]["current_points"])
        with self.store.connection() as db:
            character = self.store.character(
                self.owner["account"], self.owner["character"], db
            )
            self.assertEqual(
                [], achievement_service.drain_rewards(db, self.store, character)
            )
        self.assertEqual(
            315,
            self.service.snapshot(
                self.owner["account"], self.owner["generation"], self.owner["character"]
            )["guild"]["current_points"],
        )

    def test_temporary_bonus_manual_ready_expiry_renewal_replay_and_dissolution(self):
        from wakfu_server.guild_member_effects import projection
        from wakfu_server.guild_service import _has_unsettled_holdings

        now = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        with self.store.connection() as db:
            db.execute(
                "UPDATE guilds SET level=10,current_points=100000 WHERE id=%s",
                (self.guild_id,),
            )
        for identity in (72, 73):
            with self.subTest(bonus=identity):
                key = f"native-identical-purchase-{identity}"
                activate_key = f"native-identical-activate-{identity}"
                before = self._guild_row()["current_points"]
                with patch.object(self.store, "now", return_value=now):
                    purchased = self._bonus(identity, key=key)
                    self.assertEqual(before - 4500, purchased["points"])
                    self.assertEqual(purchased, self._bonus(identity, key=key))
                    with self.assertRaisesRegex(ValueError, "not finished learning"):
                        self._bonus(identity, activate=True, key=activate_key)
                ready = now + timedelta(hours=24)
                with patch.object(self.store, "now", return_value=ready):
                    guild_progression.tick(self.store)
                    with self.store.connection() as db:
                        state = guild_economy.economy_record(db, self.guild_id)
                        record = state["bonuses"][str(identity)]
                        self.assertFalse(record["active"])
                        self.assertNotIn("activated_at_ms", record)
                    activated = self._bonus(identity, activate=True, key=activate_key)
                    self.assertTrue(activated["bonus"]["active"])
                    self.assertEqual(
                        activated,
                        self._bonus(identity, activate=True, key=activate_key),
                    )
                    self.assertEqual(before - 4500, self._guild_row()["current_points"])
                    with self.store.connection() as db:
                        character = self.store.character(
                            self.owner["account"], self.owner["character"], db
                        )
                        records = guild_economy.bonus_snapshot(db, self.guild_id)
                    self.assertIn(
                        identity,
                        [
                            row["bonus_id"]
                            for row in projection(
                                character, records, int(ready.timestamp() * 1000)
                            )
                        ],
                    )
                expiry = ready + timedelta(hours=6)
                with patch.object(self.store, "now", return_value=expiry):
                    guild_progression.tick(self.store)
                    with self.store.connection() as db:
                        state = guild_economy.economy_record(db, self.guild_id)
                        self.assertNotIn(str(identity), state["bonuses"])
                        self.assertEqual(1, state["bonus_cycles"][str(identity)])
                        character = self.store.character(
                            self.owner["account"], self.owner["character"], db
                        )
                    self.assertNotIn(
                        identity,
                        [
                            row["bonus_id"]
                            for row in projection(
                                character,
                                state["bonuses"],
                                int(expiry.timestamp() * 1000),
                            )
                        ],
                    )
                    snapshot = self.service.snapshot(
                        self.owner["account"],
                        self.owner["generation"],
                        self.owner["character"],
                    )
                    self.assertNotIn(
                        identity, [row["bonus_id"] for row in snapshot["bonuses"]]
                    )
                    renewal = self._bonus(identity, key=key)
                    self.assertEqual(before - 9000, renewal["points"])
                    self.assertEqual(1, renewal["bonus"]["cycle"])
                    self.assertFalse(renewal["bonus"]["active"])
                    self.assertEqual(renewal, self._bonus(identity, key=key))
                    with self.assertRaisesRegex(ValueError, "not finished learning"):
                        self._bonus(identity, activate=True, key=activate_key)
                    self.assertEqual(before - 9000, self._guild_row()["current_points"])
                now = expiry + timedelta(days=2)
        with self.store.connection() as db:
            state = guild_economy.economy_record(db, self.guild_id)
        self.assertFalse(_has_unsettled_holdings("economy", state))
        for bad in ({"72": True}, {"72": -1}, {"072": 1}, {"unknown": 1}):
            self.assertTrue(
                _has_unsettled_holdings("economy", dict(state, bonus_cycles=bad))
            )
        self.service.dissolve(
            self.owner["account"], self.owner["generation"], self.owner["character"]
        )
        self.assertIsNotNone(self._guild_row()["dissolved_at"])

    def test_native_weekly_cap_42_preserves_earned_points_and_resets_next_week(self):
        from wakfu_server.guild_model import native_model
        from wakfu_server.guild_weekly_cap import effective_cap

        start = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
        week = (start.date() - timedelta(days=start.weekday())).isoformat()
        with patch.object(self.store, "now", return_value=start):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE guilds SET level=7,current_points=30000,total_points=30000,weekly_points=1490 WHERE id=%s",
                    (self.guild_id,),
                )
                state = guild_economy._state(db, self.guild_id)
                state["week"] = week
                guild_economy._save(
                    db, self.guild_id, state, "test_weekly_cap_seed", {}
                )
            earned = guild_economy.accrue_points(
                self.store,
                self.guild_id,
                self.owner["character"],
                event_key="cap-42-before",
                source="native_achievement:1389",
            )
            self.assertEqual(15, earned["awarded"])
            self.assertEqual(1505, earned["weekly_earned"])
            self.assertEqual(
                earned,
                guild_economy.accrue_points(
                    self.store,
                    self.guild_id,
                    self.owner["character"],
                    event_key="cap-42-before",
                    source="native_achievement:1389",
                ),
            )
            balance_before = self._guild_row()["current_points"]
            purchase = self._bonus(42, key="learn-weekly-cap-42")
            self.assertEqual(balance_before - 20000, purchase["points"])
            self.assertEqual(
                4 * 24 * 60 * 60 * 1000,
                purchase["bonus"]["learned_at_ms"]
                - purchase["bonus"]["purchased_at_ms"],
            )
            with self.assertRaisesRegex(ValueError, "not finished learning"):
                self._bonus(42, activate=True, key="activate-weekly-cap-42")

        ready = start + timedelta(days=4, milliseconds=1)
        with patch.object(self.store, "now", return_value=ready):
            self.assertIn(
                self.guild_id,
                {guild for guild, _ in guild_progression.tick(self.store)},
            )
            state = guild_economy.snapshot(
                self.store,
                self.owner["account"],
                self.owner["generation"],
                self.owner["character"],
                self.guild_id,
            )
            self.assertEqual(
                1500, effective_cap(self.policy["economy"], self._guild_row(), state)
            )
            self.assertEqual(1505, self._guild_row()["weekly_points"])
            snapshot = self.service.snapshot(
                self.owner["account"], self.owner["generation"], self.owner["character"]
            )
            native = native_model(snapshot)
            self.assertEqual(1500, native["weeklyPointsLimit"])
            self.assertEqual(1505, native["earnedPointsLimit"])
            blocked = guild_economy.accrue_points(
                self.store,
                self.guild_id,
                self.owner["character"],
                event_key="cap-42-still-full",
                source="native_achievement:1389",
            )
            self.assertEqual(0, blocked["awarded"])
            self.assertEqual(1505, blocked["weekly_earned"])
            self.assertEqual(purchase, self._bonus(42, key="learn-weekly-cap-42"))

        next_week = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        with patch.object(self.store, "now", return_value=next_week):
            advanced = guild_economy.accrue_points(
                self.store,
                self.guild_id,
                self.owner["character"],
                event_key="cap-42-next-week",
                source="native_achievement:1389",
            )
            self.assertEqual(15, advanced["awarded"])
            self.assertEqual(15, advanced["weekly_earned"])
            self.assertEqual(
                advanced,
                guild_economy.accrue_points(
                    self.store,
                    self.guild_id,
                    self.owner["character"],
                    event_key="cap-42-next-week",
                    source="native_achievement:1389",
                ),
            )
            self.assertEqual(15, self._guild_row()["weekly_points"])

    def test_native_bonus_84_paid_unlock_provisions_or_adopts_owned_world_atomically(
        self,
    ):
        from wakfu_server import haven_world_travel
        from wakfu_server.guild_haven_world import (
            create_assignment,
            entry_plan,
            provision_unlocked_world,
        )
        from wakfu_server.haven_world_terrain import ENTRY, TEMPLATE_MAP_ID
        from wakfu_server.position_buffer import Positions

        policy = dict(self.policy, haven_world={"enabled": True})
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(policy),),
            )
            db.execute(
                "UPDATE guilds SET level=10,current_points=200000,total_points=200000 WHERE id=%s",
                (self.guild_id,),
            )
        self.policy = policy

        balance = self._guild_row()["current_points"]
        with patch(
            "wakfu_server.guild_haven_world.provision_unlocked_world",
            side_effect=RuntimeError("injected provisioning fault"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected provisioning fault"):
                self._bonus(84, key="unlock-world-84")
        self.assertEqual(balance, self._guild_row()["current_points"])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM guild_haven_worlds WHERE guild_id=%s",
                    (self.guild_id,),
                ).fetchone()
            )
            state = guild_economy.economy_record(db, self.guild_id)
            self.assertNotIn("84", state.get("bonuses", {}))

        purchased = self._bonus(84, key="unlock-world-84")
        self.assertEqual(balance - 100000, purchased["points"])
        self.assertEqual(
            0,
            purchased["bonus"]["learned_at_ms"] - purchased["bonus"]["purchased_at_ms"],
        )
        self.assertTrue(purchased["bonus"]["active"])
        self.assertEqual(purchased, self._bonus(84, key="unlock-world-84"))
        with self.store.connection() as db:
            binding = dict(
                db.execute(
                    "SELECT * FROM guild_haven_worlds WHERE guild_id=%s",
                    (self.guild_id,),
                ).fetchone()
            )
            self.assertEqual(-self.guild_id, binding["native_world_id"])
            self.assertEqual(
                "explicit_native_bonus84_base_world_v1", binding["assignment_origin"]
            )
            self.assertEqual(TEMPLATE_MAP_ID, binding["map_id"])
            self.assertEqual(
                ENTRY, (binding["entry_x"], binding["entry_y"], binding["entry_z"])
            )
            adopted = provision_unlocked_world(
                db, self.store, self.owner["account"], self.guild_id
            )
            self.assertEqual(binding["instance_id"], adopted["instance_id"])
            self.assertEqual(
                1,
                db.execute(
                    "SELECT count(*) AS n FROM guild_haven_worlds WHERE guild_id=%s",
                    (self.guild_id,),
                ).fetchone()["n"],
            )

        destination = entry_plan(
            self.store,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
        )
        self.assertEqual(binding["instance_id"], destination["instance_id"])
        positions = Positions(
            self.store,
            lease_active=lambda account, generation, character: (
                account == self.owner["account"]
                and generation == self.owner["generation"]
            ),
        )
        character = self.store.character(self.owner["account"], self.owner["character"])
        positions.attach(self.owner["account"], self.owner["generation"], character)
        entered = haven_world_travel.travel(
            self.store,
            positions,
            self.owner["account"],
            self.owner["generation"],
            self.owner["character"],
        )
        self.assertEqual(-self.guild_id, entered["character"]["native_world_id"])
        self.assertEqual(binding["instance_id"], entered["character"]["instance_id"])

        # A member of another guild cannot invoke the trusted provisioning
        # helper with this account's identity.
        other = _guild_fixture.GuildServicePostgresTests._player(
            self, "Other World Guild Member"
        )
        other_guild = _guild_fixture.GuildServicePostgresTests._create(
            self, other, "Other World Guild"
        )["guild"]["id"]
        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "actual purchasing guild member"):
                provision_unlocked_world(
                    db, self.store, self.owner["account"], other_guild
                )
