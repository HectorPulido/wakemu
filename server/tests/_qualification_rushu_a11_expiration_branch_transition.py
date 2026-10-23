"""Correct only the retained recipe's non-attack expiration critical branch."""
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class CorrectRecipeExpirationBranch(unittest.TestCase):
    def runTest(self):
        recipe = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = recipe.RUSHU_ACTUAL_CHECKPOINT
        runtime = cp["runtime"]
        api = sys.modules["_nox_loaded_implementation_checkpoint"]
        # Reuse the already qualified code-only transition implementation.
        key = "_rushu_a11_recipe_callback_transition"
        spec = importlib.util.spec_from_file_location(
            key, ".runtime/tools/qualified_uid_code_transition.py"
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[key] = helper
        spec.loader.exec_module(helper)
        method = runtime.expiration_runtime_factory
        old = method.__code__
        self.assertEqual(old.co_consts, (None, ("action_id", "critical"), 0))
        replacement = old.replace(co_consts=(False, ("action_id", "critical"), 0))
        self.assertEqual(old.co_code, replacement.co_code)
        self.assertEqual(old.co_freevars, replacement.co_freevars)

        def bindings(label):
            self.assertEqual(label, "services")
            self.assertIs(recipe.RUSHU_ACTUAL_CHECKPOINT, cp)
            return (
                dict(
                    runtime=runtime,
                    store=cp["store"],
                    rng=cp["rng"],
                    RuntimeMessages=type(runtime),
                ),
                dict(
                    stats=runtime.runtime_stats_serializer,
                    start=runtime.turn_start_provider,
                    end=runtime.turn_end_provider,
                    expiration=runtime.expiration_runtime_factory,
                ),
            )

        original_verify = cp["loaded_implementation_verifier"]
        transition = helper.prepare(
            name="rushu-a11-original-recipe-expiration-factory",
            api=api,
            original_tokens={"services": cp["loaded_runtime_service_token"]},
            verify_original=original_verify,
            runtime=runtime,
            store=cp["store"],
            rng=cp["rng"],
            bindings=bindings,
            method=method,
            replacement=replacement,
            delta="recipe-expiration-factory-critical-None-to-False-only-actual-casts-unchanged",
            policy="authorized-rushu-recipe-expiration-critical-branch-v1",
        )
        try:
            method.__code__ = replacement
            helper.complete(transition)
        except BaseException:
            method.__code__ = old
            raise
        admission = cp["loaded_implementation_token"]

        def verify():
            self.assertIs(recipe.RUSHU_ACTUAL_CHECKPOINT, cp)
            # The original admission token is still valid; only its separate
            # service token needs an explicit linked post-transition segment.
            api.verify(
                admission,
                identities=dict(
                    store=cp["store"], rng=cp["rng"], RuntimeMessages=type(runtime)
                ),
                roots=admission.roots,
            )
            return helper.verify_adopted(transition)

        cp["authorized_recipe_expiration_transition"] = transition
        cp["authorized_service_transition_verifier"] = verify
        result = verify()
        output = Path(
            ".runtime/parallel-readiness-20261021/rushu-a11-recipe-expiration-critical-branch-transition.json"
        )
        output.write_text(
            json.dumps(
                dict(
                    transition=transition["receipt"],
                    verification=result,
                    actual_player_cast_critical_branch_unchanged=True,
                ),
                indent=2,
                default=str,
            )
            + "\n"
        )


def qualify():
    return unittest.TestSuite([CorrectRecipeExpirationBranch()])
