"""PostgreSQL/Redis regressions for automatic dungeon position barriers."""
import os
import struct
import threading
import unittest
import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
import test_dungeon_instances
from wakfu_server.maps import dungeon_auto_transition
from wakfu_server import dungeon_transport, player_parties
import test_dungeon_instances
from wakfu_server.maps.dungeon_position_barrier import run_auto_transition
from wakfu_server.maps.dungeon_progression import (
    bind_encounter,
    initialize_run,
    settle_encounter,
)
from wakfu_server.position_buffer import Positions
from wakfu_server.position_redis import Journal, PositionJournalError, RedisPositions


class _PositionDB:
    def __init__(self, store):
        self.store = store
        self.last_query = None
        self.params = None

    def execute(self, query, params=()):
        self.last_query, self.params = query, params
        return self

    def fetchone(self):
        account, generation, now = self.params
        session = self.store.sessions.get((account, generation))
        if session is None or session["expires_at"] <= now:
            return None
        return {"character_id": session["character_id"]}

    def fetchall(self):
        if "FROM dungeon_instance_members" in self.last_query:
            return list(self.store.members)
        return []


class _PositionStore:
    def __init__(self):
        self.sessions = {}
        self.characters = {}
        self.members = []
        self.loaded = []

    def now(self):
        return 100

    @contextmanager
    def connection(self, **_kwargs):
        yield _PositionDB(self)

    def character(self, account, character_id, _db):
        self.loaded.append((account, character_id))
        return dict(self.characters[(account, character_id)])


class SelectedPositionRebindTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server.position_buffer import Positions

        self.store = _PositionStore()
        self.live_accounts = set()
        self.positions = Positions(
            self.store,
            # Match LIVE's account/generation ownership: character selection
            # changes under the same lease and cannot make the old entry stale.
            lease_active=lambda account, generation, _character: (account, generation)
            in self.live_accounts,
        )

    def character(self, account, character_id, x):
        value = {
            "id": character_id,
            "account_id": account,
            "map_id": 1,
            "instance_id": 0,
            "x": x,
            "y": 2,
            "z": 0,
            "direction": 3,
        }
        self.store.characters[(account, character_id)] = value
        return value

    def select(self, account, generation, character_id, *, expires_at=200):
        self.store.sessions[(account, generation)] = {
            "character_id": character_id,
            "expires_at": expires_at,
        }

    def test_changed_hydration_baseline_preserves_buffer_until_fresh_retry(self):
        from wakfu_server.position_buffer import PositionBaselineChanged

        character = self.character(1, 10, 1)
        self.select(1, 7, character["id"])
        self.live_accounts.add((1, 7))
        self.positions.attach(1, 7, character)
        prepared = dict(character)
        previous = self.positions.entries[(1, 7, character["id"])]
        # Another committed travel wins after hydration prepared its packets.
        character.update(map_id=1086, instance_id=90, x=7)
        with self.assertRaises(PositionBaselineChanged):
            self.positions.attach(1, 7, prepared)
        self.assertIs(self.positions.entries[(1, 7, character["id"])], previous)
        self.assertEqual(previous["current"]["map_id"], 1)
        fresh = dict(self.store.characters[(1, character["id"])])
        self.positions.attach(1, 7, fresh)
        self.assertEqual(
            self.positions.entries[(1, 7, character["id"])]["persisted"]["map_id"], 1086
        )

    def test_main_to_hero_switch_prunes_only_old_clean_entry_and_keeps_attach_strict(
        self,
    ):
        from wakfu_server import dungeon_position_barrier

        main, hero, foreign = (
            self.character(1, 10, 1),
            self.character(1, 11, 2),
            self.character(2, 20, 3),
        )
        self.select(1, 7, main["id"])
        self.select(2, 9, foreign["id"])
        self.live_accounts.update({(1, 7), (2, 9)})
        self.positions.attach(1, 7, main)
        self.positions.attach(2, 9, foreign)

        # Company selection changes under the same account generation. The
        # former main's clean entry is obsolete; the other account is untouched.
        result = dungeon_position_barrier.run_account_exit(
            self.store,
            self.positions,
            1,
            transition=lambda: (
                self.select(1, 7, hero["id"]),
                {"selected": hero["id"]},
            )[1],
        )
        self.assertEqual({"selected": hero["id"]}, result)
        self.assertNotIn((1, 7, main["id"]), self.positions.entries)
        self.assertIn((2, 9, foreign["id"]), self.positions.entries)
        with self.assertRaisesRegex(ValueError, "Invalid buffered position session"):
            self.positions.attach(1, 7, main)
        self.assertEqual(hero, self.positions.attach(1, 7, hero))

    def test_dirty_stale_entry_is_retained_and_release_cas_errors_are_not_masked(self):
        from wakfu_server import dungeon_position_barrier

        main = self.character(1, 10, 1)
        hero = self.character(1, 11, 2)
        self.select(1, 7, main["id"])
        self.live_accounts.add((1, 7))
        self.positions.attach(1, 7, main)
        self.positions.entries[(1, 7, main["id"])]["dirty"] = True
        self.select(1, 7, hero["id"])
        with self.assertRaisesRegex(ValueError, "requires a clean position baseline"):
            dungeon_position_barrier._rebind_clean(self.store, self.positions, (1,))
        self.assertIn((1, 7, main["id"]), self.positions.entries)
        self.assertTrue(self.positions.entries[(1, 7, main["id"])]["dirty"])

        class FailedCAS:
            def _entry_snapshot(self):
                return [((1, 7, 10), {"dirty": False})]

            def lease_active(self, *_key):
                return True

            def rebind_selected(self, *_args):
                return None

            def release(self, *_args, **kwargs):
                self.release_kwargs = kwargs
                raise PositionJournalError("Redis position revision conflict")

        failed = FailedCAS()
        with self.assertRaisesRegex(PositionJournalError, "revision conflict"):
            dungeon_position_barrier._rebind_clean(self.store, failed, (1,))
        self.assertEqual(failed.release_kwargs, {})

    def test_rebind_selected_rejects_wrong_character_expiry_and_missing_generation(
        self,
    ):
        main = self.character(1, 10, 1)
        hero = self.character(1, 11, 2)
        self.select(1, 7, hero["id"])
        self.assertIsNone(self.positions.rebind_selected(1, 7, main["id"]))
        with self.assertRaisesRegex(ValueError, "Invalid buffered position session"):
            self.positions.attach(1, 7, main)

        self.select(1, 7, main["id"], expires_at=100)
        self.assertIsNone(self.positions.rebind_selected(1, 7, main["id"]))
        with self.assertRaisesRegex(ValueError, "Invalid buffered position session"):
            self.positions.attach(1, 7, main)

        self.store.sessions.pop((1, 7))
        self.assertIsNone(self.positions.rebind_selected(1, 7, main["id"]))
        self.assertEqual([], self.store.loaded)

    def test_auto_transition_rebinds_selected_hero_and_other_account_after_commit(self):
        from wakfu_server import dungeon_position_barrier

        main, hero, foreign = (
            self.character(1, 10, 1),
            self.character(1, 11, 2),
            self.character(2, 20, 3),
        )
        self.select(1, 7, main["id"])
        self.select(2, 9, foreign["id"])
        self.live_accounts.update({(1, 7), (2, 9)})
        self.store.members = [
            {"id": main["id"], "account_id": 1},
            {"id": hero["id"], "account_id": 1},
            {"id": foreign["id"], "account_id": 2},
        ]
        self.positions.attach(1, 7, main)
        self.select(1, 7, hero["id"])
        self.positions.attach(1, 7, hero)
        self.positions.attach(2, 9, foreign)

        def committed_transition(_store, _instance, _fight, **_kwargs):
            for character in (hero, foreign):
                saved = self.store.characters[
                    (character["account_id"], character["id"])
                ]
                saved.update(map_id=1086, instance_id=0, x=152, y=-10, z=0)
            return {"moved": [hero["id"], foreign["id"]]}

        result = dungeon_position_barrier.run_auto_transition(
            self.store,
            self.positions,
            90,
            91,
            transition=committed_transition,
            topology={},
            in_fight=lambda _character_id: False,
        )
        self.assertEqual({"moved": [hero["id"], foreign["id"]]}, result)
        self.assertNotIn((1, 7, main["id"]), self.positions.entries)
        self.assertEqual(
            (1086, 0, 152, -10, 0),
            tuple(
                self.positions.entries[(1, 7, hero["id"])]["persisted"][key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            ),
        )
        self.assertEqual(
            (1086, 0, 152, -10, 0),
            tuple(
                self.positions.entries[(2, 9, foreign["id"])]["persisted"][key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            ),
        )


class DungeonPositionBarrierPostgresTests(PostgresCase):
    """Use real disposable SQL schemas and an isolated Redis key namespace."""

    install_context_policy = (
        test_dungeon_instances.DungeonInstanceTests.install_context_policy
    )
    player = test_dungeon_instances.DungeonInstanceTests.player
    party = test_dungeon_instances.DungeonInstanceTests.party
    enter = test_dungeon_instances.DungeonInstanceTests.enter

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)
        self.members, self.party_id = self.party(2)
        self.instance_id = self.enter(self.members[0])["instance_id"]
        monster = SimpleNamespace(
            ref_id=1, count=1, native_min_level=1, native_max_level=5, role="monster"
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="d" * 64,
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            ),
        )
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)
        self.fight_id = self._settle_victory()
        self.namespace = "wakfu:test:dungeon-position-barrier:" + uuid.uuid4().hex
        redis_url = os.environ.get("WAKFU_REDIS_TEST_URL") or os.environ.get(
            "WAKFU_REDIS_URL"
        )
        if not redis_url:
            self.skipTest("Local Redis URL required for position barrier regression")
        import redis

        self.redis = redis.Redis.from_url(
            redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        self.redis.ping()
        self.addCleanup(self.redis.delete, self.namespace)
        self.journal = Journal(self.redis, namespace=self.namespace)
        leases = {
            (member["account"], member["generation"], member["character"]["id"])
            for member in self.members
        }
        self.positions = RedisPositions(
            self.store, lease_active=lambda *key: key in leases, journal=self.journal
        )

    @property
    def topology(self):
        return {
            "asset_map_id": 1086,
            "rooms": [
                {"order": 1, "anchor": (4, -12, 0)},
                {"order": 2, "anchor": (152, -10, 0)},
            ],
            "doors": [
                {"source_room": 1, "destination_room": 2, "anchor": (152, -10, 0)}
            ],
        }

    def _settle_victory(self):
        member = self.members[0]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, member["character"]["id"], member["account"]),
            )
            bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                member["character"]["id"],
                fight_id,
                player_team=0,
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=0)
            )
        return fight_id

    def _attach_and_move(self, member, delta=1):
        character = self.store.character(member["account"], member["character"]["id"])
        self.positions.attach(member["account"], member["generation"], character)
        return self.positions.move(
            member["account"],
            member["generation"],
            character["id"],
            character,
            {
                "x": character["x"] + delta,
                "y": character["y"] + 2,
                "z": character["z"],
                "direction": 5,
            },
        )

    def _transition(self, **overrides):
        transition = overrides.pop("transition", dungeon_auto_transition.advance)
        return run_auto_transition(
            self.store,
            self.positions,
            self.instance_id,
            self.fight_id,
            transition=transition,
            topology=self.topology,
            in_fight=lambda _character_id: False,
            **overrides,
        )

    def test_dirty_redis_movement_is_committed_before_travel_and_rebind_allows_attach(
        self,
    ):
        member = self.members[0]
        moved = self._attach_and_move(member)
        self.assertEqual(1, len(list(self.journal.records())))
        result = self._transition()
        self.assertFalse(result.get("deferred"))
        row = self.store.character(member["account"], member["character"]["id"])
        self.assertEqual(
            (1086, self.instance_id, 152, -10, 0),
            tuple(row[k] for k in ("map_id", "instance_id", "x", "y", "z")),
        )
        event = next(
            e for e in self._outbox() if e["character_id"] == member["character"]["id"]
        )
        self.assertEqual(
            (moved["x"], moved["y"], moved["z"]),
            (event["source_x"], event["source_y"], event["source_z"]),
        )
        entry = self.positions.entries[
            (member["account"], member["generation"], member["character"]["id"])
        ]
        self.assertFalse(entry["dirty"])
        self.assertEqual(row["x"], entry["persisted"]["x"])
        # Bootstrap may attach the authoritative destination, then the next move
        # must flush against that new baseline rather than the old room.
        self.positions.attach(member["account"], member["generation"], row)
        fresh = self.positions.move(
            member["account"],
            member["generation"],
            row["id"],
            row,
            {"x": row["x"] + 1, "y": row["y"], "z": row["z"]},
        )
        self.positions.flush(account_id=member["account"])
        saved = self.store.character(member["account"], row["id"])
        self.assertEqual(fresh["x"], saved["x"])
        self.assertEqual([], list(self.journal.records()))

    def test_busy_account_defers_without_flushing_or_travel(self):
        member = self.members[0]
        moved = self._attach_and_move(member)
        acquired, release = threading.Event(), threading.Event()

        def hold_lock():
            with self.positions.account_barrier(member["account"]):
                acquired.set()
                release.wait(3)

        thread = threading.Thread(target=hold_lock)
        thread.start()
        self.assertTrue(acquired.wait(2))
        try:
            result = self._transition()
        finally:
            release.set()
            thread.join(3)
        self.assertTrue(result["deferred"])
        self.assertEqual("position_owner_busy", result["reason"])
        saved = self.store.character(member["account"], member["character"]["id"])
        self.assertNotEqual(moved["x"], saved["x"])
        self.assertTrue(self.positions.has_dirty(account_id=member["account"]))
        self.assertEqual([], self._outbox())

    def test_postgres_cas_conflict_preserves_dirty_journal_and_skips_transition(self):
        member = self.members[0]
        self._attach_and_move(member)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET x=x+7 WHERE id=%s", (member["character"]["id"],)
            )
        callback_called = []
        with self.assertRaisesRegex(ValueError, "storage CAS conflict"):
            self._transition(
                transition=lambda *args, **kwargs: callback_called.append(True)
            )
        self.assertEqual([], callback_called)
        self.assertTrue(self.positions.has_dirty(account_id=member["account"]))
        self.assertEqual(1, len(list(self.journal.records())))
        self.assertEqual([], self._outbox())

    def test_revoked_selected_lease_preserves_journal_and_skips_transition(self):
        member = self.members[0]
        self._attach_and_move(member)
        self.positions.lease_active = lambda *_key: False
        called = []
        with self.assertRaisesRegex(ValueError, "Live lease unavailable"):
            self._transition(transition=lambda *args, **kwargs: called.append(True))
        self.assertEqual([], called)
        self.assertTrue(self.positions.has_dirty(account_id=member["account"]))
        self.assertEqual(1, len(list(self.journal.records())))
        self.assertEqual([], self._outbox())

    def test_redis_ack_failure_keeps_transition_from_traveling(self):
        member = self.members[0]
        self._attach_and_move(member)
        original_ack = self.journal.ack
        self.journal.ack = lambda *_args: False
        called = []
        try:
            with self.assertRaisesRegex(
                PositionJournalError, "changed after committed flush"
            ):
                self._transition(transition=lambda *args, **kwargs: called.append(True))
        finally:
            self.journal.ack = original_ack
        self.assertEqual([], called)
        self.assertTrue(self.positions.has_dirty(account_id=member["account"]) is False)
        self.assertEqual(1, len(list(self.journal.records())))
        self.assertEqual([], self._outbox())

    def _outbox(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT character_id,source_x,source_y,source_z FROM dungeon_transition_outbox WHERE instance_id=%s AND transition_kind='door' ORDER BY character_id",
                (self.instance_id,),
            ).fetchall()


class DungeonEntryPositionBarrierPostgresTests(PostgresCase):
    install_context_policy = (
        test_dungeon_instances.DungeonInstanceTests.install_context_policy
    )
    player = test_dungeon_instances.DungeonInstanceTests.player
    party = test_dungeon_instances.DungeonInstanceTests.party

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)
        self.members, self.party_id = self.party(2)
        self.leader, self.companion = self.members
        self.body = struct.pack(">qiBi", 26842, 2504, 0, 2)
        self.namespace = "wakfu:test:dungeon-entry-position-barrier:" + uuid.uuid4().hex
        redis_url = os.environ.get("WAKFU_REDIS_TEST_URL") or os.environ.get(
            "WAKFU_REDIS_URL"
        )
        if not redis_url:
            self.skipTest("Local Redis URL required for position barrier regression")
        import redis

        self.redis = redis.Redis.from_url(
            redis_url, socket_connect_timeout=2, socket_timeout=2
        )
        self.redis.ping()
        self.addCleanup(self.redis.delete, self.namespace)
        self.journal = Journal(self.redis, namespace=self.namespace)
        leases = {
            (member["account"], member["generation"], member["character"]["id"])
            for member in self.members
        }
        self.positions = RedisPositions(
            self.store, lease_active=lambda *key: key in leases, journal=self.journal
        )

    def _enter(self, *, initialize_instance=None):
        return dungeon_transport.enter(
            self.store,
            self.leader["account"],
            self.leader["generation"],
            self.leader["character"]["id"],
            527,
            self.body,
            source_allowed=lambda *_: True,
            criterion_allowed=lambda *_: True,
            initialize_instance=initialize_instance,
            positions=self.positions,
        )

    def _outbox(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT character_id,source_map_id,source_instance_id,source_x,source_y,source_z,"
                "destination_map_id,destination_instance_id,destination_x,destination_y,destination_z "
                "FROM dungeon_transition_outbox ORDER BY character_id"
            ).fetchall()

    def _grant_entry_item(self, character_id):
        with self.store.connection() as db:
            bag = db.execute(
                "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) "
                "VALUES(%s,1,0,30,0) ON CONFLICT(character_id,kind) "
                "DO UPDATE SET capacity=excluded.capacity RETURNING uid",
                (character_id,),
            ).fetchone()["uid"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,15133,1,%s,0) RETURNING uid",
                (character_id, bag),
            ).fetchone()["uid"]

    def test_entry_flushes_dirty_companion_before_atomic_party_travel_and_rebinds(self):
        member = self.companion
        character = self.store.character(member["account"], member["character"]["id"])
        self.positions.attach(member["account"], member["generation"], character)
        moved = self.positions.move(
            member["account"],
            member["generation"],
            character["id"],
            character,
            {
                "x": character["x"] + 3,
                "y": character["y"] + 2,
                "z": character["z"],
                "direction": 6,
            },
        )

        entered = self._enter()
        rows = {row["character_id"]: row for row in self._outbox()}
        self.assertEqual({m["character"]["id"] for m in self.members}, set(rows))
        event = rows[member["character"]["id"]]
        self.assertEqual(
            (moved["x"], moved["y"], moved["z"]),
            (event["source_x"], event["source_y"], event["source_z"]),
        )
        self.assertEqual(
            (1086, entered["instance_id"], 4, -12, 0),
            tuple(
                event[k]
                for k in (
                    "destination_map_id",
                    "destination_instance_id",
                    "destination_x",
                    "destination_y",
                    "destination_z",
                )
            ),
        )
        saved = self.store.character(member["account"], member["character"]["id"])
        key = (member["account"], member["generation"], member["character"]["id"])
        self.assertFalse(self.positions.entries[key]["dirty"])
        self.positions.attach(member["account"], member["generation"], saved)
        next_move = self.positions.move(
            member["account"],
            member["generation"],
            saved["id"],
            saved,
            {"x": saved["x"] + 1, "y": saved["y"], "z": saved["z"]},
        )
        self.positions.flush(account_id=member["account"])
        self.assertEqual(
            next_move["x"], self.store.character(member["account"], saved["id"])["x"]
        )
        self.assertEqual([], list(self.journal.records()))

    def test_paid_entry_commits_once_and_retries_delivery_after_session_lock(self):
        from wakfu_server import dungeon_instances, dungeon_hydration
        from wakfu_server.dungeon_transition_delivery import deliver_pending_transitions

        leader = self.leader
        for member in self.members:
            self._grant_entry_item(member["character"]["id"])
            self.positions.attach(
                member["account"], member["generation"], member["character"]
            )
        native = dungeon_transport.resolve_request(527, self.body)
        native["native_destination"] = dict(
            native["native_destination"], item_reference=15133, cyW=1
        )
        original_enter = dungeon_transport._enter
        lock_context = None
        producer_calls = []

        def enter_then_hold_session(*args, **kwargs):
            nonlocal lock_context
            result = original_enter(*args, **kwargs)
            producer_calls.append(result["instance_id"])
            # A separate real transaction wins the session row only AFTER
            # durable paid entry returns. Its timeout must not replay payment.
            lock_context = self.store.connection()
            locked = lock_context.__enter__()
            locked.execute(
                "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE",
                (leader["account"],),
            ).fetchone()
            return result

        location = {
            m["character"]["id"]: {
                k: m["character"][k] for k in ("map_id", "instance_id", "x", "y", "z")
            }
            for m in self.members
        }

        def deliver(member):
            def bootstrap(event):
                plan = dungeon_hydration.prepare_transition(
                    self.store,
                    member["account"],
                    member["generation"],
                    member["character"]["id"],
                    event,
                )
                self.positions.attach(
                    member["account"], member["generation"], plan.character
                )
                location[plan.character["id"]] = {
                    k: plan.character[k]
                    for k in ("map_id", "instance_id", "x", "y", "z")
                }
                return True

            return deliver_pending_transitions(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                worker_generation=member["generation"],
                current_location=lambda: location[member["character"]["id"]],
                in_fight=lambda: False,
                bootstrap=bootstrap,
            )

        try:
            with patch.object(
                dungeon_transport, "resolve_request", return_value=native
            ), patch.object(
                dungeon_transport, "_enter", side_effect=enter_then_hold_session
            ):
                result = self._enter()
            self.assertEqual([result["instance_id"]], producer_calls)
            key = (leader["account"], leader["generation"], leader["character"]["id"])
            self.assertEqual(527, self.positions.entries[key]["current"]["map_id"])
            self.assertFalse(self.positions.entries[key]["dirty"])
            deferred = deliver(leader)
            self.assertEqual("transition_owner_busy", deferred["state"])
            with self.store.connection() as db:
                self.assertEqual(
                    2,
                    db.execute(
                        "SELECT count(*) AS n FROM dungeon_transition_outbox WHERE status='pending'"
                    ).fetchone()["n"],
                )
                self.assertEqual(
                    0,
                    db.execute(
                        "SELECT count(*) AS n FROM inventory_items WHERE reference=15133"
                    ).fetchone()["n"],
                )
                self.assertEqual(
                    2,
                    db.execute(
                        "SELECT count(*) AS n FROM dungeon_instance_members WHERE status='active'"
                    ).fetchone()["n"],
                )
        finally:
            if lock_context is not None:
                lock_context.__exit__(None, None, None)
        for member in self.members:
            self.assertEqual("delivered", deliver(member)["state"])
            self.assertTrue(
                self.store.current_character_session(
                    member["account"], member["generation"], member["character"]["id"]
                )
            )
        self.assertEqual(1, len(producer_calls))
        saved = self.store.character(leader["account"], leader["character"]["id"])
        moved = self.positions.move(
            leader["account"],
            leader["generation"],
            saved["id"],
            saved,
            dict(x=saved["x"] + 1, y=saved["y"], z=saved["z"]),
        )
        self.positions.flush(account_id=leader["account"])
        self.assertEqual(
            moved["x"], self.store.character(leader["account"], saved["id"])["x"]
        )
        with self.store.connection() as db:
            self.assertEqual(
                2,
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox WHERE status='acknowledged'"
                ).fetchone()["n"],
            )
            self.assertEqual(
                2,
                db.execute(
                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                    (self.party_id,),
                ).fetchone()["n"],
            )
        self.assertEqual([], list(self.journal.records()))

    def test_raced_party_account_is_rejected_before_fee_or_travel(self):
        third = self.player("raced")
        invitation = player_parties.invite(
            self.store,
            self.leader["account"],
            self.leader["generation"],
            self.leader["character"]["id"],
            third["character"]["id"],
        )
        uid = self._grant_entry_item(self.leader["character"]["id"])
        native = dungeon_transport.resolve_request(527, self.body)
        native["native_destination"] = dict(
            native["native_destination"], item_reference=15133, cyW=1
        )
        original_flush = self.positions.flush
        raced = []

        def add_party_member_then_flush(**scope):
            if not raced:
                player_parties.answer(
                    self.store,
                    third["account"],
                    third["generation"],
                    third["character"]["id"],
                    invitation,
                    True,
                )
                raced.append(True)
            return original_flush(**scope)

        self.positions.flush = add_party_member_then_flush
        initializer_calls = []
        with patch.object(dungeon_transport, "resolve_request", return_value=native):
            with self.assertRaisesRegex(ValueError, "outside position barrier"):
                self._enter(
                    initialize_instance=lambda *_: initializer_calls.append(True)
                )
        self.assertEqual([True], raced)
        self.assertEqual([], initializer_calls)
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox"
                ).fetchone()["n"],
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
                ).fetchone()["quantity"],
            )
            positions = list(
                db.execute("SELECT map_id,instance_id FROM characters ORDER BY id")
            )
        self.assertTrue(
            all((row["map_id"], row["instance_id"]) == (527, 0) for row in positions)
        )
