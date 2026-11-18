"""Actual SQL source operations wait, cancel safely, settle and replay once."""

from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
import struct
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import source_quest_encounters as source, storage


class SourceQuestOperationPostgresTests(PostgresCase):
    def test_native_delay_position_cancel_and_three_gathers_keep_once_only_rewards(
        self,
    ):
        account = self.store.register("source-cargos", "isolated-password")["id"]
        character = self.store.create_character(account, "Source Cargos")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        document = source.document()
        revision = document["native_metadata_revision"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture": "actual2145/2146 native source definitions"}),
                    b"actual-fields-subset",
                    len(document["definitions"]),
                ),
            )
            for definition in document["definitions"]:
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (revision, definition["d"], Jsonb(dict(native=definition))),
                )
            db.execute(
                "UPDATE characters SET level=20,map_id=527,instance_id=0,x=-52,y=109,z=0 WHERE id=%s",
                (character["id"],),
            )
            before = storage.load_locked(db, character["id"])
            before.update(
                running=[2146],
                active=[2143, 2144, 2146],
                active_periods={},
                active_unknown=[],
                completed=[2143, 2144],
                objectives=[4252, 4254, 4256],
                completion_dates={"2143": 1, "2144": 1},
                tracking=[2146],
            )
            storage.store(db, character["id"], before)
            source.publish(db, document, revision)
        groups = SimpleNamespace(lock=nullcontext())
        now = [self.store.clock()]
        self.store.clock = lambda: now[0]
        gather_rules = [
            row
            for row in document["bindings"]
            if row["mode"] == "gather" and row["quest_id"] == 2146
        ]
        for n, rule in enumerate(gather_rules):
            pose = rule["approaches"][0]
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                    (*pose, character["id"]),
                )
            current = self.store.character(account, character["id"])
            body = struct.pack(">qHH", rule["source"]["id"], 0, 0)
            begun = source.interact(
                self.store,
                groups,
                account,
                generation,
                current,
                body,
                loaded=True,
                blocked=False,
            )
            self.assertIn("ticket", begun)
            self.assertIsNone(begun["target"])
            with self.store.connection() as db:
                self.assertNotIn(
                    rule["objective_id"],
                    storage.load_locked(db, character["id"])["objectives"],
                )
            early = source.complete_operation(
                self.store,
                groups,
                account,
                generation,
                current,
                begun["ticket"],
                loaded=True,
                blocked=False,
            )
            self.assertIn("ticket", early)
            if n == 0:
                # These are isolated operation fixtures, not native gameplay.
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET x=x+1 WHERE id=%s", (character["id"],)
                    )
                now[0] += 3.1
                moved = self.store.character(account, character["id"])
                cancelled = source.complete_operation(
                    self.store,
                    groups,
                    account,
                    generation,
                    moved,
                    begun["ticket"],
                    loaded=True,
                    blocked=False,
                )
                self.assertNotIn("ticket", cancelled)
                with self.store.connection() as db:
                    self.assertNotIn(
                        rule["objective_id"],
                        storage.load_locked(db, character["id"])["objectives"],
                    )
                    db.execute(
                        "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                        (*pose, character["id"]),
                    )
                current = self.store.character(account, character["id"])
                begun = source.interact(
                    self.store,
                    groups,
                    account,
                    generation,
                    current,
                    body,
                    loaded=True,
                    blocked=False,
                )
            now[0] += 3.1
            completed = source.complete_operation(
                self.store,
                groups,
                account,
                generation,
                current,
                begun["ticket"],
                loaded=True,
                blocked=False,
            )
            self.assertIn(13832, [opcode for opcode, _ in completed["packets"]])
            replay = source.complete_operation(
                self.store,
                groups,
                account,
                generation,
                current,
                begun["ticket"],
                loaded=True,
                blocked=False,
            )
            self.assertEqual(replay["packets"], [])
        with self.store.connection() as db:
            after = storage.load_locked(db, character["id"])
            self.assertIn(2146, after["completed"])
            self.assertTrue(
                {4251, 4252, 4253, 4254, 4255, 4256} <= set(after["objectives"])
            )
            claims = db.execute(
                "SELECT reward_key FROM character_achievement_reward_outbox WHERE character_id=%s AND achievement_id=2146 ORDER BY reward_key",
                (character["id"],),
            ).fetchall()
            self.assertEqual(len(claims), 2)

    def test_four_native_source_groups_bind_only_their_real_admitted_fights(self):
        account = self.store.register("source-ambushes", "isolated-password")["id"]
        character = self.store.create_character(account, "Source Ambushes")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        document = source.document()
        revision = document["native_metadata_revision"]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture": "actual2145/2146 native source definitions"}),
                    b"actual-fields-subset",
                    len(document["definitions"]),
                ),
            )
            for definition in document["definitions"]:
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                    (revision, definition["d"], Jsonb(dict(native=definition))),
                )
            db.execute(
                "UPDATE characters SET level=20,map_id=527,instance_id=0,x=-52,y=109,z=0 WHERE id=%s",
                (character["id"],),
            )
            before = storage.load_locked(db, character["id"])
            before.update(
                running=[2145, 2146],
                active=[2143, 2144, 2145, 2146],
                active_periods={},
                active_unknown=[],
                completed=[2143, 2144],
                objectives=[],
                completion_dates={"2143": 1, "2144": 1},
                tracking=[2146],
            )
            storage.store(db, character["id"], before)
            source.publish(db, document, revision)
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server import fight_store
        from wakfu_server import monsters

        groups = PersistentGroups(self.store)
        now = [self.store.clock()]
        self.store.clock = lambda: now[0]
        for rule in [
            r
            for r in document["bindings"]
            if r["mode"] == "encounter" and r["quest_id"] in (2145, 2146)
        ]:
            pose = rule["approaches"][0]
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s",
                    (*pose, character["id"]),
                )
            current = self.store.character(account, character["id"])
            begun = source.interact(
                self.store,
                groups,
                account,
                generation,
                current,
                struct.pack(">qHH", rule["source"]["id"], 0, 0),
                loaded=True,
                blocked=False,
            )
            now[0] += 3.1
            result = source.complete_operation(
                self.store,
                groups,
                account,
                generation,
                current,
                begun["ticket"],
                loaded=True,
                blocked=False,
            )
            target = result["target"]
            self.assertIsNotNone(target)
            selected = next(
                g
                for g in groups.available(527, 0)
                if target["id"] in {m["id"] for m in g["members"]}
            )
            native = monsters.reference(rule["roster"][0]["reference"])
            self.assertEqual(target["ref"], native["ref"])
            self.assertEqual(target["level"], native["min_level"])
            with self.store.connection() as db:
                self.assertTrue(
                    source.admit(db, current, selected["members"], selected["key"])
                )
                with self.assertRaisesRegex(ValueError, "another character"):
                    source.admit(
                        db,
                        dict(current, id=current["id"] + 1),
                        selected["members"],
                        selected["key"],
                    )
                self.assertNotIn(
                    rule["objective_id"],
                    storage.load_locked(db, current["id"])["objectives"],
                )
            identity = fight_store.create(
                self.store,
                account,
                generation,
                current["id"],
                on_created=lambda db, identity: source.bind_fight(
                    db,
                    self.store,
                    current,
                    identity,
                    selected["members"],
                    selected["key"],
                ),
            )
            with self.store.connection() as db:
                receipt = db.execute(
                    "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (current["id"], f"quest-source-fight:{identity}"),
                ).fetchone()["payload"]
                self.assertEqual(receipt["members"], list(selected["members"]))
                self.assertEqual(receipt["binding"], rule["id"])
                # Abort the isolated constructor fixture; no victory is synthesized.
                fight_store.finish(
                    self.store, db, account, generation, current["id"], identity
                )
