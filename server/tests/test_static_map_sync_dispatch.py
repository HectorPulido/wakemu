import ast
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace


SERVER_SOURCE = Path(__file__).resolve().parents[1] / "local_game_server.py"


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now


def _session_function(name):
    module = ast.parse(SERVER_SOURCE.read_text())
    session = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )
    return next(
        node
        for node in session.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _run_factory(factory, namespace):
    ast.fix_missing_locations(factory)
    module = ast.Module(body=[factory], type_ignores=[])
    exec(compile(module, str(SERVER_SOURCE), "exec"), namespace)
    return namespace[factory.name]()


class StaticMapSyncDispatchTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.sent = []
        self.records = []
        self.world_static = SimpleNamespace(
            snapshots=lambda map_id: (f"map:{map_id}".encode(),)
        )
        self.store = SimpleNamespace(current_session=lambda account, generation: True)
        self.namespace = {
            "time": self.clock,
            "STORE": self.store,
            "world_static": self.world_static,
            "send": lambda connection, service, opcode, body: self.sent.append(
                (connection, service, opcode, body)
            ),
            "record": lambda **row: self.records.append(row),
        }
        (
            self.mark_pending,
            self.sync,
            self.character,
            self.state,
            self.set_fight,
        ) = self._make_sync()

    def test_every_join_rearms_and_14689_keeps_the_timer(self):
        session = next(
            node
            for node in ast.parse(SERVER_SOURCE.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        joins = [
            node
            for node in ast.walk(session)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "join_world"
        ]
        marks = [
            node
            for node in ast.walk(session)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "mark_static_sync_pending"
        ]
        # Recovery may replay a settled fight between joining and rearming.
        # Check statement order in the same branch, rather than source lines.
        checked_joins = 0
        for parent in ast.walk(session):
            for _, statements in ast.iter_fields(parent):
                if not isinstance(statements, list):
                    continue
                for index, statement in enumerate(statements):
                    if not (
                        isinstance(statement, ast.Expr)
                        and isinstance(statement.value, ast.Call)
                        and isinstance(statement.value.func, ast.Name)
                        and statement.value.func.id == "join_world"
                    ):
                        continue
                    following = statements[index + 1 :]
                    while following:
                        first = following[0]
                        if (
                            isinstance(first, ast.Expr)
                            and isinstance(first.value, ast.Call)
                            and isinstance(first.value.func, ast.Name)
                            and first.value.func.id == "resume_settled_shared_combat"
                        ):
                            following = following[1:]
                            continue
                        if (
                            isinstance(first, ast.Assign)
                            and any(
                                isinstance(target, ast.Name) and target.id == "loaded"
                                for target in first.targets
                            )
                            and isinstance(first.value, ast.Constant)
                            and first.value.value is True
                        ):
                            following = following[1:]
                            continue
                        break
                    self.assertTrue(following)
                    self.assertIsInstance(following[0], ast.Expr)
                    self.assertIsInstance(following[0].value, ast.Call)
                    self.assertIsInstance(following[0].value.func, ast.Name)
                    self.assertEqual(
                        following[0].value.func.id, "mark_static_sync_pending"
                    )
                    checked_joins += 1
        self.assertEqual(checked_joins, len(joins))
        self.assertEqual(len(marks), len(joins))
        request_branch = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and any(
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "opcode"
                and any(
                    isinstance(value, ast.Constant) and value.value == 14689
                    for value in test.comparators
                )
                for test in (
                    node.test.values
                    if isinstance(node.test, ast.BoolOp)
                    else (node.test,)
                )
            )
        )
        sync_call = next(
            node
            for node in ast.walk(request_branch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sync_static_world"
        )
        keywords = {keyword.arg: keyword.value for keyword in sync_call.keywords}
        self.assertIsInstance(keywords.get("force"), ast.Constant)
        self.assertIsNone(keywords.get("validated"))

    def _make_sync(self):
        body = ast.parse(
            """
def build_sync():
    character = {"id": 7, "map_id": 1134, "instance_id": 0}
    account_id = 9
    generation = 17
    loaded = True
    fight = None
    combat_session = None
    connection = object()
    service = "world"
    static_sync_pending = False
    static_sync_attempts = 0
    static_sync_due = 0.0
    world_snapshot_pending = False
    world_snapshot_due = 0.0
    world_snapshot_identity = None
    def state():
        return static_sync_pending, static_sync_attempts, static_sync_due
    def set_fight(value):
        nonlocal fight
        fight = value
    return mark_static_sync_pending, sync_static_world, character, state, set_fight
"""
        ).body[0]
        nested = [
            deepcopy(_session_function("mark_static_sync_pending")),
            deepcopy(_session_function("sync_static_world")),
        ]
        body.body[-1:-1] = nested
        return _run_factory(body, self.namespace)

    def _make_world_sync(self):
        body = ast.parse(
            """
def build_world_sync():
    character = {"id": 7, "map_id": 1134, "instance_id": 0}
    generation = 17
    loaded = True
    fight = None
    combat_session = None
    static_sync_pending = False
    static_sync_attempts = 0
    static_sync_due = 0.0
    world_snapshot_pending = False
    world_snapshot_due = 0.0
    world_snapshot_identity = None
    sent = []
    def send_loaded_world_snapshot():
        sent.append((character["id"], character["map_id"], character["instance_id"]))
    def state():
        return world_snapshot_pending, world_snapshot_due, world_snapshot_identity
    return mark_static_sync_pending, sync_loaded_world_snapshot, character, state, sent
"""
        ).body[0]
        nested = [
            deepcopy(_session_function("mark_static_sync_pending")),
            deepcopy(_session_function("sync_loaded_world_snapshot")),
        ]
        body.body[-1:-1] = nested
        return _run_factory(
            body,
            {"time": self.clock, "record": lambda **row: self.records.append(row)},
        )

    def test_player_world_snapshot_waits_for_ready_or_one_bounded_fallback(self):
        mark, sync, character, state, sent = self._make_world_sync()
        mark()
        self.assertTrue(state()[0])
        self.clock.now = 0.2
        self.assertFalse(sync())
        self.assertEqual(sent, [])
        self.assertTrue(sync(force=True))
        self.assertEqual(sent, [(7, 1134, 0)])
        self.assertFalse(state()[0])
        self.assertFalse(sync(force=True))
        self.assertEqual(len(sent), 1)

        character.update(map_id=527, instance_id=0)
        mark()
        self.clock.now = 0.949
        self.assertFalse(sync())
        self.clock.now = 0.95
        self.assertTrue(sync())
        self.assertEqual(sent[-1], (7, 527, 0))
        self.assertFalse(sync())
        self.assertEqual(len(sent), 2)

    def test_map_change_and_private_bag_do_not_replay_stale_world_snapshot(self):
        mark, sync, character, state, sent = self._make_world_sync()
        mark()
        character.update(map_id=527)
        self.clock.now = 1.0
        self.assertFalse(sync(force=True))
        self.assertEqual(sent, [])
        self.assertFalse(state()[0])

        mark()
        character.update(map_id=9, instance_id=11)
        self.clock.now = 2.0
        self.assertFalse(sync(force=True))
        self.assertEqual(sent, [])
        self.assertFalse(state()[0])

    def test_quiet_session_retries_three_times_after_deadline(self):
        self.mark_pending()
        for tick in (0.0, 0.749):
            self.clock.now = tick
            self.sync()
            self.assertEqual(self.sent, [])
        for expected_count, tick in enumerate((0.75, 1.5, 2.25), 1):
            self.clock.now = tick
            self.sync()
            self.assertEqual(len(self.sent), expected_count)
            self.assertEqual(self.sent[-1][2:], (13984, b"map:1134"))
        self.clock.now = 4.0
        self.sync()
        self.assertEqual(len(self.sent), 3)
        self.assertEqual(self.state()[:2], (False, 3))

    def test_map_change_rearms_sync_for_the_new_map(self):
        self.mark_pending()
        self.clock.now = 0.75
        self.sync()
        self.character["map_id"] = 527
        self.mark_pending()
        self.clock.now = 1.49
        self.sync()
        self.assertEqual(len(self.sent), 1)
        self.clock.now = 1.5
        self.sync()
        self.assertEqual(self.sent[-1][3], b"map:527")

    def test_explicit_request_sends_now_but_keeps_bounded_retry(self):
        self.mark_pending()
        self.sync(force=True)
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self.state()[0])
        self.assertEqual(self.state()[1:], (0, 0.75))
        self.clock.now = 0.75
        self.sync()
        self.assertEqual(len(self.sent), 2)

    def test_early_forced_sends_do_not_consume_or_postpone_timer_slots(self):
        self.mark_pending()
        for tick in (0.1, 0.4):
            self.clock.now = tick
            self.sync(force=True)
            self.assertEqual(self.state(), (True, 0, 0.75))
        self.clock.now = 0.74
        self.sync()
        self.assertEqual(len(self.sent), 2)
        self.clock.now = 0.75
        self.sync()
        self.assertEqual(len(self.sent), 3)
        self.assertEqual(self.state(), (True, 1, 1.5))
        self.clock.now = 1.0
        self.sync(force=True)
        self.assertEqual(self.state(), (True, 1, 1.5))
        self.clock.now = 1.5
        self.sync()
        self.assertEqual(self.state(), (True, 2, 2.25))
        self.clock.now = 2.25
        self.sync()
        self.assertEqual(self.state(), (False, 3, 3.0))

    def test_complete_world_resync_clears_pending_without_using_timer_budget(self):
        self.mark_pending()
        self.clock.now = 0.2
        self.sync(force=True, validated=True)
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.state(), (False, 0, 0.75))
        self.clock.now = 1.0
        self.sync()
        self.assertEqual(len(self.sent), 1)

    def test_validated_action_sends_now_and_keeps_bounded_retry(self):
        self.mark_pending()
        self.sync(force=True)
        self.assertEqual(len(self.sent), 1)
        self.assertTrue(self.state()[0])
        self.assertEqual(self.state()[1:], (0, 0.75))
        self.clock.now = 0.75
        self.sync()
        self.assertEqual(len(self.sent), 2)
        self.assertTrue(self.state()[0])

    def test_only_explicit_world_resynchronization_can_clear_retry(self):
        session = next(
            node
            for node in ast.parse(SERVER_SOURCE.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        sync_calls = [
            node
            for node in ast.walk(session)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "sync_static_world"
        ]
        for call in sync_calls:
            if any(
                keyword.arg == "validated"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in call.keywords
            ):
                self.assertTrue(
                    any(
                        isinstance(parent, ast.FunctionDef)
                        and parent.name == "refresh_owned_world_after_spectating"
                        for parent in ast.walk(session)
                        if call in ast.walk(parent)
                    )
                )
        # A complete world replay after a load transition also validates all
        # static objects. Ordinary movement and interactions cannot do that.
        validated_calls = [
            call
            for call in sync_calls
            if any(
                keyword.arg == "validated"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in call.keywords
            )
        ]
        self.assertEqual(len(validated_calls), 2)
        self.assertEqual(len(sync_calls), 5)

    def test_post_load_replay_is_directed_and_contains_complete_map_domains(self):
        session = next(
            node
            for node in ast.parse(SERVER_SOURCE.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        replay = next(
            node
            for node in session.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "send_loaded_world_snapshot"
        )
        source = ast.unparse(replay)
        self.assertIn("WORLD.resynchronize(generation, connection, character)", source)
        self.assertIn("sync_static_world(force=True, validated=True)", source)
        self.assertIn("PLANTINGS.snapshots", source)
        self.assertIn("COMBAT_GROUPS.available", source)
        self.assertIn("HARVESTS.availability_snapshot", source)
        self.assertIn("EXTERNAL_FIGHT_MARKERS.world_snapshots", source)
        self.assertIn('character.get("map_id") == 9', source)

        ready = next(
            node
            for node in ast.walk(session)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "opcode"
            and any(
                isinstance(item, ast.Constant) and item.value == 14689
                for item in node.test.comparators
            )
        )
        replay_calls = [
            call
            for call in ast.walk(ready)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "sync_loaded_world_snapshot"
        ]
        self.assertEqual(len(replay_calls), 1)

    def test_early_movement_and_partial_interaction_keep_map_retries(self):
        session = next(
            node
            for node in ast.parse(SERVER_SOURCE.read_text()).body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )

        def tests_opcode(expression, target):
            if isinstance(expression, ast.BoolOp):
                return any(tests_opcode(value, target) for value in expression.values)
            if not isinstance(expression, ast.Compare):
                return False
            if (
                not isinstance(expression.left, ast.Name)
                or expression.left.id != "opcode"
            ):
                return False
            for comparator in expression.comparators:
                if isinstance(comparator, ast.Constant) and comparator.value == target:
                    return True
                if isinstance(comparator, (ast.Tuple, ast.List)) and any(
                    isinstance(item, ast.Constant) and item.value == target
                    for item in comparator.elts
                ):
                    return True
            return False

        branches = []
        for node in ast.walk(session):
            if not isinstance(node, ast.If):
                continue
            if tests_opcode(node.test, 13331) or tests_opcode(node.test, 12870):
                branches.append(node)
        movement_calls = {
            call.lineno: call
            for branch in branches
            for call in ast.walk(branch)
            if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "sync_static_world"
        }
        self.assertEqual(len(movement_calls), 2)
        for call in movement_calls.values():
            self.assertIn(
                "force",
                {keyword.arg for keyword in call.keywords},
            )
            self.assertNotIn(
                "validated",
                {keyword.arg for keyword in call.keywords},
            )

    def test_instance_maps_do_not_receive_static_baseline(self):
        self.character["instance_id"] = 3
        self.mark_pending()
        for tick in (0.75, 1.5, 2.25):
            self.clock.now = tick
            self.sync()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.state()[:2], (False, 3))

    def test_replaced_generation_cannot_send_static_state(self):
        self.mark_pending()
        self.store.current_session = lambda account, generation: False
        self.sync(force=True)
        self.assertEqual(self.sent, [])
        self.assertTrue(self.state()[0])

    def test_pending_world_snapshot_waits_until_combat_returns(self):
        self.mark_pending()
        self.set_fight(object())
        self.clock.now = 0.75
        self.sync()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.state()[:2], (True, 0))
        self.set_fight(None)
        self.sync()
        self.assertEqual(len(self.sent), 1)

    def test_invalid_session_generation_does_not_run_idle_sync(self):
        idle = deepcopy(_session_function("idle"))
        factory = ast.parse(
            """
def build_idle():
    account_id = 9
    generation = 17
    last_health_tick = 0
    last_session_renewal = time.monotonic()
    console_session = None
    spectator_session = None
    spectator_fight_id = None
    spectator_terminal_pending = None
    return idle
"""
        ).body[0]
        factory.body.insert(-1, idle)
        calls = []
        namespace = {
            "time": self.clock,
            "STOPPING": SimpleNamespace(is_set=lambda: False),
            "STORE": SimpleNamespace(current_session=lambda account, generation: False),
            "sync_static_world": lambda: calls.append("sent"),
        }
        idle_call = _run_factory(factory, namespace)
        self.assertFalse(idle_call())
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
