"""Use the current optional environmental metadata and new scene fixture."""
import importlib
from wakfu_server.achievements import combat_adapter
import test_environmental_gameplay

importlib.reload(combat_adapter)
importlib.reload(test_environmental_gameplay)
