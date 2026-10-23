"""Reload only edited national policy producers; retain shared native catalogs."""
import importlib
from wakfu_server import national_progression, personal_ecology
from wakfu_server.objectives import pvp

for module in (national_progression, personal_ecology, pvp):
    importlib.reload(module)
