"""Exercise the session-owned auto-transition handoff without loading server.py."""
import ast
import copy
from contextlib import contextmanager
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
HOST_SOURCES = (ROOT / "server/local_game_server.py",)


class _IdentityProfiler:
    """Keep source-extracted dispatcher tests independent of server bootstrap."""

    @staticmethod
    def profile(_name):
        return lambda function: function


def _source_paths():
    """Use the repository source, or the single source packaged in the image."""
    if HOST_SOURCES[0].is_file():
        return HOST_SOURCES
    packaged = Path("/app/local_game_server.py")
    if packaged.is_file():
        return (packaged,)
    raise FileNotFoundError("Dispatcher source is unavailable: " + str(HOST_SOURCES[0]))


def _extract_dispatcher(source, namespace):
    module = ast.parse(source.read_text(encoding="utf8"))
    session = next(
        node
        for node in module.body
        if isinstance(node, ast.FunctionDef) and node.name == "session"
    )
    dispatcher = next(
        node
        for node in ast.walk(session)
        if isinstance(node, ast.FunctionDef)
        and node.name == "deliver_dungeon_transitions"
    )
    dispatcher = copy.deepcopy(dispatcher)
    factory = ast.FunctionDef(
        name="_make_dispatcher",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="state")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            ast.Assign(
                [ast.Name("character", ast.Store())],
                ast.Subscript(
                    ast.Name("state", ast.Load()), ast.Constant("character"), ast.Load()
                ),
            ),
            ast.Assign(
                [ast.Name("position", ast.Store())],
                ast.Subscript(
                    ast.Name("state", ast.Load()), ast.Constant("position"), ast.Load()
                ),
            ),
            ast.Assign([ast.Name("movement_state", ast.Store())], ast.Constant(None)),
            ast.Assign(
                [ast.Name("last_dungeon_transition_poll", ast.Store())],
                ast.Constant(0.0),
            ),
            ast.Assign(
                [ast.Name("last_dungeon_transition_report", ast.Store())],
                ast.Constant(None),
            ),
            dispatcher,
            ast.Return(ast.Name("deliver_dungeon_transitions", ast.Load())),
        ],
        decorator_list=[],
    )
    ast.fix_missing_locations(factory)
    harness = ast.Module(body=[factory], type_ignores=[])
    exec(compile(harness, str(source), "exec"), namespace)
    return namespace["_make_dispatcher"]


class _Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _Database:
    def __init__(self, pending):
        self.pending = pending
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((sql, params))
        if "SELECT e.fight_id" in sql:
            return _Cursor(self.pending)
        if "SELECT current_room,status,revision" in sql:
            return _Cursor({"current_room": 1, "status": "active", "revision": 4})
        if "UPDATE dungeon_room_encounters SET result=result" in sql:
            return _Cursor(None)
        raise AssertionError(f"Unexpected dispatch query: {sql}")


class _Store:
    def __init__(self, pending):
        self.db = _Database(pending)
        self.connections = 0

    @contextmanager
    def connection(self):
        self.connections += 1
        yield self.db


class DungeonAutoTransitionDispatchTests(unittest.TestCase):
    def setUp(self):
        self.instance_id = 144115188075855873
        self.character = {
            "id": 701,
            "map_id": 1086,
            "instance_id": self.instance_id,
            "x": 4,
            "y": -12,
            "z": 0,
        }
        self.topology = {
            "asset_map_id": 1086,
            "policy": "local_accessible_anchor_policy",
            "rooms": [
                {"order": 1, "anchor": [4, -12, 0], "cells": [[4, -12, 0]]},
                {"order": 2, "anchor": [152, -10, 0], "cells": [[152, -10, 0]]},
            ],
            "doors": [],
            "auto_edges": [
                {"source_room": 1, "destination_room": 2, "anchor": [152, -10, 0]}
            ],
        }

    def test_source_selection_requires_both_checkout_files_or_uses_packaged_dispatcher(
        self,
    ):
        host = (Path("/checkout/server/local_game_server.py"),)
        packaged = Path("/app/local_game_server.py")
        with patch(__name__ + ".HOST_SOURCES", host), patch.object(
            Path, "is_file", autospec=True, side_effect=lambda path: path in host
        ):
            self.assertEqual(host, _source_paths())
        with patch(__name__ + ".HOST_SOURCES", host), patch.object(
            Path, "is_file", autospec=True, side_effect=lambda path: path == packaged
        ):
            self.assertEqual((packaged,), _source_paths())
        with patch(__name__ + ".HOST_SOURCES", host), patch.object(
            Path, "is_file", autospec=True, return_value=False
        ):
            with self.assertRaises(FileNotFoundError):
                _source_paths()

    def _run(
        self,
        source,
        *,
        pending=None,
        fight=None,
        combat_session=None,
        dungeon_run=True,
        before_action=True,
    ):
        from wakfu_server import dungeon_auto_transition, dungeon_runtime
        from wakfu_server.maps import dungeon_transition_delivery

        store = _Store(pending)
        sessions = SimpleCombatSessions()
        configuration = {"topology": self.topology}
        state = {
            "character": dict(self.character),
            "position": {"x": 4, "y": -12, "z": 0},
        }
        namespace = {
            "PROFILER": _IdentityProfiler(),
            "DUNGEON_TRANSITION_OUTBOX_AVAILABLE": True,
            "DUNGEON_ROOM_RUNTIME_AVAILABLE": True,
            "time": time,
            "selected": True,
            "loaded": True,
            "account_id": 55,
            "generation": "generation-a",
            "fight": fight,
            "combat_session": combat_session,
            "is_dungeon_run": lambda _instance: dungeon_run,
            "STORE": store,
            "COMBAT_SESSIONS": sessions,
            "dungeon_transition_delivery": dungeon_transition_delivery,
            "dungeon_hydration": Mock(),
            "cancel_crafting": Mock(),
            "WORLD": Mock(),
            "POSITIONS": Mock(),
            "Movement": Mock(),
            "send": Mock(),
            "connection": object(),
            "service": "world",
            "join_world": Mock(),
            "mark_static_sync_pending": Mock(),
            "record": Mock(),
        }
        make = _extract_dispatcher(source, namespace)
        dispatch = make(state)
        return (
            dispatch,
            namespace,
            store,
            dungeon_auto_transition,
            dungeon_runtime,
            dungeon_transition_delivery,
            configuration,
            before_action,
        )

    def test_committed_victory_is_pinned_and_advanced_once_before_delivery_poll(self):
        for source in _source_paths():
            with self.subTest(source=str(source)):
                pending = {"fight_id": 9001}
                (
                    dispatch,
                    namespace,
                    store,
                    auto_transition,
                    runtime,
                    delivery,
                    config,
                    before_action,
                ) = self._run(source, pending=pending)
                result = {"state": "idle", "pending_event_ids": ()}
                order = []
                with patch.object(
                    runtime,
                    "configuration_for_instance",
                    return_value=({"instance_id": self.instance_id}, config),
                ) as pinned, patch.object(
                    auto_transition,
                    "advance",
                    side_effect=lambda *_args, **_kwargs: order.append("advance")
                    or {"revision": 8},
                ) as advance, patch.object(
                    delivery,
                    "deliver_pending_transitions",
                    side_effect=lambda *_args, **_kwargs: order.append("poll")
                    or result,
                ) as poll:
                    self.assertIs(result, dispatch(before_action=before_action))

                self.assertEqual(1, store.connections)
                self.assertEqual(1, len(store.db.queries))
                sql, params = store.db.queries[0]
                self.assertEqual((self.instance_id,), params)
                for required in (
                    "e.status='victory'",
                    "e.result_revision=r.revision",
                    "auto_transition_revision",
                    "completed",
                    "ORDER BY e.fight_id DESC",
                ):
                    self.assertIn(required, sql)
                pinned.assert_called_once_with(store.db, self.instance_id)
                advance.assert_called_once()
                self.assertEqual(
                    (store, self.instance_id, 9001), advance.call_args.args
                )
                self.assertEqual(self.topology, advance.call_args.kwargs["topology"])
                self.assertFalse(advance.call_args.kwargs["in_fight"](12))
                poll.assert_called_once()
                self.assertEqual(["advance", "poll"], order)

    def test_completed_victory_uses_auto_exit_and_strict_native_result_may_be_none(
        self,
    ):
        from wakfu_server import dungeon_auto_exit

        for source in _source_paths():
            for topology, exit_result in (
                (self.topology, {"map_id": 527, "instance_id": 0}),
                (dict(self.topology, policy="verified_native_door_topology"), None),
            ):
                with self.subTest(source=str(source), policy=topology["policy"]):
                    pending = {"fight_id": 9002, "completed": True}
                    (
                        dispatch,
                        _namespace,
                        store,
                        auto_transition,
                        runtime,
                        delivery,
                        _config,
                        before_action,
                    ) = self._run(source, pending=pending)
                    config = {"topology": topology}
                    result = {"state": "idle", "pending_event_ids": ()}
                    order = []
                    with patch.object(
                        runtime,
                        "configuration_for_instance",
                        return_value=({"instance_id": self.instance_id}, config),
                    ) as pinned, patch.object(
                        dungeon_auto_exit,
                        "complete",
                        side_effect=lambda *_args, **_kwargs: order.append("complete")
                        or exit_result,
                    ) as complete, patch.object(
                        auto_transition, "advance"
                    ) as advance, patch.object(
                        delivery,
                        "deliver_pending_transitions",
                        side_effect=lambda *_args, **_kwargs: order.append("poll")
                        or result,
                    ) as poll:
                        self.assertIs(result, dispatch(before_action=before_action))

                    sql, params = store.db.queries[0]
                    self.assertEqual((self.instance_id,), params)
                    for required in (
                        "e.result_revision=r.revision",
                        "auto_exit_revision",
                        "COALESCE((e.result->>'completed')::boolean,false)",
                    ):
                        self.assertIn(required, sql)
                    pinned.assert_called_once_with(store.db, self.instance_id)
                    complete.assert_called_once()
                    self.assertEqual(
                        (store, self.instance_id, 9002), complete.call_args.args
                    )
                    self.assertEqual(topology, complete.call_args.kwargs["topology"])
                    self.assertFalse(complete.call_args.kwargs["in_fight"](12))
                    advance.assert_not_called()
                    poll.assert_called_once()
                    self.assertEqual(["complete", "poll"], order)

    def test_combat_defers_before_database_or_transition_delivery(self):
        for source in _source_paths():
            for field_values in ((object(), None), (None, object())):
                with self.subTest(source=str(source), combat=field_values):
                    (
                        dispatch,
                        _namespace,
                        store,
                        auto,
                        _runtime,
                        delivery,
                        _config,
                        before_action,
                    ) = self._run(
                        source,
                        pending={"fight_id": 9001},
                        fight=field_values[0],
                        combat_session=field_values[1],
                    )
                    with patch.object(auto, "advance") as advance, patch.object(
                        delivery, "deliver_pending_transitions"
                    ) as poll:
                        result = dispatch(before_action=before_action)
                    self.assertEqual(
                        {"state": "deferred_combat", "pending_event_ids": ()}, result
                    )
                    self.assertEqual(0, store.connections)
                    advance.assert_not_called()
                    poll.assert_not_called()

    def test_no_pending_committed_victory_skips_advance_but_keeps_normal_delivery_poll(
        self,
    ):
        for source in _source_paths():
            with self.subTest(source=str(source)):
                (
                    dispatch,
                    _namespace,
                    store,
                    auto,
                    runtime,
                    delivery,
                    _config,
                    before_action,
                ) = self._run(source, pending=None)
                result = {"state": "idle", "pending_event_ids": ()}
                with patch.object(
                    runtime, "configuration_for_instance"
                ) as pinned, patch.object(auto, "advance") as advance, patch.object(
                    delivery, "deliver_pending_transitions", return_value=result
                ) as poll:
                    self.assertIs(result, dispatch(before_action=before_action))
                self.assertEqual(1, store.connections)
                pinned.assert_not_called()
                advance.assert_not_called()
                poll.assert_called_once()

    def test_non_dungeon_run_keeps_ordinary_transition_delivery_path(self):
        for source in _source_paths():
            with self.subTest(source=str(source)):
                (
                    dispatch,
                    _namespace,
                    store,
                    auto,
                    runtime,
                    delivery,
                    _config,
                    before_action,
                ) = self._run(source, dungeon_run=False)
                result = {"state": "idle", "pending_event_ids": ()}
                with patch.object(
                    runtime, "configuration_for_instance"
                ) as pinned, patch.object(auto, "advance") as advance, patch.object(
                    delivery, "deliver_pending_transitions", return_value=result
                ) as poll:
                    self.assertIs(result, dispatch(before_action=before_action))
                self.assertEqual(0, store.connections)
                pinned.assert_not_called()
                advance.assert_not_called()
                poll.assert_called_once()

    def test_object_state_fallback_accepts_local_auto_edges_without_native_doors(self):
        from wakfu_server.maps.dungeon_object_states import packets

        self.assertEqual(
            (),
            packets(
                self.topology,
                (),
                map_id=1086,
                instance_id=self.instance_id,
                unlocked_room=1,
                completed=False,
            ),
        )

    def test_physical_victory_publishes_gate_and_current_group_without_teleport(self):
        from wakfu_server import dungeon_native_flow
        from wakfu_server.maps import dungeon_physical_doors, dungeon_runtime

        for source in _source_paths():
            with self.subTest(source=str(source)):
                (
                    dispatch,
                    namespace,
                    store,
                    auto,
                    runtime,
                    delivery,
                    _config,
                    before_action,
                ) = self._run(source, pending={"fight_id": 9003})
                topology = dict(self.topology, policy=dungeon_physical_doors.POLICY)
                config = {"topology": topology}
                groups = Mock()
                groups.lock = __import__("threading").RLock()
                groups.available.return_value = (
                    {"members": (), "key": (1087, self.instance_id, 33)},
                )
                namespace["COMBAT_GROUPS"] = groups
                namespace["WORLD"].emit_location = Mock()
                with patch.object(
                    dungeon_native_flow, "enabled", return_value=True
                ), patch.object(
                    dungeon_native_flow,
                    "packets",
                    return_value=((13766, b"closed-gates"),),
                ) as packets, patch.object(
                    runtime,
                    "configuration_for_instance",
                    return_value=({"instance_id": self.instance_id}, config),
                ), patch(
                    "wakfu_server.combat_monster_world.spawn_group",
                    return_value=b"spawn",
                ) as spawn, patch.object(
                    auto, "advance"
                ) as advance, patch.object(
                    delivery, "deliver_pending_transitions"
                ) as poll:
                    result = dispatch(before_action=before_action)

                self.assertEqual(
                    {"state": "physical_room_published", "pending_event_ids": ()},
                    result,
                )
                self.assertEqual(2, store.connections)
                packets.assert_called_once_with(
                    topology,
                    map_id=self.character["map_id"],
                    instance_id=self.instance_id,
                    unlocked_room=1,
                    completed=False,
                )
                spawn.assert_called_once()
                emitted = namespace["WORLD"].emit_location.call_args_list
                self.assertEqual(2, len(emitted))
                self.assertEqual(
                    (
                        self.character["map_id"],
                        self.instance_id,
                        13766,
                        b"closed-gates",
                    ),
                    emitted[0].args,
                )
                self.assertEqual(
                    (self.character["map_id"], self.instance_id, 12608, b"spawn"),
                    emitted[1].args,
                )
                advance.assert_not_called()
                poll.assert_not_called()

    def test_native_teleport_victory_publishes_next_group_without_automatic_travel(
        self,
    ):
        from wakfu_server import dungeon_native_flow
        from wakfu_server.maps import dungeon_runtime

        for source in _source_paths():
            with self.subTest(source=str(source)):
                (
                    dispatch,
                    namespace,
                    store,
                    auto,
                    runtime,
                    delivery,
                    _config,
                    before_action,
                ) = self._run(source, pending={"fight_id": 9003})
                topology = dict(
                    self.topology, policy=dungeon_native_flow.TELEPORT_POLICY
                )
                config = {"topology": topology}
                groups = Mock()
                groups.lock = __import__("threading").RLock()
                groups.available.return_value = (
                    {"members": (), "key": (1087, self.instance_id, 33)},
                )
                namespace["COMBAT_GROUPS"] = groups
                namespace["WORLD"].emit_location = Mock()
                with patch.object(
                    dungeon_native_flow, "enabled", return_value=True
                ), patch.object(
                    dungeon_native_flow,
                    "packets",
                    return_value=((13766, b"closed-gates"),),
                ) as packets, patch.object(
                    runtime,
                    "configuration_for_instance",
                    return_value=({"instance_id": self.instance_id}, config),
                ), patch(
                    "wakfu_server.combat_monster_world.spawn_group",
                    return_value=b"spawn",
                ) as spawn, patch.object(
                    auto, "advance"
                ) as advance, patch.object(
                    delivery, "deliver_pending_transitions"
                ) as poll:
                    result = dispatch(before_action=before_action)

                self.assertEqual(
                    {"state": "physical_room_published", "pending_event_ids": ()},
                    result,
                )
                self.assertEqual(2, store.connections)
                packets.assert_called_once_with(
                    topology,
                    map_id=self.character["map_id"],
                    instance_id=self.instance_id,
                    unlocked_room=1,
                    completed=False,
                )
                spawn.assert_called_once()
                emitted = namespace["WORLD"].emit_location.call_args_list
                self.assertEqual(2, len(emitted))
                self.assertEqual(
                    (
                        self.character["map_id"],
                        self.instance_id,
                        13766,
                        b"closed-gates",
                    ),
                    emitted[0].args,
                )
                self.assertEqual(
                    (self.character["map_id"], self.instance_id, 12608, b"spawn"),
                    emitted[1].args,
                )
                advance.assert_not_called()
                poll.assert_not_called()


class SimpleCombatSessions:
    def lookup_character(self, _character_id):
        return None


if __name__ == "__main__":
    unittest.main()
