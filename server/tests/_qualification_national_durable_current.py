"""Use new owned persistence code while retaining the native catalog cache."""
import importlib
from wakfu_server import national_progression, equipment_persisted_context, store, wire
from wakfu_server.characters import nation_state

for module in (
    national_progression,
    equipment_persisted_context,
    nation_state,
    wire,
    store,
):
    importlib.reload(module)
try:
    from wakfu_server import nation_state as flat_nation_state

    if flat_nation_state is not nation_state:
        importlib.reload(flat_nation_state)
except ImportError:
    pass
