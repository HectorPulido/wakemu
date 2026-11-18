"""Owned deterministic ground loot, journal publication and atomic retries."""

from copy import deepcopy
from unittest.mock import patch
import struct
import unittest

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import ground_quest_pickups as pickups, storage


class GroundPickupProfileTests(unittest.TestCase):
    def test_exact_descriptor_loot_binding_and_malformed_profiles(self):
        source = pickups.profile()
        row = source["bindings"][0]
        self.assertEqual(
            (
                row["descriptor_id"],
                row["native_action_id"],
                row["loot_list_id"],
                row["item_reference"],
            ),
            (447, 497, 2435, 18689),
        )
        self.assertTrue(pickups.recognizes(527, struct.pack(">qHH", 23033, 0, 0)))
        for body in (b"", b"x" * 11, struct.pack(">qHH", 23034, 0, 0)):
            self.assertFalse(pickups.recognizes(527, body))
        self.assertFalse(pickups.recognizes(528, struct.pack(">qHH", 23033, 0, 0)))
        for key, value in (
            ("max_distance", 50),
            ("item_reference", True),
            ("quantity", 0),
            ("native_payload_hex", "xxx"),
        ):
            bad = deepcopy(source)
            bad["bindings"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                pickups.validate(bad)
        original = dict(
            map_id=row["map_id"],
            type=row["object_type"],
            x=-121,
            y=64,
            z=0,
            payload_hex=row["native_payload_hex"],
        )
        with patch("wakfu_server.native_catalog.record", return_value=original):
            pickups._source(row)
        for key in ("map_id", "type", "payload_hex", "z"):
            bad = dict(original, **{key: None})
            with patch(
                "wakfu_server.native_catalog.record", return_value=bad
            ), self.assertRaises(ValueError):
                pickups._source(row)


class GroundPickupPostgresTests(PostgresCase):
    def test_session_range_active_quest_personal_item_receipt_wire_and_rollback(self):
        account = self.store.register("ground-books", "local-password")["id"]
        character = self.store.create_character(account, "Ground Books")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        rule = pickups.profile()["bindings"][0]
        definition = dict(
            d=2048,
            native_class="aJM",
            aqb=False,
            cjI="",
            cjJ=[
                dict(d=4135, ckc="", cke="", ckf=[]),
                dict(d=4136, ckc="", cke="", ckf=[]),
            ],
            cjK=[],
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-120,y=64,z=0 WHERE id=%s",
                (character["id"],),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,1)",
                (
                    pickups.profile()["native_revision"],
                    Jsonb({"fixture": "ground quest subset"}),
                    b"ground quest fixture",
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,2048,%s)",
                (pickups.profile()["native_revision"], Jsonb({"native": definition})),
            )
        current = self.store.character(account, character["id"])
        body = struct.pack(">qHH", 23033, 0, 0)
        interaction = dict(type=rule["object_type"], x=-121, y=64, z=0)
        # Static catalog and cpF classification are external native fixtures;
        # authentication, source validation, inventory, journal and SQL stay real.
        original = dict(
            map_id=527,
            type=rule["object_type"],
            x=-121,
            y=64,
            z=0,
            payload_hex=rule["native_payload_hex"],
        )
        with patch("wakfu_server.native_catalog.record", return_value=original), patch(
            "wakfu_server.world_static.interaction", return_value=interaction
        ):

            def invoke(**kwargs):
                return pickups.interact(
                    self.store,
                    account,
                    generation,
                    current,
                    body,
                    loaded=True,
                    blocked=False,
                    **kwargs
                )

            absent = invoke()
            self.assertFalse(absent["applied"])
            with self.store.connection() as db:
                state = storage.load_locked(db, current["id"])
                state["running"] = [2048]
                storage.store(db, current["id"], state)
            for override in (dict(loaded=False), dict(blocked=True)):
                with self.subTest(override=override), self.assertRaises(ValueError):
                    pickups.interact(
                        self.store,
                        account,
                        generation,
                        current,
                        body,
                        **dict(dict(loaded=True, blocked=False), **override)
                    )
            with self.assertRaises(ValueError):
                pickups.interact(
                    self.store,
                    account,
                    "expired",
                    current,
                    body,
                    loaded=True,
                    blocked=False,
                )
            with self.assertRaises(ValueError):
                pickups.interact(
                    self.store,
                    account + 1,
                    generation,
                    current,
                    body,
                    loaded=True,
                    blocked=False,
                )
            for wrong in (
                struct.pack(">qHH", 23033, 1, 0),
                struct.pack(">qHH", 23033, 0, 1),
            ):
                with self.assertRaises(ValueError):
                    pickups.interact(
                        self.store,
                        account,
                        generation,
                        current,
                        wrong,
                        loaded=True,
                        blocked=False,
                    )
            with self.store.connection() as db:
                db.execute("UPDATE characters SET x=-115 WHERE id=%s", (current["id"],))
            with self.assertRaises(ValueError):
                invoke()
            with self.store.connection() as db:
                db.execute("UPDATE characters SET x=-120 WHERE id=%s", (current["id"],))
            with patch.object(
                pickups.mission_dependencies,
                "settle",
                side_effect=RuntimeError("abort after inventory grant"),
            ), self.assertRaisesRegex(RuntimeError, "abort"):
                invoke()
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) n FROM character_quest_items WHERE character_id=%s AND reference=18689",
                        (current["id"],),
                    ).fetchone()["n"],
                    0,
                )
                self.assertNotIn(
                    4135, storage.load_locked(db, current["id"])["objectives"]
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) n FROM character_achievement_events WHERE character_id=%s AND event_key LIKE 'quest-ground-pickup:%%'",
                        (current["id"],),
                    ).fetchone()["n"],
                    0,
                )
            result = invoke()
            self.assertTrue(result["applied"])
            self.assertEqual(
                [
                    row
                    for row in result["character"]["quest_items"]
                    if row["reference"] == 18689
                ][0]["quantity"],
                1,
            )
            self.assertIn(13879, [opcode for opcode, _ in result["packets"]])
            self.assertIn(13832, [opcode for opcode, _ in result["packets"]])
            self.assertEqual(result["completed"], [])
            self.assertFalse(invoke()["applied"])
            # Even after consumption, reconnect/replay cannot manufacture bags.
            with self.store.connection() as db:
                db.execute(
                    "DELETE FROM character_quest_items WHERE character_id=%s AND reference=18689",
                    (current["id"],),
                )
                state = storage.load_locked(db, current["id"])
                state["objectives"] = []
                storage.store(db, current["id"], state)
            self.assertFalse(invoke()["applied"])
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) n FROM character_quest_items WHERE character_id=%s AND reference=18689",
                        (current["id"],),
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) n FROM character_achievement_events WHERE character_id=%s AND event_key LIKE 'quest-ground-pickup:%%'",
                        (current["id"],),
                    ).fetchone()["n"],
                    1,
                )
