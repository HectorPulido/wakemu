"""Actual Registry withdrawal/checkpoint contention and stale-index custody."""
import ast
from copy import deepcopy
import hashlib
from pathlib import Path
import threading
import unittest

from wakfu_server import combat_shared
from wakfu_server.combat_shared import Registry, Session
from test_combat_shared import SharedCombatTests


class LockWaitExpired(RuntimeError):
    pass


class EncounterLockProbe:
    """Real RLock plus an attempt latch and a bounded deadlock watchdog."""

    def __init__(self, watched):
        self.lock = threading.RLock()
        self.watched = watched
        self.attempted = threading.Event()

    def acquire(self, blocking=True, timeout=-1):
        if threading.current_thread().name == self.watched and blocking:
            self.attempted.set()
            # Old lock inversion must terminate the test without orphaned
            # threads. No Registry method or lock acquisition order is mocked.
            if not self.lock.acquire(timeout=1.5):
                raise LockWaitExpired("Registry holder could not acquire encounter")
            return True
        return (
            self.lock.acquire(blocking)
            if timeout == -1
            else self.lock.acquire(blocking, timeout)
        )

    def release(self):
        self.lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *args):
        self.release()


def withdrawn_fixture(registry_type=Registry):
    fixture = SharedCombatTests(
        "test_returned_withdrawn_marker_leader_remains_join_target_during_placement"
    )
    fixture.setUp()
    if registry_type is not Registry:
        fixture.registry = registry_type(lambda session: session in fixture.live)
        fixture.shared = fixture.registry.register(
            fixture.fight,
            fixture.one,
            runtime=None,
            join_context={"leaders": {0: 10, 1: -200}, "world_marker_cells": ((0, 0),)},
        )
    fixture.join()
    fixture.shared.runtime = None
    fixture.receipt = fixture.registry.withdraw_pve(
        fixture.one, persist=lambda fight: {"character": {"id": 10, "hp": 60}}
    )
    return fixture


class SharedLockOrderTests(unittest.TestCase):
    def contend(self, registry_type):
        fixture = withdrawn_fixture(registry_type)
        registry, shared = fixture.registry, fixture.shared
        probe = EncounterLockProbe("withdraw-return")
        shared.lock = probe
        owner_ready = threading.Event()
        observations, errors, persisted, deliveries = [], [], [], []

        def checkpoint_owner():
            try:
                with shared.lock:
                    owner_ready.set()
                    if not probe.attempted.wait(3):
                        raise AssertionError(
                            "Withdrawal never attempted encounter lock"
                        )
                    # Actual World checkpoint callback performs Registry lookup
                    # and dispatch while its accepted-action owner holds Fight.
                    observations.append(registry.lookup(99))
                    registry.dispatch_connected(
                        99,
                        lambda session, batches: deliveries.append((session, batches)),
                    )
            except BaseException as error:
                errors.append(error)

        def returning_owner():
            try:
                if not owner_ready.wait(3):
                    raise AssertionError("Checkpoint owner did not acquire Fight")
                registry.return_withdrawn_pve(
                    99,
                    fixture.one,
                    persist=lambda: persisted.append("durable-return")
                    or {"returned": True},
                )
            except BaseException as error:
                errors.append(error)

        threads = [
            threading.Thread(target=checkpoint_owner, name="checkpoint-owner"),
            threading.Thread(target=returning_owner, name="withdraw-return"),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(observations, [shared])
        return fixture, errors, persisted, deliveries

    def test_real_withdrawal_checkpoint_contention_and_recovery_revalidate_identity(
        self,
    ):
        before = Path(".runtime/shared-lock-order/before.py")
        if before.is_file():
            payload = before.read_bytes()
            self.assertEqual(
                hashlib.sha256(payload).hexdigest(),
                "d63b074000f9aa7e8f2f80a669c58f5333ab6cca9ff7fc5cffcd45ff555b4ae5",
            )
            old = next(
                node
                for node in ast.parse(payload).body
                if isinstance(node, ast.ClassDef) and node.name == "Registry"
            )
            namespace = dict(vars(combat_shared))
            exec(
                compile(
                    ast.Module(body=[deepcopy(old)], type_ignores=[]),
                    "actual-running-Registry-before",
                    "exec",
                ),
                namespace,
            )
            _, errors, persisted, _ = self.contend(namespace["Registry"])
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], LockWaitExpired)
            self.assertEqual(persisted, [])

        fixture, errors, persisted, deliveries = self.contend(Registry)
        self.assertEqual(errors, [])
        self.assertEqual(persisted, ["durable-return"])
        self.assertTrue(deliveries)
        self.assertNotIn(10, fixture.registry.by_actor)
        self.assertNotIn(10, fixture.registry.by_character)
        self.assertEqual(fixture.registry.by_character[20], 99)
        self.assertEqual(fixture.shared.returned, {1})

        for changed in ("fight_reference", "character_index"):
            with self.subTest(changed=changed):
                case = withdrawn_fixture()
                registry, shared = case.registry, case.shared
                probe = EncounterLockProbe("withdraw-recover")
                shared.lock = probe
                replacement = Session(1, 10, "replacement", 1134, 0)
                case.live.remove(case.one)
                case.live.add(replacement)
                results, errors, persisted = [], [], []

                def recover():
                    try:
                        results.append(
                            registry.recover_withdrawn_pve(
                                replacement,
                                persist=lambda *args: persisted.append(args),
                            )
                        )
                    except BaseException as error:
                        errors.append(error)

                with shared.lock:
                    thread = threading.Thread(target=recover, name="withdraw-recover")
                    thread.start()
                    self.assertTrue(probe.attempted.wait(3))
                    # Declared concurrent retirement/rebinding of the indexes:
                    # use another genuine registered SharedFight as authority.
                    other = withdrawn_fixture()
                    with registry.lock:
                        if changed == "fight_reference":
                            registry.fights[99] = other.shared
                        else:
                            registry.by_character[10] = 100
                    expected_index = dict(registry.by_character)
                thread.join(4)
                self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])
                self.assertEqual(results, [None])
                self.assertEqual(persisted, [])
                self.assertEqual(registry.by_character, expected_index)
                self.assertEqual(shared.returned, set())
                self.assertEqual(shared.withdrawals[1]["session"], case.one)

        case = withdrawn_fixture()
        replacement = Session(1, 10, "replacement", 1134, 0)
        case.live.add(replacement)
        calls = []
        with self.assertRaisesRegex(ValueError, "still active"):
            case.registry.recover_withdrawn_pve(
                replacement, persist=lambda *args: calls.append(args)
            )
        self.assertEqual(calls, [])
        case.live.remove(case.one)
        self.assertEqual(
            case.registry.recover_withdrawn_pve(
                replacement, persist=lambda *args: calls.append(args) or {"hp": 60}
            ),
            {"hp": 60},
        )
        self.assertEqual(calls, [(99, case.one.generation)])
        self.assertEqual(case.shared.participants[1], replacement)
        self.assertEqual(case.registry.by_character[20], 99)
