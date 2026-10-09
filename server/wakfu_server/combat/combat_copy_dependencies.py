"""Original class character-copy constructor profile dependency closures."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_copy_profiles():
    source = protocol_catalog.load(DATA_ROOT / "native-class-copy-profiles.json")
    seeds = source.get("seed_identity", {})
    if (
        source.get("schema") != "native-class-copy-profiles-v1"
        or seeds.get("schema") != "native-class-copy-profile-seeds-v1"
        or seeds.get("reference_contract") != "eZw.fRo -> faB.aV -> faB.aXA"
        or seeds.get("profile_ids") != [2382]
        or set(source.get("profiles", {})) != {"2382"}
    ):
        raise ValueError("Unattested original eZw constructor profile domain")
    return source["profiles"]


def merge_profile_component(existing, component):
    merged = dict(existing)
    for reference, profile in native_copy_profiles().items():
        if reference in merged and merged[reference][component] != profile[component]:
            raise ValueError("Conflicting original class-copy profile component")
        if reference not in merged:
            merged[reference] = profile
    return merged
