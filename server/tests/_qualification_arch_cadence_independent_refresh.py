"""Refresh only the qualified arch cadence sources and its focused test."""
import importlib

for name in (
    "wakfu_server.objectives.environmental_schedule",
    "wakfu_server.objectives.environmental_archmonster_runtime",
    "test_environmental_archmonster_runtime",
):
    importlib.reload(importlib.import_module(name))
