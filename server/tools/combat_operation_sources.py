"""Source closure for dependency inventories using operation metadata."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server import (
    combat_operation_registry,
    combat_damage_contracts,
    combat_subscription_contracts,
)


def operation_source_paths():
    return tuple(
        Path(module.__file__).resolve()
        for module in (
            combat_operation_registry,
            combat_damage_contracts,
            combat_subscription_contracts,
        )
    ) + (Path(__file__).resolve(),)
