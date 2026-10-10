"""Live marker delivery cannot wait behind unrelated ecology group work."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


class MarkerLockScopeTests(unittest.TestCase):
    def test_live_batch_bypasses_group_fence_and_terminal_batch_retains_it(self):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "publish_external_marker"
        )

        class GroupFence:
            entered = False
            entries = 0

            def __enter__(self):
                self.entered = True
                self.entries += 1

            def __exit__(self, *_args):
                self.entered = False

        fence = GroupFence()
        deliveries = []

        def emit(map_id, instance_id, packets, *, exclude_sessions):
            deliveries.append((tuple(packets), exclude_sessions, fence.entered))
            return 1

        namespace = {
            "COMBAT_TEST": True,
            "EXTERNAL_FIGHT_MARKERS": SimpleNamespace(
                location=lambda _: (5, 0),
                update=lambda _: (13753, b"marker"),
                actor_packet=lambda _: (12608, b"actor"),
                remove=lambda _: (12238, b"removed"),
            ),
            "SPECTATORS": SimpleNamespace(
                sessions=lambda _: (
                    SimpleNamespace(character_id=2, generation="observer"),
                )
            ),
            "COMBAT_GROUPS": SimpleNamespace(lock=fence),
            "WORLD": SimpleNamespace(emit_location_batch=emit),
            "record": lambda **_: None,
        }
        exec(
            compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        shared = SimpleNamespace(
            fight=SimpleNamespace(id=1, phase="placement", winner=0),
            map_id=5,
            instance_id=0,
            settlement_ready=True,
            group_lease=None,
            participants={1: SimpleNamespace(character_id=1, generation="owner")},
        )
        for phase in ("placement", "active"):
            shared.fight.phase = phase
            namespace["publish_external_marker"](shared)
            self.assertFalse(deliveries[-1][2])
            self.assertEqual(deliveries[-1][0], ((12608, b"actor"), (13753, b"marker")))
            self.assertEqual(
                deliveries[-1][1], frozenset({(1, "owner"), (2, "observer")})
            )
        self.assertEqual(fence.entries, 0)
        shared.fight.phase = "finished"
        namespace["publish_external_marker"](shared)
        self.assertEqual(deliveries[-1][0], ((12238, b"removed"),))
        self.assertTrue(deliveries[-1][2])
        self.assertEqual(fence.entries, 1)
