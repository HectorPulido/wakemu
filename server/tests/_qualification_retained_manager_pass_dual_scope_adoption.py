"""Adopt the reviewed operation-local manager validation pass in held scopes."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

TRANSITIONS = {}


class AdoptRetainedManagerPass(unittest.TestCase):
    def runTest(self):
        from wakfu_server.combat_retained_effects import NativeRetainedEffectView
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime

        prior = sys.modules[
            "_qualification_condition_local_reader_dual_scope_adoption"
        ].TRANSITIONS
        nox = sys.modules["test_nox_full_party_victory_v5"]
        nr = nox.retained_components[0]
        rushu = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        nv, rv = (
            nr["authorized_scoped_policy_transition_verifier"],
            cp["authorized_service_transition_verifier"],
        )
        spec = importlib.util.spec_from_file_location(
            "_private_retained_manager_pass_transition",
            ".runtime/tools/qualified_retained_manager_pass_transition.py",
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)
        patches = helper.approved_patches(
            prior["nox"]["api"],
            [
                NativeRetainedEffectView.__init__,
                NativeRetainedRuntime._live,
                NativeRetainedRuntime.view,
            ],
        )
        prepared = {}
        for name, verify in (("nox", lambda: nv(nr)), ("rushu", rv)):
            old = prior[name]
            prepared[name] = helper.prepare(
                previous_transition=old,
                patches=patches,
                shared_helper=prepared["nox"]["helper"] if name == "rushu" else None,
                name=name + "-retained-manager-pass-segment",
                api=old["api"],
                original_tokens=old["new_tokens"],
                verify_original=verify,
                runtime=old["runtime"],
                store=old["store"],
                rng=old["rng"],
                bindings=old["bindings"],
            )
        originals = [(fn, fn.__code__, fn.__kwdefaults__) for fn, code in patches]
        first = prepared["nox"]
        try:
            first["effects"]._RetainedManagerPass = first["helper"]
            first["retained"]._RetainedManagerPass = first["helper"]
            for fn, code in patches:
                fn.__code__ = code
                if fn.__name__ in ("__init__", "_live"):
                    fn.__kwdefaults__ = dict(
                        fn.__kwdefaults__ or {}, _manager_pass=None
                    )
            helper.complete(prepared["nox"])
            helper.complete(prepared["rushu"])
        except BaseException:
            for fn, code, defaults in originals:
                fn.__code__, fn.__kwdefaults__ = code, defaults
            for module in (first["effects"], first["retained"]):
                if hasattr(module, "_RetainedManagerPass"):
                    delattr(module, "_RetainedManagerPass")
            raise

        def verify_nox(record=None):
            assert record is None or record is nr
            assert nox.retained_components[0] is nr
            return helper.verify_adopted(prepared["nox"])

        def verify_rushu():
            assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
            return helper.verify_adopted(prepared["rushu"])

        nr["authorized_retained_manager_pass_transition"] = prepared["nox"]
        nr["authorized_scoped_policy_transition_verifier"] = verify_nox
        cp["authorized_retained_manager_pass_transition"] = prepared["rushu"]
        cp["authorized_service_transition_verifier"] = verify_rushu
        cp["authorized_scoped_policy_transition_verifier"] = verify_rushu
        TRANSITIONS.update(prepared)
        facts = dict(
            nox=prepared["nox"]["receipt"],
            rushu=prepared["rushu"]["receipt"],
            nox_verification=verify_nox(nr),
            rushu_verification=verify_rushu(),
            no_gameplay_actions=True,
        )
        Path(
            ".runtime/parallel-readiness-20261021/qualified-retained-manager-pass-dual-scope-transition.json"
        ).write_text(json.dumps(facts, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptRetainedManagerPass()])
