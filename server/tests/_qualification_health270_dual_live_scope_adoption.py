"""Adopt reviewed descending health ordering without touching held fight state."""
import importlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

TRANSITIONS = {}


class AdoptHealth270(unittest.TestCase):
    def runTest(self):
        ordering = importlib.import_module("wakfu_server.combat_target_ordering")
        events = importlib.import_module("wakfu_server.combat_native_events")
        prior = sys.modules[
            "_qualification_terminal269_dual_live_scope_adoption"
        ].TRANSITIONS
        nox = sys.modules["test_nox_full_party_victory_v5"]
        nr = nox.retained_components[0]
        rushu = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        nv = nr["authorized_scoped_policy_transition_verifier"]
        rv = cp["authorized_service_transition_verifier"]
        spec = importlib.util.spec_from_file_location(
            "_private_qualified_health270_transition",
            ".runtime/tools/qualified_health_ordering_270_transition.py",
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)
        patches = helper.approved_patches(
            prior["nox"]["api"],
            [
                ordering.validate_native_target_ordering_identity,
                ordering.order_native_targets,
                events.validate_group_registration_flags,
            ],
        )
        prepared = {}
        for name, verify in (("nox", lambda: nv(nr)), ("rushu", rv)):
            old = prior[name]
            prepared[name] = helper.prepare(
                name=name + "-descending-health270-segment",
                api=old["api"],
                original_tokens=old["new_tokens"],
                verify_original=verify,
                runtime=old["runtime"],
                store=old["store"],
                rng=old["rng"],
                bindings=old["bindings"],
                previous_transition=old,
                patches=patches,
                shared_comparator=prepared["nox"]["comparator"]
                if name == "rushu"
                else None,
            )
        originals = [(fn, fn.__code__) for fn, new in patches]
        health = prepared["nox"]["health"]
        try:
            for fn, new in patches:
                fn.__code__ = new
            health.compare_native_health_descending = prepared["nox"]["comparator"]
            helper.complete(prepared["nox"])
            helper.complete(prepared["rushu"])
        except BaseException:
            for fn, old in originals:
                fn.__code__ = old
            if hasattr(health, "compare_native_health_descending"):
                delattr(health, "compare_native_health_descending")
            raise

        def verify_nox(record=None):
            assert record is None or record is nr
            assert nox.retained_components[0] is nr
            return helper.verify_adopted(prepared["nox"])

        def verify_rushu():
            assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
            return helper.verify_adopted(prepared["rushu"])

        nr["authorized_health270_transition"] = prepared["nox"]
        nr["authorized_scoped_policy_transition_verifier"] = verify_nox
        cp["authorized_health270_transition"] = prepared["rushu"]
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
            ".runtime/parallel-readiness-20261021/qualified-health270-dual-live-scope-transition.json"
        ).write_text(json.dumps(result, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptHealth270()])
