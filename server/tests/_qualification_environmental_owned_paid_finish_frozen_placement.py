"""Reload the corrected full native placement fixture, preserving warm services."""
import importlib

importlib.reload(importlib.import_module("test_environmental_owned_combat_route"))
