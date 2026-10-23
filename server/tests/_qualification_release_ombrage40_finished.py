"""Release the finished authentic scoped Ombrage fight after terminal export."""
import importlib, json, unittest
from pathlib import Path


def release():
    module = importlib.import_module("test_ombrage_native_paid_clock")
    checkpoint = module.OMBRAGE_ACTUAL_CHECKPOINT
    assert checkpoint is not None and checkpoint["runtime"].fight.phase == "finished"
    cleanup_count = len(checkpoint["cleanups"])
    module.release_actual_ombrage_checkpoint()
    module.OMBRAGE_HOLD_ACTUAL_CHECKPOINT = False
    assert module.OMBRAGE_ACTUAL_CHECKPOINT is None
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ombrage40-finished-checkpoint-release.json"
    ).write_text(
        json.dumps(
            dict(
                released=True,
                slot_none=True,
                hold=False,
                cleanup_callbacks_executed=cleanup_count,
                terminal_artifact="ombrage40-original-terminal-authentic-tail.json",
            ),
            indent=2,
        )
    )
    return unittest.TestSuite()
