"""Pure source wiring proof; native publication behavior has a real Registry test."""
import ast
from pathlib import Path
import unittest


class WorldPreparedDispatchWiringTests(unittest.TestCase):
    def test_custom_shapes_keep_original_callback_publication(self):
        source = Path(__file__).with_name("candidate") / "world_shared.py"
        if not source.exists():
            source = (
                Path(__file__).resolve().parents[1]
                / "ai-service/wakfu_ai/bridge/world_shared.py"
            )
        tree = ast.parse(source.read_text())
        helper = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_publish_native_transition"
        )
        # Exercise the actual dispatch body with inert fixture classes. The
        # native Registry/transaction behavior is covered by the separate real
        # publication test; this checks only exact-type selection and forwarding.
        body = [
            node
            for node in helper.body
            if not isinstance(node, (ast.Import, ast.ImportFrom))
        ]

        class Fight:
            pass

        class RuntimeMessages:
            pass

        class Transition:
            def __init__(self, fight, runtime):
                self.fight, self.runtime = fight, runtime

        class Registry:
            def execute_prepared_server(self, *args, **kwargs):
                return ("native", args, kwargs)

            def execute_server(self, fight_id, actor_id, operation, **kwargs):
                return ("legacy", (fight_id, actor_id, operation(None, None)), kwargs)

        namespace = dict(
            Fight=Fight,
            RuntimeMessages=RuntimeMessages,
            Transition=Transition,
            Registry=Registry,
        )
        helper.body = body
        exec(
            compile(ast.Module(body=[helper], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        publish = namespace["_publish_native_transition"]
        native = Transition(Fight(), RuntimeMessages())

        class CustomRegistry(Registry):
            pass

        class CustomTransition(Transition):
            pass

        class CustomFight(Fight):
            pass

        class CustomRuntime(RuntimeMessages):
            pass

        cases = [
            (Registry(), native, "native"),
            (CustomRegistry(), native, "legacy"),
            (Registry(), CustomTransition(Fight(), RuntimeMessages()), "legacy"),
            (Registry(), Transition(CustomFight(), RuntimeMessages()), "legacy"),
            (Registry(), Transition(Fight(), CustomRuntime()), "legacy"),
        ]
        for registry, transition, expected in cases:
            with self.subTest(expected=expected, shape=type(transition)):
                kind, args, kwargs = publish(
                    registry, 91, -200, transition, expected_sequence=4
                )
                self.assertEqual(kind, expected)
                self.assertEqual(args[:2], (91, -200))
                self.assertIs(args[2], transition)
                self.assertEqual(kwargs, {"expected_sequence": 4})
        run = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_run_shared_turn"
        )
        calls = [node for node in ast.walk(run) if isinstance(node, ast.Call)]
        self.assertEqual(
            sum(
                isinstance(node.func, ast.Name)
                and node.func.id == "_publish_native_transition"
                for node in calls
            ),
            1,
        )
        self.assertTrue(
            any(
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute_server"
                for node in calls
            )
        )
