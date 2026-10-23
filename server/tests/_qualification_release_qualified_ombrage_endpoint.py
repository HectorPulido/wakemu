"""Diagnose the original v1 token without renewal, then release the qualified endpoint."""
import importlib, importlib.util, json, sys, unittest
from pathlib import Path


def release():
    recipe = importlib.import_module("test_ombrage_native_paid_clock")
    checkpoint = recipe.OMBRAGE_ACTUAL_CHECKPOINT
    assert checkpoint is not None
    base = Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components"
    )
    name = "_private_diagnose_checkpoint_v1"
    spec = importlib.util.spec_from_file_location(
        name, ".runtime/tools/diagnose_checkpoint_v1.py"
    )
    helper = importlib.util.module_from_spec(spec)
    sys.modules[name] = helper
    spec.loader.exec_module(helper)
    report = helper.diagnose(
        sys.modules["_private_loaded_implementation_checkpoint"],
        checkpoint["loaded_implementation_token"],
    )
    base.joinpath(
        "ombrage-original-v1-token-member-diff-before-release.json"
    ).write_text(json.dumps(report, indent=2, default=str))
    fight = checkpoint["runtime"].fight
    row = dict(
        scope="CSV earned Sun/Shadow endpoint; no extra victory gate",
        turn=fight.turn_id,
        table=getattr(fight, "native_table_turn", None),
        body_status=checkpoint["receipt"].get("status"),
        areas=[
            {
                k: area.get(k)
                for k in ("uid", "reference", "owner_id", "effect_reference")
            }
            for area in fight.native_effect_areas.values()
            if area.get("reference") in (1349, 1357)
        ],
        cleanup_callbacks=len(checkpoint["cleanups"]),
        historical_test_status="ERROR v1 marshal attestation; body qualified independently",
    )
    recipe.release_actual_ombrage_checkpoint()
    recipe.OMBRAGE_HOLD_ACTUAL_CHECKPOINT = False
    row.update(slot_none=recipe.OMBRAGE_ACTUAL_CHECKPOINT is None, released=True)
    base.joinpath(
        "ombrage-earned-sun-shadow-qualified-endpoint-release.json"
    ).write_text(json.dumps(row, indent=2, default=str))
    return unittest.TestSuite()
