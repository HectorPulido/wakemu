"""Adopt one per-call retained reader without changing either held encounter."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

TRANSITIONS = {}


class AdoptConditionLocalReader(unittest.TestCase):
    def runTest(self):
        from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter

        prior = sys.modules[
            "_qualification_health270_dual_live_scope_adoption"
        ].TRANSITIONS
        nox = sys.modules["test_nox_full_party_victory_v5"]
        nr = nox.retained_components[0]
        rushu = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        nv = nr["authorized_scoped_policy_transition_verifier"]
        rv = cp["authorized_service_transition_verifier"]
        spec = importlib.util.spec_from_file_location(
            "_private_condition_local_reader_transition",
            ".runtime/tools/qualified_condition_retained_reader_transition.py",
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)
        method = NativeServerRuntimeAdapter.condition
        replacement = helper.approved_code(prior["nox"]["api"], method)
        prepared = {}
        for name, verify in (("nox", lambda: nv(nr)), ("rushu", rv)):
            old = prior[name]
            prepared[name] = helper.prepare(
                previous_transition=old,
                method=method,
                replacement=replacement,
                name=name + "-condition-local-reader-segment",
                api=old["api"],
                original_tokens=old["new_tokens"],
                verify_original=verify,
                runtime=old["runtime"],
                store=old["store"],
                rng=old["rng"],
                bindings=old["bindings"],
            )
        original = method.__code__
        try:
            method.__code__ = replacement
            helper.complete(prepared["nox"])
            helper.complete(prepared["rushu"])
        except BaseException:
            method.__code__ = original
            raise

        def verify_nox(record=None):
            assert record is None or record is nr
            assert nox.retained_components[0] is nr
            return helper.verify_adopted(prepared["nox"])

        def verify_rushu():
            assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
            return helper.verify_adopted(prepared["rushu"])

        nr["authorized_condition_reader_transition"] = prepared["nox"]
        nr["authorized_scoped_policy_transition_verifier"] = verify_nox
        cp["authorized_condition_reader_transition"] = prepared["rushu"]
        cp["authorized_service_transition_verifier"] = verify_rushu
        cp["authorized_scoped_policy_transition_verifier"] = verify_rushu
        TRANSITIONS.update(prepared)
        result = dict(
            nox=prepared["nox"]["receipt"],
            rushu=prepared["rushu"]["receipt"],
            nox_verification=verify_nox(nr),
            rushu_verification=verify_rushu(),
            no_gameplay_actions=True,
        )
        Path(
            ".runtime/parallel-readiness-20261021/qualified-condition-local-reader-dual-scope-transition.json"
        ).write_text(json.dumps(result, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptConditionLocalReader()])
