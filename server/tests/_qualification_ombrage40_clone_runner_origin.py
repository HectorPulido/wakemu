"""Reload only diagnostic instrumentation, never the retained gameplay modules."""
import importlib, unittest
from pathlib import Path


def qualify():
    recipe = importlib.import_module("test_ombrage_native_paid_clock")
    checkpoint = recipe.OMBRAGE_ACTUAL_CHECKPOINT
    assert checkpoint is not None
    helper = importlib.reload(
        importlib.import_module("tools.ombrage_live_checkpoint_diagnostic")
    )
    helper.diagnose(
        checkpoint,
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ombrage40-cloned-native-runner-zero-origin.json"
        ),
    )
    return unittest.TestSuite()
