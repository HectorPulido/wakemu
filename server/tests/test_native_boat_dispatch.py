"""Execute the current 13686 dispatcher without importing the game server."""
import ast
from pathlib import Path
import struct
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch

from wakfu_server import native_boats
from wakfu_server.performance_profiler import PerformanceProfiler
from test_native_boat_catalog import seeded_indexes


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


def dispatch_code():
    tree = ast.parse(SERVER.read_text(encoding="utf8"))
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "opcode == 13686 and loaded"
    ]
    if len(matches) != 1:
        raise AssertionError("Expected one native transport dispatcher")
    return compile(
        ast.fix_missing_locations(ast.Module(body=matches[0].body, type_ignores=[])),
        str(SERVER),
        "exec",
    )


class NativeBoatDispatchTests(unittest.TestCase):
    def setUp(self):
        indexes = patch.object(native_boats, "_indexes", return_value=seeded_indexes())
        indexes.start()
        self.addCleanup(indexes.stop)
        self.character = dict(
            id=7, account_id=9, map_id=504, instance_id=0, x=4, y=3, z=9, level=50
        )
        self.body = struct.pack(">qq", 18259, 21678)
        self.destination = dict(map_id=794, instance_id=0, x=-3, y=-4, z=6)
        self.saved = dict(self.character, **self.destination)
        self.store = Mock()
        self.store.clock.return_value = 1791763200.0
        self.store.transition_map.return_value = self.saved
        self.namespace = dict(
            character=self.character,
            body=self.body,
            STORE=self.store,
            account_id=9,
            generation=11,
            environment_blocked=Mock(return_value=False),
            native_transports=Mock(),
            known_transports=Mock(return_value=(123,)),
            ALL_ZAAPS=False,
            record=Mock(),
            cancel_crafting=Mock(),
            WORLD=Mock(),
            POSITIONS=Mock(),
            Movement=Mock(),
            owned_native_bootstrap=Mock(
                return_value=[(13256, b""), (13974, b"bootstrap"), (12318, b"position")]
            ),
            send=Mock(),
            connection=object(),
            service="world",
            join_world=Mock(),
            mark_static_sync_pending=Mock(),
            PROFILER=PerformanceProfiler(),
        )
        self.terrain = ModuleType("wakfu_server.combat_terrain")
        self.terrain.map_geometry = Mock(
            return_value={"edges": [((-3, -4, 6), (-3, -3, 6))]}
        )

    def run_dispatch(self):
        with patch.dict(sys.modules, {"wakfu_server.combat_terrain": self.terrain}):
            exec(dispatch_code(), self.namespace)

    def test_boat_requires_authority_then_fenced_commit_and_normal_bootstrap(self):
        order = []

        def admit(store, account_id, generation, actor, origin, *, blocked):
            order.append("authority")
            self.assertIs(self.store, store)
            self.assertEqual(
                (9, 11, self.character, 18259, False),
                (account_id, generation, actor, origin["id"], blocked),
            )
            return True

        self.store.transition_map.side_effect = (
            lambda *args: order.append("commit") or self.saved
        )
        self.namespace["owned_native_bootstrap"].side_effect = lambda actor: (
            order.append("bootstrap") or [(13974, b"native")]
        )
        with patch.object(native_boats, "admit_source", side_effect=admit):
            self.run_dispatch()
        self.assertEqual(["authority", "commit", "bootstrap"], order)
        self.store.transition_map.assert_called_once_with(
            9, 11, 7, self.character, self.destination
        )
        self.namespace["native_transports"].resolve.assert_not_called()
        self.namespace["WORLD"].leave.assert_called_once_with(7, 11)
        self.namespace["POSITIONS"].attach.assert_called_once_with(9, 11, self.saved)
        self.namespace["send"].assert_called_once_with(
            self.namespace["connection"], "world", 13974, b"native"
        )
        self.namespace["join_world"].assert_called_once_with(
            11, self.namespace["connection"], self.saved, defer_scene_snapshot=True
        )
        self.namespace["mark_static_sync_pending"].assert_called_once_with()

    def test_blocked_boat_never_commits_or_bootstraps(self):
        self.namespace["environment_blocked"].return_value = True

        def admit(*args, blocked):
            self.assertTrue(blocked)
            raise ValueError("occupied")

        with patch.object(native_boats, "admit_source", side_effect=admit):
            self.run_dispatch()
        self.store.transition_map.assert_not_called()
        self.namespace["owned_native_bootstrap"].assert_not_called()
        self.namespace["WORLD"].leave.assert_not_called()
        self.namespace["record"].assert_called_once_with(
            event="native_transport_rejected", actor_id=7, reason="occupied"
        )

    def test_commit_race_rejects_without_leaving_old_world_or_sending_bootstrap(self):
        self.store.transition_map.side_effect = ValueError("stale source")
        with patch.object(native_boats, "admit_source", return_value=True):
            self.run_dispatch()
        self.namespace["WORLD"].leave.assert_not_called()
        self.assertEqual(self.namespace["send"].call_args.args[2], 349)
        self.assertIs(self.character, self.namespace["character"])

    def test_nonboat_zaap_and_drago_keep_existing_resolver_and_transition(self):
        for identity in (31316, 29238):
            with self.subTest(identity=identity):
                self.setUp()
                self.namespace["body"] = struct.pack(">qq", identity, 999)
                route = dict(
                    source_id=identity, destination_id=999, destination=self.destination
                )
                self.namespace["native_transports"].resolve.return_value = route
                with patch.object(native_boats, "admit_source") as admit:
                    self.run_dispatch()
                admit.assert_not_called()
                self.terrain.map_geometry.assert_not_called()
                self.namespace["native_transports"].resolve.assert_called_once_with(
                    self.character,
                    self.namespace["body"],
                    known_ids=(123,),
                    waive_criteria=False,
                )
                self.store.transition_map.assert_called_once_with(
                    9, 11, 7, self.character, self.destination
                )
                self.namespace["owned_native_bootstrap"].assert_called_once_with(
                    self.saved
                )


if __name__ == "__main__":
    unittest.main()
