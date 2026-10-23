"""Append a movement-only code segment to both existing authorized chains."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

TRANSITIONS = {}


class AdoptMovementOnly(unittest.TestCase):
    def runTest(self):
        from wakfu_server.combat_voluntary_movement_events import (
            deliver_voluntary_movement,
        )

        prior = sys.modules[
            "_qualification_authorized_pv_and_nox267_both_realms"
        ].TRANSITIONS
        nox = sys.modules["test_nox_full_party_victory_v4"]
        nr = nox.retained_components[0]
        rushu = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = rushu.RUSHU_ACTUAL_CHECKPOINT
        old_nox_verify = nr["authorized_scoped_policy_transition_verifier"]
        old_rushu_verify = cp["authorized_service_transition_verifier"]
        spec = importlib.util.spec_from_file_location(
            "_private_qualified_movement_transition",
            ".runtime/tools/qualified_movement_code_transition.py",
        )
        helper = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = helper
        spec.loader.exec_module(helper)
        method = deliver_voluntary_movement
        replacement = helper.approved_code(prior["nox"]["api"], method)
        prepared = {}
        for name, verify in (
            ("nox", lambda: old_nox_verify(nr)),
            ("rushu", old_rushu_verify),
        ):
            previous = prior[name]
            prepared[name] = helper.prepare(
                previous_transition=previous,
                method=method,
                replacement=replacement,
                name=name + "-calendar-movement-isolation",
                api=previous["api"],
                original_tokens=previous["new_tokens"],
                verify_original=verify,
                runtime=previous["runtime"],
                store=previous["store"],
                rng=previous["rng"],
                bindings=previous["bindings"],
            )
        old = method.__code__
        try:
            method.__code__ = replacement
            helper.complete(prepared["nox"])
            helper.complete(prepared["rushu"])
        except BaseException:
            method.__code__ = old
            raise

        def verify_nox(record=None):
            assert record is None or record is nr
            assert nox.retained_components[0] is nr
            return helper.verify_adopted(prepared["nox"])

        def verify_rushu():
            assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
            return helper.verify_adopted(prepared["rushu"])

        nr["authorized_movement_transition"] = prepared["nox"]
        nr["authorized_scoped_policy_transition_verifier"] = verify_nox
        cp["authorized_movement_transition"] = prepared["rushu"]
        cp["authorized_scoped_policy_transition_verifier"] = verify_rushu
        cp["authorized_service_transition_verifier"] = verify_rushu
        TRANSITIONS.update(prepared)
        result = dict(
            nox=prepared["nox"]["receipt"],
            rushu=prepared["rushu"]["receipt"],
            nox_verification=verify_nox(nr),
            rushu_verification=verify_rushu(),
            no_gameplay_or_metadata_change=True,
            original_tokens_replaced=False,
            unchanged_since_admission_claimed=False,
        )
        Path(
            ".runtime/parallel-readiness-20261021/qualified-movement-isolation-dual-live-scope-transition.json"
        ).write_text(json.dumps(result, indent=2, default=str) + "\n")


def qualify():
    return unittest.TestSuite([AdoptMovementOnly()])
