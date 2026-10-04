import os
import tempfile
import unittest
import uuid
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.build_journal import BuildJournal
from wakfu_server.state_journal import StateJournalError
from wakfu_server.wire import proto_field
from test_combat_group_redis import MemoryRedis


class BuildJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "world.db"
        self.now = [100.0]
        self.store = Store(self.path, clock=lambda: self.now[0])
        self.account = self.store.register("builder", "local-builder-password")["id"]
        self.char = self.store.create_character(self.account, "Builder", breed=8)
        self.generation = self.store.begin_session(self.account, ttl=10000)
        self.store.select_character(self.account, self.generation, self.char["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=6,hp=110,max_hp=110 WHERE id=?",
                (self.char["id"],),
            )
        self.char = self.store.character(self.account, self.char["id"])
        from wakfu_server.inventory_items import grant

        self.item = grant(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            reference=2021,
            quantity=1,
            container=self.char["inventory_containers"][0]["uid"],
            slot=0,
            allowed_references={2021},
        )
        self.client = self.make_client()
        self.namespace = "wakfu:test:builds:" + uuid.uuid4().hex
        self.addCleanup(self.client.delete, self.namespace)
        self.journal = self.attach(self.store)
        self.blobs = dict(
            sheet=b"".join(
                proto_field(t, v)
                for t, v in [(8, 0), (18, b"Owned"), (24, (1 << 64) - 1), (56, 1)]
            ),
            equipment=proto_field(
                10, proto_field(8, self.item["uid"]) + proto_field(16, 4)
            ),
            deck=b"",
            aptitudes=b"",
        )

    def make_client(self):
        return MemoryRedis()

    def attach(self, store):
        journal = BuildJournal(
            store, self.client, namespace=self.namespace, clock=lambda: self.now[0]
        )
        store.build_journal = journal
        return journal

    def save(self, **changes):
        return self.store.save_build(
            self.account,
            self.generation,
            self.char["id"],
            0,
            dict(self.blobs, **changes),
        )

    def sql_builds(self):
        with self.store.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM character_builds")]

    def test_durable_before_ack_reconnect_and_twenty_minute_batch(self):
        saved = self.save()
        self.assertEqual(self.sql_builds(), [])
        self.assertEqual((saved["hp"], saved["max_hp"]), (116, 116))
        reopened = Store(self.path, clock=lambda: self.now[0])
        self.attach(reopened)
        self.assertEqual(
            reopened.character(self.account, self.char["id"])["builds"], saved["builds"]
        )
        self.now[0] += 1199
        self.assertEqual(self.journal.flush_due(), 0)
        self.assertEqual(self.sql_builds(), [])
        self.now[0] += 1
        self.assertEqual(self.journal.flush_due(), 1)
        self.assertEqual(self.sql_builds()[0]["equipment"], self.blobs["equipment"])
        self.assertEqual(self.journal.flush(), 0)

    def test_session_replacement_and_foreign_unit_cannot_ack(self):
        invalid = proto_field(
            10, proto_field(8, self.item["uid"] + 99) + proto_field(16, 4)
        )
        with self.assertRaises(ValueError):
            self.save(equipment=invalid)
        self.assertEqual(list(self.journal.journal.records()), [])
        self.store.begin_session(self.account)
        with self.assertRaises(ValueError):
            self.save()
        self.assertEqual(self.sql_builds(), [])

    def test_redis_outage_never_falls_back_to_sql_or_changes_hp(self):
        if not isinstance(self.client, MemoryRedis):
            self.skipTest("Failure injection only")
        self.client.fail = True
        with self.assertRaises(StateJournalError):
            self.save()
        self.client.fail = False
        self.assertEqual(self.sql_builds(), [])
        self.assertEqual(self.store.character(self.account, self.char["id"])["hp"], 110)

    def test_pending_gear_prevents_destroy_or_direct_remove(self):
        self.save()
        from wakfu_server.inventory_items import remove

        with self.assertRaises(ValueError):
            remove(
                self.store,
                self.account,
                self.generation,
                self.char["id"],
                self.item["uid"],
                1,
            )
        self.assertEqual(
            len(self.store.character(self.account, self.char["id"])["inventory_items"]),
            1,
        )
        self.assertEqual(self.sql_builds(), [])

    def test_health_damage_and_death_survive_overlay_and_flush(self):
        self.save()
        with self.store.connection() as db:
            db.execute("UPDATE characters SET hp=0 WHERE id=?", (self.char["id"],))
        self.assertEqual(self.store.character(self.account, self.char["id"])["hp"], 0)
        self.journal.close()
        self.assertEqual(self.store.character(self.account, self.char["id"])["hp"], 0)
        with self.store.connection() as db:
            db.execute("UPDATE characters SET hp=41 WHERE id=?", (self.char["id"],))
        self.save(equipment=bytes.fromhex("a803ffffffffffffffffff01"))
        self.assertEqual(self.store.character(self.account, self.char["id"])["hp"], 41)
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["max_hp"], 110
        )

    def test_checkpoint_outage_is_retryable_and_keeps_newer_revision(self):
        self.save()
        checkpoint = self.journal.journal.checkpoint
        self.journal.journal.checkpoint = lambda *args: (_ for _ in ()).throw(
            StateJournalError("outage")
        )
        with self.assertRaises(StateJournalError):
            self.journal.flush()
        self.assertEqual(len(self.sql_builds()), 1)
        self.journal.journal.checkpoint = checkpoint
        # Recovery recognizes the committed revision without losing Redis state.
        recovered = self.attach(Store(self.path, clock=lambda: self.now[0]))
        self.assertEqual(recovered.flush(), 0)
        self.save(equipment=bytes.fromhex("a803ffffffffffffffffff01"))
        self.assertEqual(self.journal.close(), 1)
        self.assertEqual(
            self.sql_builds()[0]["equipment"], bytes.fromhex("a803ffffffffffffffffff01")
        )

    def test_sql_conflict_does_not_overwrite_builds(self):
        self.save()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO character_builds VALUES(?,?,?,?,?,?)",
                (self.char["id"], 1, b"foreign", b"", b"", b""),
            )
        with self.assertRaises(StateJournalError):
            self.journal.flush()
        self.assertEqual(self.sql_builds()[0]["build_index"], 1)

    def test_checkpoint_preserves_mutation_after_sql_commit(self):
        self.save()
        checkpoint = self.journal.journal.checkpoint

        def mutate_then_checkpoint(key, encoded):
            self.save(equipment=bytes.fromhex("a803ffffffffffffffffff01"))
            return checkpoint(key, encoded)

        self.journal.journal.checkpoint = mutate_then_checkpoint
        self.assertEqual(self.journal.flush(), 1)
        self.journal.journal.checkpoint = checkpoint
        self.assertEqual(self.sql_builds()[0]["equipment"], self.blobs["equipment"])
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["builds"][0][
                "equipment"
            ],
            "a803ffffffffffffffffff01",
        )
        self.assertEqual(self.journal.flush(), 1)

    def test_two_workers_and_replaced_generation_read_latest_overlay(self):
        self.save()
        worker = Store(self.path, clock=lambda: self.now[0])
        self.attach(worker)
        newer = worker.begin_session(self.account, ttl=10000)
        worker.select_character(self.account, newer, self.char["id"])
        with self.assertRaises(ValueError):
            self.save()
        worker.save_build(
            self.account,
            newer,
            self.char["id"],
            0,
            dict(self.blobs, equipment=bytes.fromhex("a803ffffffffffffffffff01")),
        )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["max_hp"], 110
        )
        self.assertEqual(self.sql_builds(), [])
        self.assertEqual(self.journal.close(), 1)

    def test_health_regeneration_uses_overlay_maximum_without_revival(self):
        from wakfu_server import health_store

        health_store.initialize(
            self.store, self.account, self.generation, self.char["id"]
        )
        self.save()
        result = health_store.sync(
            self.store, self.account, self.generation, self.char["id"], 116, 40
        )
        self.assertEqual((result["hp"], result["max_hp"]), (40, 116))
        self.journal.flush()
        self.assertEqual(self.store.character(self.account, self.char["id"])["hp"], 40)


@unittest.skipUnless(
    os.environ.get("WAKFU_REDIS_TEST_URL"), "Isolated Redis URL required"
)
class RealRedisBuildJournalTests(BuildJournalTests):
    def make_client(self):
        import redis

        return redis.Redis.from_url(
            os.environ["WAKFU_REDIS_TEST_URL"], decode_responses=True
        )
