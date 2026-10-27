"""Scope newly imported NPC spells without changing native ownership."""
from collections import OrderedDict
from sys import getsizeof
from threading import RLock
from types import MappingProxyType


_INVALID = object()
_RECORDS = OrderedDict()
_LOCK = RLock()
_BYTES = 0
_MAX_ENTRIES = 16
_MAX_BYTES = 8 * 1024 * 1024


def _monsters(policy):
    from wakfu_server.native_catalog_document import is_native_json_mapping

    if (
        not is_native_json_mapping(policy)
        or policy.get("schema") != "native-npc-activation-v1"
    ):
        raise ValueError("Invalid native NPC activation policy")
    legacy = policy.get("legacy_spell_ids")
    if not isinstance(legacy, list) or any(type(s) is not int for s in legacy):
        raise ValueError("Invalid native NPC activation policy")
    monsters = policy.get("enabled_monsters")
    if not isinstance(monsters, dict):
        raise ValueError("Invalid native NPC activation policy")
    return monsters


def _rule(record):
    if record is None:
        return None
    if (
        not isinstance(record, dict)
        or type(record.get("min_level")) is not int
        or type(record.get("max_level")) is not int
        or not 1 <= record["min_level"] <= record["max_level"]
        or not isinstance(record.get("spell_ids"), list)
        or any(type(s) is not int for s in record["spell_ids"])
    ):
        return _INVALID
    # Tuple membership preserves list equality semantics, including unhashable
    # query values, without retaining mutable source records.
    return record["min_level"], record["max_level"], tuple(record["spell_ids"])


def _published_rules(policy):
    global _BYTES
    from wakfu_server.combat_published_catalogs import static_catalog_descriptor

    descriptor = static_catalog_descriptor(policy)
    if (
        descriptor is None
        or policy.representation != "native_json"
        or descriptor["revision"] == "0" * 64
    ):
        return None
    key = tuple(sorted(descriptor.items()))
    with _LOCK:
        found = _RECORDS.get(key)
        if found is not None:
            _RECORDS.move_to_end(key)
            return found[0]
    rules = {monster: _rule(record) for monster, record in _monsters(policy).items()}
    # Invalid unselected records remain lazy errors, as in the original policy.
    # Charge the entire retained projection; do not retain decoded source rows.
    charge = getsizeof(key) + getsizeof(rules) + getsizeof(MappingProxyType(rules))
    charge += sum(
        getsizeof(part) + sum(getsizeof(value) for value in part) for part in key
    )
    for monster, rule in rules.items():
        charge += getsizeof(monster) + getsizeof(rule)
        if rule is not None and rule is not _INVALID:
            charge += sum(getsizeof(value) for value in rule)
            charge += sum(getsizeof(spell) for spell in rule[2])
    result = MappingProxyType(rules)
    if charge > _MAX_BYTES:
        return result
    with _LOCK:
        found = _RECORDS.get(key)
        if found is not None:
            _RECORDS.move_to_end(key)
            return found[0]
        _RECORDS[key] = result, charge
        _BYTES += charge
        while len(_RECORDS) > _MAX_ENTRIES or _BYTES > _MAX_BYTES:
            _, (_, removed) = _RECORDS.popitem(last=False)
            _BYTES -= removed
    return result


def imports_enabled(policy, monster_ref, actor_level, spell):
    if policy is None:
        return True
    rules = _published_rules(policy)
    record = (
        _rule(_monsters(policy).get(str(monster_ref)))
        if rules is None
        else rules.get(str(monster_ref))
    )
    if record is _INVALID:
        raise ValueError("Invalid native NPC activation range")
    return (
        record is not None
        and record[0] <= actor_level <= record[1]
        and spell in record[2]
    )


def _clear_cache():
    global _BYTES
    with _LOCK:
        _RECORDS.clear()
        _BYTES = 0


imports_enabled.cache_clear = _clear_cache
