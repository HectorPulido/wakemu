"""Authorized console departures cannot strand a frozen dungeon company."""
from copy import deepcopy
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.characters import heroes
from wakfu_server.characters.creation import create, select_created
from wakfu_server.command_permissions import set_admin
from wakfu_server.combat_groups import Groups
from wakfu_server.console_relocation import relocate
from wakfu_server.test_console import execute
from wakfu_server.position_buffer import Positions
from wakfu_server.wire import appearance_section


class ConsoleDungeonRelocationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("console-dungeon", "test-password")["id"]
        set_admin(
            self.store, self.account, True, operator="test", reason="console fixture"
        )
        self.main = self.store.create_character(self.account, "Console Main")
        self.hero = self.store.create_character(self.account, "Console Hero")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])
        heroes.add(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        self.ids = [self.main["id"], self.hero["id"]]
        with self.store.connection() as db:
            self.party = db.execute(
                "SELECT p.* FROM player_parties p JOIN player_party_members m ON m.party_id=p.id WHERE m.character_id=%s",
                (self.main["id"],),
            ).fetchone()
            self.run = db.execute(
                "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,template_id,definition_id,"
                "entry_map_id,entry_object_id,entry_destination_id,start_map_id) VALUES(%s,%s,%s,1,1,527,1,1,312) RETURNING *",
                (self.party["id"], self.party["revision"], self.main["id"]),
            ).fetchone()
            for identity in self.ids:
                self.member(db, identity, self.generation)
                db.execute(
                    "UPDATE characters SET map_id=312,instance_id=%s,x=4,y=2,z=0 WHERE id=%s",
                    (self.run["instance_id"], identity),
                )
                self.pending(db, identity, self.generation)
        self.source = self.store.character(self.account, self.main["id"])
        self.destination = dict(map_id=527, instance_id=0, x=0, y=32, z=0)

    def member(self, db, identity, generation):
        db.execute(
            "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,session_generation,party_revision,role) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                self.run["instance_id"],
                self.party["id"],
                identity,
                generation,
                self.party["revision"],
                "leader" if identity == self.main["id"] else "member",
            ),
        )

    def pending(self, db, identity, generation):
        db.execute(
            "INSERT INTO dungeon_transition_outbox(instance_id,party_id,transition_revision,character_id,session_generation,"
            "source_map_id,source_instance_id,source_x,source_y,source_z,destination_map_id,destination_instance_id,destination_x,destination_y,destination_z) "
            "VALUES(%s,%s,1,%s,%s,527,0,0,32,0,312,%s,4,2,0)",
            (
                self.run["instance_id"],
                self.party["id"],
                identity,
                generation,
                self.run["instance_id"],
            ),
        )

    def command(self, text="!astrub", *, positions=None):
        return execute(
            self.store,
            Groups(),
            self.account,
            self.generation,
            self.source,
            text,
            positions=positions,
        )

    def snapshot(self):
        with self.store.connection() as db:
            return tuple(
                db.execute(query, parameters).fetchall()
                for query, parameters in (
                    (
                        "SELECT * FROM characters WHERE id=ANY(%s) ORDER BY id",
                        (self.ids,),
                    ),
                    (
                        "SELECT * FROM dungeon_instance_members WHERE instance_id=%s ORDER BY character_id",
                        (self.run["instance_id"],),
                    ),
                    (
                        "SELECT * FROM dungeon_transition_outbox WHERE instance_id=%s ORDER BY event_id",
                        (self.run["instance_id"],),
                    ),
                    (
                        "SELECT * FROM dungeon_instances WHERE instance_id=%s",
                        (self.run["instance_id"],),
                    ),
                    (
                        "SELECT * FROM account_hero_rosters WHERE account_id=%s",
                        (self.account,),
                    ),
                    (
                        "SELECT * FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                        (self.account,),
                    ),
                    (
                        "SELECT * FROM character_progression WHERE character_id=ANY(%s) ORDER BY character_id",
                        (self.ids,),
                    ),
                    (
                        "SELECT * FROM character_builds WHERE character_id=ANY(%s) ORDER BY character_id,build_index",
                        (self.ids,),
                    ),
                )
            )

    def assert_departed(self):
        rows, members, outbox, runs, *_ = self.snapshot()
        self.assertTrue(
            all(row["instance_id"] == 0 and row["map_id"] == 527 for row in rows)
        )
        self.assertTrue(
            all(
                row["status"] == "returned" and row["ended_at"] is not None
                for row in members
            )
        )
        self.assertTrue(all(row["status"] == "superseded" for row in outbox))
        self.assertEqual(runs[0]["status"], "closed")

    def test_actual_astrub_departure_allows_character_creation_and_selection(self):
        before = self.snapshot()
        result = self.command()
        self.assertEqual(result["action"], "tp")
        self.assert_departed()
        after = self.snapshot()
        self.assertEqual(before[4:], after[4:])
        for old, new in zip(before[0], after[0]):
            for field in ("hp", "max_hp", "hp_damage", "health_dead", "level"):
                self.assertEqual(old[field], new[field])
        name = b"After Dungeon"
        self.store.clear_character(self.account, self.generation)
        body = (
            struct.pack(">qhB", -1, 15, len(name))
            + name
            + b"\x01"
            + appearance_section({"sex": 0})
        )
        status, created = create(self.store, self.account, self.generation, body)
        self.assertEqual(status, 0)
        selected = select_created(
            self.store, self.account, self.generation, created["id"]
        )
        self.assertEqual(selected["id"], created["id"])

    def test_actual_teleport_departure_completes_the_same_owned_lifecycle(self):
        result = self.command("!teleport 527 0 32 0")
        self.assertEqual(result["character"]["instance_id"], 0)
        self.assert_departed()

    def test_position_registry_is_rebound_cleanly_after_console_departure(self):
        positions = Positions(
            self.store,
            lease_active=lambda account, generation, character: (
                account == self.account
                and generation == self.generation
                and character == self.main["id"]
            ),
        )
        positions.attach(self.account, self.generation, self.source)
        result = self.command(positions=positions)
        self.assertEqual(result["character"]["instance_id"], 0)
        self.assert_departed()
        key = (self.account, self.generation, self.main["id"])
        entry = positions.entries[key]
        self.assertFalse(entry["dirty"])
        self.assertEqual(
            (527, 0, 0, 32, 0),
            tuple(
                entry["persisted"][field]
                for field in ("map_id", "instance_id", "x", "y", "z")
            ),
        )

    def test_foreign_member_combat_and_pending_transition_are_preserved(self):
        foreign_account = self.store.register("console-foreign", "test-password")["id"]
        foreign = self.store.create_character(foreign_account, "Foreign Member")
        with self.store.connection() as db:
            self.member(db, foreign["id"], "foreign-generation")
            self.pending(db, foreign["id"], "foreign-generation")
            db.execute(
                "UPDATE characters SET map_id=312,instance_id=%s WHERE id=%s",
                (self.run["instance_id"], foreign["id"]),
            )
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight, foreign["id"], foreign_account),
            )
            original = db.execute(
                "SELECT * FROM characters WHERE id=%s", (foreign["id"],)
            ).fetchone()
        self.command()
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT * FROM characters WHERE id=%s", (foreign["id"],)
                ).fetchone(),
                original,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instances WHERE instance_id=%s",
                    (self.run["instance_id"],),
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s",
                    (self.run["instance_id"], foreign["id"]),
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_transition_outbox WHERE instance_id=%s AND character_id=%s",
                    (self.run["instance_id"], foreign["id"]),
                ).fetchone()["status"],
                "pending",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight,)
                ).fetchone()["status"],
                "active",
            )

    def assert_combat_rejected(self, identity):
        with self.store.connection() as db:
            fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight, identity, self.account),
            )
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "during combat"):
            self.command()
        self.assertEqual(self.snapshot(), before)

    def test_active_main_combat_cannot_partially_depart(self):
        self.assert_combat_rejected(self.main["id"])

    def test_active_owned_hero_combat_cannot_partially_depart(self):
        self.assert_combat_rejected(self.hero["id"])

    def test_failure_after_membership_mutation_rolls_back_whole_departure(self):
        before = self.snapshot()
        with patch.object(
            self.store,
            "transition_map_in_transaction",
            side_effect=ValueError("Injected CAS failure"),
        ):
            with self.assertRaisesRegex(ValueError, "Injected CAS failure"):
                self.command()
        self.assertEqual(self.snapshot(), before)

    def test_stale_source_and_generation_preserve_membership_and_location(self):
        before = self.snapshot()
        stale = deepcopy(self.source)
        stale["x"] += 1
        for generation, source in (
            (self.generation, stale),
            ("expired-generation", self.source),
        ):
            with self.assertRaises(ValueError):
                relocate(
                    self.store,
                    self.account,
                    generation,
                    self.main["id"],
                    source,
                    self.destination,
                )
            self.assertEqual(self.snapshot(), before)
