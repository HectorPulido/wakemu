"""Reload the single corrected fixture; no gameplay/runtime/catalog refresh."""
import importlib

importlib.reload(importlib.import_module("test_environmental_owned_combat_route"))
