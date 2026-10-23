"""Execute the authorized bounded continuation under the exact disk-only exception."""
import importlib, hashlib, json, unittest
from pathlib import Path


def qualify():
    recipe = importlib.import_module("test_ombrage_native_paid_clock")
    checkpoint = recipe.OMBRAGE_ACTUAL_CHECKPOINT
    assert checkpoint is not None
    base = Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components"
    )
    proof = json.loads(
        (
            base / "ombrage40-two-file-disk-drift-loaded-code-attestation.json"
        ).read_text()
    )
    root = Path("server/wakfu_server")
    actual = {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*.py")
    }
    expected = checkpoint["runtime_source_pins"]
    drift = {
        k: dict(before=expected.get(k), after=actual.get(k))
        for k in set(actual) | set(expected)
        if actual.get(k) != expected.get(k)
    }
    assert drift == proof["drift"], drift
    fight = checkpoint["runtime"].fight
    assert (
        fight.native_encounter_table_listener_policy
        == checkpoint["receipt"]["frozen_listener_policy"]
    )
    assert (
        fight.native_encounter_roles
        == checkpoint["receipt"]["premise"]["encounter_roles"]
    )
    from tools.ombrage_live_phase_handoff import continue_handoff

    continue_handoff(
        checkpoint, base / "ombrage40-retained-native-integer80-back-phase-handoff.json"
    )
    return unittest.TestSuite()
