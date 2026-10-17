"""Owned journal projection and native tracking use durable session authority."""
import struct
from postgres_case import PostgresCase
from wakfu_server.achievements import catalog, service, storage, wire


class AchievementProjectionPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("projection-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Projection Owner")

    def test_projection_reconnect_preserves_progress_without_writing_authority(self):
        identity = self.character["id"]
        with self.store.connection() as db:
            state = storage.load_locked(db, identity)
            state.update(
                variables={"51": 3, "52": 2},
                objectives=[617, 618, 619],
                completed=[238],
                running=[239],
                tracking=[239],
                recent=[{"id": 238, "date_ms": 1700000000000}],
                completion_dates={"238": 1700000000000},
            )
            storage.store(db, identity, state)
            authority = dict(
                db.execute(
                    "SELECT * FROM character_achievement_authority WHERE character_id=%s",
                    (identity,),
                ).fetchone()
            )
        expected = wire.section(
            dict(state, running=sorted(set(catalog.load()["definitions"]) - {238}))
        )
        reopened = self.reopen()
        with reopened.connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            actual = reopened.character(self.account, identity, db)
            self.assertEqual(actual["achievement_section"], expected)
            self._assert_actual_initial_bootstrap(actual, expected)
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM character_achievement_authority WHERE character_id=%s",
                        (identity,),
                    ).fetchone()
                ),
                authority,
            )
            self.assertEqual(
                db.execute(
                    "SELECT state FROM character_achievement_progress WHERE character_id=%s",
                    (identity,),
                ).fetchone()["state"],
                state,
            )
            with self.assertRaises(ValueError):
                reopened.character(self.account + 9999, identity, db)

    def test_tracking_native_packets_persist_and_stale_foreign_completed_reject(self):
        identity = self.character["id"]
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, identity)
        body = struct.pack(">iB", 239, 1)
        self.assertEqual(
            service.tracking_request(
                self.store, self.account, generation, identity, body
            ),
            [(13371, struct.pack(">qiB", identity, 239, 1))],
        )
        for malformed in (b"", body + b"\0", struct.pack(">iB", 239, 2)):
            with self.assertRaises(ValueError):
                service.tracking_request(
                    self.store, self.account, generation, identity, malformed
                )
        foreign = self.store.register("projection-foreign", "local-password")["id"]
        with self.assertRaises(ValueError):
            service.tracking_request(self.store, foreign, generation, identity, body)
        newer = self.store.begin_session(self.account)
        self.store.select_character(self.account, newer, identity)
        with self.assertRaises(ValueError):
            service.tracking_request(
                self.store, self.account, generation, identity, body
            )
        with self.store.connection() as db:
            state = storage.load_locked(db, identity)
            self.assertEqual(state["tracking"], [239])
            state["completed"] = [238]
            storage.store(db, identity, state)
        with self.assertRaises(ValueError):
            service.tracking_request(
                self.store, self.account, newer, identity, struct.pack(">iB", 238, 1)
            )
        with self.reopen().connection() as db:
            self.assertEqual(storage.load_locked(db, identity)["tracking"], [239])

    def _assert_actual_initial_bootstrap(self, character, expected):
        import base64
        import hashlib
        import os
        from pathlib import Path
        from protocol_codec import Reader
        from wakfu_server import wire as entity_wire
        from wakfu_server.postgres import Database
        from wakfu_server.storage.bootstrap_capture import load

        # The original carrier is imported runtime authority, not a copied
        # private capture. Its manifest and every ordered frame are verified.
        runtime_url = os.environ.get("WAKFU_DATABASE_URL")
        self.assertTrue(runtime_url, "Original bootstrap runtime database is required")
        runtime = Database(
            runtime_url, password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        )
        try:
            with runtime.connection() as db:
                self.assertEqual(
                    db.execute("SHOW transaction_read_only").fetchone()[
                        "transaction_read_only"
                    ],
                    "on",
                    "Bootstrap reference acquisition requires a read-only runtime connection",
                )
                frames = load(
                    db,
                    "native-bootstrap-v1",
                    expected_source_sha256="061e3c7c2c4dca1d63e1986910b79467a26f0aa52eb86e43d3e1abb8ad8619ba",
                )
        finally:
            runtime.close()
        originals = [
            base64.b64decode(frame["body_base64"], validate=True)
            for frame in frames
            if frame.get("direction") == "in" and frame.get("opcode") == 12666
        ]
        self.assertEqual(
            len(originals), 1, "Expected one original owned bootstrap carrier"
        )
        original = originals[0]
        self.assertEqual(
            hashlib.sha256(original).hexdigest(),
            "a8ba7c9bbe6e1073473d0b9eea4d117ffd5aebb7854fd65e21ae03d45cb7c2b4",
        )
        published = entity_wire.adapt(12666, original, self.account, character)
        marker = b"private-achievement-boundary-marker"
        control = entity_wire.adapt(
            12666, original, self.account, dict(character, achievement_section=marker)
        )

        def first_entity(body):
            reader = Reader(body)
            reader.take(reader.number("H") * 8)
            return reader.take(reader.number("I"))

        entity = first_entity(published)
        boundary = first_entity(control)
        self.assertEqual(entity[0], 10)
        offset = boundary.index(marker)
        self.assertEqual(entity[:offset], boundary[:offset])
        self.assertEqual(entity[offset : offset + len(expected)], expected)
        self.assertEqual(
            entity[offset + len(expected) :], boundary[offset + len(marker) :]
        )
        output = Path(".runtime/local/verification-achievement-projection-20261011")
        output.mkdir(parents=True, exist_ok=True)
        (output / "initial12666-achievement-section.bin").write_bytes(
            entity[offset : offset + len(expected)]
        )
