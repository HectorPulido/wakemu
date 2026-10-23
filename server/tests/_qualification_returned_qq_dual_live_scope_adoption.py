"""Append the qualified returned-Qq guard change to both live scope chains."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

TRANSITIONS = {}


class AdoptReturnedQqGuard(unittest.TestCase):
    def runTest(self):
        from wakfu_server.combat_encounter_area_seed_source import (
            seed_program_removal_selection_source,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
        from wakfu_server.combat_server_spell import server_runtime

        nox = sys.modules["test_nox_full_party_victory_v5"]
        nr = nox.retained_components[0]
        rushu = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        prior = cp["authorized_effect_recipient268_transition"]
        rv = cp["authorized_service_transition_verifier"]
        spec = importlib.util.spec_from_file_location(
            "_private_qualified_returned_qq_transition",
            ".runtime/tools/qualified_returned_qq_code_transition.py",
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)
        na = sys.modules["_nox_loaded_implementation_checkpoint_v2_canonical"]

        def nox_bindings(label):
            assert label == "admission" and nox.retained_components[0] is nr
            c = nr["case"]
            rt = c.runtime
            return (
                dict(
                    runtime=rt,
                    store=nr["fixture"].store,
                    rng=c.rng,
                    RuntimeMessages=RuntimeMessages,
                ),
                dict(
                    dispatcher=EffectDispatcher,
                    amount=NativeRunnerAmount,
                    turn_start=rt.turn_start_provider,
                    turn_end=rt.turn_end_provider,
                    expiration_factory=rt.expiration_runtime_factory,
                    server_runtime=server_runtime,
                ),
            )

        method = seed_program_removal_selection_source
        replacement = helper.approved_code(na, method)
        nt = helper.prepare(
            previous_transition=None,
            method=method,
            replacement=replacement,
            name="nox-v5-original-admission-returned-qq-code-only",
            api=na,
            original_tokens={"admission": nr["loaded_code_attestation"]},
            verify_original=lambda: nox.verify_retained_component(nr),
            runtime=nr["case"].runtime,
            store=nr["fixture"].store,
            rng=nr["case"].rng,
            bindings=nox_bindings,
        )
        rt = helper.prepare(
            previous_transition=prior,
            method=method,
            replacement=replacement,
            name="rushu-a11-returned-qq-code-only-after268",
            api=prior["api"],
            original_tokens=prior["new_tokens"],
            verify_original=rv,
            runtime=cp["runtime"],
            store=cp["store"],
            rng=cp["rng"],
            bindings=prior["bindings"],
        )
        old = method.__code__
        try:
            method.__code__ = replacement
            helper.complete(nt)
            helper.complete(rt)
        except BaseException:
            method.__code__ = old
            raise

        def verify_nox(record=None):
            assert record is None or record is nr
            assert nox.retained_components[0] is nr
            return helper.verify_adopted(nt)

        def verify_rushu():
            assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
            return helper.verify_adopted(rt)

        nr["authorized_returned_qq_transition"] = nt
        nr["authorized_scoped_policy_transition_verifier"] = verify_nox
        cp["authorized_returned_qq_transition"] = rt
        cp["authorized_service_transition_verifier"] = verify_rushu
        cp["authorized_scoped_policy_transition_verifier"] = verify_rushu
        TRANSITIONS.update(nox=nt, rushu=rt)
        facts = dict(
            nox=nt["receipt"],
            rushu=rt["receipt"],
            nox_verification=verify_nox(nr),
            rushu_verification=verify_rushu(),
            original_tokens_replaced=False,
            pending_qq_completion_executed=False,
            no_gameplay_actions=True,
        )
        Path(
            ".runtime/parallel-readiness-20261021/qualified-returned-qq-code-dual-live-scope-transition.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptReturnedQqGuard()])
