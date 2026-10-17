"""Fight-owned attachment authority and definitions, independent of live bags.

The pin survives plain checkpoint serialization. Its digest detects accidental
mutation, including restored checkpoints; it is not a replacement for the
inventory/enablement authority used before the pin is created.
"""
from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import math

from .combat_owned_equipment import compiled_with_sources, prepare
from .combat_definitions import effect_profile
from .combat_static_catalogs import ImmutableCatalog


def has_equipped_attachments(character):
    """Discover whether readiness needs SQL authority; never grant eligibility.

    Empty builds and attachments in unequipped bags do not require an authority
    lookup. Actual ownership, slot, level and native pattern checks still occur
    in the planner before pinning any source.
    """
    from wakfu_server.wire import proto_fields
    from wakfu_server.inventory_shards import validate

    index = character.get("active_build_index", 0)
    builds = character.get("builds", {})
    sheet = builds.get(index, builds.get(str(index), {}))
    equipment = bytes.fromhex(sheet.get("equipment", ""))
    owned = {item["uid"]: item for item in character.get("inventory_items", [])}
    for tag, nested in proto_fields(equipment):
        if tag == 424:
            continue
        if tag != 10 or not isinstance(nested, bytes):
            raise ValueError("Malformed equipped attachment discovery")
        fields = list(proto_fields(nested))
        values = dict(fields)
        if len(fields) != 2 or set(values) != {8, 16} or values[8] not in owned:
            raise ValueError("Malformed equipped attachment unit")
        state = owned[values[8]].get("shard_state")
        if state is not None:
            state = bytes(state)
            validate(state)
            if any(
                field in (24, 32) and reference != 0
                for field, reference in proto_fields(state)
            ):
                return True
    return False


def _plain(value):
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError("Equipment pin contains a nonstring key")
        return {key: _plain(entry) for key, entry in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(entry) for entry in value]
    raise ValueError("Equipment pin contains an unsupported value")


def _digest(payload):
    encoded = json.dumps(
        _plain(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def execution_contract_sha256(sources, compiled, registry):
    """Bind all reachable state definitions, children and characteristic contracts.

    Item roots are already in the pin. Their referenced state graph must also
    retain its meaning after recovery on a different published catalog. Unrelated
    catalog additions, such as CopyBook flags, do not invalidate this contract.
    """
    states, effects, characteristics = {}, {}, {}
    for source in sources:
        level = source["native_retained_container"]["level"]
        for reference in source["roots"]:
            root = source["effects"][str(reference)]
            if root["effect_class"] != 304:
                raise ValueError("Unqualified equipment state contract")
            state_reference = effect_profile(root, level)["parameters"][0]
            state = compiled.source_states["states"][str(state_reference)]
            states[str(state_reference)] = state
            pending = list(state["effect_ids"])
            while pending:
                child_reference = str(pending.pop())
                if child_reference in effects:
                    continue
                child = compiled.effects[child_reference]
                effects[child_reference] = child
                key = str(child["effect_class"])
                characteristics[key] = registry["effects"].get(key)
                pending.extend(child.get("children", ()))
                if child["effect_class"] == 304:
                    # Reachable bounded state transitions retain the same
                    # catalog meaning after checkpoint recovery as at Ready.
                    for child_level in range(state["maximum_level"] + 1):
                        nested_id = effect_profile(child, child_level)["parameters"][0]
                        nested_key = str(nested_id)
                        if nested_key not in states:
                            nested_state = compiled.source_states["states"][nested_key]
                            states[nested_key] = nested_state
                            pending.extend(nested_state["effect_ids"])
    return _digest(
        dict(states=states, effects=effects, characteristics=characteristics)
    )


def _payload(record):
    if not isinstance(record, Mapping) or set(record) != {
        "version",
        "actor_id",
        "owner_id",
        "sources",
        "deferred",
        "execution_sha256",
        "sha256",
    }:
        raise ValueError("Malformed fight equipment pin")
    payload = {key: value for key, value in record.items() if key != "sha256"}
    if (
        record["version"] != 1
        or type(record["version"]) is not int
        or type(record["actor_id"]) is not int
        or record["actor_id"] <= 0
        or type(record["owner_id"]) is not int
        or record["owner_id"] <= 0
        or not isinstance(record["sources"], (list, tuple))
        or not isinstance(record["deferred"], (list, tuple))
        or record["sha256"] != _digest(payload)
    ):
        raise ValueError("Fight equipment pin integrity mismatch")
    return payload


def pinned_sources(fight, compiled, registry=None):
    """Validate all pins and return static sources without compiling them.

    No live character or SQL access occurs here. Removed/dead fighters' pins
    remain valid static definitions for retained inverse/departure processing.
    """
    if registry is None:
        from .combat_static_catalogs import characteristic_registry

        registry = characteristic_registry()
    pins = getattr(fight, "native_owned_equipment_sources", {})
    if not isinstance(pins, Mapping):
        raise ValueError("Malformed fight equipment pins")
    sources = []
    for actor_id, record in pins.items():
        payload = _payload(record)
        if type(actor_id) is not str or str(payload["actor_id"]) != actor_id:
            raise ValueError("Fight equipment pin actor mismatch")
        if payload["execution_sha256"] != execution_contract_sha256(
            payload["sources"], compiled, registry
        ):
            raise ValueError("Fight equipment execution contract mismatch")
        sources.extend(payload["sources"])
    return tuple(sources)


def compiled_for_fight(fight, compiled):
    """Compose pinned sources, rejecting changed state or characteristic meaning."""
    sources = pinned_sources(fight, compiled)
    return compiled_with_sources(compiled, sources) if sources else compiled


def preparation_for_actor(fight, actor_id, compiled):
    """Recover the exact pinned initialization input, including deferred scope."""
    pins = getattr(fight, "native_owned_equipment_sources", {})
    record = pins.get(str(actor_id))
    if record is None:
        raise ValueError("Missing fight equipment pin")
    payload = _payload(record)
    if payload["actor_id"] != actor_id:
        raise ValueError("Fight equipment pin actor mismatch")
    return dict(
        compiled=compiled_for_fight(fight, compiled),
        sources=tuple(payload["sources"]),
        deferred=tuple(payload["deferred"]),
    )


def pin_transaction(
    fight,
    character,
    attachment_authority,
    compiled,
    registry,
    *,
    owner_id,
    ordinary_only=False
):
    """Validate inventory once, then pin a detached immutable private preview.

    This does not execute sources or choose class/aptitude ordering. The shared
    initialization coordinator owns application, atomic commit and publication.
    """
    actor_id = character["id"]
    actor = fight.actors.get(actor_id)
    if (
        actor is None
        or actor.hp <= 0
        or fight.phase != "active"
        or not actor.controlled
        or type(owner_id) is not int
        or owner_id <= 0
        or actor.owner_id != owner_id
    ):
        raise ValueError("Equipment pin requires an owned active fighter")
    pins = getattr(fight, "native_owned_equipment_sources", {})
    if not isinstance(pins, Mapping) or str(actor_id) in pins:
        raise ValueError("Fighter equipment source is already pinned or malformed")
    initial = prepare(
        character, attachment_authority, compiled, registry, ordinary_only=ordinary_only
    )
    payload = dict(
        version=1,
        actor_id=actor_id,
        owner_id=owner_id,
        sources=_plain(initial["sources"]),
        deferred=_plain(initial["deferred"]),
    )
    payload["execution_sha256"] = execution_contract_sha256(
        initial["sources"], initial["compiled"], registry
    )
    record = dict(payload, sha256=_digest(payload))
    preview = deepcopy(fight)
    preview.native_owned_equipment_sources = dict(pins)
    preview.native_owned_equipment_sources[str(actor_id)] = ImmutableCatalog(record)
    return preview, preparation_for_actor(preview, actor_id, compiled)
