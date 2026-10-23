"""Append the qualified268 code/default/module segment to retained Rushu."""
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

TRANSITION = None


class AdoptQualified268(unittest.TestCase):
    def runTest(self):
        global TRANSITION
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory

        roles = importlib.import_module("wakfu_server.combat_encounter_roles")
        recipe = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = recipe.RUSHU_ACTUAL_CHECKPOINT
        previous = sys.modules[
            "_qualification_authorized_movement_both_scopes"
        ].TRANSITIONS["rushu"]
        verify_current = cp["authorized_service_transition_verifier"]
        spec = importlib.util.spec_from_file_location(
            "_private_effect_recipient268_transition",
            ".runtime/tools/qualified_effect_recipient_268_transition.py",
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)
        functions = [
            EffectDispatcher.__init__,
            EffectDispatcher._execute,
            NativeEffectRuntimeFactory.__call__,
            roles.bind_roles,
        ]
        patches = helper.approved_patches(previous["api"], functions)
        transition = helper.prepare(
            name="retained-rushu-a11-no-recipient-policy-opt-in",
            api=previous["api"],
            original_tokens=previous["new_tokens"],
            verify_original=verify_current,
            runtime=cp["runtime"],
            store=cp["store"],
            rng=cp["rng"],
            bindings=previous["bindings"],
            previous_transition=previous,
            patches=patches,
        )
        old = [(fn, fn.__code__, fn.__kwdefaults__) for fn, code in patches]
        try:
            for fn, code in patches:
                fn.__code__ = code
            EffectDispatcher.__init__.__kwdefaults__ = dict(
                EffectDispatcher.__init__.__kwdefaults__ or {},
                invocation_reconstruction=None,
            )
            helper.complete(transition)
        except BaseException:
            for fn, code, kw in old:
                fn.__code__ = code
                fn.__kwdefaults__ = kw
            raise

        def verify():
            assert recipe.RUSHU_ACTUAL_CHECKPOINT is cp
            return helper.verify_adopted(transition)

        cp["authorized_effect_recipient268_transition"] = transition
        cp["authorized_service_transition_verifier"] = verify
        cp["authorized_scoped_policy_transition_verifier"] = verify
        TRANSITION = transition
        facts = dict(
            transition=transition["receipt"],
            verification=verify(),
            original_tokens_replaced=False,
            unchanged_since_admission_claimed=False,
            no_gameplay_actions=True,
        )
        Path(
            ".runtime/parallel-readiness-20261021/qualified-recipient268-retained-rushu-linked-transition.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptQualified268()])
