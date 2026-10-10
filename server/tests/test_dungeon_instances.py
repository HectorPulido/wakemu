from concurrent.futures import ThreadPoolExecutor
import struct
import threading
import unittest
import uuid

from postgres_case import PostgresCase
from psycopg.errors import RaiseException
from wakfu_server import dungeon_instances, dungeon_transport, player_parties
from wakfu_server.maps import dungeon_context


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
        self.install_context_policy(1)

    def install_context_policy(self, version, *, activate=True, allowed_ids=None):
        route = dungeon_instances.route("jalato_normal")
        if allowed_ids is None:
            # Deliberately unrelated to party characters: this is a synthetic
            # config fixture, not a claim about the native allowed_ids policy.
            allowed_ids = [777_777]
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO dungeon_context_policy_versions(route_key,policy_version,"
                "template_id,definition_id,max_level,min_level,difficulty_level,"
                "is_difficulty_available,can_increase_difficulty,"
                "is_competitive_cancelled,allowed_ids,provenance) "
                "VALUES(%s,%s,%s,%s,0,0,2,false,true,false,%s,%s)",
                (
                    route.key,
                    version,
                    route.template_id,
                    route.definition_id,
                    allowed_ids,
                    "synthetic PostgreSQL test fixture; not native dungeon values",
                ),
            )
            if activate:
                db.execute(
                    "INSERT INTO dungeon_context_active_policies(route_key,policy_version) "
                    "VALUES(%s,%s) ON CONFLICT(route_key) DO UPDATE "
                    "SET policy_version=excluded.policy_version",
                    (route.key, version),
                )

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

    def test_frozen_party_members_rejoin_without_moving_inside_companions(self):
        from wakfu_server.maps import dungeon_exit

        for count in (2, 3):
            with self.subTest(count=count):
                members, _ = self.party(count)
                first = self.enter(members[0])
                inside_id = members[-1]["character"]["id"]
                with self.store.connection() as db:
                    db.execute("UPDATE characters SET x=x+4 WHERE id=%s", (inside_id,))
                before = self.store.character(members[-1]["account"], inside_id)
                # Both leader and ordinary member may return to the same run.
                for member in members[:-1]:
                    dungeon_exit._leave(
                        self.store,
                        member["account"],
                        member["generation"],
                        member["character"]["id"],
                        in_fight=lambda _: False,
                        destination_for=lambda db, character, run: {
                            "map_id": 527,
                            "x": -245,
                            "y": -90,
                            "z": 0,
                        },
                    )
                    again = self.enter(member)
                    self.assertEqual(again["instance_id"], first["instance_id"])
                    self.assertTrue(again["reused"])
                after = self.store.character(members[-1]["account"], inside_id)
                self.assertEqual(
                    tuple(before[k] for k in ("map_id", "instance_id", "x", "y", "z")),
                    tuple(after[k] for k in ("map_id", "instance_id", "x", "y", "z")),
                )

    def test_owned_hero_is_frozen_moved_and_returned_without_private_outbox(self):
        from wakfu_server.characters import heroes
        from wakfu_server.maps import dungeon_exit

        main = self.player("hero-main")
        hero = self.store.create_character(main["account"], "Dng Owned Hero")
        heroes.add(
            self.store,
            main["account"],
            main["generation"],
            main["character"]["id"],
            hero["id"],
        )
        result = self.enter(main)
        instance_id = result["instance_id"]
        main_id, hero_id = main["character"]["id"], hero["id"]
        self.assertEqual({main_id, hero_id}, set(result["members"]))
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id,status FROM dungeon_instance_members "
                "WHERE instance_id=%s ORDER BY character_id",
                (instance_id,),
            ).fetchall()
            outbox = db.execute(
                "SELECT character_id,transition_kind FROM dungeon_transition_outbox "
                "WHERE instance_id=%s ORDER BY character_id",
                (instance_id,),
            ).fetchall()
        self.assertEqual({main_id, hero_id}, {row["character_id"] for row in rows})
        self.assertEqual({"active"}, {row["status"] for row in rows})
        self.assertEqual(
            [(main_id, "enter")],
            [(row["character_id"], row["transition_kind"]) for row in outbox],
        )
        hero_inside = self.store.character(main["account"], hero_id)
        self.assertEqual(
            (result["destination"]["map_id"], instance_id),
            (hero_inside["map_id"], hero_inside["instance_id"]),
        )

        dungeon_exit._leave(
            self.store,
            main["account"],
            main["generation"],
            main_id,
            in_fight=lambda _identity: False,
            destination_for=lambda _db, _character, _run: {
                "map_id": 527,
                "x": -245,
                "y": -90,
                "z": 0,
            },
        )
        hero_outside = self.store.character(main["account"], hero_id)
        self.assertEqual(
            (527, 0), (hero_outside["map_id"], hero_outside["instance_id"])
        )
        with self.store.connection() as db:
            returned = db.execute(
                "SELECT character_id,status FROM dungeon_instance_members "
                "WHERE instance_id=%s ORDER BY character_id",
                (instance_id,),
            ).fetchall()
            final_outbox = db.execute(
                "SELECT character_id,transition_kind,status FROM dungeon_transition_outbox "
                "WHERE instance_id=%s AND transition_kind='exit'",
                (instance_id,),
            ).fetchall()
        self.assertEqual({"returned"}, {row["status"] for row in returned})
        self.assertEqual(
            [(main_id, "exit", "pending")],
            [
                (row["character_id"], row["transition_kind"], row["status"])
                for row in final_outbox
            ],
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
        self.assertEqual(result["context_policy_version"], 1)
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
            events = db.execute(
                "SELECT character_id,session_generation,transition_revision,"
                "source_map_id,source_instance_id,source_x,source_y,source_z,"
                "destination_map_id,destination_instance_id,destination_x,"
                "destination_y,destination_z,status FROM dungeon_transition_outbox "
                "WHERE instance_id=%s ORDER BY character_id",
                (live_instance,),
            ).fetchall()
            self.assertEqual(len(events), 2)
            self.assertEqual(
                [row["character_id"] for row in events],
                sorted(member["character"]["id"] for member in members),
            )

    def test_proto_context_uses_pinned_version_and_explicit_allow_ids(self):
        members, _party_id = self.party(2)
        entered = self.enter(members[0])
        instance_id = entered["instance_id"]
        member_ids = {member["character"]["id"] for member in members}
        self.assertNotEqual(set((777_777,)), member_ids)

        self.install_context_policy(2, allowed_ids=[888_888])
        with self.assertRaisesRegex(RaiseException, "immutable"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE dungeon_context_policy_versions SET allowed_ids=%s "
                    "WHERE route_key=%s AND policy_version=1",
                    ([999_999], "jalato_normal"),
                )
        context = dungeon_context.for_instance(
            self.store, instance_id, fight_in_progress=True
        )
        self.assertEqual(context["allowed_ids"], (777_777,))
        self.assertTrue(context["is_fight_in_progress"])
        self.assertEqual(context["difficulty_level"], 2)

        reused = self.enter(members[0])
        self.assertTrue(reused["reused"])
        self.assertEqual(reused["context_policy_version"], 1)
        self.assertEqual(
            dungeon_context.for_instance(
                self.store, instance_id, fight_in_progress=False
            )["allowed_ids"],
            (777_777,),
        )

    def test_missing_context_policy_fails_before_any_party_move(self):
        members, _party_id = self.party(2)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM dungeon_context_active_policies WHERE route_key=%s",
                ("jalato_normal",),
            )
        with self.assertRaisesRegex(ValueError, "policy is not configured"):
            self.enter(members[0])
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT map_id,instance_id FROM characters WHERE id=ANY(%s)",
                ([member["character"]["id"] for member in members],),
            ).fetchall()
            self.assertEqual(len(rows), 2)
            self.assertTrue(
                all(row["map_id"] == 527 and row["instance_id"] == 0 for row in rows)
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                0,
            )

    def test_fight_state_is_required_and_invalid_context_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "fight state is required"):
            dungeon_context.ContextPolicy(
                "jalato_normal", 1, 91, 90, 0, 0, 2, False, True, False, (), "fixture"
            ).proto_context(fight_in_progress=None)
            self.assertTrue(
                all(
                    row["source_map_id"] == 527
                    and row["source_instance_id"] == 0
                    and row["source_x"] == -245
                    and row["source_y"] == -90
                    and row["source_z"] == 2
                    and row["destination_map_id"] == 1086
                    and row["destination_instance_id"] == live_instance
                    and row["destination_x"] == 4
                    and row["destination_y"] == -12
                    and row["destination_z"] == 0
                    and row["transition_revision"] == 1
                    and row["status"] == "pending"
                    for row in events
                )
            )

    def test_transition_outbox_is_private_idempotent_and_acknowledged_once(self):
        members, _ = self.party(2)
        entered = self.enter(members[0])
        instance_id = entered["instance_id"]
        for member in members:
            events = dungeon_instances.pending_transitions(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
            )
            self.assertEqual(len(events), 1)
            event = events[0]
            self.assertEqual(event["instance_id"], instance_id)
            self.assertEqual(event["character_id"], member["character"]["id"])
            self.assertEqual(event["session_generation"], member["generation"])
            self.assertTrue(
                dungeon_instances.acknowledge_transition(
                    self.store,
                    member["account"],
                    member["generation"],
                    member["character"]["id"],
                    event["event_id"],
                )
            )
            self.assertFalse(
                dungeon_instances.acknowledge_transition(
                    self.store,
                    member["account"],
                    member["generation"],
                    member["character"]["id"],
                    event["event_id"],
                )
            )
            self.assertEqual(
                dungeon_instances.pending_transitions(
                    self.store,
                    member["account"],
                    member["generation"],
                    member["character"]["id"],
                ),
                (),
            )

        retry = self.enter(members[0])
        self.assertTrue(retry["transition"]["already_entered"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox "
                    "WHERE instance_id=%s",
                    (instance_id,),
                ).fetchone()["n"],
                2,
            )

    def test_replaced_generation_supersedes_old_event_without_removing_member(self):
        members, _ = self.party(2)
        entered = self.enter(members[0])
        owner, replaced = members
        events = dungeon_instances.pending_transitions(
            self.store,
            replaced["account"],
            replaced["generation"],
            replaced["character"]["id"],
        )
        self.assertEqual(len(events), 1)
        old_event = events[0]

        new_generation = self.store.begin_session(replaced["account"], ttl=10_000)
        fresh_character = self.store.select_character(
            replaced["account"], new_generation, replaced["character"]["id"]
        )
        # The leader's exact retry refreshes membership generation, but the
        # persisted destination means the replacement session must not move.
        retry = self.enter(owner)
        self.assertEqual(retry["instance_id"], entered["instance_id"])
        self.assertTrue(retry["transition"]["already_entered"])
        self.assertEqual(retry["transition"]["members"], ())
        self.assertEqual(
            (fresh_character["map_id"], fresh_character["instance_id"]),
            (1086, entered["instance_id"]),
        )
        self.assertEqual(
            dungeon_instances.pending_transitions(
                self.store,
                replaced["account"],
                new_generation,
                replaced["character"]["id"],
            ),
            (),
        )
        with self.assertRaisesRegex(ValueError, "Sesión o personaje"):
            dungeon_instances.acknowledge_transition(
                self.store,
                replaced["account"],
                replaced["generation"],
                replaced["character"]["id"],
                old_event["event_id"],
            )
        with self.store.connection() as db:
            stale = db.execute(
                "SELECT status FROM dungeon_transition_outbox WHERE event_id=%s",
                (old_event["event_id"],),
            ).fetchone()
            membership = db.execute(
                "SELECT session_generation,status FROM dungeon_instance_members "
                "WHERE instance_id=%s AND character_id=%s",
                (entered["instance_id"], replaced["character"]["id"]),
            ).fetchone()
            saved = db.execute(
                "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=%s",
                (replaced["character"]["id"],),
            ).fetchone()
        self.assertEqual(stale["status"], "superseded")
        self.assertEqual(membership["session_generation"], new_generation)
        self.assertEqual(membership["status"], "active")
        self.assertEqual(
            tuple(saved[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            (1086, entered["instance_id"], 4, -12, 0),
        )

    def test_ack_requires_active_membership_for_pending_and_repeated_ack(self):
        members, _ = self.party(2)
        entered = self.enter(members[0])
        saved_events = {}
        for member in members:
            saved_events[
                member["character"]["id"]
            ] = dungeon_instances.pending_transitions(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
            )[
                0
            ]

        acknowledged_member = members[0]
        acknowledged_event = saved_events[acknowledged_member["character"]["id"]]
        self.assertTrue(
            dungeon_instances.acknowledge_transition(
                self.store,
                acknowledged_member["account"],
                acknowledged_member["generation"],
                acknowledged_member["character"]["id"],
                acknowledged_event["event_id"],
            )
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_instance_members SET status='returned',ended_at=%s "
                "WHERE instance_id=%s AND character_id=%s",
                (
                    self.store.now(),
                    entered["instance_id"],
                    acknowledged_member["character"]["id"],
                ),
            )
        with self.assertRaisesRegex(ValueError, "membership or session was replaced"):
            dungeon_instances.acknowledge_transition(
                self.store,
                acknowledged_member["account"],
                acknowledged_member["generation"],
                acknowledged_member["character"]["id"],
                acknowledged_event["event_id"],
            )

        pending_member = members[1]
        pending_event = saved_events[pending_member["character"]["id"]]
        with self.store.connection() as db:
            db.execute(
                "UPDATE dungeon_instance_members SET status='removed',ended_at=%s "
                "WHERE instance_id=%s AND character_id=%s",
                (
                    self.store.now(),
                    entered["instance_id"],
                    pending_member["character"]["id"],
                ),
            )
        with self.assertRaisesRegex(ValueError, "membership or session was replaced"):
            dungeon_instances.acknowledge_transition(
                self.store,
                pending_member["account"],
                pending_member["generation"],
                pending_member["character"]["id"],
                pending_event["event_id"],
            )

    def test_transition_outbox_insert_failure_rolls_back_every_party_move(self):
        members, _ = self.party(2)
        failing_character = members[1]["character"]["id"]
        with self.store.connection() as db:
            db.execute(
                f"CREATE FUNCTION fail_dungeon_outbox() RETURNS trigger LANGUAGE plpgsql "
                f"AS $$ BEGIN IF NEW.character_id={failing_character} THEN "
                "RAISE EXCEPTION 'injected dungeon outbox failure'; END IF; "
                "RETURN NEW; END $$"
            )
            db.execute(
                "CREATE TRIGGER fail_dungeon_outbox BEFORE INSERT ON "
                "dungeon_transition_outbox FOR EACH ROW EXECUTE FUNCTION fail_dungeon_outbox()"
            )
        with self.assertRaisesRegex(RaiseException, "injected dungeon outbox failure"):
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
                    "SELECT count(*) AS n FROM dungeon_transition_outbox"
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

    def test_nonleader_stale_generation_and_native_denial_are_rejected(self):
        members, _ = self.party(2)
        with self.assertRaisesRegex(ValueError, "leader"):
            self.create(members[1])
        with self.assertRaisesRegex(ValueError, "not authorized"):
            self.create(members[0], lambda _character, _route: False)
        stale = dict(members[0], generation="stale-generation")
        with self.assertRaisesRegex(ValueError, "leader"):
            self.create(stale)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                0,
            )

    def test_solo_entry_creates_singleton_and_reuses_owned_run(self):
        solo = self.player("solo-entry")
        first = self.create(solo)
        second = self.create(solo)
        self.assertEqual(first["instance_id"], second["instance_id"])
        entered = self.enter(solo)
        self.assertEqual(first["instance_id"], entered["instance_id"])
        with self.store.connection() as db:
            party = db.execute(
                "SELECT * FROM player_parties WHERE id=%s", (first["party_id"],)
            ).fetchone()
            members = db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=%s",
                (first["party_id"],),
            ).fetchall()
            self.assertEqual(party["leader_id"], solo["character"]["id"])
            self.assertEqual(members, [{"character_id": solo["character"]["id"]}])
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM dungeon_instances").fetchone()[
                    "n"
                ],
                1,
            )
        self.assertEqual(
            self.store.character(solo["account"], solo["character"]["id"])[
                "instance_id"
            ],
            first["instance_id"],
        )

    def test_solo_authorization_or_initializer_failure_rolls_back_singleton(self):
        solo = self.player("solo-denied")
        with self.assertRaisesRegex(ValueError, "not authorized"):
            self.create(solo, lambda character, route: False)

        def fail_initializer(db, result):
            raise ValueError("Initializer denied")

        with self.assertRaisesRegex(ValueError, "Initializer denied"):
            dungeon_instances.create_or_reuse(
                self.store,
                solo["account"],
                solo["generation"],
                solo["character"]["id"],
                "jalato_normal",
                authorize_entry=lambda character, route: True,
                initialize_instance=fail_initializer,
            )
        with self.store.connection() as db:
            for table in (
                "player_parties",
                "player_party_members",
                "dungeon_instances",
            ):
                self.assertEqual(
                    db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"],
                    0,
                )

    def test_concurrent_solo_requests_create_one_party_and_run(self):
        solo = self.player("solo-concurrent")
        barrier = threading.Barrier(2)

        def enter():
            barrier.wait(timeout=5)
            return self.create(solo)

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: enter(), range(2)))
        self.assertEqual(results[0]["instance_id"], results[1]["instance_id"])
        with self.store.connection() as db:
            for table in (
                "player_parties",
                "player_party_members",
                "dungeon_instances",
            ):
                self.assertEqual(
                    db.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"],
                    1,
                )

    def test_solo_entry_reconciles_outside_membership_from_old_party(self):
        members, old_party = self.party(2)
        old_run = self.create(members[0])
        solo = members[0]
        other_id = members[1]["character"]["id"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE player_parties SET leader_id=%s WHERE id=%s",
                (members[1]["character"]["id"], old_run["party_id"]),
            )
            db.execute(
                "DELETE FROM player_party_members WHERE character_id=%s",
                (solo["character"]["id"],),
            )
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=%s",
                (old_run["instance_id"], other_id),
            )
        entered = self.enter(solo)
        self.assertNotEqual(entered["party_id"], old_party)
        self.assertNotEqual(entered["instance_id"], old_run["instance_id"])
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id,status FROM dungeon_instance_members "
                "WHERE instance_id=%s ORDER BY character_id",
                (old_run["instance_id"],),
            ).fetchall()
        self.assertEqual(
            {row["character_id"]: row["status"] for row in rows},
            {solo["character"]["id"]: "returned", other_id: "active"},
        )

    def test_solo_entry_preserves_foreign_membership_when_still_inside(self):
        members, _ = self.party(2)
        old_run = self.create(members[0])
        solo = members[0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE player_parties SET leader_id=%s WHERE id=%s",
                (members[1]["character"]["id"], old_run["party_id"]),
            )
            db.execute(
                "DELETE FROM player_party_members WHERE character_id=%s",
                (solo["character"]["id"],),
            )
            db.execute(
                "UPDATE characters SET instance_id=%s WHERE id=%s",
                (old_run["instance_id"], solo["character"]["id"]),
            )
        with self.assertRaisesRegex(ValueError, "already belongs"):
            self.create(solo)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM dungeon_instance_members "
                    "WHERE instance_id=%s AND character_id=%s",
                    (old_run["instance_id"], solo["character"]["id"]),
                ).fetchone()["status"],
                "active",
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
