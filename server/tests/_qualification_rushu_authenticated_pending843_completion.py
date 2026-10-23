"""Complete one authenticated pending removal, guarding the independent Nox scope."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class CompleteAuthenticatedPendingRemoval(unittest.TestCase):
    def runTest(self):
        nox = sys.modules["test_nox_full_party_victory_v5"]
        nr = nox.retained_components[0]
        nv = nr["authorized_scoped_policy_transition_verifier"]
        before = nv(nr)
        p = Path(".runtime/rushu-pending843-stage/complete_committed_pickup_removal.py")
        self.assertEqual(
            hashlib.sha256(p.read_bytes()).hexdigest(),
            "cde8b229d40cf0aaf26c35c873faeeaccbbc5ec963d298ef6a0eb04c89c5966b",
        )
        spec = importlib.util.spec_from_file_location(
            "_private_rushu_authenticated_pending843", p
        )
        m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = m
        spec.loader.exec_module(m)
        try:
            m.CompleteCommittedPickupRemoval().runTest()
        finally:
            after = nv(nr)
            Path(
                ".runtime/parallel-readiness-20261021/nox-v5-verification-around-rushu-authenticated843-completion.json"
            ).write_text(
                json.dumps(dict(before=before, after=after), indent=2, default=str)
                + "\n"
            )


def qualify():
    return unittest.TestSuite([CompleteAuthenticatedPendingRemoval()])
