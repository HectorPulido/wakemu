"""Diagnose one cloned window using the authentic retained services."""
import importlib, unittest
from pathlib import Path


def qualify():
    module = importlib.import_module("test_ombrage_native_paid_clock")
    checkpoint = module.OMBRAGE_ACTUAL_CHECKPOINT
    assert checkpoint is not None
    from tools.ombrage_live_checkpoint_diagnostic import diagnose

    diagnose(
        checkpoint,
        Path(
            ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ombrage40-cloned-native-damage-attribution.json"
        ),
    )
    return unittest.TestSuite()
