"""Explicit Wakemu turn routing for source-qualified event-only ordinary NPCs.

This admission installs native constructor states and supplies pass-turn control.
It never grants an action book or overrides any native effect criterion.
"""
import hashlib
import json

SCHEMA = "native-event-only-npc-v1"


def _bootstrap_roots(authority, catalog, plan, roots):
    """Qualify one local constructor-state hop, never arbitrary event closure."""
    links = authority.get("bootstrap_links", [])
    if type(links) is not list or len(links) > 32:
        raise ValueError("Malformed event-only bootstrap links")
    if not links:
        return set()
    from .combat_definitions import effect_profile, state_profile
    from .combat_effect_targets import native_selector_policy

    initial = {state.state_id: state.level for state in plan}
    callbacks = authority.get("callback_roots")
    if type(callbacks) is not list or any(
        not isinstance(row, dict) or type(row.get("state_id")) is not int
        for row in callbacks
    ):
        raise ValueError("Missing event-only bootstrap callbacks")
    requested = {row["state_id"] for row in callbacks}
    seen = set()
    qualified = set()
    for link in links:
        if (
            not isinstance(link, dict)
            or set(link)
            != {
                "initial_state_id",
                "initial_effect_id",
                "apply_effect_id",
                "state_id",
                "state_level",
            }
            or any(type(value) is not int for value in link.values())
        ):
            raise ValueError("Malformed event-only bootstrap identity")
        source, root = link["initial_state_id"], link["initial_effect_id"]
        target, grade = link["state_id"], link["state_level"]
        if (
            source not in initial
            or (source, root) not in roots
            or target in initial
            or target in seen
            or target not in requested
            or not 1 <= target <= 32767
            or not 1 <= grade <= 32767
        ):
            raise ValueError(
                "Event-only bootstrap must be one acyclic initial-state hop"
            )
        parent = catalog["effects"].get(str(root))
        apply = catalog["effects"].get(str(link["apply_effect_id"]))
        if not isinstance(parent, dict) or not isinstance(apply, dict):
            raise ValueError("Missing event-only bootstrap definitions")
        parent_policy = native_selector_policy(parent)
        child_policy = native_selector_policy(apply)
        if (
            parent.get("effect_class") != 330
            or parent.get("criteria") != ""
            or parent.get("target_masks")
            != [None, None, None, None, None, [1003], None]
            or parent.get("area_native") != "point"
            or parent_policy["relations"] != frozenset({"self"})
            or link["apply_effect_id"] not in parent.get("children", [])
            or apply.get("effect_class") != 304
            or apply.get("criteria") != ""
            or apply.get("children") != []
            or apply.get("target_masks") != [None] * 7
            or apply.get("area_native") != "point"
            or not child_policy["in_area"]
            or "self" not in child_policy["relations"]
        ):
            raise ValueError(
                "Event-only bootstrap is not a guaranteed local state installation"
            )
        parent_values = effect_profile(parent, initial[source])
        apply_values = effect_profile(apply, initial[source])
        if (
            parent_values["probability"] != 100
            or apply_values["probability"] != 100
            or apply_values["parameters"] != [target, grade, -1]
        ):
            raise ValueError(
                "Event-only bootstrap has conditional or mismatched state values"
            )
        profile = state_profile(catalog, target, grade)
        if profile["level"] != grade:
            raise ValueError("Event-only bootstrap level differs from native state")
        qualified.update((target, effect) for effect in profile["effects"])
        seen.add(target)
    return qualified


def event_controller_record(policy, reference, level):
    """Return a reviewed empty-book admission after checking its native sources."""
    from wakfu_server.native_catalog_document import is_native_json_mapping

    if (
        not is_native_json_mapping(policy)
        or policy.get("schema") != "native-npc-activation-v1"
    ):
        raise ValueError("Invalid native NPC activation policy")
    row = policy.get("enabled_monsters", {}).get(str(reference))
    if not isinstance(row, dict) or "event_controller" not in row:
        return None
    authority = row["event_controller"]
    if not isinstance(authority, dict) or authority.get("schema") != SCHEMA:
        raise ValueError("Missing native event-only NPC authority")
    source = authority.get("descriptor")
    if not isinstance(source, dict):
        raise ValueError("Missing native event-only descriptor")
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if (
        authority.get("descriptor_sha256")
        != hashlib.sha256(encoded.encode()).hexdigest()
    ):
        raise ValueError("Native event-only descriptor changed")
    if (
        type(reference) is not int
        or source.get("reference") != reference
        or source.get("native_class") != "aMb"
        or source.get("raw_csd") != []
        or type(source.get("raw_csd")) is not list
        or row.get("spell_ids") != []
        or type(row.get("spell_ids")) is not list
        or type(row.get("min_level")) is not int
        or type(row.get("max_level")) is not int
        or not 1 <= row["min_level"] <= row["max_level"] <= 32767
        or source.get("min_level") != row["min_level"]
        or source.get("max_level") != row["max_level"]
        or not row.get("initial_state_triples")
        or source.get("raw_cle") != row["initial_state_triples"]
    ):
        raise ValueError("Native event-only source disagrees with admission")
    from wakfu_server.monsters import reference as monster_reference

    native = monster_reference(reference)
    if (
        native.get("native_abilities") != []
        or type(native.get("native_abilities")) is not list
        or native.get("min_level") != row["min_level"]
        or native.get("max_level") != row["max_level"]
        or native.get("statistics", {}).get("HP", {}).get("base", 0) <= 0
    ):
        raise ValueError("Event-only NPC lacks a living native empty-book descriptor")
    if type(level) is not int or not 1 <= level <= 32767:
        return None
    from .combat_summon_initial_states import initial_state_plan
    from .combat_definitions import state_profile
    from wakfu_server.spell_audit import states_catalog

    plan = initial_state_plan(row["initial_state_triples"], level)
    catalog = states_catalog()
    roots = {
        (state.state_id, root)
        for state in plan
        for root in state_profile(catalog, state.state_id, state.level)["effects"]
    }
    roots.update(_bootstrap_roots(authority, catalog, plan, roots))
    callbacks = authority.get("callback_roots")
    if not isinstance(callbacks, list) or not callbacks:
        raise ValueError("Event-only NPC needs a native own-turn callback")
    seen = set()
    for callback in callbacks:
        if not isinstance(callback, dict):
            raise ValueError("Malformed native event-only callback")
        state, root = callback.get("state_id"), callback.get("effect_id")
        if type(state) is not int or type(root) is not int or (state, root) in seen:
            raise ValueError("Malformed native event-only callback identity")
        seen.add((state, root))
        definition = catalog["effects"].get(str(root))
        masks = callback.get("target_masks")
        if (
            type(masks) is not list
            or len(masks) != 7
            or any(
                group is not None
                and (
                    type(group) is not list
                    or any(type(event) is not int for event in group)
                )
                for group in masks
            )
            or not any(event in (masks[5] or []) for event in (1001, 1002))
        ):
            raise ValueError("Event-only NPC needs an actual local own-turn mask")
        if (
            (state, root) not in roots
            or not isinstance(definition, dict)
            or definition.get("effect_class") != 330
            or definition.get("target_masks") != callback.get("target_masks")
            or not definition.get("children")
        ):
            raise ValueError("Missing actual native own-turn callback root")
    return row
