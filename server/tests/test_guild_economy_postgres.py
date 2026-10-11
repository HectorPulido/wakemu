"""Prepared isolated PostgreSQL economy tests; never enabled implicitly."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
import test_guild_service_postgres as guild_fixture
from wakfu_server.characters.guild_service import GuildService
from wakfu_server.characters import guild_economy as economy


class GuildEconomyPostgresTests(PostgresCase):
    _player = guild_fixture.GuildServicePostgresTests._player
    _create = guild_fixture.GuildServicePostgresTests._create
    _wallet = guild_fixture.GuildServicePostgresTests._wallet

    def setUp(self):
        if os.environ.get("WAKFU_RUN_GUILD_POSTGRES_TESTS") != "1":
            self.skipTest(
                "Set WAKFU_RUN_GUILD_POSTGRES_TESTS=1 for isolated guild DB tests"
            )
        super().setUp()
        self.service = GuildService(self.store)
        self.policy = dict(
            enabled=True,
            owner_id_semantics="account",
            creation_kamas=10000,
            creation_item=16942,
            max_members=20,
            max_ranks=15,
            name_pattern=r"[A-Za-z][A-Za-z0-9 ]{2,30}",
            name_normalization="NFKC_CASEFOLD",
            allowed_blazons=[123],
            leader_permissions=(1 << 63) - 1,
            member_permissions=0,
            permissions={},
            invitation_seconds=3600,
            economy=dict(
                treasury_enabled=True,
                progression_enabled=True,
                bonuses_enabled=True,
                permission_bits=dict(
                    treasury_deposit=0,
                    treasury_withdraw=1,
                    bonus_learn=2,
                    bonus_activate=3,
                ),
                point_sources={"fight": 7},
                weekly_point_cap=10,
                bonus_catalog={
                    "1": dict(
                        cost=3,
                        learning_duration_ms=1000,
                        effect=dict(kind="unlock_level", value=2, duration_ms=-1),
                    )
                },
            ),
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='guild_policy'",
                (Jsonb(self.policy),),
            )
        self.owner = self._player("Economy Owner")
        self.guild_id = self._create(self.owner, "Guild Economy")["guild"]["id"]

    def _transfer(self, amount, key, withdraw=False):
        p = self.owner
        return economy.transfer_kamas(
            self.store,
            p["account"],
            p["generation"],
            p["character"],
            self.guild_id,
            amount,
            withdraw=withdraw,
            operation_key=key,
        )

    def _state(self):
        p = self.owner
        return economy.snapshot(
            self.store, p["account"], p["generation"], p["character"], self.guild_id
        )

    def _points(self, key):
        return economy.accrue_points(
            self.store,
            self.guild_id,
            self.owner["character"],
            event_key=key,
            source="fight",
        )

    def _bonus(self, key, activate=False):
        p = self.owner
        return economy.bonus_operation(
            self.store,
            p["account"],
            p["generation"],
            p["character"],
            self.guild_id,
            1,
            activate=activate,
            operation_key=key,
        )

    def test_treasury_conservation_idempotence_and_insufficient_balance(self):
        initial = self._wallet(self.owner["account"])
        first = self._transfer(100, "deposit")
        self.assertEqual(first, self._transfer(100, "deposit"))
        self.assertEqual(
            initial, self._wallet(self.owner["account"]) + self._state()["kamas"]
        )
        self._transfer(40, "withdraw", True)
        self.assertEqual(
            initial, self._wallet(self.owner["account"]) + self._state()["kamas"]
        )
        with self.assertRaises(ValueError):
            self._transfer(61, "insufficient", True)
        with self.assertRaises(ValueError):
            self._transfer(101, "deposit")
        self.assertEqual(60, self._state()["kamas"])

    def test_treasury_rollback_after_wallet_write(self):
        initial = self._wallet(self.owner["account"])
        with patch.object(economy, "_save", side_effect=RuntimeError("rollback")):
            with self.assertRaises(RuntimeError):
                self._transfer(100, "rollback")
        self.assertEqual(initial, self._wallet(self.owner["account"]))
        self.assertEqual(0, self._state().get("kamas", 0))
        self.assertEqual(100, self._transfer(100, "rollback")["treasury_kamas"])

    def test_wallet_overflow_does_not_remove_treasury(self):
        self._transfer(1, "deposit")
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_wallets SET kamas=%s WHERE account_id=%s",
                (2**63 - 1, self.owner["account"]),
            )
        with self.assertRaises(ValueError):
            self._transfer(1, "overflow", True)
        self.assertEqual(1, self._state()["kamas"])

    def test_concurrent_withdrawals_cannot_overspend(self):
        self._transfer(100, "deposit")

        def withdraw(key):
            try:
                self._transfer(80, key, True)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(withdraw, ["first", "second"]))
        self.assertEqual(1, sum(results))
        self.assertEqual(20, self._state()["kamas"])

    def test_points_duplicate_weekly_cap_and_monday_rollover(self):
        sunday = datetime(2026, 10, 11, 23, 59, tzinfo=timezone.utc)
        monday = datetime(2026, 10, 12, tzinfo=timezone.utc)
        with patch.object(self.store, "now", return_value=sunday):
            first = self._points("fight-one")
            self.assertEqual(first, self._points("fight-one"))
            self.assertEqual(3, self._points("fight-two")["awarded"])
            self.assertEqual(0, self._points("fight-three")["awarded"])
        with patch.object(self.store, "now", return_value=monday):
            self.assertEqual(7, self._points("fight-four")["awarded"])
        # Read with actual session time, independently of trusted event clock.
        state = self._state()
        self.assertEqual(17, state["current_points"])
        self.assertEqual(17, state["total_points"])
        self.assertEqual(7, state["weekly_points"])

    def test_bonus_learning_activation_and_point_columns(self):
        self._points("funding")
        first = self._bonus("learn")
        self.assertEqual(first, self._bonus("learn"))
        with self.assertRaises(ValueError):
            self._bonus("early", True)
        later = datetime.fromtimestamp(
            (first["bonus"]["learned_at_ms"] + 1) / 1000, timezone.utc
        )
        with patch.object(self.store, "now", return_value=later):
            active = self._bonus("activate", True)
            self.assertEqual(active, self._bonus("activate", True))
            with self.assertRaises(ValueError):
                self._bonus("activate-again", True)
        with self.store.connection() as db:
            guild = db.execute(
                "SELECT level,current_points,total_points FROM guilds WHERE id=%s",
                (self.guild_id,),
            ).fetchone()
        self.assertEqual(
            {"level": 2, "current_points": 4, "total_points": 7}, dict(guild)
        )
