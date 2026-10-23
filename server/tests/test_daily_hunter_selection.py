"""One compound qualification of owned UTC-day selection and immutable pinning."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from test_guild_service_postgres import GuildServicePostgresTests
from wakfu_server.objectives import environmental_daily_selection as daily
from wakfu_server.objectives import environmental_presence as presence


class DailyHunterSelectionTests(PostgresCase):
    _player = GuildServicePostgresTests._player

    def test_owned_concurrent_global_choice_turnover_repin_and_vacant_no_writes(self):
        owners = [self._player("Daily first"), self._player("Daily second")]
        characters = [
            self.store.character(o["account"], o["character"]) for o in owners
        ]
        identities = {c["id"]: (o["generation"], c) for o, c in zip(owners, characters)}

        class Occupancy:
            occupied = True

            def scope_presence(self, map_id, instance_id):
                return 7 if self.occupied else None

            def live_identity(self, *, character_id):
                return identities.get(character_id)

        world = Occupancy()
        clock = [datetime(2050, 1, 1, tzinfo=timezone.utc)]
        sql = Path(".runtime/staging/daily-hunter-294/294_daily_hunter_selection.sql")
        if not sql.exists():
            sql = Path("server/migrations/294_daily_hunter_selection.sql")
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET expires_at=%s WHERE account_id=ANY(%s)",
                (clock[0] + timedelta(days=3), [o["account"] for o in owners]),
            )
            if (
                db.execute(
                    "SELECT to_regclass('recurring_hunter_daily_pools') AS t"
                ).fetchone()["t"]
                is None
            ):
                db.execute(sql.read_text())
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_daily_members WHERE pool_version="
                    "'wakemu.daily-hunter50-modulox62-v1'"
                ).fetchone()["n"],
                112,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT category_id) AS n FROM recurring_hunter_daily_members "
                    "WHERE pool_version=(SELECT pool_version FROM recurring_hunter_daily_active WHERE singleton)"
                ).fetchone()["n"],
                20,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_daily_members WHERE category_id=703 AND pool_version='wakemu.daily-hunter50-modulox62-v1'"
                ).fetchone()["n"],
                0,
            )
        with patch.object(presence, "_world", world), patch.object(
            self.store, "now", side_effect=lambda: clock[0]
        ):
            with self.store.connection() as db:
                self.assertEqual(
                    daily.select_for_character(db, self.store, characters[0]), ()
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM recurring_hunter_daily_choices"
                    ).fetchone()["n"],
                    0,
                )
                db.execute("UPDATE recurring_hunter_daily_active SET enabled=true")
            world.occupied = False

            class NoSQL:
                def execute(self, *args, **kwargs):
                    raise AssertionError("Vacant scope touched SQL")

            self.assertEqual(
                daily.select_for_character(NoSQL(), self.store, characters[0]), ()
            )
            world.occupied = True

            # Detach immediately after the LAST real insert. The final fence
            # must reject and roll back every choice from this transaction.
            class DepartOnLastInsert:
                def __init__(self, connection):
                    self.connection = connection
                    self.inserted = 0

                def __getattr__(self, name):
                    return getattr(self.connection, name)

                def execute(self, sql, parameters=None):
                    result = self.connection.execute(sql, parameters)
                    if sql.startswith("INSERT INTO recurring_hunter_daily_choices "):
                        self.inserted += 1
                        if self.inserted == 20:
                            world.occupied = False
                    return result

            with self.assertRaisesRegex(
                ValueError, "presence changed before completion"
            ):
                with self.store.connection() as db:
                    daily.select_for_character(
                        DepartOnLastInsert(db), self.store, characters[0]
                    )
            world.occupied = True
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM recurring_hunter_daily_choices"
                    ).fetchone()["n"],
                    0,
                )

            def select(character):
                with self.store.connection() as db:
                    return daily.select_for_character(db, self.store, character)

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(select, characters))
            signature = lambda rows: [
                (
                    r["category_id"],
                    r["utc_day"],
                    r["pool_version"],
                    r["definition_id"],
                    r["version"],
                )
                for r in rows
            ]
            self.assertEqual(signature(results[0]), signature(results[1]))
            self.assertEqual(len(results[0]), 20)
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM recurring_hunter_daily_choices"
                    ).fetchone()["n"],
                    20,
                )
                first = results[0][0]
                self.assertIsNone(
                    daily.chosen_for_receipt(
                        db,
                        category_id=first["category_id"],
                        occurred_at_ms=int(
                            (clock[0] - timedelta(days=1)).timestamp() * 1000
                        ),
                    )
                )
                self.assertIsNone(
                    daily.chosen_for_receipt(
                        db,
                        category_id=first["category_id"],
                        occurred_at_ms=int(clock[0].timestamp() * 1000),
                        definition_id=-1,
                    )
                )
                with self.assertRaises(ValueError):
                    daily.select_for_character(
                        db,
                        self.store,
                        characters[0],
                        now_ms=int((clock[0] - timedelta(days=1)).timestamp() * 1000),
                    )
                # A new immutable source pool can be activated, but today's
                # already-issued global choices retain their original version.
                db.execute(
                    "INSERT INTO recurring_hunter_daily_pools VALUES('qualified45-v2',%s,%s,false)",
                    (daily.POLICY, "a" * 64),
                )
                db.execute(
                    "INSERT INTO recurring_hunter_daily_members SELECT 'qualified45-v2',category_id,definition_id,version "
                    "FROM recurring_hunter_daily_members WHERE pool_version=%s",
                    (first["pool_version"],),
                )
                db.execute(
                    "UPDATE recurring_hunter_daily_pools SET sealed=true WHERE pool_version='qualified45-v2'"
                )
                db.execute(
                    "UPDATE recurring_hunter_daily_active SET pool_version='qualified45-v2'"
                )
                self.assertEqual(
                    signature(
                        daily.select_for_character(db, self.store, characters[0])
                    ),
                    signature(results[0]),
                )
            clock[0] += timedelta(days=1)
            next_day = select(characters[1])
            self.assertEqual(len(next_day), 20)
            self.assertEqual({r["pool_version"] for r in next_day}, {"qualified45-v2"})
            self.assertEqual(
                {r["utc_day"] for r in next_day}, {results[0][0]["utc_day"] + 1}
            )
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM recurring_hunter_daily_choices"
                    ).fetchone()["n"],
                    40,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM recurring_hunter_acceptances"
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    signature(
                        daily.select_for_character(db, self.store, characters[0])
                    ),
                    signature(next_day),
                )
