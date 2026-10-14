"""Explicit spell-isolation fixtures, never ordinary encounter admission proof.

The user authorizes prerequisite states/areas for isolated
spell compatibility. Every preparation occurs on a deep copy. Definitions,
spell costs and the original live/fresh actor remain unchanged. Fixture
availability is deliberately separate from authentic encounter availability.
"""
from copy import deepcopy


def validate_recipe(recipe):
    allowed = {"states", "areas", "absent_states"}
    if not isinstance(recipe, dict) or set(recipe) - allowed:
        raise ValueError("Unknown isolated prerequisite fixture")
    absent = recipe.get("absent_states", [])
    if not isinstance(absent, list) or any(
        type(v) is not int or v <= 0 for v in absent
    ):
        raise ValueError("Explicit positive absent-state fixture identifiers required")
    states = recipe.get("states", [])
    areas = recipe.get("areas", [])
    for row in states:
        if (
            set(row) not in ({"state_id", "level"}, {"state_id", "level", "role"})
            or any(
                type(row[k]) is not int or row[k] <= 0 for k in ("state_id", "level")
            )
            or row.get("role", "caster") not in ("caster", "target")
        ):
            raise ValueError("Explicit positive native state and level required")
    for row in areas:
        if (
            set(row)
            not in (
                {"effect_id", "level", "cell"},
                {"effect_id", "level", "cell", "area_reference"},
            )
            or any(
                type(row[k]) is not int or row[k] <= 0 for k in ("effect_id", "level")
            )
            or len(row["cell"]) != 3
            or any(type(v) is not int for v in row["cell"])
        ):
            raise ValueError("Explicit native315 effect, level and cell required")
    return deepcopy(recipe)


def prepare(fight, character, monsters, deck, *, actor_id, recipe):
    """Apply existing state/area runtime handlers to a disposable fight copy."""
    recipe = validate_recipe(recipe)
    isolated = deepcopy(fight)
    actor = isolated.actors[actor_id]
    if isolated.phase != "active" or isolated.current is None:
        raise ValueError("Isolation requires an actual initialized combat context")
    from wakfu_server.combat_server_spell import server_runtime
    from wakfu_server.combat_effect_dispatch import EffectInvocation
    from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider

    factory, _ = server_runtime(character, monsters, deck, action_id=1, critical=False)
    dispatcher, packets = factory(
        isolated, {"native_retained_container": {"present": False}}
    )
    receipt = dict(
        mode="isolated_spell_compatibility",
        ordinary_fresh_availability_proven=False,
        original_fight_mutated=False,
        actor_id=actor_id,
        states=[],
        areas=[],
        resource_grants=False,
    )
    for reference in recipe.get("absent_states", []):
        # Explicit post-expiry fixture, using the existing class eZi remover.
        effect = factory.effects.get("114569", factory.effects.get(114569))
        if effect is None or effect["effect_class"] != 321:
            raise ValueError("Missing native class decurse fixture primitive")
        invocation = EffectInvocation(114569, 1, actor_id, actor_id, actor.position)
        dispatcher.handlers[321](effect, {"parameters": [reference]}, invocation)
        if any(e.reference == reference for e in actor.state_ledger.entries):
            raise ValueError(
                "Native decurse did not establish isolated absent-state fixture"
            )
    receipt["absent_states"] = list(recipe.get("absent_states", []))
    timing = NativeEffectTimingProvider(dispatcher.native_state_handler.catalog)
    for row in recipe.get("states", []):
        target_id = (
            actor_id if row.get("role", "caster") == "caster" else character["id"]
        )
        target = isolated.actors[target_id]
        invocation = EffectInvocation(
            2226, row["level"], actor_id, target_id, target.position
        )
        context = timing.direct_state_reference(
            isolated, invocation, row["state_id"], row["level"], critical=False
        )
        applied = dispatcher.native_retention.apply_state_reference(
            dispatcher.native_state_handler,
            invocation,
            row["state_id"],
            row["level"],
            carrier_context=context,
        )
        if not applied:
            raise ValueError("Isolation state handler rejected requested prerequisite")
        receipt["states"].append(dict(row))
    for row in recipe.get("areas", []):
        effect = factory.effects.get(
            str(row["effect_id"]), factory.effects.get(row["effect_id"])
        )
        if effect is None or effect["effect_class"] != 315:
            raise ValueError("Isolation requires an actual native315 definition")
        cell = tuple(row["cell"])
        if cell not in isolated.walkable:
            raise ValueError("Isolation area cell outside actual combat terrain")
        invocation = EffectInvocation(
            row["effect_id"], row["level"], actor_id, None, cell
        )
        if "area_reference" in row:
            reference = row["area_reference"]
            if type(reference) is not int or reference <= 0:
                raise ValueError("Positive native area definition required")
            # Explicit fixture input to the existing class area handler, not
            # a claim that this source effect naturally produces this area.
            applied = dispatcher.handlers[315](
                effect, {"parameters": [reference]}, invocation
            )
        else:
            applied = dispatcher.execute(invocation)
        if not applied:
            raise ValueError("Native area handler rejected isolated prerequisite")
        receipt["areas"].append(dict(row))
    receipt["preparation_packet_ids"] = [opcode for opcode, _ in packets]
    return isolated, receipt
