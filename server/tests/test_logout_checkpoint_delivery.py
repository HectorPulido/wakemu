"""A closed logout socket cannot block the canonical PostgreSQL checkpoint."""
from copy import deepcopy
import ast
from pathlib import Path
import errno
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import time

from psycopg import OperationalError, InterfaceError
from postgres_case import PostgresCase
import test_publication_recovery_socket_adapter as socket_fixtures
from wakfu_server import fight_store
from wakfu_server.checkpoint_worker import CheckpointWorker, checkpoint_cleanup_barrier
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.performance_profiler import PROFILER
from wakfu_server.position_redis import PositionJournalUnavailable
from wakfu_server.session_cleanup import retry_step


class LogoutCheckpointDeliveryTests(PostgresCase):
    def test_logout_persists_without_draining_closed_owner_and_rejects_stale_writer(
        self,
    ):
        self.store.clock = lambda: 2_000_000_000.0
        owners = []
        for index, name in enumerate(("Logout Owner", "Logout Peer")):
            account = self.store.register(
                "logout-checkpoint-" + str(index), "private-test-password"
            )["id"]
            actor = self.store.create_character(account, name)["id"]
            generation = self.store.begin_session(account)
            self.store.select_character(account, generation, actor)
            owners.append(Session(account, actor, generation, 1134, 0))
        one, two = owners
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(77,'active')"
            )
            for owner in owners:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(77,%s,%s,0,%s)",
                    (owner.character_id, owner.account_id, owner.generation),
                )
        fight = Fight(
            77,
            [
                Actor(
                    one.character_id,
                    0,
                    (0, 0, 0),
                    60,
                    6,
                    3,
                    100,
                    1,
                    one.account_id,
                    True,
                ),
                Actor(-200, 1, (1, 0, 0), 20, 4, 2, 5, 1),
            ],
            {(0, 0, 0), (1, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0), (2, 0, 0)}, 1: {(1, 0, 0)}},
        )
        registry = Registry(
            lambda owner: self.store.current_character_session(
                owner.account_id, owner.generation, owner.character_id
            )
        )
        shared = registry.register(
            fight, one, runtime=RuntimeMessages(fight, clock=lambda: 10.0)
        )
        registry.join(
            two,
            struct.pack(">qB", one.character_id, 0),
            Actor(
                two.character_id, 0, (2, 0, 0), 60, 6, 3, 90, 1, two.account_id, True
            ),
            actor_payload=lambda *args: (b"stats", b"effects"),
            bootstrap_packets=lambda *args: ((12847, b"placement-boundary"),),
        )
        shared.fight.ready(one.account_id)
        shared.fight.ready(two.account_id)

        def end(fight, native):
            return Transition(
                fight,
                native,
                native.end_turn(
                    one.account_id, one.character_id, fight.current.turn_count
                ),
            )

        registry.execute(77, one, one.character_id, end)
        self.assertIsNotNone(shared.runtime.awaiting_ack)
        self.assertTrue(shared.runtime.pending)
        original = (shared.fight, shared.runtime)
        native_ack = shared.runtime.awaiting_ack
        pending = tuple(shared.runtime.pending)
        ack = deepcopy(vars(shared.ack))
        outboxes = {
            account: deepcopy(tuple(queue))
            for account, queue in shared.outboxes.items()
        }
        checkpoints = Checkpoints(self.store)
        worker = CheckpointWorker(checkpoints, workers=1)
        self.addCleanup(worker.close)
        drains = []
        events = []

        def dead_drain():
            drains.append(True)
            raise OSError(errno.EBADF, "Bad file descriptor")

        namespace = dict(
            PROFILER=PROFILER,
            STORE=self.store,
            CHECKPOINTS=checkpoints,
            CHECKPOINT_WRITER=worker,
            COMBAT_SESSIONS=SimpleNamespace(registry=registry),
            fight=shared.fight,
            fight_messages=shared.runtime,
            combat_session=one,
            account_id=one.account_id,
            generation=one.generation,
            character={"id": one.character_id},
            time=time,
            drain_shared_combat=dead_drain,
            record=lambda **row: events.append(row),
            retry_step=retry_step,
            OperationalError=OperationalError,
            InterfaceError=InterfaceError,
            PositionJournalUnavailable=PositionJournalUnavailable,
            redact=lambda value: value,
        )
        initial = dict(
            checkpoint_revision=None,
            checkpoint_id=None,
            checkpoint_terminal=False,
            checkpoint_local_shared=None,
        )
        with patch.object(
            socket_fixtures, "HELPERS", ("checkpoint_fight", "logout_barrier")
        ):
            functions = socket_fixtures.extracted_helpers(namespace, initial)
        # The default live path retains ordered presentation and reproduces
        # the transport failure before it can queue a durable snapshot.
        with self.assertRaises(OSError):
            functions["checkpoint_fight"]()
        self.assertEqual(drains, [True])
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT revision FROM fight_checkpoints WHERE fight_id=77"
                ).fetchone()
            )
        source = (
            Path(socket_fixtures.__file__).resolve().parents[1] / "local_game_server.py"
        )
        session_node = next(
            node
            for node in ast.parse(source.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        cleanup = next(
            node
            for node in ast.walk(session_node)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "checkpoint_cleanup_barrier"
            and node.args
            and isinstance(node.args[0], ast.Lambda)
            and isinstance(node.args[0].body, ast.Call)
            and isinstance(node.args[0].body.func, ast.Name)
            and node.args[0].body.func.id == "logout_barrier"
            and isinstance(node.args[0].body.args[0], ast.Constant)
            and node.args[0].body.args[0].value == "fight_checkpoint"
        )
        cleanup_scope = dict(
            namespace,
            **functions,
            checkpoint_cleanup_barrier=checkpoint_cleanup_barrier,
        )
        with patch.object(
            self.store, "heartbeat", wraps=self.store.heartbeat
        ) as heartbeat:
            eval(compile(ast.Expression(cleanup), str(source), "eval"), cleanup_scope)
            self.assertTrue(worker.flush_fight(77, timeout=5))
            heartbeat.assert_not_called()
        self.assertEqual(drains, [True])
        self.assertEqual(shared.checkpoint_revision, 1)
        self.assertEqual((shared.fight, shared.runtime), original)
        self.assertEqual(shared.runtime.awaiting_ack, native_ack)
        self.assertEqual(tuple(shared.runtime.pending), pending)
        self.assertEqual(vars(shared.ack), ack)
        self.assertEqual(
            {account: tuple(queue) for account, queue in shared.outboxes.items()},
            outboxes,
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT revision,snapshot FROM fight_checkpoints WHERE fight_id=77"
            ).fetchone()
        self.assertEqual(row["revision"], 1)
        self.assertEqual(row["snapshot"]["runtime"]["awaiting_ack"], native_ack)
        self.assertEqual(
            len(
                [
                    event
                    for event in events
                    if event.get("event") == "combat_checkpoint_queued"
                ]
            ),
            1,
        )
        replacement = self.store.begin_session(one.account_id)
        self.store.select_character(one.account_id, replacement, one.character_id)
        self.assertTrue(
            fight_store.takeover_participant(
                self.store,
                one.account_id,
                replacement,
                one.character_id,
                77,
                previous_generation=one.generation,
            )
        )
        shared.fight.actors[one.character_id].hp = 57
        self.assertEqual(
            checkpoints.save_shared(shared, one.account_id, replacement), (2, False)
        )
        with self.assertRaisesRegex(ValueError, "session is stale"):
            checkpoints.save_shared(shared, one.account_id, one.generation)
        with self.assertRaisesRegex(ValueError, "Stale or foreign"):
            checkpoints.save(
                one.account_id,
                replacement,
                shared.fight,
                expected_revision=1,
                runtime=shared.runtime,
            )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT revision,generation,snapshot FROM fight_checkpoints WHERE fight_id=77"
            ).fetchone()
        self.assertEqual((row["revision"], row["generation"]), (2, replacement))
        self.assertEqual(row["snapshot"]["actors"][str(one.character_id)]["hp"], 57)
        self.assertEqual(shared.runtime.awaiting_ack, native_ack)
        self.assertEqual(tuple(shared.runtime.pending), pending)
        self.assertEqual(
            {account: tuple(queue) for account, queue in shared.outboxes.items()},
            outboxes,
        )


if __name__ == "__main__":
    unittest.main()
