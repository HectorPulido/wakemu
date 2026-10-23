"""Run one paid Nox admission while preserving the authentic Rushu scope."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest


class SerialNoxV4(unittest.TestSuite):
    def run(self, result, debug=False):
        rushu = sys.modules.get("test_rushu_dd230_eleven_slot_opening")
        cp = None if rushu is None else rushu.RUSHU_ACTUAL_CHECKPOINT
        verifier = None
        if cp is not None:
            verifier = cp.get(
                "authorized_service_transition_verifier",
                cp.get(
                    "authorized_uid_transition_verifier", rushu.verify_actual_checkpoint
                ),
            )
            before = verifier()
        try:
            return super().run(result, debug)
        finally:
            if verifier is not None:
                assert rushu.RUSHU_ACTUAL_CHECKPOINT is cp
                after = verifier()
                Path(
                    ".runtime/parallel-readiness-20261021/rushu-a11-verification-around-nox-v4.json"
                ).write_text(
                    json.dumps(
                        dict(before=before, after=after, same_checkpoint=True),
                        indent=2,
                        default=str,
                    )
                    + "\n"
                )


def qualify():
    path = Path(
        ".runtime/staging/nox-cube24-fixed12-joint/qualify_nox_full_party_victory_v4.py"
    )
    name = "_private_qualify_nox_full_party_victory_v4"
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    suite = SerialNoxV4(
        [
            m.qualify(
                cancel_path=".runtime/parallel-readiness-20261021/nox-v4-stop-requested"
            )
        ]
    )
    return unittest.TestSuite([suite])
