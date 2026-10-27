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


def _execution_effect_definition(effect):
    """Ignore optional exporter observations, preserving all execution fields.

    The equipment and spell exports may include different JVM timing samples
    for the same original definition. These samples are not consumed by the
    runtime; native_timing_definition remains authoritative and digest-bound.
    Neither source metadata nor the compiled definition is modified here.
    """
    return {
        key: value for key, value in effect.items() if key != "native_timing_checks"
    }


def _legacy_execution_contract_payload(sources, compiled, registry):
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
                from .combat_equipment_direct_marker_contract import direct_owned_effect

                if not direct_owned_effect(root):
                    raise ValueError("Unqualified equipment state contract")
                effects[str(reference)] = root
                if root["effect_class"] == 449:
                    from .combat_world_properties import (
                        registry as world_property_registry,
                    )

                    identity = effect_profile(root, level)["parameters"][0]
                    characteristics["449"] = dict(
                        runner="eWw",
                        world_property=world_property_registry()[str(identity)],
                    )
                else:
                    characteristics["400"] = registry["effects"].get("400")
                continue
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
    return dict(states=states, effects=effects, characteristics=characteristics)


def _execution_contract_payload(sources, compiled, registry):
    """Bind the complete reachable graph using each state's own level domain.

    A child304's state graph is selected at that child's execution level, and
    that referenced state's maximum level may differ from its parent. Traverse
    (effect reference, execution level) pairs and enumerate every level of each
    reached state so pin identity covers nested transitions exactly.
    """
    from .combat_definitions import state_profile

    states, effects, characteristics = {}, {}, {}
    operator_contexts = {}
    expanded_states = set()
    source_states = compiled.source_states
    state_catalog = source_states.get("states")
    if not isinstance(state_catalog, Mapping):
        raise ValueError("Missing source state catalog for equipment pin")

    for source in sources:
        root_level = source["native_retained_container"]["level"]
        ordinary_roots = []
        for root_reference in source["roots"]:
            root_key = str(root_reference)
            root = source.get("effects", {}).get(root_key)
            if root is None:
                root = compiled.effects.get(root_key)
            if not isinstance(root, Mapping):
                raise ValueError("Missing reachable equipment root definition")
            # Only the complete-graph admission result can extend ordinary
            # roots beyond the legacy state/direct-marker contracts. Its flag
            # is digest-bound in the pin and revalidated against the live
            # factory bindings before initialization executes any operator.
            generic = source.get("_generic_operation_admission") is True
            if root.get("effect_class") == 304:
                ordinary_roots.append(root_reference)
                continue
            from .combat_equipment_direct_marker_contract import direct_owned_effect

            direct = direct_owned_effect(root)
            if generic and not direct:
                ordinary_roots.append(root_reference)
                continue
            if not direct:
                raise ValueError("Unqualified equipment state contract")
            effects[root_key] = root
            if root["effect_class"] == 449:
                from .combat_world_properties import registry as world_property_registry

                identity = effect_profile(root, root_level)["parameters"][0]
                characteristics["449"] = dict(
                    runner="eWw",
                    world_property=world_property_registry()[str(identity)],
                )
            else:
                characteristics["400"] = registry.get("effects", {}).get("400")
        if not ordinary_roots:
            continue
        pending = [(str(reference), root_level, True) for reference in ordinary_roots]
        visited = set()
        while pending:
            reference, execution_level, caster_is_owner = pending.pop()
            identity = (reference, execution_level, caster_is_owner)
            if identity in visited:
                continue
            visited.add(identity)
            definition = compiled.effects.get(reference)
            if definition is None:
                definition = source.get("effects", {}).get(reference)
            if not isinstance(definition, Mapping):
                raise ValueError("Missing reachable equipment effect definition")
            effects[reference] = definition
            family = definition.get("effect_class")
            minimum, maximum = definition.get("minimum_level"), definition.get(
                "maximum_level"
            )
            if (
                type(minimum) is int
                and type(maximum) is int
                and minimum <= maximum
                and not minimum <= execution_level <= maximum
            ):
                # Match the real dispatcher and admission before interpreting
                # level-dependent operators or their descendant branches.
                continue
            child_is_owner = caster_is_owner
            if family in (330, 844, 912, 913, 999, 1020, 1047):
                from .combat_effect_groups import decode_group_mode

                mode = decode_group_mode(
                    effect_profile(definition, execution_level)["parameters"][:6],
                    raw_target_parameter=definition["parameters"][4]
                    if definition.get("parameter_count", 0) >= 3
                    else None,
                )
                if mode.actor_rebind:
                    child_is_owner = False

            def enqueue(reference, level):
                pending.append((str(reference), level, child_is_owner))

            key = str(family)
            characteristics[key] = registry.get("effects", {}).get(key)
            if family == 449:
                from .combat_world_properties import registry as world_properties

                property_id = effect_profile(definition, execution_level)["parameters"][
                    0
                ]
                operator_contexts.setdefault("world_properties", {})[
                    str(property_id)
                ] = world_properties()[str(property_id)]
            elif family == 1093:
                from .combat_final_modifier import FAQ_FAMILIES

                operator_contexts["final_modifier_families"] = sorted(FAQ_FAMILIES)
            elif family in (913, 1047):
                from .combat_actor_snapshot import native_actor_catalog

                stat_id = (
                    effect_profile(definition, execution_level)["parameters"][6] & 255
                )
                operator_contexts.setdefault("selected_characteristics", {})[
                    str(stat_id)
                ] = native_actor_catalog()["characteristics"].get(str(stat_id))
            if family == 844:
                from .combat_equipment_world_final_state_capability import (
                    state_level_domain,
                )

                domain = state_level_domain(
                    definition,
                    effect_profile(definition, execution_level),
                    execution_level,
                    source_states,
                )
                read_state = state_catalog[str(domain.state_id)]
                operator_contexts.setdefault("read_states", {})[
                    str(domain.state_id)
                ] = read_state
                for child in definition.get("children", ()):
                    for level in domain.child_levels:
                        enqueue(child, level)
            elif family in (913, 1047):
                from .combat_equipment_hp_group_parser import child_domain_witnesses

                for child, level in child_domain_witnesses(
                    definition, compiled.effects, source_states, registry=registry
                ):
                    enqueue(child, level)
            elif family == 912:
                from .combat_equipment_cost_level_domain import child_domain_witnesses

                for child, child_level in child_domain_witnesses(
                    definition,
                    compiled.effects,
                    source_states,
                    registry=registry,
                    level=execution_level,
                ):
                    enqueue(child, child_level)
            elif family == 1020:
                from .combat_equipment_trigger_level_domain import (
                    child_domain_witnesses,
                )

                for child, level in child_domain_witnesses(
                    definition,
                    compiled.effects,
                    registry=registry,
                    states=source_states,
                ):
                    enqueue(child, level)
            elif family == 999:
                from .combat_equipment_dynamic_levels import (
                    source_level_facts,
                    group_child_levels,
                )

                profiled = dict(definition, _capability_reference=int(reference))
                domain = group_child_levels(
                    profiled,
                    execution_level,
                    source_level_facts(source) if caster_is_owner else None,
                )
                if getattr(domain, "child_level_domain", None) is not None:
                    from .combat_equipment_selected_level_domain import (
                        child_domain_witnesses,
                    )

                    for child, level in child_domain_witnesses(
                        profiled, compiled.effects, source_states, registry=registry
                    ):
                        enqueue(child, level)
                else:
                    for child in definition.get("children", ()):
                        for level in domain.levels:
                            enqueue(child, level)
            else:
                for child in definition.get("children", ()):
                    enqueue(child, execution_level)

            if family != 304:
                continue
            try:
                state_reference = effect_profile(definition, execution_level)[
                    "parameters"
                ][0]
            except (
                IndexError,
                KeyError,
                TypeError,
                ValueError,
                OverflowError,
            ) as error:
                raise ValueError(
                    "Invalid reachable equipment state reference"
                ) from error
            if type(state_reference) is not int or state_reference <= 0:
                raise ValueError("Invalid reachable equipment state reference")
            state_key = str(state_reference)
            state = state_catalog.get(state_key)
            if not isinstance(state, Mapping):
                raise ValueError("Missing reachable equipment state definition")
            from .combat_state_parameters import interpret_state_parameters

            application = interpret_state_parameters(
                effect_profile(definition, execution_level)["parameters"],
                allow_signed_calculation=True,
            )
            if application["level"] < 0:
                children = state.get("effect_ids")
                if not isinstance(children, (tuple, list)) or any(
                    not isinstance(compiled.effects.get(str(child)), Mapping)
                    or type(compiled.effects[str(child)].get("minimum_level"))
                    is not int
                    or compiled.effects[str(child)]["minimum_level"] < 0
                    for child in children
                ):
                    raise ValueError(
                        "Negative state descendants need a complete domain proof"
                    )
            maximum = state.get("maximum_level")
            if type(maximum) is not int or not 0 <= maximum <= 32767:
                raise ValueError("Invalid reachable equipment state level domain")
            states[state_key] = state
            state_owner = (state_key, caster_is_owner)
            if state_owner in expanded_states:
                continue
            expanded_states.add(state_owner)
            for requested_level in range(maximum + 1):
                profile = state_profile(source_states, state_reference, requested_level)
                for child in profile["effects"]:
                    pending.append((str(child), profile["level"], caster_is_owner))

    payload = dict(states=states, effects=effects, characteristics=characteristics)
    if operator_contexts:
        payload["operator_contexts"] = operator_contexts
    return payload


def execution_state_references(source, compiled, registry=None):
    """Return applied-state reachability from the canonical pinned traversal.

    Callers supply a source already validated through preparation_for_actor.
    Read-only state operands remain operator context, not applied carriers.
    Dynamic child levels use the same complete domains as pin verification.
    """
    if registry is None:
        from .combat_static_catalogs import characteristic_registry

        registry = characteristic_registry()
    payload = _execution_contract_payload((source,), compiled, registry)
    return frozenset(int(reference) for reference in payload["states"])


def execution_contract_sha256(sources, compiled, registry):
    payload = _execution_contract_payload(sources, compiled, registry)
    return _digest(
        dict(
            payload,
            effects={
                key: _execution_effect_definition(effect)
                for key, effect in payload["effects"].items()
            },
        )
    )


def _legacy_execution_contract_sha256(sources, compiled, registry):
    # Accept an old pin only when its complete current execution definition,
    # including optional observational samples, still matches exactly. Never
    # restore missing metadata from a pin or weaken actual timing/flags/criteria.
    return _digest(_legacy_execution_contract_payload(sources, compiled, registry))


def _normalized_legacy_execution_contract_sha256(sources, compiled, registry):
    """Recognize v1 pins made with the prior traversal and filtered samples."""
    payload = _legacy_execution_contract_payload(sources, compiled, registry)
    return _digest(
        dict(
            payload,
            effects={
                key: _execution_effect_definition(effect)
                for key, effect in payload["effects"].items()
            },
        )
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
        if (
            payload["execution_sha256"]
            != execution_contract_sha256(payload["sources"], compiled, registry)
            and payload["execution_sha256"]
            != _normalized_legacy_execution_contract_sha256(
                payload["sources"], compiled, registry
            )
            and payload["execution_sha256"]
            != _legacy_execution_contract_sha256(payload["sources"], compiled, registry)
        ):
            raise ValueError("Fight equipment execution contract mismatch")
        from .combat_equipment_dynamic_levels import verify_source_level_facts

        for source in payload["sources"]:
            if not verify_source_level_facts(
                source,
                fight,
                actor_id=payload["actor_id"],
                owner_id=payload["owner_id"],
                allow_missing=True,
            ):
                raise ValueError("Pinned native equipment owner-level facts changed")
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
    ordinary_only=False,
    include_attachments=False,
    runtime_capability=None,
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
    from .combat_equipment_dynamic_levels import OwnerLevelFacts

    owner_level_facts = OwnerLevelFacts.capture(fight, actor_id, owner_id)
    initial = prepare(
        character,
        attachment_authority,
        compiled,
        registry,
        ordinary_only=ordinary_only,
        include_attachments=include_attachments,
        runtime_capability=runtime_capability,
        owner_level_facts=owner_level_facts,
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
