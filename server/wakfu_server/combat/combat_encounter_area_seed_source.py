"""Explicit reconstructed Qq operand for versioned seed callback state reads."""


def seed_program_level_source(fight, effect, values, invocation):
    """Return the real area PL for one manifest-owned, unrebound844 read.

    This is a Wakemu reconstruction of the missing server callback operand.
    It does not change the native p7 calculation or the invocation's caster,
    target, children, attribution or retained state/listener ownership.
    """
    from .combat_encounter_seed_programs import encounter_seed_programs
    from .combat_state_managers import registered_area_pv

    manifest = getattr(fight, "native_encounter_area_seed_policy", None)
    if (
        manifest is None
        or invocation.state_uid is not None
        or effect.get("effect_class") != 844
    ):
        return None
    parameters = values["parameters"]
    if len(parameters) < 8 or parameters[7] != 1:
        return None
    rebind = ((parameters[5] + 128) % 256) - 128
    if rebind in (1, 2):
        return None
    container = invocation.native_retained_container
    if (
        not isinstance(container, dict)
        or container.get("present") is not True
        or container.get("type") != 3
        or type(container.get("id")) is not int
        or container.get("native_kind") != "effect_area"
    ):
        return None
    row = getattr(fight, "native_effect_areas", {}).get(container["id"])
    if (
        row is None
        or row.get("owner_id") != invocation.caster_id
        or row.get("uid") != container["id"]
        or row.get("level") != container.get("level")
    ):
        return None
    programs = encounter_seed_programs(fight, boss_reference=manifest["boss_reference"])
    program = next(
        (
            program
            for program in programs
            if program["area_reference"] == row.get("reference")
            and program["creator_reference"] == row.get("effect_reference")
            and program["state_reference"] == parameters[6]
        ),
        None,
    )
    if program is None:
        return None
    pv = registered_area_pv(fight, row["uid"])
    ledger = None if pv is None else pv.state_ledger
    if ledger is None or not any(
        entry.reference == program["state_reference"] for entry in ledger.entries
    ):
        return None
    return pv


def seed_program_removal_selection_source(
    fight, effect, invocation, *, effects, definitions
):
    """Bind only a reviewed SELF removal query to its actual callback Qq.

    The caller uses this PV solely while evaluating the selector and restores
    the original fighter caster on every selected invocation. This reconstructed
    callback operand does not change the native843 handler or effect program.
    """
    from .combat_encounter_seed_programs import encounter_seed_programs
    from .combat_state_managers import registered_area_pv
    from .combat_parameters import parameter_value

    manifest = getattr(fight, "native_encounter_area_seed_policy", None)
    if manifest is None or invocation.state_uid is not None:
        return None
    if not native_removal_wrapper(effect, invocation, effects):
        return None
    container = invocation.native_retained_container
    if (
        not isinstance(container, dict)
        or container.get("present") is not True
        or container.get("type") != 3
        or type(container.get("id")) is not int
        or container.get("native_kind") != "effect_area"
    ):
        return None
    row = getattr(fight, "native_effect_areas", {}).get(container["id"])
    if (
        row is None
        or row.get("uid") != container["id"]
        or row.get("owner_id") != invocation.caster_id
        or row.get("executing") is not True
        or row.get("level") != container.get("level")
    ):
        return None
    programs = encounter_seed_programs(fight, boss_reference=manifest["boss_reference"])
    program = next(
        (
            item
            for item in programs
            if item["area_reference"] == row.get("reference")
            and item["creator_reference"] == row.get("effect_reference")
        ),
        None,
    )
    if program is None:
        return None
    committed = False
    for receipt in getattr(fight, "native_encounter_area_setups", {}).values():
        if receipt.get("schema") != "wakemu-native-area-setup-v1":
            continue
        plan = receipt.get("plan", {})
        seeds = plan.get("seeds", ())
        uids = receipt.get("created_area_uids", ())
        if len(seeds) != len(uids) or plan.get("creator_id") != invocation.caster_id:
            continue
        for uid, seed in zip(uids, seeds):
            if (
                seed.get("area_reference") == program["area_reference"]
                and seed.get("effect_reference") == program["creator_reference"]
                and seed.get("program_reference") == program["program_reference"]
                and seed.get("state_reference") == program["state_reference"]
                and seed.get("state_effect_reference")
                == program["state_effect_reference"]
            ):
                initial = uid == row["uid"] and tuple(seed.get("cell", ())) == tuple(
                    row.get("cell", ())
                )
                # The same original315 is called again by native phase return.
                # Its new Qq has a fresh UID/cell, not an initial-scene UID.
                # Keep the frozen program/owner receipt and require actual
                # constructor authority before accepting that later instance.
                returned = (
                    row.get("effect_class") == 315
                    and row.get("native_area_contract") == "faY"
                    and row.get("native_qq_guard_source") == "Qq.constructor"
                    and row.get("native_qq_bhi") is False
                    and row.get("native_running_effect_manager") is True
                    and type(row.get("effect_uid")) is int
                    and row["effect_uid"] > 0
                    and row.get("level") == program["level"]
                )
                if initial or returned:
                    committed = True
    if not committed:
        return None
    definition = definitions.get(str(row["reference"]))
    if definition is None:
        return None
    if not native_removal_getter_path(
        effect, invocation, effects, definition, program["state_reference"]
    ):
        return None
    pv = registered_area_pv(fight, row["uid"])
    if pv is None or not any(
        item.reference == program["state_reference"] for item in pv.state_ledger.entries
    ):
        return None
    return pv


def resolve_seed_program_selection(
    resolver, fight, effect, invocation, *, effects, definitions
):
    """Keep selection's temporary Qq operand out of committed caster ownership."""
    from dataclasses import replace

    source = seed_program_removal_selection_source(
        fight, effect, invocation, effects=effects, definitions=definitions
    )
    if source is None:
        from .combat_encounter_area_callback_source import (
            callback_program_removal_selection_source,
        )

        source = callback_program_removal_selection_source(
            fight, effect, invocation, effects=effects, definitions=definitions
        )
    if source is None:
        return resolver(effect, invocation)
    selected = resolver(effect, replace(invocation, caster_id=source.id))
    return tuple(replace(item, caster_id=invocation.caster_id) for item in selected)


def native_removal_wrapper(effect, invocation, effects):
    """Recognize the original Qq SELF330 -> Qq843 selection program."""
    from .combat_parameters import parameter_value

    if (
        effect.get("effect_class") != 330
        or effect.get("parameter_count") != 0
        or effect.get("native_target_selector")
        != {"class": "fcE", "mask": (1 << 51) | 64 | 2}
        or effect.get("criteria", "").strip()
        or len(effect.get("children", ())) != 1
    ):
        return False
    leaf = effects.get(str(effect["children"][0]))
    if (
        leaf is None
        or leaf.get("effect_class") != 843
        or leaf.get("native_target_selector")
        != {"class": "fcE", "mask": (1 << 51) | 64 | 1}
        or leaf.get("parameter_count") != 1
        or parameter_value(leaf["parameters"], 0, invocation.level) != -1
        or not leaf.get("criteria", "").strip()
    ):
        return False
    return True


def native_removal_getter_path(
    effect, invocation, effects, definition, state_reference
):
    """Prove this wrapper belongs to the prototype's unrebound state read."""
    from .combat_parameters import parameter_value

    # Prove membership in this prototype's real callback tree, including its
    # original caster-state getter. A similarly shaped unrelated330 cannot opt in.
    pending = [(reference, False) for reference in definition["effect_ids"]]
    visited = set()
    matched = False
    while pending:
        reference, getter = pending.pop()
        if (reference, getter) in visited:
            continue
        visited.add((reference, getter))
        node = effects.get(str(reference))
        if node is None:
            continue
        if node.get("effect_class") == 844:
            count = node.get("parameter_count", 0)
            getter = (
                count >= 8
                and (
                    (parameter_value(node["parameters"], 5, invocation.level) + 128)
                    % 256
                )
                - 128
                not in (1, 2)
                and parameter_value(node["parameters"], 6, invocation.level)
                == state_reference
                and parameter_value(node["parameters"], 7, invocation.level) == 1
            )
        if reference == invocation.reference and getter:
            matched = True
            break
        pending.extend((child, getter) for child in node.get("children", ()))
    return matched
