from concurrent.futures import ThreadPoolExecutor
import struct
import threading
import unittest
import uuid

from postgres_case import PostgresCase
from psycopg.errors import RaiseException
from wakfu_server import dungeon_instances, dungeon_transport, player_parties


class DungeonRouteConfigurationTests(unittest.TestCase):
    def test_configured_jalato_route_matches_catalog_ids_without_waiving_criterion(
        self,
    ):
        route = dungeon_instances.route("jalato_normal")
        self.assertEqual(
            (
                route.entry_map_id,
                route.entry_object_id,
                route.destination_id,
                route.template_id,
                route.definition_id,
                route.start_map_id,
            ),
            (527, 26842, 2504, 91, 90, 1086),
        )
        self.assertEqual(route.criterion, "not IsNeoServer()")
        with self.assertRaisesRegex(ValueError, "Unknown configured"):
            dungeon_instances.route("untrusted-client-route")


class DungeonInstanceTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0

    def player(self, label):
        account = self.store.register("di" + uuid.uuid4().hex[:10], "test-password")[
            "id"
        ]
        suffix = "".join(
            chr(ord("a") + int(value, 16)) for value in uuid.uuid4().hex[:9]
        )
        name = "Dng" + suffix
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=-245,y=-90,z=2 "
                "WHERE id=%s",
                (character["id"],),
            )
        character.update(map_id=527, instance_id=0, x=-245, y=-90, z=2)
        return {"account": account, "generation": generation, "character": character}

    def party(self, count=2):
        members = [self.player(f"m{i}") for i in range(count)]
        party_id = None
        for member in members[1:]:
            token = player_parties.invite(
                self.store,
                members[0]["account"],
                members[0]["generation"],
                members[0]["character"]["id"],
                member["character"]["id"],
            )
            party_id = player_parties.answer(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
                token,
                True,
            )
        return members, party_id

    def create(self, leader, callback=lambda character, route: True):
        return dungeon_instances.create_or_reuse(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            "jalato_normal",
            authorize_entry=callback,
        )

    def enter(
        self,
        leader,
        *,
        criterion=lambda _character, _expression: True,
        source=lambda _character, _native_source: True,
    ):
        return dungeon_transport.enter(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            leader["character"]["map_id"],
            struct.pack(">qiBi", 26842, 2504, 0, 2),
            criterion_allowed=criterion,
            source_allowed=source,
        )

    def test_entry_creates_live_run_and_moves_all_members_atomically(self):
        members, party_id = self.party(2)
        checks = []

        def criterion(_character, expression):
            checks.append(("criterion", expression))
            return True

        def source(_character, native_source):
            checks.append(("source", native_source["map_id"], native_source["id"]))
            return True

        result = self.enter(members[0], criterion=criterion, source=source)
        live_instance = result["instance_id"]
        self.assertEqual(result["party_id"], party_id)
        self.assertEqual(result["template_id"], 91)
        self.assertGreater(live_instance, 0)
        self.assertNotEqual(live_instance, 91)
        self.assertEqual(
            result["destination"],
            {
                "map_id": 1086,
                "x": 4,
                "y": -12,
                "z": 0,
                "direction": 7,
                "instance_id": live_instance,
            },
        )
        self.assertEqual(
            result["transition"]["members"],
            tuple(sorted(member["character"]["id"] for member in members)),
        )
        self.assertEqual(
            checks, [("source", 527, 26842), ("criterion", "not IsNeoServer()")]
        )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters "
                "WHERE id=ANY(%s) ORDER BY id",
                ([member["character"]["id"] for member in members],),
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertTrue(
                all(
                    (row["map_id"], row["instance_id"], row["x"], row["y"], row["z"])
                    == (1086, live_instance, 4, -12, 0)
                    for row in rows
                )
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_instances WHERE instance_id=%s "
                    "AND template_id=91 AND start_map_id=1086",
                    (live_instance,),
                ).fetchone()["n"],
                1,
            )

    def test_denied_native_criterion_or_source_leaves_no_run_or_partial_move(self):
        members, _ = self.party(2)
        for criterion, source in (
            (lambda _character, _expr: False, lambda _character, _source: True),
            (lambda _character, _expr: True, lambda _character, _source: False),
        ):
            with self.assertRaisesRegex(ValueError, "not authorized"):
                self.enter(members[0], criterion=criterion, source=source)
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM dungeon_instances"
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM characters WHERE id=ANY(%s) "
                        "AND map_id=527 AND instance_id=0",
                        ([member["character"]["id"] for member in members],),
                    ).fetchone()["n"],
                    2,
                )

    def test_location_update_failure_rolls_back_run_and_entire_party_transition(self):
        members, _ = self.party(2)
        failing_id = members[1]["character"]["id"]
        with self.store.connection() as db:
            db.execute(
                f"CREATE FUNCTION fail_dungeon_move() RETURNS trigger LANGUAGE plpgsql "
                f"AS $$ BEGIN IF NEW.id={failing_id} AND NEW.instance_id<>0 THEN "
                "RAISE EXCEPTION 'injected dungeon movement failure'; END IF; "
                "RETURN NEW; END $$"
            )
            db.execute(
                "CREATE TRIGGER fail_dungeon_move BEFORE UPDATE ON characters "
                "FOR EACH ROW EXECUTE FUNCTION fail_dungeon_move()"
            )
        with self.assertRaisesRegex(
            RaiseException, "injected dungeon movement failure"
        ):
            self.enter(members[0])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_instance_members"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM characters WHERE id=ANY(%s) "
                    "AND map_id=527 AND instance_id=0",
                    ([member["character"]["id"] for member in members],),
                ).fetchone()["n"],
                2,
            )

    def test_duplicate_entry_request_is_idempotent_after_atomic_transition(self):
        members, _ = self.party(2)
        checks = []
        first = self.enter(
            members[0],
            criterion=lambda _c, expr: checks.append(expr) is None,
        )
        retry = self.enter(
            members[0],
            criterion=lambda _c, expr: self.fail(
                "retry should not reevaluate entry criteria"
            ),
            source=lambda _c, _s: self.fail(
                "retry should not recheck source after moving"
            ),
        )
        self.assertEqual(first["instance_id"], retry["instance_id"])
        self.assertFalse(first["transition"]["already_entered"])
        self.assertTrue(retry["transition"]["already_entered"])
        self.assertEqual(retry["transition"]["members"], ())
        self.assertEqual(checks, ["not IsNeoServer()"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                1,
            )

    def test_concurrent_entry_requests_share_one_run_and_transition_once(self):
        members, _ = self.party(2)
        barrier = threading.Barrier(2)

        def enter():
            barrier.wait(timeout=5)
            return self.enter(members[0])

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: enter(), range(2)))
        self.assertEqual(results[0]["instance_id"], results[1]["instance_id"])
        self.assertEqual(
            sorted(row["transition"]["already_entered"] for row in results),
            [False, True],
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM characters WHERE id=ANY(%s) "
                    "AND map_id=1086 AND instance_id=%s AND x=4 AND y=-12 AND z=0",
                    (
                        [member["character"]["id"] for member in members],
                        results[0]["instance_id"],
                    ),
                ).fetchone()["n"],
                2,
            )

    def test_party_session_separates_template_from_unique_live_instance_and_reuses(
        self,
    ):
        members, party_id = self.party(3)
        seen = []
        first = self.create(
            members[0], lambda character, route: seen.append(route) is None
        )
        second = self.create(members[0])

        self.assertEqual(first["party_id"], party_id)
        self.assertEqual(first["template_id"], 91)
        self.assertEqual(first["definition_id"], 90)
        self.assertEqual(first["start_map_id"], 1086)
        self.assertGreater(first["instance_id"], 0)
        self.assertNotEqual(first["instance_id"], first["template_id"])
        self.assertNotEqual(first["instance_id"], party_id)
        self.assertIsNone(
            dungeon_instances.authorize_member(
                self.store,
                members[1]["account"],
                members[1]["generation"],
                members[1]["character"]["id"],
                first["template_id"],
            ),
            "a native cyZ template identifier must never authorize a live run",
        )
        self.assertEqual(
            first["members"], tuple(sorted(m["character"]["id"] for m in members))
        )
        self.assertEqual(seen[0].criterion, "not IsNeoServer()")
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["instance_id"], second["instance_id"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_instance_members WHERE instance_id=%s "
                    "AND status='active'",
                    (first["instance_id"],),
                ).fetchone()["n"],
                3,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM characters WHERE map_id=527 AND instance_id=0 "
                    "AND id=ANY(%s)",
                    ([m["character"]["id"] for m in members],),
                ).fetchone()["n"],
                3,
            )

    def test_nonleader_no_party_stale_generation_and_native_denial_are_rejected(self):
        members, _ = self.party(2)
        with self.assertRaisesRegex(ValueError, "leader"):
            self.create(members[1])
        with self.assertRaisesRegex(ValueError, "not authorized"):
            self.create(members[0], lambda _character, _route: False)
        stale = dict(members[0], generation="stale-generation")
        with self.assertRaisesRegex(ValueError, "leader"):
            self.create(stale)
        solo = self.player("solo")
        with self.assertRaisesRegex(ValueError, "not in a player party"):
            self.create(solo)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                0,
            )

    def test_entry_fails_closed_if_party_member_offline_or_not_at_entrance(self):
        members, _ = self.party(2)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134 WHERE id=%s",
                (members[1]["character"]["id"],),
            )
        with self.assertRaisesRegex(ValueError, "online at the dungeon entrance"):
            self.create(members[0])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527 WHERE id=%s",
                (members[1]["character"]["id"],),
            )
            db.execute(
                "UPDATE sessions SET expires_at=%s WHERE account_id=%s",
                (self.store.now(-1), members[1]["account"]),
            )
        with self.assertRaisesRegex(ValueError, "online at the dungeon entrance"):
            self.create(members[0])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                0,
            )

    def test_creation_rolls_back_session_and_all_member_rows_on_mid_transaction_failure(
        self,
    ):
        members, _ = self.party(2)
        failing_character = members[1]["character"]["id"]
        with self.store.connection() as db:
            db.execute(
                f"CREATE FUNCTION fail_dungeon_member_insert() RETURNS trigger "
                f"LANGUAGE plpgsql AS $$ BEGIN IF NEW.character_id={failing_character} THEN "
                "RAISE EXCEPTION 'injected dungeon member failure'; END IF; RETURN NEW; END $$"
            )
            db.execute(
                "CREATE TRIGGER fail_dungeon_member BEFORE INSERT ON dungeon_instance_members "
                "FOR EACH ROW EXECUTE FUNCTION fail_dungeon_member_insert()"
            )
        with self.assertRaisesRegex(RaiseException, "injected dungeon member failure"):
            self.create(members[0])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_instance_members"
                ).fetchone()["n"],
                0,
            )

    def test_concurrent_entry_requests_reuse_one_party_instance(self):
        members, _ = self.party(2)
        barrier = threading.Barrier(2)

        def enter():
            barrier.wait(timeout=5)
            return self.create(members[0])

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: enter(), range(2)))
        self.assertEqual(results[0]["instance_id"], results[1]["instance_id"])
        self.assertEqual(sorted(result["reused"] for result in results), [False, True])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                1,
            )

    def test_only_current_session_generation_can_authorize_instance_membership(self):
        members, _ = self.party(2)
        session = self.create(members[0])
        allowed = dungeon_instances.authorize_member(
            self.store,
            members[1]["account"],
            members[1]["generation"],
            members[1]["character"]["id"],
            session["instance_id"],
        )
        self.assertEqual(allowed["role"], "member")
        next_generation = self.store.begin_session(members[1]["account"], ttl=10_000)
        self.store.select_character(
            members[1]["account"], next_generation, members[1]["character"]["id"]
        )
        self.assertIsNone(
            dungeon_instances.authorize_member(
                self.store,
                members[1]["account"],
                next_generation,
                members[1]["character"]["id"],
                session["instance_id"],
            )
        )
        refreshed = self.create(members[0])
        self.assertTrue(refreshed["reused"])
        self.assertEqual(refreshed["revision"], session["revision"] + 1)
        self.assertIsNotNone(
            dungeon_instances.authorize_member(
                self.store,
                members[1]["account"],
                next_generation,
                members[1]["character"]["id"],
                session["instance_id"],
            )
        )
