"""Reload the sole corrected canonical-state replay fixture."""
import importlib, unittest


def qualify():
    module = importlib.reload(importlib.import_module("test_tal_event_population"))
    return unittest.defaultTestLoader.loadTestsFromName(
        "TalEventPopulationTests.test_real_native_event_replay_selects_pyramid_and_retains_original_marker",
        module,
    )
