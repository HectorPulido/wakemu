"""Reviewed Wakemu event admission supplements; native catalog stays immutable."""

from functools import lru_cache
import hashlib
import json
from pathlib import Path
from threading import RLock

_SOURCE_SHA256 = "4849ea67314053288752d965e2446d886dc7ebd02ea5e853eeb1e2799d1d1fd7"
_CACHE = []
_LOCK = RLock()


@lru_cache(maxsize=1)
def _supplement():
    raw = (
        Path(__file__).with_name("reviewed_native_event_controllers.json").read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != _SOURCE_SHA256:
        raise ValueError("Reviewed NPC admission supplement changed")
    source = json.loads(raw)
    if (
        source.get("schema") != "wakemu-reviewed-native-event-admission-v1"
        or type(source.get("native_catalog_revision")) is not str
        or len(source["native_catalog_revision"]) != 64
        or type(source.get("enabled_monsters")) is not dict
    ):
        raise ValueError("Malformed reviewed NPC admission supplement")
    return source


def merge_policy(base, *, revision=None):
    """Merge only reviewed event rows, once per immutable base/revision pair."""
    from wakfu_server import native_catalog
    from wakfu_server.native_catalog_document import is_native_json_mapping

    revision = native_catalog.release() if revision is None else revision
    with _LOCK:
        for original, source_revision, merged in _CACHE:
            if original is base and source_revision == revision:
                return merged
        if (
            not is_native_json_mapping(base)
            or base.get("schema") != "native-npc-activation-v1"
            or not isinstance(base.get("enabled_monsters"), dict)
        ):
            raise ValueError("Missing native NPC activation authority")
        source = _supplement()
        if revision != source["native_catalog_revision"]:
            if revision != native_catalog.release():
                return base
            from wakfu_server.native_catalog_compatibility import (
                require_source_revision,
            )

            try:
                require_source_revision(
                    source["native_catalog_revision"],
                    (
                        "native-npc-spell-effect-trees.json",
                        "monsters.json",
                        "combat-state-definitions.json",
                    ),
                )
            except ValueError:
                # Changed/unavailable source documents retain original admission.
                return base
        enabled = dict(base["enabled_monsters"])
        for key, row in source["enabled_monsters"].items():
            if type(key) is not str or not key.isdecimal() or str(int(key)) != key:
                raise ValueError("Malformed reviewed NPC admission identity")
            if key in enabled and enabled[key] != row:
                raise ValueError("Reviewed NPC admission conflicts with native policy")
            enabled[key] = row
        result = dict(base)
        result["enabled_monsters"] = enabled
        from wakfu_server.combat_npc_event_controller import event_controller_record

        for key, row in source["enabled_monsters"].items():
            if (
                not isinstance(row, dict)
                or any(
                    type(row.get(field)) is not int
                    for field in ("min_level", "max_level")
                )
                or not 1 <= row["min_level"] <= row["max_level"] <= 32767
            ):
                raise ValueError("Malformed reviewed NPC admission range")
            source_digest = row.get("native_source_sha256")
            if source_digest is not None:
                if (
                    key != "2502"
                    or row["spell_ids"] != [3700]
                    or row.get("initial_state_triples") != []
                    or type(source_digest) is not str
                    or len(source_digest) != 64
                ):
                    raise ValueError(
                        "Malformed reviewed native minigame spell admission"
                    )
                from wakfu_server.paths import DATA_ROOT

                native = native_catalog.record(
                    DATA_ROOT / "monsters.json", "monsters", key
                )
                if not isinstance(native, dict):
                    raise ValueError("Reviewed minigame NPC source is absent")
                identity = {
                    field: native.get(field)
                    for field in ("ref", "min_level", "max_level", "native_abilities")
                }
                encoded = json.dumps(
                    identity, sort_keys=True, separators=(",", ":"), allow_nan=False
                ).encode()
                actual_spells = [
                    ability.get("spell_id")
                    for ability in native.get("native_abilities", ())
                    if isinstance(ability, dict)
                ]
                if (
                    hashlib.sha256(encoded).hexdigest() != source_digest
                    or native.get("ref") != int(key)
                    or (row["min_level"], row["max_level"])
                    != (native.get("min_level"), native.get("max_level"))
                    or row["spell_ids"] != actual_spells
                ):
                    raise ValueError(
                        "Reviewed minigame NPC spell admission differs from native"
                    )
                continue
            if row["spell_ids"]:
                raise ValueError(
                    "Non-empty reviewed NPC books require an exact native source pin"
                )
            for grade in range(row["min_level"], row["max_level"] + 1):
                if event_controller_record(result, int(key), grade) is None:
                    raise ValueError("Unqualified reviewed event controller")
        _CACHE.append((base, revision, result))
        del _CACHE[:-2]
        return result


@lru_cache(maxsize=1)
def current_policy():
    """Use indexed native records for ordinary spawn admission and consumers."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    path = DATA_ROOT / "native-npc-spell-effect-trees.json"
    base = {
        key: native_catalog.record(path, "activation_policy", key)
        for key in ("schema", "legacy_spell_ids", "enabled_monsters")
    }
    return merge_policy(base)
