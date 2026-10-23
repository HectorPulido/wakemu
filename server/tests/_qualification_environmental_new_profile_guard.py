"""Load only the newly extended pure environmental scope for its new guard."""
import importlib
import unittest


def qualify():
    module = importlib.import_module("wakfu_server.objectives.environmental_runtime")
    importlib.reload(module)
    tests = importlib.reload(importlib.import_module("test_environmental_runtime"))
    return unittest.TestSuite(
        [
            tests.EnvironmentalRuntimeTests(
                "test_profile_requires_frozen_family_scope_and_positive_authority"
            )
        ]
    )
