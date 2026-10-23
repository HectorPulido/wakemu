"""Continue the original T1 endpoint; reconstruct recipe functions, never admission."""
import ast
import copy
import importlib
import json
from pathlib import Path
import time
import traceback
import unittest

RECIPE_SHA = "48d682f2aade719b72a0bd4720b27ad98632528e84d75f4f432795f09c184233"


def _continuation(checkpoint, recipe):
    import hashlib

    path = Path(recipe.__file__)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == RECIPE_SHA
    source = ast.parse(path.read_text())
    case = next(node for node in source.body if isinstance(node, ast.ClassDef))
    method = next(
        node
        for node in case.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run"
    )
    original_try = next(node for node in method.body if isinstance(node, ast.Try))
    original_with = original_try.body[0]
    loop_index = next(
        index
        for index, node in enumerate(original_with.body)
        if isinstance(node, ast.For)
        and isinstance(node.target, ast.Name)
        and node.target.id == "boundary"
    )
    actions = copy.deepcopy(original_with.body[loop_index:])
    loop = actions[0]
    # First NPC1001 has already happened. Strategic spacing is paid by the
    # first player turns and applies before NPC2, never retroactively to Ready.
    for node in ast.walk(loop):
        if (
            isinstance(node, ast.If)
            and ast.unparse(node.test) == "'minimum_player_pair_distance' in snapshot"
        ):
            node.test = ast.BoolOp(
                op=ast.And(),
                values=[
                    node.test,
                    ast.Compare(
                        left=ast.Attribute(
                            value=ast.Name(id="current", ctx=ast.Load()),
                            attr="native_table_turn",
                            ctx=ast.Load(),
                        ),
                        ops=[ast.GtE()],
                        comparators=[ast.Constant(2)],
                    ),
                ],
            )
        if isinstance(node, ast.If) and ast.unparse(node.test) == "6334 not in states":
            # Original6978 forbids an allied target still carrying6357.
            node.test = ast.BoolOp(
                op=ast.And(),
                values=[
                    node.test,
                    ast.Compare(
                        left=ast.Constant(6357),
                        ops=[ast.NotIn()],
                        comparators=[ast.Name(id="states", ctx=ast.Load())],
                    ),
                ],
            )
    imports = [
        copy.deepcopy(node)
        for node in method.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assignments = []
    selected = {
        "positions",
        "rear",
        "healer_homes",
        "heal_hub",
        "cycle_end",
        "original_damage",
        "original_heal",
        "original_execute",
        "original_event",
    }
    for node in method.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(part, ast.Name) and part.id in selected
            for target in node.targets
            for part in ast.walk(target)
        ):
            assignments.append(copy.deepcopy(node))
    observers = [
        copy.deepcopy(node)
        for node in method.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in ("observe_event", "observe_vitality", "observe_damage", "observe_heal")
    ]
    helpers = [
        copy.deepcopy(node)
        for node in original_with.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("visible", "cast", "movement_path", "move")
    ]
    observed_actions = ast.With(
        items=copy.deepcopy(original_with.items[2:]), body=actions
    )
    function = ast.FunctionDef(
        name="continue_recipe",
        args=ast.arguments(
            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
        ),
        body=imports + assignments + observers + helpers + [observed_actions],
        decorator_list=[],
    )
    namespace = dict(vars(recipe))
    namespace.update(checkpoint)
    namespace.update(
        self=checkpoint["fixture"],
        facts=copy.deepcopy(checkpoint["receipt"]),
        seed_probe=False,
        admission_only=False,
        tanks=checkpoint["identities"][:4],
        healers=checkpoint["identities"][4:],
        started=time.monotonic(),
    )
    output = Path(checkpoint["receipt_path"]).with_name(
        Path(checkpoint["receipt_path"]).stem
        + f'-continued-t{checkpoint["runtime"].fight.native_table_turn}-turn{checkpoint["runtime"].fight.turn_id}.json'
    )
    namespace.update(output=output, journal=output.with_suffix(".boundaries.jsonl"))
    facts = namespace["facts"]
    facts.update(
        status="continuing_original_endpoint",
        prefix_receipt=checkpoint["receipt_path"],
        prefix_error=facts.pop("error", None),
    )
    facts.pop("traceback", None)
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            str(Path(__file__)),
            "exec",
        ),
        namespace,
    )
    return namespace["continue_recipe"], facts, output


class ContinueOriginalSpacingEndpoint(unittest.TestCase):
    def runTest(self):
        recipe = importlib.import_module("test_rushu_native_party_phase_one")
        checkpoint = recipe.RUSHU_ACTUAL_CHECKPOINT
        recipe.verify_actual_checkpoint()
        self.assertEqual(
            (
                checkpoint["runtime"].fight.native_table_turn,
                checkpoint["runtime"].fight.turn_id,
            ),
            (2, 9),
        )
        self.assertEqual(checkpoint["receipt"]["pending_cast"]["spell"], 6978)
        action, facts, output = _continuation(checkpoint, recipe)
        try:
            action()
        except Exception as error:
            facts.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            facts[
                "loaded_implementation_attestation"
            ] = recipe.verify_actual_checkpoint()
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")
            checkpoint["receipt"] = facts
            checkpoint["continuation_receipt_path"] = str(output)


def qualify():
    return unittest.TestSuite([ContinueOriginalSpacingEndpoint()])
