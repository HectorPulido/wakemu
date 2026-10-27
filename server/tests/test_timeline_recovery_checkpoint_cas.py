"""Timeline recovery keeps the actual durable checkpoint CAS writer fence."""
import ast
from copy import deepcopy
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import Checkpoints


class TimelineRecoveryCheckpointCASTests(PostgresCase):
    def test_real_recovery_checkpoint_across_owners_and_post_commit_publication_failure(
        self,
    ):
        self.store.clock = lambda: 2_000_000_000.0
        owners = []
        for index, name in enumerate(("Recovery Owner", "Recovery Peer")):
            account = self.store.register(f"recovery-cas-{index}", "local-password")[
                "id"
            ]
            character = self.store.create_character(account, name)["id"]
            generation = self.store.begin_session(account)
            self.store.select_character(account, generation, character)
            owners.append(Session(account, character, generation, 1134, 0))
        one, two = owners
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(77,'active')"
            )
            for session in owners:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(77,%s,%s,0,%s)",
                    (session.character_id, session.account_id, session.generation),
                )
        player = Actor(
            one.character_id, 0, (0, 0, 0), 60, 6, 3, 100, 1, one.account_id, True
        )
        npc = Actor(-200, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        fight = Fight(
            77,
            [player, npc],
            {(0, 0, 0), (1, 0, 0), (2, 0, 0)},
            {0: {(0, 0, 0), (2, 0, 0)}, 1: {(1, 0, 0)}},
        )
        runtime = RuntimeMessages(fight, clock=lambda: 10.0)
        registry = Registry(lambda session: session in owners)
        shared = registry.register(fight, one, runtime=runtime)
        peer = Actor(
            two.character_id, 0, (2, 0, 0), 60, 6, 3, 90, 1, two.account_id, True
        )
        registry.join(
            two,
            struct.pack(">qB", one.character_id, 0),
            peer,
            actor_payload=lambda *args: (b"stats", b"effects"),
            bootstrap_packets=lambda *args: [(12847, b"bootstrap")],
        )
        shared.fight.ready(one.account_id)
        shared.fight.ready(two.account_id)
        shared.fight.rift_wave_state = dict(
            instance_id=9, wave=1, turn_budget=40, staged_receipts=[]
        )
        checkpoints = Checkpoints(self.store)
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        callback = next(
            node
            for node in ast.walk(ast.parse(source.read_text()))
            if isinstance(node, ast.FunctionDef)
            and node.name == "checkpoint_accepted_rift"
        )
        namespace = {"STORE": self.store, "CHECKPOINTS": checkpoints}
        exec(
            compile(ast.Module(body=[callback], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        shared.join_context = {
            "rift_accepted_action": namespace["checkpoint_accepted_rift"]
        }
        boundaries = {
            "wakfu_server.rift_dispatch_lifecycle": SimpleNamespace(
                actor_reservation_shortfall=lambda candidate: False,
                replenish_actor_ids=lambda *args: None,
            ),
            "wakfu_server.rift_dispatch_combat": SimpleNamespace(
                finish_accepted_action=lambda candidate, native, packets, **kwargs: Transition(
                    candidate, native, tuple(packets)
                )
            ),
        }

        def durable_revision():
            with self.store.connection() as db:
                return db.execute(
                    "SELECT revision FROM fight_checkpoints WHERE fight_id=77"
                ).fetchone()["revision"]

        def drain():
            return [registry.drain(77, session) for session in owners]

        with patch.dict(sys.modules, boundaries), patch(
            "wakfu_server.rift_runtime.persist_progress", return_value=None
        ):
            self.assertEqual(
                checkpoints.save_shared(shared, one.account_id, one.generation),
                (1, False),
            )
            drain()
            self.assertTrue(
                registry.recover_timeline(77, two, struct.pack(">i", 77), now_ms=20_000)
            )
            self.assertEqual((shared.checkpoint_revision, durable_revision()), (2, 2))
            published = drain()
            self.assertTrue(all(len(batch) == 1 for batch in published))
            self.assertEqual(published[0][0].packets, published[1][0].packets)
            self.assertTrue(
                any(opcode == 12053 for opcode, body in published[0][0].packets)
            )
            self.assertEqual(
                checkpoints.save_shared(shared, two.account_id, two.generation),
                (3, False),
            )
            self.assertTrue(
                registry.recover_timeline(77, one, struct.pack(">i", 77), now_ms=21_000)
            )
            self.assertEqual((shared.checkpoint_revision, durable_revision()), (4, 4))
            self.assertEqual(
                checkpoints.save_shared(shared, one.account_id, one.generation),
                (5, False),
            )
            drain()
            old_fight, old_runtime = shared.fight, shared.runtime
            old_ack = deepcopy(shared.ack)
            old_sequence = shared.sequence
            with patch.object(
                registry,
                "_accepted_ack",
                side_effect=ValueError("fixture publication ACK rejected"),
            ):
                with self.assertRaisesRegex(ValueError, "publication ACK"):
                    registry.recover_timeline(
                        77, two, struct.pack(">i", 77), now_ms=22_000
                    )
            self.assertIs(shared.fight, old_fight)
            self.assertIs(shared.runtime, old_runtime)
            self.assertEqual(vars(shared.ack), vars(old_ack))
            self.assertEqual(shared.sequence, old_sequence)
            self.assertTrue(all(not queue for queue in shared.outboxes.values()))
            self.assertEqual((shared.checkpoint_revision, durable_revision()), (6, 6))
            self.assertFalse(shared.checkpoint_terminal)
            self.assertEqual(
                checkpoints.save_shared(shared, two.account_id, two.generation),
                (7, False),
            )
            self.assertEqual(durable_revision(), 7)
