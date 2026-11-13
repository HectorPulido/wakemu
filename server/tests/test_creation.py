import struct
import unittest
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.creation import create, select_created
from wakfu_server.characters import heroes
from wakfu_server.wire import appearance_section


class CreationTests(PostgresCase):
    def test_intro_choice_only_affects_new_characters(self):
        from wakfu_server.intro_cinematic import private_instance_id

        account = self.store.register("intro-creator", "creation-password")["id"]
        revision = "f" * 64
        definitions = {
            5160: {
                "d": 5160,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjK": [],
                "cjJ": [{"d": 10612, "ckc": "", "cke": ""}],
            },
            5146: {
                "d": 5146,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjK": [],
                "cjJ": [{"d": 10582, "ckc": "", "cke": ""}],
            },
            5144: {
                "d": 5144,
                "native_class": "aJM",
                "aqb": True,
                "isVisible": True,
                "aHe": "GetRealLevel() < 30",
                "bwX": 5160,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjK": [],
                "cjJ": [{"d": 10577, "ckc": "", "cke": "", "ckf": []}],
            },
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) "
                "VALUES (%s,%s,%s,%s)",
                (revision, Jsonb({}), b"creation-intro-fixture", len(definitions)),
            )
            for identity, native in definitions.items():
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES (%s,%s,%s)",
                    (revision, identity, Jsonb({"native": native})),
                )
        previous = self.store.create_character(account, "Before Intro")
        created = self.store.create_character(account, "New Intro", tutorial=True)
        another = self.store.create_character(account, "Other Intro", tutorial=True)
        skipped = self.store.create_character(account, "Skip Intro", tutorial=False)
        keys = ("map_id", "instance_id", "x", "y", "z")
        self.assertEqual(
            tuple(created[key] for key in keys),
            (1465, private_instance_id(created["id"]), 0, 0, 40),
        )
        self.assertNotEqual(created["instance_id"], another["instance_id"])
        self.assertEqual(tuple(skipped[key] for key in keys), (1385, 0, 27, 1, 1))
        current = self.store.character(account, previous["id"])
        self.assertEqual(
            tuple(previous[key] for key in keys), tuple(current[key] for key in keys)
        )

    def test_creation_auto_selection_rebinds_existing_company_before_world_join(self):
        store = self.store
        account = store.register("creator-company", "creation-password")["id"]
        previous = store.create_character(account, "Previous Main")
        companion = store.create_character(account, "Saved Companion")
        generation = store.begin_session(account)
        store.select_character(account, generation, previous["id"])
        heroes.add(store, account, generation, previous["id"], companion["id"])
        encoded = b"New Main"
        body = (
            struct.pack(">qhB", -1, 3, len(encoded))
            + encoded
            + b"\x01"
            + appearance_section({"sex": 0, "clothIndex": 1, "skinColor": -9065766})
        )
        status, created = create(store, account, generation, body)
        self.assertEqual(0, status)
        selected = select_created(store, account, generation, created["id"])
        roster = heroes.ensure_company_party(store, account, generation, selected["id"])
        self.assertEqual(created["id"], roster["leader"]["id"])
        self.assertEqual((companion["id"],), tuple(c["id"] for c in roster["heroes"]))
        self.assertEqual(-9065766, selected["appearance"]["skinColor"])
        with store.connection() as db:
            party = db.execute(
                "SELECT p.leader_id FROM player_parties p JOIN player_party_members m "
                "ON m.party_id=p.id WHERE m.character_id=%s",
                (selected["id"],),
            ).fetchone()
            self.assertEqual(selected["id"], party["leader_id"])

    def test_protocol_creation_persistence_errors_and_session_ownership(self):
        store = self.store
        store.max_characters = 5
        account = store.register("creator", "creation-password")["id"]
        generation = store.begin_session(account)

        def request(name, character_id=-1):
            encoded = name.encode()
            return (
                struct.pack(">qhB", character_id, 2, len(encoded))
                + encoded
                + b"\x01"
                + appearance_section(
                    {"skinColor": -1, "sex": 0, "faceIndex": 3, "clothIndex": 0}
                )
            )

        status, char = create(store, account, generation, request("Fresh"))
        self.assertEqual(status, 0)
        self.assertEqual(char["appearance"]["skinColor"], -1)
        self.assertEqual(
            create(store, account, generation, request("Fresh")), (102, None)
        )
        self.assertEqual(create(store, account, generation, request("12")), (103, None))
        self.assertEqual(
            create(store, account, generation, request("Modify", char["id"])),
            (101, None),
        )
        for name in ("Second", "Third", "Fourth", "Fifth"):
            self.assertEqual(create(store, account, generation, request(name))[0], 0)
        self.assertEqual(
            create(store, account, generation, request("Sixth")), (104, None)
        )
        store.begin_session(account)
        with self.assertRaises(ValueError):
            create(store, account, generation, request("Stale"))
