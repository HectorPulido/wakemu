"""Native owner routing and eVv.eo arithmetic for evaluated Qe delivery."""
from wakfu_server import native_catalog as protocol_catalog
from functools import lru_cache
import json
import math
from wakfu_server.paths import DATA_ROOT
from .combat_parameters import _float32, _integer as java_integer
from .combat_effect_groups import native_group_route


@lru_cache(maxsize=1)
def owner_catalog():
    return protocol_catalog.load(DATA_ROOT / "native-runner-registration-owners.json")


def native_owner_flags(effect):
    route = native_group_route(effect)
    if route is not None:
        return route == "actors", route == "cell"
    row = owner_catalog()["effects"].get(str(effect["effect_class"]))
    if (
        isinstance(row, dict)
        and row.get("bbA_owner") == "eYZ"
        and row.get("bbB_owner") == "eYZ"
    ):
        from .combat_triggered_spell import triggered_spell_owner_flags

        return triggered_spell_owner_flags(effect["parameters"])
    if (
        not isinstance(row, dict)
        or type(row.get("bbA")) is not bool
        or type(row.get("bbB")) is not bool
    ):
        raise ValueError("Missing native delivery owner routing")
    return row["bbA"], row["bbB"]


def native_delay_nonzero(effect, level):
    fields = effect.get("native_timing_definition")
    if effect.get("native_definition_class") not in ("eVy", "eVI") or not isinstance(
        fields, dict
    ):
        raise ValueError("Missing native eVv.eo definition")
    product = _float32(_float32(fields["ryI"]) * level)
    delta = (
        java_integer(math.floor(product))
        if math.isfinite(product)
        else java_integer(product)
    )
    value = ((fields["ryH"] + delta + 2**31) % 2**32) - 2**31
    return ((value + 32768) % 65536) - 32768 != 0
