"""Reload the corrected occupied-schedule fixture, no runtime/catalog refresh."""
import importlib

importlib.reload(importlib.import_module("test_environmental_owned_combat_route"))
