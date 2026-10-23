"""Native current-characteristic equipment admission and FIFO reconciliation."""
from .equipment_characteristics import apply_scalar, native_rows, trace
from .equipment_conditions import catalog, evaluate
from copy import deepcopy


def _maxima(current, resource_states):
    rows = native_rows()
    maximum = {identity: rows[identity]["maximum"] for identity in current}
    maximum.update(
        {identity: state["maximum"] for identity, state in resource_states.items()}
    )
    return maximum


def _sync_resources(current, resource_states):
    current.update(
        {identity: state["current"] for identity, state in resource_states.items()}
    )


def _projection(
    character,
    entries,
    *,
    criterion_context=None,
    native_baseline=None,
    build_index=None,
    include_consumable_buffs=False
):
    from .equipment_stats import bonuses

    result = bonuses(
        character,
        build_index=build_index,
        criterion_context=criterion_context,
        native_baseline=native_baseline,
        include_consumable_buffs=include_consumable_buffs,
        _selected_entries=entries,
    )
    from wakfu_server.combat_equipment_snapshot_roles import (
        native_relic_aura,
        prestart_state_roles,
    )

    role_character = dict(character, active_build_index=result["build_index"])
    start_roles = prestart_state_roles(role_character, entries, result["unsupported"])
    # Companion EQUIP criteria are evaluated against native NPC baselines.
    # Ordinary runtime roots have no snapshot contribution, so let the shared
    # root-role classifier defer them to the same complete Ready-time graph
    # validator instead of treating them as missing scalar math. Player
    # admission keeps its existing role boundary unchanged.
    companion_roles = {}
    if criterion_context.get("actor_kind") == "native_companion_npc":
        from wakfu_server.combat_equipment_snapshot_roles import snapshot_roles

        companion_roles = snapshot_roles(role_character, result["unsupported"])

    # Existing particle-only relic roots have no static characteristic delta.
    # Keep their source rows for the combat visual-role pipeline; querying this
    # pure role must not recurse through selected-sheet validation.
    unknown = [
        row
        for row in result["unsupported"]
        if not (
            row.get("reason") == "unsupported-native-effect"
            and (
                (
                    row.get("uid"),
                    row.get("reference"),
                    row.get("effect_id"),
                    row.get("generic"),
                )
                in start_roles
                or (
                    row.get("uid"),
                    row.get("reference"),
                    row.get("effect_id"),
                    row.get("generic"),
                )
                in companion_roles
                or (
                    row.get("generic") == 400
                    and native_relic_aura(row["reference"], row["effect_id"])
                )
            )
        )
    ]
    if unknown:
        raise ValueError(
            "Equipment characteristic criteria require qualified effect contributions"
        )
    initial, current, inverse = trace(
        result["stat_operations"], baseline=native_baseline
    )
    resources = result.get("resource_projection", {})
    states = deepcopy(resources.get("final", {}))
    initial.update(
        {
            identity: state["current"]
            for identity, state in resources.get("initial", {}).items()
        }
    )
    _sync_resources(current, states)
    for step in resources.get("steps", ()):
        inverse[step["index"]] = dict(deepcopy(step["receipt"]), stat=step["stat"])
    result["resource_states"] = states
    result["maximum_characteristics"] = _maxima(current, states)
    return result, initial, current, inverse


def _condition(item):
    actions = catalog().get(str(item["reference"]))
    if actions is None:
        raise ValueError("Missing native equipment condition catalog")
    return actions.get("EQUIP")


def reconcile(
    character,
    physical,
    *,
    criterion_context=None,
    native_baseline=None,
    build_index=None,
    include_consumable_buffs=False
):
    """Apply all candidates, then remove invalid units without reconsidering them.

    Physical slot ownership remains intact. Each FIFO removal uses the actual
    clipped inverse stored at registration, not a newly evaluated item formula.
    Later predicates therefore see all earlier removals in the same pass.
    """
    from .equipment_context import for_character

    criterion_context = for_character(character, criterion_context)
    entries = [
        dict(uid=row["uid"], slot=row["slot"])
        for row in physical
        if not row.get("_level_ineligible")
    ]
    owned = {row["uid"]: row for row in character.get("inventory_items", [])}
    result, initial, current, inverse = _projection(
        character,
        entries,
        criterion_context=criterion_context,
        native_baseline=native_baseline,
        build_index=build_index,
        include_consumable_buffs=include_consumable_buffs,
    )
    resource_states = deepcopy(result["resource_states"])
    physical_entries = [dict(uid=row["uid"], slot=row["slot"]) for row in physical]
    removed = set()
    rows = native_rows()
    while True:
        changed = False
        for entry in sorted(entries, key=lambda row: row["slot"]):
            uid = entry["uid"]
            if uid in removed:
                continue
            item = owned[uid]
            criterion = _condition(item)
            if not criterion or evaluate(
                criterion,
                item=item,
                selected=physical_entries,
                owned=owned,
                criterion_context=criterion_context,
                current_characteristics=current,
                maximum_characteristics=_maxima(current, resource_states),
            ):
                continue
            removed.add(uid)
            changed = True
            start, end = result["gear_operation_ranges"].get(uid, (0, 0))
            for index in range(start, end):
                operation = inverse[index]
                if isinstance(operation, dict):
                    from .equipment_resource_projection import remove_operation

                    identity = result["stat_operations"][index][0]
                    resource_states[identity] = remove_operation(
                        resource_states[identity], operation
                    )
                    _sync_resources(current, resource_states)
                elif operation is not None:
                    identity, amount, subtract = operation
                    current[identity] = apply_scalar(
                        current[identity], rows[identity], amount, subtract
                    )
        if not changed:
            break
    return dict(
        entries=[row for row in entries if row["uid"] not in removed],
        scalar_overrides={
            identity: ((value - initial[identity] + (1 << 31)) % (1 << 32)) - (1 << 31)
            for identity, value in current.items()
            if identity not in resource_states
            and (value != initial[identity] or identity in result["stats"])
        },
        current_characteristics=current,
        maximum_characteristics=_maxima(current, resource_states),
        resource_states=resource_states,
        removed_uids=frozenset(removed),
        inverse_operations=inverse,
        gear_operation_ranges=result["gear_operation_ranges"],
    )


def precheck_new(
    character,
    physical,
    *,
    previous_character=None,
    criterion_context=None,
    native_baseline=None,
    build_index=None,
    include_consumable_buffs=False,
    current_characteristics=None
):
    """Check newly introduced units against the current actor before application."""
    from .equipment import resolve_sheet
    from wakfu_server.builds import effective_sheet_level
    from .equipment_context import for_character

    criterion_context = for_character(character, criterion_context)
    current_character = character if previous_character is None else previous_character
    current_index = current_character.get("active_build_index", 0)
    level = effective_sheet_level(current_character, current_index)
    current_character = dict(current_character, level=level, effective_level=level)
    old_blob = bytes.fromhex(
        current_character.get("builds", {}).get(current_index, {}).get("equipment", "")
    )
    resolution = resolve_sheet(
        current_character,
        old_blob,
        criterion_context=criterion_context,
        native_baseline=native_baseline,
        build_index=current_index,
        include_consumable_buffs=include_consumable_buffs,
        ignore_ineligible=criterion_context.get("actor_kind") == "native_companion_npc",
    )
    projected, _, current, inverse = _projection(
        current_character,
        resolution["entries"],
        criterion_context=criterion_context,
        native_baseline=native_baseline,
        build_index=current_index,
        include_consumable_buffs=include_consumable_buffs,
    )
    current.update(resolution.get("current_characteristics", {}))
    resource_states = deepcopy(
        resolution.get("resource_states", projected["resource_states"])
    )
    _sync_resources(current, resource_states)
    if current_characteristics is not None:
        current = dict(current_characteristics)
        _sync_resources(current, resource_states)
    inverse = resolution.get("inverse_operations", inverse)
    ranges = resolution.get("gear_operation_ranges", projected["gear_operation_ranges"])
    old_physical = physical_sheet_entries(
        current_character, old_blob, criterion_context
    )
    old_uids = {row["uid"] for row in old_physical}
    owned = {row["uid"]: row for row in character.get("inventory_items", [])}
    selected = [dict(uid=row["uid"], slot=row["slot"]) for row in physical]
    pending = [row for row in physical if row["uid"] not in old_uids]
    if not pending:
        return
    proposed, _, _, _ = _projection(
        character,
        selected,
        criterion_context=criterion_context,
        native_baseline=native_baseline,
        build_index=build_index,
        include_consumable_buffs=include_consumable_buffs,
    )
    # Validate every predicate before exploring order; malformed or unsupported
    # branches remain errors rather than becoming a search alternative.
    import ast
    from .combat_local_criteria import parse_local_criterion
    from wakfu_server.combat_characteristic_conditions import native_aliases

    aliases = native_aliases()
    dependencies = set()
    candidates = []
    rows = native_rows()
    for entry in sorted(pending, key=lambda row: row["slot"]):
        item = owned[entry["uid"]]
        criterion = _condition(item)
        if criterion:
            evaluate(
                criterion,
                item=item,
                selected=selected,
                owned=owned,
                criterion_context=criterion_context,
                current_characteristics=current,
                maximum_characteristics=_maxima(current, resource_states),
            )
            for node in ast.walk(parse_local_criterion(criterion)):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id
                    in ("GetCharac", "GetCharacMax", "GetCharacteristicMax")
                ):
                    dependencies.add(aliases[node.args[0].value.upper()]["id"])
        operations = []
        # Physical validation guarantees one candidate per slot, so each old
        # slot's recorded inverse can occur only once in an addition sequence.
        for old in old_physical:
            if old["slot"] == entry["slot"] and old["uid"] not in resolution.get(
                "removed_uids", ()
            ):
                start, end = ranges.get(old["uid"], (0, 0))
                for index in range(start, end):
                    operation = inverse[index]
                    if operation is not None:
                        operations.append(
                            (
                                "remove",
                                operation["stat"]
                                if isinstance(operation, dict)
                                else operation[0],
                                operation,
                            )
                        )
        start, end = proposed["gear_operation_ranges"].get(entry["uid"], (0, 0))
        for index in range(start, end):
            operation = proposed["stat_operations"][index]
            operations.append(("apply", index, operation))
        candidates.append((item, criterion, operations))

    dependencies = tuple(sorted(dependencies))
    failed = set()

    resource_dependencies = tuple(
        identity for identity in dependencies if identity in resource_states
    )

    def resource_key(states):
        return tuple(
            (
                identity,
                tuple(
                    states[identity][field]
                    for field in (
                        "raw_minimum",
                        "raw_maximum",
                        "current",
                        "percentage",
                        "hard_minimum",
                        "hard_maximum",
                    )
                ),
            )
            for identity in resource_dependencies
        )

    def admit(mask, values, states):
        if not mask:
            return True
        key = (
            mask,
            tuple(values[identity] for identity in dependencies),
            resource_key(states),
        )
        if key in failed:
            return False
        branches = []
        for index, (item, criterion, operations) in enumerate(candidates):
            bit = 1 << index
            if not mask & bit:
                continue
            if criterion and not evaluate(
                criterion,
                item=item,
                selected=selected,
                owned=owned,
                criterion_context=criterion_context,
                current_characteristics=values,
                maximum_characteristics=_maxima(values, states),
            ):
                continue
            after = dict(values)
            after_states = deepcopy(states)
            for direction, index, operation in operations:
                if direction == "remove" and isinstance(operation, dict):
                    from .equipment_resource_projection import remove_operation

                    after_states[index] = remove_operation(
                        after_states[index], operation
                    )
                    continue
                identity, amount, subtract = operation
                if direction == "apply" and identity in after_states:
                    from .equipment_resource_bonuses import apply as apply_resource

                    kind = proposed["resource_kinds"].get(index)
                    if kind is None:
                        raise ValueError(
                            "Missing resource metadata for equipment addition"
                        )
                    after_states[identity], _ = apply_resource(
                        after_states[identity], amount, subtract, kind
                    )
                elif identity in after:
                    after[identity] = apply_scalar(
                        after[identity], rows[identity], amount, subtract
                    )
            _sync_resources(after, after_states)
            if all(
                after[identity] == values[identity] for identity in dependencies
            ) and resource_key(after_states) == resource_key(states):
                # This eligible addition cannot affect any remaining predicate.
                # Moving it first preserves every legal ordering and avoids
                # enumerating permutations of unrelated equipment.
                accepted = admit(mask ^ bit, after, after_states)
                if not accepted:
                    failed.add(key)
                return accepted
            branches.append((bit, after, after_states))
        for bit, after, after_states in branches:
            if admit(mask ^ bit, after, after_states):
                return True
        failed.add(key)
        return False

    # A full-sheet request has no click-order field. Search for any legal
    # incremental sequence, preserving native clipping in each branch. A failed
    # greedy prefix must not reject a different valid order.
    if not admit((1 << len(candidates)) - 1, current, resource_states):
        raise ValueError(
            "Native equipment EQUIP pre-application criteria are not satisfied"
        )


def physical_sheet_entries(character, blob, criterion_context):
    from .equipment import physical_sheet

    return physical_sheet(
        character,
        blob,
        criterion_context=criterion_context,
        ignore_ineligible=(
            criterion_context is not None
            and criterion_context.get("actor_kind") == "native_companion_npc"
        ),
    )
