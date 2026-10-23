"""Reload only the corrected one-use replay consumer fixture."""
import importlib, unittest


def qualify():
    module = importlib.reload(importlib.import_module("test_nox_owned_start_binding"))
    return unittest.defaultTestLoader.loadTestsFromName(
        "NoxOwnedStartReplayHookTests.test_real_replay_binds_clone_and_children_only_and_failed_preview_is_discardable",
        module,
    )
