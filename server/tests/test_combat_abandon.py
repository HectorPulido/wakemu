import struct
import tempfile
from contextlib import contextmanager
from postgres_case import PostgresCase
from wakfu_server import health_store, combat_abandon
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages


def setup_abandon_state(store):
    store.clock = lambda: 1000
    account = store.register("one", "local-password")["id"]
    generation = store.begin_session(account)
    character = store.create_character(account, "One")
    character = store.select_character(account, generation, character["id"])
    character = health_store.initialize(
        store, account, generation, character["id"], coefficient=0
    )
    with store.connection() as db:
        db.execute(
            "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(%s,'placement')",
            (7,),
        )
        db.execute(
            "INSERT INTO combat_fight_participants"
            "(fight_id,character_id,account_id,team,session_generation,entry_hp,"
            "entry_max_hp,entry_hp_damage,entry_health_dead) "
            "VALUES(%s,%s,%s,0,%s,%s,%s,%s,%s)",
            (
                7,
                character["id"],
                account,
                generation,
                character["hp"],
                character["max_hp"],
                character["hp_damage"],
                character["health_dead"],
            ),
        )
    fight = Fight(
        7,
        [
            Actor(
                character["id"],
                0,
                (0, 0, 0),
                character["hp"],
                6,
                3,
                0,
                account,
                1,
                True,
            ),
            Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
        ],
        {(0, 0, 0), (1, 0, 0)},
        {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
    )
    return store, account, generation, character, fight, RuntimeMessages(fight)


class AbandonTests(PostgresCase):
    def test_earned_scene_abandonment_restores_book_after_durable_abort(self):
        from unittest.mock import patch

        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        actor = fight.actors[character["id"]]
        fight.native_abomination_quest_grant = dict(
            status="granted",
            source=dict(participant_id=character["id"]),
            carrier_uid=41,
        )
        actions = []

        def factory(*, action_id):
            actions.append(action_id)
            return "native-runtime"

        runtime.expiration_runtime_factory = factory

        def cleanup(candidate, native_factory, packets):
            self.assertIsNot(candidate, fight)
            self.assertEqual(native_factory, "native-runtime")
            candidate.native_abomination_quest_grant["status"] = "cleaned"

        with patch(
            "wakfu_server.combat_abomination_scene.cleanup", side_effect=cleanup
        ):
            result = combat_abandon.prepare(
                store, account, generation, character, runtime, b""
            )
        self.assertTrue(result["applied"])
        self.assertIs(runtime.fight, fight)
        self.assertIs(fight.actors[character["id"]], actor)
        self.assertEqual(fight.native_abomination_quest_grant["status"], "cleaned")
        self.assertEqual(actions, [1])

    def test_earned_scene_abandonment_failure_keeps_original_book_and_counters(self):
        from unittest.mock import patch

        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        fight.native_abomination_quest_grant = dict(
            status="granted",
            source=dict(participant_id=character["id"]),
            carrier_uid=41,
        )
        runtime.expiration_runtime_factory = lambda **kwargs: "native-runtime"

        def cleanup(candidate, native_factory, packets):
            candidate.native_abomination_quest_grant["status"] = "cleaned"

        with patch(
            "wakfu_server.combat_abomination_scene.cleanup", side_effect=cleanup
        ), patch(
            "wakfu_server.combat_abandon.combat_health.persist_owned",
            side_effect=ValueError("settlement rejected"),
        ):
            with self.assertRaisesRegex(ValueError, "settlement rejected"):
                combat_abandon.prepare(
                    store, account, generation, character, runtime, b""
                )
        self.assertIs(runtime.fight, fight)
        self.assertEqual(fight.native_abomination_quest_grant["status"], "granted")
        self.assertEqual(fight.phase, "placement")
        self.assertEqual(runtime.action_id, 0)

    def test_committed_abort_publishes_one_spectator_terminal_without_npc_settlement(
        self,
    ):
        import ast
        from pathlib import Path
        from types import SimpleNamespace
        from wakfu_server.combat_spectator_events import is_normal_finish_packet
        from wakfu_server.performance_profiler import PROFILER

        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        self.assertIsNone(combat_abandon.committed_abandon_team(runtime))
        result = combat_abandon.prepare(
            store, account, generation, character, runtime, b""
        )
        self.assertTrue(result["applied"])
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "aborted",
            )
        self.assertEqual(combat_abandon.committed_abandon_team(runtime), 0)
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        (function,) = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "publish_spectator_state"
        ]
        for events in (tuple(result["packets"]), ()):
            with self.subTest(retry_without_events=not events):
                deliveries, errors = [], []
                registry = SimpleNamespace(
                    fights={fight.id: SimpleNamespace(revision=1)},
                    publish_terminal=lambda identity, **kwargs: deliveries.append(
                        (identity, kwargs)
                    ),
                )
                scope = {
                    "COMBAT_TEST": True,
                    "PROFILER": PROFILER,
                    "SPECTATORS": registry,
                    "spectator_waiting_for_ack": lambda shared: False,
                    "record": lambda **kwargs: errors.append(kwargs),
                }
                exec(
                    compile(
                        ast.fix_missing_locations(
                            ast.Module(body=[function], type_ignores=[])
                        ),
                        str(source),
                        "exec",
                    ),
                    scope,
                )
                shared = SimpleNamespace(
                    fight=fight,
                    runtime=runtime,
                    settlement_ready=False,
                    participants={},
                    sequence=2,
                )
                scope["publish_spectator_state"](shared, events)
                self.assertEqual(errors, [])
                self.assertEqual(len(deliveries), 1)
                identity, delivery = deliveries[0]
                self.assertEqual(identity, fight.id)
                terminals = [
                    packet for packet in delivery["event_packets"] if packet[0] == 12238
                ]
                self.assertEqual(len(terminals), 1)
                self.assertTrue(is_normal_finish_packet(terminals[0], fight.id))
                self.assertFalse(shared.settlement_ready)

    def test_committed_abort_projection_rejects_foreign_and_withdrawn_continuation(
        self,
    ):
        from copy import deepcopy

        store, account, generation, character, fight, runtime = setup_abandon_state(
            self.store
        )
        combat_abandon.prepare(store, account, generation, character, runtime, b"")
        for invalid in ("foreign_owner", "missing_actor", "withdrawn_actor", "winner"):
            with self.subTest(invalid=invalid):
                candidate = deepcopy(runtime)
                if invalid == "foreign_owner":
                    candidate.abandon_owner = (account + 1, character["id"])
                elif invalid == "missing_actor":
                    candidate.abandon_owner = (account, character["id"] + 1000)
                elif invalid == "withdrawn_actor":
                    candidate.fight.actors[character["id"]].pve_withdrawn = True
                else:
                    candidate.fight.winner = 1
                with self.assertRaises(ValueError):
                    combat_abandon.committed_abandon_team(candidate)

    def test_returns_persist_all_owned_hero_health_atomically(self):
        from wakfu_server import combat_lifecycle

        s, a, g, c, f, r = setup_abandon_state(self.store)
        hero = s.create_character(a, "Return Hero")
        f.actors[hero["id"]] = Actor(
            hero["id"],
            0,
            (2, 0, 0),
            hero["hp"] - 4,
            6,
            3,
            0,
            hero["level"],
            a,
            True,
            max_hp=hero["max_hp"],
        )
        with s.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (f.id, hero["id"], a, g),
            )
        f.phase, f.winner = "finished", 0
        result = combat_lifecycle.return_to_world(
            s, a, g, c, r, struct.pack(">iB", f.id, 0), wp=6
        )
        self.assertTrue(result["applied"])
        self.assertEqual(s.character(a, hero["id"])["hp"], hero["hp"] - 4)
        # A normal return cannot be reinterpreted as a committed abandonment.
        r.abandon_owner = (a, c["id"])
        r.abandon_returned = False
        f.winner = None
        with self.assertRaisesRegex(ValueError, "committed terminal abort"):
            combat_abandon.return_to_world(
                s, a, g, result["character"], r, struct.pack(">iB", f.id, 0), wp=6
            )
        with s.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_health_exits " "WHERE fight_id=%s",
                    (f.id,),
                ).fetchone()["n"],
                2,
            )

    def test_abort_returns_persist_all_owned_hero_health_atomically(self):
        s, a, g, c, f, r = setup_abandon_state(self.store)
        hero = s.create_character(a, "Return Hero")
        f.actors[hero["id"]] = Actor(
            hero["id"],
            0,
            (2, 0, 0),
            hero["hp"] - 4,
            6,
            3,
            0,
            hero["level"],
            a,
            True,
            max_hp=hero["max_hp"],
        )
        with s.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (f.id, hero["id"], a, g),
            )
        combat_abandon.prepare(s, a, g, c, r, b"")
        result = combat_abandon.return_to_world(
            s, a, g, c, r, struct.pack(">iB", f.id, 0), wp=6
        )
        self.assertTrue(result["applied"])
        self.assertEqual(s.character(a, hero["id"])["hp"], hero["hp"] - 4)

    def test_prepare_abort_persists_all_hero_receipts_before_client_callback(self):
        s, a, g, c, f, r = setup_abandon_state(self.store)
        hero = s.create_character(a, "Abort Hero")
        f.actors[hero["id"]] = Actor(
            hero["id"],
            0,
            (2, 0, 0),
            hero["hp"] - 4,
            6,
            3,
            0,
            hero["level"],
            a,
            True,
            max_hp=hero["max_hp"],
        )
        with s.connection() as db:
            db.execute(
                "INSERT INTO combat_fight_participants"
                "(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (f.id, hero["id"], a, g),
            )
        prepared = combat_abandon.prepare(s, a, g, c, r, b"")
        self.assertTrue(prepared["applied"])
        self.assertEqual(s.character(a, hero["id"])["hp"], hero["hp"] - 4)
        with s.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_health_exits " "WHERE fight_id=%s",
                    (f.id,),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (f.id,)
                ).fetchone()["status"],
                "aborted",
            )
        self.assertFalse(
            combat_abandon.prepare(s, a, g, prepared["character"], r, b"")["applied"]
        )

    def setup(self, directory):
        return setup_abandon_state(self.store)

    def test_abandon_placement_waits_for_matching_callback_without_rewards(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, f, r = self.setup(directory)
            result = combat_abandon.prepare(s, a, g, c, r, b"")
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT status FROM combat_fights WHERE id=%s", (f.id,)
                    ).fetchone()["status"],
                    "aborted",
                )  # Durable outcome is committed by prepare, before any checkpoint/ACK.
            self.assertEqual([op for op, body in result["packets"]], [12238, 13420])
            self.assertEqual(result["packets"][0][1][12], 0)
            self.assertEqual(
                result["packets"][0][1][13:],
                struct.pack(">bqbqb", 1, c["id"], 1, -200, 0),
            )
            self.assertEqual((f.phase, f.winner), ("finished", None))
            self.assertFalse(
                combat_abandon.prepare(s, a, g, result["character"], r, b"")["applied"]
            )
            with self.assertRaises(ValueError):
                combat_abandon.return_to_world(
                    s, a, g, result["character"], r, struct.pack(">iB", 8, 1), wp=6
                )
            with self.assertRaises(ValueError):
                combat_abandon.return_to_world(
                    s, a, g, result["character"], r, struct.pack(">iB", 7, 2), wp=6
                )
            returned = combat_abandon.return_to_world(
                s, a, g, result["character"], r, struct.pack(">iB", 7, 1), wp=6
            )
            self.assertEqual(returned["character"]["hp"], c["hp"])
            self.assertEqual(
                [op for op, body in returned["packets"]], [13046, 13046, 13046, 12436]
            )
            self.assertFalse(
                combat_abandon.return_to_world(
                    s, a, g, returned["character"], r, struct.pack(">iB", 7, 0), wp=6
                )["applied"]
            )
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_health_exits"
                    ).fetchone()["count"],
                    1,
                )

    def test_rejected_ready_without_message_runtime_can_abandon_and_return(self):
        from wakfu_server.combat_ready import prepare_ready

        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, fight, unused = self.setup(directory)

            def rejected(preview, action_id):
                raise ValueError("Unsupported HasStateFromUser actor selector")

            with self.assertRaisesRegex(ValueError, "HasStateFromUser"):
                prepare_ready(
                    fight,
                    a,
                    True,
                    initialize=rejected,
                    stats_serializer=lambda actor: b"",
                    effects_serializer=lambda: b"",
                )
            self.assertEqual(fight.phase, "placement")
            runtime = combat_abandon.placement_runtime(fight, None)
            done = combat_abandon.prepare(s, a, g, c, runtime, b"")
            delivery = runtime.prepare_delivery(done["packets"])
            self.assertEqual([op for op, _ in delivery], [12238, 13420])
            self.assertEqual(fight.phase, "finished")
            returned = combat_abandon.return_to_world(
                s,
                a,
                g,
                done["character"],
                runtime,
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
            self.assertTrue(returned["applied"])
            self.assertTrue(runtime.abandon_returned)
            self.assertEqual(returned["character"]["hp"], c["hp"])

    def test_runtime_recovery_does_not_replace_active_counters_or_accept_foreign_fight(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, fight, runtime = self.setup(directory)
            runtime.native_action_id = 37
            self.assertIs(combat_abandon.placement_runtime(fight, runtime), runtime)
            self.assertEqual(runtime.native_action_id, 37)
            with self.assertRaisesRegex(ValueError, "disagrees"):
                combat_abandon.placement_runtime(object(), runtime)
            fight.ready(a)
            with self.assertRaisesRegex(ValueError, "outside placement"):
                combat_abandon.placement_runtime(fight, None)
            with self.assertRaisesRegex(ValueError, "outside placement"):
                combat_abandon.placement_runtime(None, None)

    def test_legacy_client_win_presentation_still_returns_owned_abort(self):
        # Clients already cleaned by the old reversed lists legitimately send
        # huO=false. Outcome remains an abort, never a rewarded victory.
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, f, r = self.setup(directory)
            prepared = combat_abandon.prepare(s, a, g, c, r, b"")
            returned = combat_abandon.return_to_world(
                s, a, g, prepared["character"], r, struct.pack(">iB", f.id, 0), wp=6
            )
            self.assertTrue(returned["applied"])
            self.assertEqual((f.phase, f.winner), ("finished", None))
            self.assertTrue(r.abandon_returned)
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) AS count FROM fight_rewards"
                    ).fetchone()["count"],
                    0,
                )
            with self.assertRaises(ValueError):
                combat_abandon.return_to_world(
                    s, a + 1, g, c, r, struct.pack(">iB", f.id, 0), wp=6
                )

    def test_active_damage_survives_abort_and_invalid_request_is_nonmutating(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, f, r = self.setup(directory)
            f.ready(a)
            f.actors[c["id"]].hp -= 5
            r.awaiting_ack = 1
            r.pending = [(1, b"pending")]
            with self.assertRaises(ValueError):
                combat_abandon.prepare(s, a, g, c, r, b"\0")
            self.assertEqual(f.phase, "active")
            self.assertEqual(r.awaiting_ack, 1)
            done = combat_abandon.prepare(s, a, g, c, r, b"")
            self.assertEqual(done["character"]["hp"], c["hp"] - 5)
            self.assertIsNone(r.awaiting_ack)
            self.assertEqual(r.pending, [])

    def test_stale_owner_cannot_mutate_fsm_or_health(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, f, r = self.setup(directory)
            s.begin_session(a)
            with self.assertRaises(ValueError):
                combat_abandon.prepare(s, a, g, c, r, b"")
            self.assertEqual(f.phase, "placement")
            self.assertEqual(r.action_id, 0)

    def test_status_update_failure_rolls_back_health_receipt_and_runtime_state(self):
        from unittest.mock import patch
        from wakfu_server.fight_store import activate

        s, a, g, c, f, r = self.setup(None)
        f.ready(a)
        f.actors[c["id"]].hp -= 5
        activate(s, a, g, c["id"], f.id)
        r.awaiting_ack = 17
        r.pending = [(123, b"pending")]
        pending = r.pending
        original_connection = s.connection

        @contextmanager
        def fail_abort_status():
            with original_connection() as db:

                class FaultingConnection:
                    def execute(self, query, *args, **kwargs):
                        if "UPDATE combat_fights SET status='aborted'" in query:
                            raise RuntimeError("injected abort status failure")
                        return db.execute(query, *args, **kwargs)

                    def __getattr__(self, name):
                        return getattr(db, name)

                yield FaultingConnection()

        before = s.character(a, c["id"])
        with patch.object(s, "connection", side_effect=fail_abort_status):
            with self.assertRaisesRegex(RuntimeError, "injected abort status failure"):
                combat_abandon.prepare(s, a, g, c, r, b"")

        after = s.character(a, c["id"])
        self.assertEqual(
            (after["hp"], after["hp_damage"], after["health_dead"]),
            (before["hp"], before["hp_damage"], before["health_dead"]),
        )
        self.assertEqual(
            (f.phase, f.winner, f.actors[c["id"]].hp), ("active", None, c["hp"] - 5)
        )
        self.assertEqual((r.awaiting_ack, r.pending), (17, pending))
        self.assertIs(r.pending, pending)
        with s.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (f.id,)
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM fight_health_exits WHERE fight_id=%s",
                    (f.id,),
                ).fetchone()["count"],
                0,
            )

    def test_finished_durable_fight_rejects_abandon_without_any_mutation(self):
        s, a, g, c, f, r = self.setup(None)
        f.ready(a)
        f.actors[c["id"]].hp -= 5
        r.awaiting_ack = 17
        r.pending = [(123, b"pending")]
        with s.connection() as db:
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (f.id,)
            )
        before = s.character(a, c["id"])

        with self.assertRaisesRegex(ValueError, "durably abandoned"):
            combat_abandon.prepare(s, a, g, c, r, b"")

        after = s.character(a, c["id"])
        self.assertEqual(
            (after["hp"], after["hp_damage"], after["health_dead"]),
            (before["hp"], before["hp_damage"], before["health_dead"]),
        )
        self.assertEqual(
            (f.phase, f.winner, f.actors[c["id"]].hp), ("active", None, c["hp"] - 5)
        )
        self.assertEqual((r.awaiting_ack, r.pending), (17, [(123, b"pending")]))
        with s.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (f.id,)
                ).fetchone()["status"],
                "finished",
            )
            self.assertEqual(
                db.execute(
                    "SELECT COUNT(*) AS count FROM fight_health_exits WHERE fight_id=%s",
                    (f.id,),
                ).fetchone()["count"],
                0,
            )

    def test_durable_abandon_locks_fight_before_owned_session_and_character(self):
        from unittest.mock import patch

        s, a, g, c, f, r = self.setup(None)
        original_connection = s.connection
        statements = []

        @contextmanager
        def observing_connection():
            with original_connection() as db:

                class ObservingConnection:
                    def execute(self, query, *args, **kwargs):
                        statements.append(" ".join(query.split()))
                        return db.execute(query, *args, **kwargs)

                    def __getattr__(self, name):
                        return getattr(db, name)

                yield ObservingConnection()

        with patch.object(s, "connection", side_effect=observing_connection):
            combat_abandon.prepare(s, a, g, c, r, b"")

        fight_lock = next(
            index
            for index, statement in enumerate(statements)
            if statement.startswith("SELECT id FROM combat_fights WHERE id=")
            and statement.endswith("FOR UPDATE")
        )
        session_lock = next(
            index
            for index, statement in enumerate(statements)
            if statement.startswith("SELECT character_id FROM sessions")
            and statement.endswith("FOR UPDATE")
        )
        self.assertLess(fight_lock, session_lock)
