"""One final durable Rift state before publication; explicit socket dedup only."""
import ast
from pathlib import Path
from types import SimpleNamespace
import time
import unittest
from unittest.mock import patch

import test_combat_shared as fixtures
from wakfu_server.combat_shared import Transition
from wakfu_server.combat_checkpoint_publication import is_checkpointed_publication


class RiftFinalCheckpointPublicationTests(unittest.TestCase):
    def test_final_writer_selects_smallest_live_owner_without_reading_other_leases(
        self,
    ):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        node = next(
            n
            for n in ast.walk(ast.parse(source.read_text()))
            if isinstance(n, ast.FunctionDef) and n.name == "checkpoint_final_rift"
        )
        reads, saves = [], []
        live = {10, 20, 30, 40}

        def current(account, generation, character):
            reads.append(character)
            return character in live

        def save(account, generation, candidate, **kwargs):
            saves.append(account)
            return kwargs["expected_revision"] + 1

        namespace = dict(
            STORE=SimpleNamespace(current_character_session=current),
            CHECKPOINTS=SimpleNamespace(save=save),
        )
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        shared = SimpleNamespace(
            participants={
                identity: SimpleNamespace(
                    account_id=identity, generation="current", character_id=identity
                )
                for identity in (40, 20, 30, 10)
            },
            checkpoint_revision=4,
        )
        writer = namespace["checkpoint_final_rift"]
        writer(shared, object(), object(), ())
        self.assertEqual((reads, saves), ([10], [10]))
        reads.clear()
        live.remove(10)
        writer(shared, object(), object(), ())
        self.assertEqual(reads, [10, 20])
        self.assertEqual(saves[-1], 20)
        live.clear()
        with self.assertRaisesRegex(ValueError, "current participant lease"):
            writer(shared, object(), object(), ())
        self.assertEqual(len(saves), 2)

    def fixture(self, *, fail=False):
        case = fixtures.SharedCombatTests()
        case.setUp()
        case.fight.rift_wave_state = dict(instance_id=1, wave=1, turn_budget=40)
        case.fight.ready(1)
        case.shared.checkpoint_revision = 4
        writes = []

        def prepare(shared, candidate, runtime, packets):
            candidate.actors[10].hp = 51
            runtime["action"] = 8
            return Transition(candidate, runtime, packets)

        def synchronize(shared, candidate, runtime, packets):
            candidate.actors[10].hp = 52
            runtime["action"] = 9
            return packets

        def persist(shared, candidate, runtime, packets):
            self.assertEqual(shared.fight.actors[10].hp, 60)
            self.assertFalse(shared.outboxes[1])
            writes.append((candidate.actors[10].hp, runtime["action"]))
            if fail:
                raise ValueError("writer unavailable")
            shared.checkpoint_revision += 1

        case.shared.join_context.update(
            rift_accepted_action=prepare, rift_checkpoint_action=persist
        )
        return case, writes, synchronize

    def test_final_writer_sees_post_preparation_mutations_once_before_broadcast(self):
        case, writes, synchronize = self.fixture()
        with patch.object(case.registry, "_synchronize_defeated_current", synchronize):
            case.registry.execute(99, case.one, 10, lambda *_: ((12873, b"state"),))
        self.assertEqual(writes, [(52, 9)])
        self.assertTrue(is_checkpointed_publication(case.shared))
        self.assertEqual(case.shared.checkpoint_revision, 5)
        self.assertEqual(len(case.registry.drain(99, case.one)), 1)

    def test_validation_or_writer_failure_does_not_publish_or_adopt(self):
        for failure in ("validation", "writer"):
            case, writes, synchronize = self.fixture(fail=failure == "writer")
            previous = case.shared.fight, case.shared.runtime
            with patch.object(
                case.registry, "_synchronize_defeated_current", synchronize
            ):
                with patch.object(
                    case.registry,
                    "_accepted_ack",
                    side_effect=ValueError("ACK rejected")
                    if failure == "validation"
                    else None,
                    return_value=case.shared.ack,
                ):
                    with self.assertRaises(ValueError):
                        case.registry.execute(99, case.one, 10, lambda *_: ())
            self.assertEqual((case.shared.fight, case.shared.runtime), previous)
            self.assertEqual(case.shared.checkpoint_revision, 4)
            self.assertFalse(case.shared.outboxes[1])
            self.assertFalse(is_checkpointed_publication(case.shared))
            self.assertEqual(writes, [] if failure == "validation" else [(52, 9)])

    def test_socket_skip_requires_explicit_accepted_call_and_current_receipt(self):
        case, writes, synchronize = self.fixture()
        with patch.object(case.registry, "_synchronize_defeated_current", synchronize):
            case.registry.execute(99, case.one, 10, lambda *_: ())
        calls = []

        def save(*args, **kwargs):
            calls.append((args[2].actors[10].hp, kwargs["runtime"]["action"]))
            return kwargs["expected_revision"] + 1

        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        node = next(
            n
            for n in ast.walk(ast.parse(source.read_text()))
            if isinstance(n, ast.FunctionDef) and n.name == "checkpoint_fight"
        )
        node.decorator_list = []
        # Preserve the actual closure's nonlocal bookkeeping without starting a socket.
        outer = ast.parse(
            "def build():\n    checkpoint_revision = None\n"
            "    checkpoint_id = 99\n    checkpoint_terminal = False\n"
            "    checkpoint_local_shared = None\n"
        ).body[0]
        outer.body.extend((node, ast.Return(ast.Name("checkpoint_fight", ast.Load()))))
        namespace = dict(
            fight=case.shared.fight,
            fight_messages=case.shared.runtime,
            combat_session=case.one,
            account_id=1,
            generation="first",
            time=time,
            COMBAT_SESSIONS=SimpleNamespace(registry=case.registry),
            CHECKPOINT_WRITER=SimpleNamespace(terminal_pending=lambda *_: False),
            CHECKPOINTS=SimpleNamespace(save=save),
            record=lambda **_: None,
            drain_shared_combat=lambda: None,
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=[outer], type_ignores=[])),
                str(source),
                "exec",
            ),
            namespace,
        )
        checkpoint = namespace["build"]()
        checkpoint(accepted_publication=True)
        self.assertEqual(calls, [])
        # Direct mutations of the SAME fight/runtime objects use the ordinary
        # caller. An object-identity cache must not suppress this new state.
        case.shared.fight.actors[10].hp = 49
        case.shared.runtime["action"] = 10
        checkpoint()
        self.assertEqual(calls, [(49, 10)])
        self.assertFalse(is_checkpointed_publication(case.shared))
        checkpoint(accepted_publication=True)
        self.assertEqual(calls, [(49, 10), (49, 10)])
