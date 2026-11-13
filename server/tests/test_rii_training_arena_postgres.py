"""Exercise the Rii floor relocation and recovery against isolated Postgres."""
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from psycopg.types.json import Jsonb

from postgres_case import PostgresCase
from wakfu_server.achievements import rii_training_arena as arena
from wakfu_server import heroes


class RiiTrainingTransitPostgresTests(PostgresCase):
    def test_group_and_ready_receipt_commit_or_rollback_together(self):
        account = self.store.register("rii-floor-atomic", "test-password")["id"]
        character = self.store.create_character(account, "Rii Atomic")
        generation = self.store.begin_session(account)
        character = self.store.select_character(account, generation, character["id"])
        pedestal = dict(map_id=1388, instance_id=0, x=1, y=-19, z=3)
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            source = self.store.transition_map(
                account, generation, character["id"], character, pedestal
            )
            floor = arena.enter(
                self.store,
                account,
                generation,
                source,
                10608,
                available=lambda position: True,
            )
        marked = dict(floor, _rii_training_objective=10608)

        def register(db, identity):
            db.execute(
                "INSERT INTO combat_groups(map_id,instance_id,group_id,members,status) "
                "VALUES(1388,0,%s,%s,'available')",
                (identity, Jsonb([{"id": -identity, "ref": 5466}])),
            )
            arena.mark_setup_ready_in_transaction(db, marked, 10608)

        with self.assertRaisesRegex(RuntimeError, "injected rollback"):
            with self.store.connection() as db:
                register(db, 1001)
                raise RuntimeError("injected rollback")
        with self.reopen().connection() as db:
            self.assertTrue(
                db.execute(
                    "SELECT setup_failed FROM rii_training_transits WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["setup_failed"]
            )
            self.assertIsNone(
                db.execute("SELECT 1 FROM combat_groups WHERE group_id=1001").fetchone()
            )
        with self.store.connection() as db:
            register(db, 1002)
        with self.reopen().connection() as db:
            self.assertFalse(
                db.execute(
                    "SELECT setup_failed FROM rii_training_transits WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["setup_failed"]
            )
            self.assertIsNotNone(
                db.execute("SELECT 1 FROM combat_groups WHERE group_id=1002").fetchone()
            )
        self.assertTrue(arena.setup_is_ready(self.store, account, character["id"]))
        with self.assertRaisesRegex(ValueError, "already pending"):
            arena.enter(
                self.store,
                account,
                generation,
                floor,
                10609,
                available=lambda position: True,
            )
        resumed = arena.enter(
            self.store,
            account,
            generation,
            floor,
            10608,
            available=lambda position: True,
        )
        self.assertEqual(
            tuple(resumed[k] for k in arena.POSITION),
            tuple(floor[k] for k in arena.POSITION),
        )
        self.assertFalse(arena.setup_is_ready(self.store, account, character["id"]))
        with self.store.connection() as db:
            arena.mark_setup_ready_in_transaction(db, marked, 10608)
        self.assertTrue(arena.setup_is_ready(self.reopen(), account, character["id"]))
        self.assertIsNone(
            arena.return_to_source(
                self.store,
                account,
                generation,
                floor,
                available=lambda position: True,
                only_completed=True,
            )
        )

    def test_individual_withdrawal_allows_return_while_shared_fight_stays_active(self):
        account = self.store.register("rii-floor-withdraw", "test-password")["id"]
        character = self.store.create_character(account, "Rii Withdraw")
        generation = self.store.begin_session(account)
        character = self.store.select_character(account, generation, character["id"])
        source_position = dict(map_id=1388, instance_id=0, x=1, y=-19, z=3)
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            source = self.store.transition_map(
                account, generation, character["id"], character, source_position
            )
            floor = arena.enter(
                self.store,
                account,
                generation,
                source,
                10608,
                available=lambda position: True,
            )
            with self.store.connection() as db:
                fight_id = db.execute(
                    "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                    "VALUES(%s,%s,%s,0,%s)",
                    (fight_id, character["id"], account, generation),
                )
            with self.assertRaisesRegex(ValueError, "during combat"):
                arena.return_to_source(
                    self.store,
                    account,
                    generation,
                    floor,
                    available=lambda position: True,
                )
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO combat_pve_withdrawals(fight_id,character_id,account_id,session_generation,created_at) "
                    "VALUES(%s,%s,%s,%s,%s)",
                    (fight_id, character["id"], account, generation, self.store.now()),
                )
            recovered = arena.return_to_source(
                self.store, account, generation, floor, available=lambda position: True
            )
        self.assertEqual(
            tuple(recovered[k] for k in arena.POSITION),
            tuple(source_position[k] for k in arena.POSITION),
        )
        with self.reopen().connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight_id,)
                ).fetchone()["status"],
                "active",
            )

    def test_company_follows_transit_and_failed_setup_recovers_after_relogin(self):
        account = self.store.register("rii-floor-company", "test-password")["id"]
        leader = self.store.create_character(account, "Rii Leader")
        hero = self.store.create_character(account, "Rii Companion")
        generation = self.store.begin_session(account)
        selected = self.store.select_character(account, generation, leader["id"])
        heroes.add(self.store, account, generation, leader["id"], hero["id"])
        pedestal = dict(map_id=1388, instance_id=0, x=1, y=-19, z=3)
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            source = self.store.transition_map(
                account, generation, leader["id"], selected, pedestal
            )
            floor = arena.enter(
                self.store,
                account,
                generation,
                source,
                10609,
                available=lambda position: True,
            )
            with self.reopen().connection() as db:
                companion = self.store.character(account, hero["id"], db)
                roster = heroes.load_roster(db, self.store, account, leader["id"])
                self.assertEqual(
                    [item["id"] for item in roster["heroes"]], [hero["id"]]
                )
                self.assertEqual(
                    tuple(companion[k] for k in arena.POSITION),
                    tuple(floor[k] for k in arena.POSITION),
                )
            arena.mark_setup_failed(self.store, account, generation, floor)
            generation = self.store.begin_session(account)
            reselected = self.store.select_character(account, generation, leader["id"])
            self.assertTrue(arena.pending(self.store, account, leader["id"]))
            recovered = arena.return_to_source(
                self.store,
                account,
                generation,
                reselected,
                available=lambda position: True,
                only_completed=True,
            )
        self.assertEqual(
            tuple(recovered[k] for k in arena.POSITION),
            tuple(pedestal[k] for k in arena.POSITION),
        )
        with self.reopen().connection() as db:
            companion = self.store.character(account, hero["id"], db)
            roster = heroes.load_roster(db, self.store, account, leader["id"])
            self.assertEqual([item["id"] for item in roster["heroes"]], [hero["id"]])
            self.assertEqual(
                tuple(companion[k] for k in arena.POSITION),
                tuple(pedestal[k] for k in arena.POSITION),
            )
            self.assertFalse(arena.pending(self.store, account, leader["id"]))

    def test_failed_setup_reconnect_recovers_without_completed_quest(self):
        account = self.store.register("rii-floor-recover", "test-password")["id"]
        character = self.store.create_character(account, "Rii Recovery")
        generation = self.store.begin_session(account)
        character = self.store.select_character(account, generation, character["id"])
        source_position = dict(map_id=1388, instance_id=0, x=1, y=-19, z=3)
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            source = self.store.transition_map(
                account, generation, character["id"], character, source_position
            )
            floor = arena.enter(
                self.store,
                account,
                generation,
                source,
                10608,
                available=lambda position: True,
            )

            def marker_failure(_moved):
                raise RuntimeError("injected marker failure")

            events = []
            with self.assertRaisesRegex(ValueError, "could not be prepared"):
                arena.stage(
                    lambda: floor,
                    lambda moved: None,
                    lambda moved: events.append("return") or None,
                    lambda moved: events.append("floor"),
                    lambda moved: events.append("source"),
                    marker_failure,
                    lambda moved: arena.setup_is_ready(
                        self.store, account, moved["id"]
                    ),
                )
            self.assertEqual(events, ["return", "floor"])
            self.assertIsNone(
                arena.return_to_source(
                    self.store,
                    account,
                    generation,
                    floor,
                    available=lambda position: False,
                    only_completed=True,
                )
            )
            with self.reopen().connection() as db:
                row = db.execute(
                    "SELECT setup_failed FROM rii_training_transits WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
            self.assertTrue(row["setup_failed"])
            recovered = arena.return_to_source(
                self.store,
                account,
                generation,
                floor,
                available=lambda position: True,
                only_completed=True,
            )
        self.assertEqual(
            tuple(recovered[k] for k in arena.POSITION),
            tuple(source_position[k] for k in arena.POSITION),
        )

    def test_two_accounts_reserve_distinct_destinations_and_return(self):
        players = []
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            for index in range(2):
                account = self.store.register(
                    f"rii-floor-peer-{index}", "test-password"
                )["id"]
                character = self.store.create_character(
                    account, ("Rii Alpha", "Rii Beta")[index]
                )
                generation = self.store.begin_session(account)
                selected = self.store.select_character(
                    account, generation, character["id"]
                )
                source = self.store.transition_map(
                    account,
                    generation,
                    character["id"],
                    selected,
                    dict(map_id=1388, instance_id=0, x=index, y=-19, z=3),
                )
                players.append((account, generation, source))
            barrier = Barrier(2, timeout=10)

            def move(player):
                account, generation, source = player
                barrier.wait()
                return arena.enter(
                    self.store,
                    account,
                    generation,
                    source,
                    10608,
                    available=lambda position: True,
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                floors = list(executor.map(move, players))
            self.assertNotEqual(
                tuple(floors[0][k] for k in ("x", "y", "z")),
                tuple(floors[1][k] for k in ("x", "y", "z")),
            )
            for player, floor in zip(players, floors):
                account, generation, source = player
                returned = arena.return_to_source(
                    self.store,
                    account,
                    generation,
                    floor,
                    available=lambda position: True,
                )
                self.assertEqual(
                    tuple(returned[k] for k in arena.POSITION),
                    tuple(source[k] for k in arena.POSITION),
                )

    def test_transit_return_and_replay_survive_reopened_connection(self):
        account = self.store.register("rii-floor-test", "test-password")["id"]
        character = self.store.create_character(account, "Rii Floor")
        generation = self.store.begin_session(account)
        character = self.store.select_character(account, generation, character["id"])
        source_position = dict(map_id=1388, instance_id=0, x=1, y=-19, z=3)
        # This targeted test covers positions and durable ownership. Health's
        # compiled equipment catalog is validated by its own integration tests.
        with patch(
            "wakfu_server.characters.dungeon_modulation_health.reconcile",
            return_value=(),
        ):
            source = self.store.transition_map(
                account, generation, character["id"], character, source_position
            )
            floor = arena.enter(
                self.store,
                account,
                generation,
                source,
                10608,
                available=lambda pos: True,
            )
            with self.reopen().connection() as db:
                saved = self.store.character(account, character["id"], db)
                receipt = db.execute(
                    "SELECT * FROM rii_training_transits WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
            self.assertEqual(
                tuple(saved[k] for k in arena.POSITION),
                tuple(arena.FLOOR[k] for k in arena.POSITION),
            )
            self.assertEqual(receipt["source_z"], 3)
            with self.assertRaisesRegex(ValueError, "already pending"):
                arena.enter(
                    self.store,
                    account,
                    generation,
                    floor,
                    10608,
                    available=lambda pos: True,
                )
            returned = arena.return_to_source(
                self.store, account, generation, floor, available=lambda pos: True
            )
        self.assertEqual(
            tuple(returned[k] for k in arena.POSITION),
            tuple(source_position[k] for k in arena.POSITION),
        )
        with self.reopen().connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM rii_training_transits WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
            )
