"""Resume the admitted A11 opening from its untouched pre-start endpoint."""
import ast
import copy
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
import sys
import time
import traceback
import unittest


class ContinueOriginalA11Opening(unittest.TestCase):
    def runTest(self):
        recipe = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = recipe.RUSHU_ACTUAL_CHECKPOINT
        verify = cp["authorized_service_transition_verifier"]
        before = verify()
        runtime = cp["runtime"]
        facts = cp["receipt"]
        self.assertEqual(
            (
                runtime.fight.native_table_turn,
                runtime.fight.turn_id,
                runtime.fight.current.id,
            ),
            (1, 1, -200),
        )
        self.assertFalse(facts["casts"])
        self.assertFalse(facts["movements"])
        path = Path(
            ".runtime/staging/rushu-dd230-eleven-slot-opening/rushu_eleven_slot_opening.py"
        )
        self.assertEqual(
            hashlib.sha256(path.read_bytes()).hexdigest(),
            "0fecfe6bdc7f8a347d82dc55b2f77f988d277008ea1e2f33559a33109baa77ad",
        )
        tree = ast.parse(path.read_text())
        cls = next(
            n
            for n in tree.body
            if isinstance(n, ast.ClassDef)
            and n.name == "RushuElevenSlot230OpeningTests"
        )
        method = next(
            n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "_run"
        )
        loop = next(
            n
            for n in ast.walk(method)
            if isinstance(n, ast.For)
            and isinstance(n.target, ast.Name)
            and n.target.id == "boundary"
        )
        start = ast.parse("runtime.turn_started()").body[0]
        wrapper = ast.FunctionDef(
            name="continue_original_opening",
            args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]
            ),
            body=[start, copy.deepcopy(loop)],
            decorator_list=[],
        )
        program = ast.fix_missing_locations(ast.Module(body=[wrapper], type_ignores=[]))
        namespace = dict(vars(recipe))
        for key in ("cast", "cast_cell", "move", "movement_path", "visible"):
            values = inspect.getclosurevars(cp[key])
            namespace.update(values.globals)
            namespace.update(values.nonlocals)
        output = Path(cp["receipt_path"]).with_name(
            Path(cp["receipt_path"]).stem + "-same-store-opening.json"
        )
        facts["historical_expiration_failure"] = dict(
            error_type=facts.get("error_type"),
            error=facts.get("error"),
            receipt=cp["receipt_path"],
        )
        facts.update(
            status="same_store_opening_resumed", earned_first_round_carriers={}
        )
        namespace.update(cp)
        namespace.update(
            self=cp["fixture"],
            facts=facts,
            acted=set(),
            started=time.monotonic(),
            journal=output.with_suffix(".boundaries.jsonl"),
            staged_score=sys.modules["wakfu_server.boss_score_runtime"].staged_score,
            advance_actual_turn=sys.modules[
                "tools.combat_audit_turns"
            ].advance_actual_turn,
        )
        exec(compile(program, str(path), "exec", dont_inherit=True), namespace)
        try:
            namespace["continue_original_opening"]()
            self.assertEqual(
                facts["status"], "full_native230_a11_paid_pipeline_ap_and_four_foods_t1"
            )
            cp["continuation_receipt_path"] = str(output)
        except BaseException as error:
            facts.update(
                status="same_store_opening_failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            facts["continued_original_store_without_admission"] = True
            facts["service_transition_before_continuation"] = before
            facts["service_transition_after_continuation"] = verify()
            facts["continued_at"] = datetime.now(timezone.utc).isoformat()
            output.write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([ContinueOriginalA11Opening()])
