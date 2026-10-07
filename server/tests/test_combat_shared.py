import ast
import concurrent.futures
import struct, threading, unittest
from pathlib import Path
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_multiplayer_wire import (
    decode_added,
    decode_join,
    external,
    decode_external,
)


class SharedCombatTests(unittest.TestCase):
    def setUp(self):
        self.one = Session(1, 10, "first", 1134, 0)
        self.two = Session(2, 20, "second", 1134, 0)
        self.live = {self.one, self.two}
        self.registry = Registry(lambda session: session in self.live)
        self.fight = Fight(
            99,
            [
                Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(-200, 1, (3, 0, 0), 20, 4, 2, 1, 1),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0)}},
        )
        self.shared = self.registry.register(
            self.fight, self.one, runtime={"native": "own"}, group_lease=("own-group",)
        )

    def join(self, session=None):
        session = session or self.two
        actor = Actor(
            session.character_id,
            0,
            (0, 0, 0),
            60,
            6,
            3,
            90,
            1,
            session.account_id,
            True,
        )
        return self.registry.join(
            session,
            struct.pack(">qB", 10, 0),
            actor,
            actor_payload=lambda *args: (b"ownstats", b"owneffects"),
            bootstrap_packets=lambda f, s, o: [(12847, b"owned-bootstrap")],
        )

    def test_delayed_owner_checkpoint_read_cannot_regress_shared_revision(self):
        # Two sockets can read SQL before either reacquires the shared lock.
        # A stale read must not overwrite the newer fight-wide revision.
        self.assertEqual(self.shared.seed_checkpoint_revision(4), 4)
        self.assertEqual(self.shared.seed_checkpoint_revision(3), 4)
        self.assertEqual(self.shared.seed_checkpoint_revision(None), 4)
        with self.assertRaisesRegex(ValueError, "revision"):
            self.shared.seed_checkpoint_revision(0)

    def test_login_bootstrap_invokes_settled_shared_takeover(self):
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        resume = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef)
            and node.name == "resume_settled_shared_combat"
        )

        class ScopeCalls(ast.NodeVisitor):
            def __init__(self, target, name):
                self.target = target
                self.name = name
                self.calls = []

            def visit_FunctionDef(self, node):
                if node is self.target:
                    for statement in node.body:
                        self.visit(statement)

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                if isinstance(node.func, ast.Name) and node.func.id == self.name:
                    self.calls.append(node)
                self.generic_visit(node)

        def calls_in_scope(target, name):
            visitor = ScopeCalls(target, name)
            visitor.visit(target)
            return visitor.calls

        login_calls = calls_in_scope(session, "resume_settled_shared_combat")
        adopt = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef) and node.name == "adopt_shared_duel"
        )
        duel_takeover_calls = calls_in_scope(adopt, "resume_settled_shared_combat")
        self.assertEqual(len(login_calls), 1)
        self.assertEqual(len(duel_takeover_calls), 1)
        self.assertGreater(login_calls[0].lineno, resume.lineno)
        join_calls = calls_in_scope(session, "join_world")
        static_marks = calls_in_scope(session, "mark_static_sync_pending")
        self.assertTrue(
            any(call.lineno < login_calls[0].lineno for call in join_calls),
            "login settlement replay must follow a world join",
        )
        self.assertTrue(
            any(call.lineno > login_calls[0].lineno for call in static_marks),
            "login settlement replay must precede static snapshot arming",
        )
        guarded_resume = [
            node
            for node in ast.walk(adopt)
            if isinstance(node, ast.If)
            and any(
                isinstance(test_node, ast.Attribute)
                and test_node.attr == "settlement_ready"
                for test_node in ast.walk(node.test)
            )
            and any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "resume_settled_shared_combat"
                for statement in node.body
                for call in ast.walk(statement)
            )
        ]
        self.assertEqual(len(guarded_resume), 1)
        self.assertTrue(
            any(
                isinstance(node, ast.Attribute) and node.attr == "settlement_ready"
                for node in ast.walk(guarded_resume[0].test)
            )
        )
        resume_calls = {
            node.func.attr
            for node in ast.walk(resume)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertIn("takeover_settled", resume_calls)
        self.assertTrue(
            any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "drain_shared_combat"
                for node in ast.walk(resume)
            )
        )

    def test_duel_socket_adopts_before_first_readiness_dispatch(self):
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        opcode_assignment = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.Assign)
            and any(
                any(
                    isinstance(child, ast.Name) and child.id == "opcode"
                    for child in ast.walk(target)
                )
                for target in node.targets
            )
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Attribute)
            and node.value.func.attr == "unpack"
        )
        readiness_route = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and any(
                isinstance(candidate, ast.Compare)
                and isinstance(candidate.left, ast.Name)
                and candidate.left.id == "opcode"
                and any(
                    isinstance(comparator, ast.Constant) and comparator.value == 12523
                    for comparator in candidate.comparators
                )
                for candidate in ast.walk(node.test)
            )
        )
        adoption = [
            node
            for node in ast.walk(session)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "adopt_shared_duel"
            and node.lineno > opcode_assignment.lineno
            and node.lineno < readiness_route.lineno
        ]
        self.assertTrue(
            adoption,
            "a peer may send 12523 as soon as it receives placement, before its idle callback adopts the shared duel",
        )

    def test_socket_drainer_pushes_other_owners_in_atomic_batches(self):
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        drain = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef) and node.name == "drain_shared_combat"
        )
        attrs = {
            node.func.attr
            for node in ast.walk(drain)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        self.assertIn("dispatch_connected", attrs)
        self.assertIn("send_batch_to", attrs)
        names = {
            node.func.id
            for node in ast.walk(drain)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertIn("send_batch", names)

    def test_shared_readiness_drives_an_initial_nonplayer_turn(self):
        source_path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        session = next(
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "session"
        )
        apply_readiness = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.FunctionDef) and node.name == "apply_readiness"
        )
        calls = [
            node
            for node in ast.walk(apply_readiness)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "pass_test_monster_turn"
        ]
        self.assertGreaterEqual(
            len(calls),
            2,
            "both shared and single-owner readiness must drive an initial NPC turn",
        )

    def test_two_sessions_share_fsm_and_ordered_native_outboxes(self):
        self.join()
        f = self.shared.fight
        self.assertEqual(f.actors[20].position, (1, 0, 0))
        first = self.registry.drain(99, self.one)
        second = self.registry.drain(99, self.two)
        self.assertEqual([p[0] for p in first[0].packets], [13091, 13026])
        self.assertEqual(decode_added(first[0].packets[0][1])["actor_id"], 20)
        self.assertEqual([p[0] for p in second[0].packets], [12847])
        self.assertEqual(first[0].sequence, second[0].sequence)
        self.registry.ready(99, self.one, True, lambda f, r: [])
        self.assertEqual(self.shared.fight.phase, "placement")
        self.registry.ready(99, self.two, True, lambda f, r: [])
        self.assertEqual(self.shared.fight.phase, "active")
        self.assertEqual(self.shared.fight.current.id, 10)
        with self.assertRaises(ValueError):
            self.registry.execute(99, self.two, 10, lambda f, r: [])
        with self.assertRaises(ValueError):
            self.registry.execute(99, self.two, 20, lambda f, r: [])
        seq = self.shared.sequence
        self.registry.execute(
            99,
            self.one,
            10,
            lambda f, r: (f.end_turn(1, 10, f.turn_id), [])[1],
            expected_sequence=seq,
        )
        with self.assertRaises(ValueError):
            self.registry.execute(
                99, self.one, 10, lambda f, r: [], expected_sequence=seq
            )

    def test_dispatch_pushes_ordered_batches_to_idle_connected_peer(self):
        self.join()
        self.registry.drain(99, self.one)
        self.registry.drain(99, self.two)
        self.registry.publish(99, self.one, ((13482, b"turn-start"),))
        self.registry.publish(99, self.one, ((12873, b"actor-state"),))
        delivered = []

        def push(owner, batches):
            # The callback represents socket I/O: neither registry lock may
            # be held, including when pushing to a peer that sent no request.
            self.assertTrue(self.registry.lock.acquire(blocking=False))
            self.registry.lock.release()
            self.assertTrue(self.shared.lock.acquire(blocking=False))
            self.shared.lock.release()
            delivered.append(
                (
                    owner.account_id,
                    tuple(batch.sequence for batch in batches),
                    tuple(packet for batch in batches for packet in batch.packets),
                )
            )

        self.registry.dispatch_connected(99, push)
        self.assertEqual([owner for owner, _, _ in delivered], [1, 2])
        self.assertEqual(delivered[0][1], delivered[1][1])
        self.assertEqual(
            delivered[1][2],
            ((13482, b"turn-start"), (12873, b"actor-state")),
        )
        self.assertEqual(self.registry.drain(99, self.two), [])

    def test_broken_socket_does_not_block_other_roster_pushes(self):
        self.join()
        self.registry.drain(99, self.one)
        self.registry.drain(99, self.two)
        self.registry.publish(99, self.one, ((12755, b"owner-result"),))
        delivered = []

        def push(owner, batches):
            if owner == self.one:
                raise BrokenPipeError("owner socket closed")
            delivered.append((owner, batches))

        with self.assertRaises(BrokenPipeError):
            self.registry.dispatch_connected(99, push)
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0][0], self.two)
        self.assertEqual(delivered[0][1][0].packets, ((12755, b"owner-result"),))

    def test_concurrent_drainers_preserve_batch_sequence_without_registry_lock_io(self):
        self.join()
        self.registry.drain(99, self.one)
        self.registry.drain(99, self.two)
        self.registry.publish(99, self.one, ((13482, b"first"),))
        entered = threading.Event()
        release = threading.Event()
        observed = []

        def slow_push(owner, batches):
            if owner == self.one:
                entered.set()
                self.assertTrue(release.wait(2))
            observed.append((owner.account_id, tuple(b.sequence for b in batches)))

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(self.registry.dispatch_connected, 99, slow_push)
            self.assertTrue(entered.wait(2))
            # The previous delivery has released the fight lock, so a new FSM
            # operation can commit while socket I/O for the prior batch waits.
            self.registry.publish(99, self.one, ((13482, b"second"),))
            second = pool.submit(self.registry.dispatch_connected, 99, slow_push)
            self.assertFalse(second.done())
            release.set()
            first.result(2)
            second.result(2)
        owner_one = [entry[1] for entry in observed if entry[0] == self.one.account_id]
        self.assertEqual(len(owner_one), 2)
        self.assertEqual(owner_one[1][0], owner_one[0][0] + 1)

    def test_takeover_and_old_disconnect_do_not_remove_new_owner(self):
        self.join()
        self.live.remove(self.one)
        new = Session(1, 10, "replacement", 1134, 0)
        self.live.add(new)
        self.registry.takeover(
            99, new, lambda f, s, o: [(12847, b"new-owned-bootstrap")]
        )
        self.assertEqual(self.registry.disconnect(self.one), [])
        self.assertIn(1, self.shared.connected)
        with self.assertRaises(ValueError):
            self.registry.drain(99, self.one)
        self.assertEqual(
            self.registry.drain(99, new)[0].packets, ((12847, b"new-owned-bootstrap"),)
        )
        self.assertEqual(self.registry.disconnect(new), [99])
        self.assertIn(2, self.shared.connected)
        self.assertEqual(self.shared.group_lease, ("own-group",))

    def test_last_pve_disconnect_claims_abort_then_retires_all_actor_indexes(self):
        self.assertEqual(self.registry.disconnect(self.one), [99])
        self.assertTrue(self.shared.disconnect_abort_pending)
        replacement = Session(1, 10, "replacement", 1134, 0)
        self.live.add(replacement)
        with self.assertRaisesRegex(ValueError, "closed"):
            self.registry.takeover(
                99, replacement, lambda *args: [(12847, b"bootstrap")]
            )

        self.assertTrue(self.registry.retire_disconnected_pve(99, self.one))
        self.assertNotIn(99, self.registry.fights)
        self.assertNotIn(10, self.registry.by_character)
        self.assertNotIn(10, self.registry.by_actor)
        self.assertNotIn(-200, self.registry.by_actor)

    def test_disconnect_of_one_owner_does_not_retire_shared_pve_group(self):
        self.join()
        self.assertEqual(self.registry.disconnect(self.one), [99])
        self.assertFalse(self.shared.disconnect_abort_pending)
        self.assertFalse(self.registry.retire_disconnected_pve(99, self.one))
        self.assertIn(99, self.registry.fights)
        self.assertEqual(self.registry.disconnect(self.two), [99])
        self.assertTrue(self.shared.disconnect_abort_pending)
        self.assertTrue(self.registry.retire_disconnected_pve(99, self.two))
        self.assertNotIn(99, self.registry.fights)
        self.assertFalse(self.registry.by_character)

    def test_failed_last_owner_abort_can_be_retried_without_reusing_old_actor(self):
        self.registry.disconnect(self.one)
        self.assertTrue(self.shared.disconnect_abort_pending)
        self.assertTrue(self.registry.clear_disconnect_abort(99))
        replacement = Session(1, 10, "replacement", 1134, 0)
        self.live.discard(self.one)
        self.live.add(replacement)
        self.registry.takeover(99, replacement, lambda *args: [(12847, b"recovery")])
        self.assertEqual(self.shared.participants[1], replacement)
        self.assertIn(99, self.registry.fights)

    def test_single_owner_shared_abandon_registry_retires_only_after_ack(self):
        from types import SimpleNamespace

        self.shared.runtime = SimpleNamespace(
            abandon_owner=(self.one.account_id, self.one.character_id),
            abandon_returned=False,
        )
        self.fight.phase = "finished"
        self.fight.winner = None
        self.assertFalse(self.registry.retire_abandoned_single_owner(99, self.one))
        self.shared.runtime.abandon_returned = True
        self.assertTrue(self.registry.retire_abandoned_single_owner(99, self.one))
        self.assertNotIn(99, self.registry.fights)
        self.assertNotIn(10, self.registry.by_character)

    def test_disconnected_single_owner_abandon_retires_without_native_ack(self):
        from types import SimpleNamespace

        self.shared.runtime = SimpleNamespace(
            abandon_owner=(self.one.account_id, self.one.character_id),
            abandon_returned=False,
        )
        self.fight.phase = "finished"
        self.fight.winner = None
        self.registry.disconnect(self.one)
        self.assertTrue(self.registry.retire_disconnected_abandon(99, self.one))
        self.assertNotIn(99, self.registry.fights)

    def test_concurrent_last_free_cell_reserves_once(self):
        three = Session(3, 30, "third", 1134, 0)
        self.live.add(three)
        results = []

        def attempt(session):
            try:
                self.join(session)
                results.append(True)
            except ValueError:
                results.append(False)

        threads = [
            threading.Thread(target=attempt, args=(s,)) for s in (self.two, three)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(len(self.shared.fight.actors), 3)

    def test_serializer_failure_does_not_mutate_membership_or_placement(self):
        def fail(*args):
            raise ValueError("Invalid own codec")

        with self.assertRaises(ValueError):
            self.registry.join(
                self.two,
                struct.pack(">qB", 10, 0),
                Actor(20, 0, (0, 0, 0), 60, 6, 3, 90, 1, 2, True),
                actor_payload=fail,
                bootstrap_packets=lambda *args: [],
            )
        self.assertEqual(set(self.shared.fight.actors), {10, -200})
        self.assertNotIn(20, self.registry.by_character)

    def test_finish_retry_settles_all_owners_once(self):
        self.join()
        self.shared.fight.phase = "finished"
        seen = []

        def settle(shared):
            seen.append(tuple(shared.participants))

        self.assertTrue(self.registry.remove_finished(99, settle))
        self.assertFalse(self.registry.remove_finished(99, settle))
        self.assertEqual(seen, [(1, 2)])

    def test_foreign_map_and_native_join_flag_rejected(self):
        outsider = Session(3, 30, "outside", 1134, 5)
        self.live.add(outsider)
        with self.assertRaises(ValueError):
            self.join(outsider)
        with self.assertRaises(ValueError):
            decode_join(struct.pack(">qB", 10, 2))

    def test_external_codec_preserves_all_explicit_native_fields(self):
        value = dict(
            fight_id=99,
            kind=2,
            myo=1134,
            myp=123,
            jqi=6,
            myu=1000,
            myr=[10, -200],
            teams=[(10, 0), (-200, 1)],
            phase_code=0,
            flags=[False, False, False, False],
            mys=[(2, 3)],
            topology=b"own-native-topology",
        )
        opcode, body = external(value)
        self.assertEqual(opcode, 13753)
        self.assertEqual(decode_external(body), value)

    def test_failed_action_rolls_back_fsm_runtime_and_does_not_broadcast(self):
        self.registry.ready(99, self.one, True, lambda f, r: [])
        before = self.shared.sequence

        def invalid(fight, runtime):
            runtime["native"] = "corrupted"
            fight.current.hp = 1
            raise ValueError("Rejected native action")

        with self.assertRaises(ValueError):
            self.registry.execute(99, self.one, 10, invalid)
        self.assertEqual(self.shared.runtime, {"native": "own"})
        self.assertEqual(self.shared.fight.current.hp, 60)
        self.assertEqual(self.shared.sequence, before)

    def test_group_lease_survives_starter_socket_disconnect_until_settlement(self):
        self.join()
        self.registry.disconnect(self.one)
        self.assertTrue(self.registry.lease_active(("own-group",)))
        self.shared.fight.phase = "finished"
        self.registry.remove_finished(99, lambda shared: None)
        self.assertFalse(self.registry.lease_active(("own-group",)))

    def test_duel_registry_rows_have_no_group_lease_for_recovery_scans(self):
        first = Session(3, 30, "third", 1134, 0)
        second = Session(4, 40, "fourth", 1134, 0)
        self.live.update((first, second))
        duel = Fight(
            100,
            [
                Actor(30, 0, (0, 0, 0), 60, 6, 3, 100, 1, 3, True),
                Actor(40, 1, (3, 0, 0), 60, 6, 3, 90, 1, 4, True),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0)}, 1: {(3, 0, 0)}},
        )
        shared = self.registry.register_duel(
            duel,
            (first, second),
            initial_packets={3: (), 4: ()},
        )
        self.assertIsNone(shared.group_lease)
        self.assertTrue(self.registry.lease_active(("own-group",)))
        self.assertFalse(self.registry.lease_generation_active("first"))

    def test_shared_finish_queues_private_owner_batches_until_all_return(self):
        self.join()
        self.shared.fight.phase = "finished"
        self.shared.fight.winner = 0
        batches = {
            self.one.account_id: ((12755, b"left-report"),),
            self.two.account_id: ((12755, b"right-report"),),
        }
        self.assertTrue(
            self.registry.settle_finished(
                self.fight.id, self.one, lambda shared: batches
            )
        )
        self.assertFalse(
            self.registry.settle_finished(
                self.fight.id, self.one, lambda shared: self.fail("settled twice")
            )
        )
        left_batches = self.registry.drain(self.fight.id, self.one)
        right_batches = self.registry.drain(self.fight.id, self.two)
        self.assertEqual(left_batches[-1].packets, batches[self.one.account_id])
        self.assertEqual(right_batches[-1].packets, batches[self.two.account_id])
        self.assertFalse(self.registry.mark_returned(self.fight.id, self.one))
        self.assertFalse(self.registry.mark_returned(self.fight.id, self.one))
        self.assertTrue(self.registry.mark_returned(self.fight.id, self.two))
        with self.assertRaisesRegex(ValueError, "Unknown shared fight"):
            self.registry.lookup(self.fight.id)

    def test_settlement_callback_does_not_hold_registry_lock(self):
        self.join()
        self.shared.fight.phase = "finished"
        self.shared.fight.winner = 0
        entered = threading.Event()
        release = threading.Event()
        errors = []

        def prepare(shared):
            entered.set()
            if not release.wait(2):
                raise AssertionError("settlement callback timed out")
            return {
                self.one.account_id: ((12755, b"left"),),
                self.two.account_id: ((12755, b"right"),),
            }

        def settle():
            try:
                self.registry.settle_finished(self.fight.id, self.one, prepare)
            except Exception as error:  # surfaced on the test thread below
                errors.append(error)

        worker = threading.Thread(target=settle)
        worker.start()
        self.assertTrue(entered.wait(1))
        lookup_done = threading.Event()

        def lookup():
            self.assertIs(self.registry.lookup(self.fight.id), self.shared)
            lookup_done.set()

        disconnect = threading.Thread(target=lambda: self.registry.disconnect(self.two))
        disconnection_lookup = threading.Thread(target=lookup)
        disconnect.start()
        disconnection_lookup.start()
        try:
            # A disconnected peer may wait on this fight lock. That wait must
            # not retain the registry-wide lock and stall unrelated lookups.
            self.assertTrue(lookup_done.wait(0.5))
        finally:
            release.set()
        worker.join(2)
        disconnect.join(2)
        disconnection_lookup.join(2)
        self.assertFalse(worker.is_alive())
        self.assertFalse(disconnect.is_alive())
        self.assertFalse(disconnection_lookup.is_alive())
        self.assertEqual(errors, [])

    def test_settlement_rejects_unserializable_opcode_before_queueing(self):
        self.join()
        self.registry.drain(self.fight.id, self.one)
        self.registry.drain(self.fight.id, self.two)
        self.shared.fight.phase = "finished"
        self.shared.fight.winner = 0
        with self.assertRaisesRegex(ValueError, "native opcode/body"):
            self.registry.settle_finished(
                self.fight.id,
                self.one,
                lambda shared: {
                    self.one.account_id: ((0x10000, b"invalid"),),
                    self.two.account_id: ((12755, b"right"),),
                },
            )
        self.assertFalse(self.shared.settlement_ready)
        self.assertEqual(self.registry.drain(self.fight.id, self.one), [])
        self.assertEqual(self.registry.drain(self.fight.id, self.two), [])

    def test_settled_owner_takeover_replays_cached_private_result(self):
        self.join()
        self.shared.fight.phase = "finished"
        self.shared.fight.winner = 0
        self.registry.settle_finished(
            self.fight.id,
            self.one,
            lambda shared: {
                self.one.account_id: ((12755, b"left"),),
                self.two.account_id: ((12755, b"right"),),
            },
        )
        self.live.remove(self.two)
        self.registry.disconnect(self.two)
        replacement = Session(2, 20, "second-reconnect", 1134, 0)
        self.live.add(replacement)
        self.registry.takeover(
            self.fight.id,
            replacement,
            lambda *args: self.fail("settled takeover must replay its saved result"),
        )
        replay = self.registry.drain(self.fight.id, replacement)
        self.assertEqual([item.packets for item in replay], [((12755, b"right"),)])
        self.assertFalse(self.registry.mark_returned(self.fight.id, replacement))
        self.assertTrue(self.registry.mark_returned(self.fight.id, self.one))

    def test_takeover_persistence_failure_keeps_previous_registry_owner(self):
        self.live.remove(self.one)
        replacement = Session(1, 10, "replacement", 1134, 0)
        self.live.add(replacement)
        with self.assertRaisesRegex(ValueError, "injected persistence failure"):
            self.registry.takeover(
                self.fight.id,
                replacement,
                lambda *args: ((12847, b"bootstrap"),),
                persist_takeover=lambda previous: (_ for _ in ()).throw(
                    ValueError("injected persistence failure")
                ),
            )
        self.assertIs(self.registry.lookup_character(10), self.shared)
        self.assertEqual(self.shared.participants[1], self.one)
        self.assertIn(1, self.shared.connected)

    def test_native_ack_waits_for_both_sessions_not_only_current_owner(self):
        self.join()
        self.registry.drain(99, self.one)
        self.registry.drain(99, self.two)
        self.registry.arm_ack(99, 7)
        calls = []

        def release(fight, runtime, body):
            calls.append(body)
            return [(13482, b"next-turn")]

        self.assertFalse(
            self.registry.acknowledge(99, self.one, struct.pack(">i", 7), release)
        )
        self.assertFalse(
            self.registry.acknowledge(99, self.one, struct.pack(">i", 7), release)
        )
        self.assertEqual(calls, [])
        self.assertEqual(self.registry.drain(99, self.two), [])
        with self.assertRaises(ValueError):
            self.registry.acknowledge(99, self.two, struct.pack(">i", 6), release)
        self.assertTrue(
            self.registry.acknowledge(99, self.two, struct.pack(">i", 7), release)
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            self.registry.drain(99, self.one)[0].packets, ((13482, b"next-turn"),)
        )

    def test_disconnect_does_not_synthesize_missing_turn_ack(self):
        self.join()
        self.registry.arm_ack(99, 7)
        self.registry.disconnect(self.two)
        self.assertFalse(
            self.registry.acknowledge(
                99, self.one, struct.pack(">i", 7), lambda *args: []
            )
        )
        self.assertEqual(self.shared.ack.expected, {1: "first", 2: "second"})
        self.assertFalse(self.shared.ack.complete)

    def test_runtime_fsm_reference_remains_same_authority_after_dispatch(self):
        self.shared.runtime = {"fight": self.shared.fight}
        self.registry.ready(99, self.one, True, lambda f, r: [])
        self.assertIs(self.shared.runtime["fight"], self.shared.fight)

        def action(f, r):
            self.assertIs(r["fight"], f)
            f.spend(1, 10, ap=1)
            return []

        self.registry.execute(99, self.one, 10, action)
        self.assertEqual(self.shared.runtime["fight"].current.ap, 5)

    def test_transition_result_atomically_replaces_shared_fight_and_runtime(self):
        self.join()
        self.registry.ready(99, self.one, True, lambda f, r: [])
        self.registry.ready(99, self.two, True, lambda f, r: [])
        self.registry.drain(99, self.one)
        self.registry.drain(99, self.two)
        replacement = self.shared.fight
        runtime = {"fight": replacement, "revision": 2}

        def operation(candidate, old_runtime):
            candidate.spend(1, 10, ap=1)
            return Transition(replacement, runtime, ((12502, b"same-state"),))

        self.registry.execute(99, self.one, 10, operation)
        self.assertIs(self.shared.fight, replacement)
        self.assertIs(self.shared.runtime, runtime)
        self.assertIs(self.shared.runtime["fight"], self.shared.fight)
        self.assertEqual(self.shared.fight.actors[10].ap, 6)
        self.assertEqual(
            self.registry.drain(99, self.two)[0].packets,
            ((12502, b"same-state"),),
        )

    def test_duel_turn_expiry_is_one_shared_transition_for_both_owners(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        first = Session(1, 30, "first-duel", 1134, 0)
        second = Session(2, 40, "second-duel", 1134, 0)
        self.live.update((first, second))
        duel = Fight(
            101,
            [
                Actor(30, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(40, 1, (3, 0, 0), 60, 6, 3, 90, 1, 2, True),
            ],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0)}, 1: {(3, 0, 0)}},
        )
        shared = self.registry.register_duel(
            duel,
            (first, second),
            initial_packets={1: (), 2: ()},
        )
        self.registry.ready(101, first, True, lambda _fight, _runtime: ())
        self.registry.ready(101, second, True, lambda _fight, _runtime: ())
        runtime = RuntimeMessages(shared.fight, turn_duration_ms=100, clock=lambda: 0)
        runtime.turn_started()
        runtime.turn_deadline = -1
        runtime.deadline_turn = shared.fight.turn_id
        shared.runtime = runtime
        self.registry.drain(101, first)
        self.registry.drain(101, second)

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(
                    self.registry.expire_current_turn,
                    101,
                    participant,
                    now_ms=1,
                )
                for participant in (first, second)
            ]
            results = [future.result(timeout=5) for future in futures]

        self.assertEqual(sum(expired for expired, _error in results), 1)
        self.assertEqual(shared.fight.turn_id, 2)
        self.assertEqual(shared.runtime.awaiting_ack, 1)
        self.assertEqual(shared.ack.turn, 1)
        left = self.registry.drain(101, first)
        right = self.registry.drain(101, second)
        self.assertEqual(len(left), 1)
        self.assertEqual(len(right), 1)
        self.assertEqual(left[0].sequence, right[0].sequence)
        self.assertEqual(left[0].packets, right[0].packets)

        canonical_fight, canonical_runtime = shared.fight, shared.runtime
        sequence = shared.sequence
        # A second idle poll sees the outstanding ACK barrier and cannot end
        # the next turn or replace the canonical Fight/runtime references.
        self.assertEqual(
            self.registry.expire_current_turn(101, first, now_ms=2),
            (False, None),
        )
        self.assertIs(shared.fight, canonical_fight)
        self.assertIs(shared.runtime, canonical_runtime)
        self.assertEqual((shared.fight.turn_id, shared.sequence), (2, sequence))

        release = lambda fight, current_runtime, body: current_runtime.acknowledge_turn(
            body
        )
        self.assertFalse(
            self.registry.acknowledge(101, first, struct.pack(">i", 1), release)
        )
        self.assertTrue(
            self.registry.acknowledge(101, second, struct.pack(">i", 1), release)
        )
        self.assertIsNone(shared.ack.turn)
        self.assertIs(shared.runtime.fight, shared.fight)
