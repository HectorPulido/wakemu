"""Refresh only occupancy fixtures after the shared typed-fact module changed."""
import importlib
import test_environmental_active_maps

importlib.reload(test_environmental_active_maps)
