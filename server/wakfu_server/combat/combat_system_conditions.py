"""Native eJs Boolean configuration and eOL PvP category predicates."""

from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT

CONFIG_SOURCE = "wakemu.fresh-eEI-empty-overrides.native-eEL-defaults-v1"


@lru_cache(maxsize=1)
def system_predicate_catalog():
    return protocol_catalog.load(DATA_ROOT / "native-combat-system-predicates.json")


def fresh_system_configuration():
    """Explicit fresh-server policy matching the original empty eEI constructor."""
    return dict(source=CONFIG_SOURCE, overrides={})


def boolean_system_configuration(fight, key):
    if type(key) is not str:
        raise ValueError("Native Boolean configuration key must be a string")
    row = system_predicate_catalog()["configurations"].get(key)
    if row is None:
        return False  # eJs: eEL.tk returned null before reading configuration.
    if row.get("boolean") is not True:
        raise ValueError("Native Boolean configuration requested a non-Boolean entry")
    state = getattr(fight, "native_system_configuration", None)
    if (
        not isinstance(state, dict)
        or state.get("source") != CONFIG_SOURCE
        or not isinstance(state.get("overrides"), dict)
    ):
        raise ValueError("Missing current native system configuration producer")
    overrides = state["overrides"]
    value = overrides.get(key, row["default"])
    if type(value) is not bool:
        raise ValueError("Invalid current native Boolean configuration value")
    return value


def fight_is_pvp(model):
    if model is None:
        return False  # eOL: native fight/context explicitly absent.
    if type(model) is not int or not -128 <= model <= 127:
        raise ValueError("Missing native signed-byte fight model")
    row = system_predicate_catalog()["fight_models"].get(str(model))
    if not isinstance(row, dict) or type(row.get("is_pvp")) is not bool:
        raise ValueError("Unknown native fight model PvP category")
    return row["is_pvp"]  # fcz.fVU().fcL.fVT(), including DUEL.


def evaluate_system_predicate(context, name, key=None):
    if (
        name == "GetBooleanSystemConfiguration"
        and key not in system_predicate_catalog()["configurations"]
    ):
        return False  # Original enum lookup precedes any configuration read.
    callback = (
        context.pvp_query
        if name == "IsPvp"
        else (
            context.battleground_query
            if name == "IsBattleground"
            else (
                context.dungeon_query
                if name == "IsDungeon"
                else context.boolean_system_configuration_query
            )
        )
    )
    if not callable(callback):
        raise ValueError("Missing native system predicate authority: " + name)
    value = (
        callback()
        if name in ("IsPvp", "IsBattleground", "IsDungeon")
        else callback(key)
    )
    if type(value) is not bool:
        raise ValueError("Invalid native system predicate boolean: " + name)
    return value
