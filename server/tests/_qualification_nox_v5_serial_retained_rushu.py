"""Admit one qualified Noxv5 scope, keeping the original Rushu Store intact."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class SerialV5Suite(unittest.TestSuite):
    def run(self, result, debug=False):
        recipe = sys.modules["test_rushu_dd230_eleven_slot_opening"]
        cp = recipe.RUSHU_ACTUAL_CHECKPOINT
        verify = cp["authorized_service_transition_verifier"]
        before = verify()
        try:
            return super().run(result, debug)
        finally:
            assert recipe.RUSHU_ACTUAL_CHECKPOINT is cp
            after = verify()
            Path(
                ".runtime/parallel-readiness-20261021/rushu-a11-verification-around-nox-v5.json"
            ).write_text(
                json.dumps(dict(before=before, after=after), indent=2, default=str)
                + "\n"
            )


def qualify():
    base = Path(".runtime/staging/nox-cube24-fixed12-joint")
    frozen = json.loads(
        Path(
            ".runtime/parallel-readiness-20261021/nox-v5-private-source-freeze.json"
        ).read_text()
    )
    assert all(
        hashlib.sha256((base / name).read_bytes()).hexdigest() == expected
        for name, expected in frozen.items()
    )
    path = base / "qualify_nox_full_party_victory_v5.py"
    spec = importlib.util.spec_from_file_location("_private_qualify_nox_v5", path)
    entry = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = entry
    spec.loader.exec_module(entry)
    return unittest.TestSuite(
        [
            SerialV5Suite(
                [
                    entry.qualify(
                        cancel_path=".runtime/parallel-readiness-20261021/nox-v5-stop-requested"
                    )
                ]
            )
        ]
    )
