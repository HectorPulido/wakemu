"""Refresh only the armor handler and its scoped-construction regression."""
import importlib
from wakfu_server import combat_armor

importlib.reload(combat_armor)
import test_combat_armor

importlib.reload(test_combat_armor)
