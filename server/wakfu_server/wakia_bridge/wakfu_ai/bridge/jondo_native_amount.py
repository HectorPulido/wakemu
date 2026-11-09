"""Stateless native base/healing descriptors, evaluated only by candidate context."""
from collections.abc import Mapping


def project_native_amount(effect, level, *, source_binding_known=False):
    """Keep evaluated percentages, not a flat value for one current target.

    The consumer resolves kind1..6 against CURRENT simulated HP1 values, using
    native signed-int32 multiplication, float32 and stochastic outcomes. No
    authoritative rounding sample or native action is evaluated here.
    """
    from wakfu_server.combat_damage_parameters import damage_parameter_specification
    from wakfu_server.combat_damage_contracts import DAMAGE_FAMILIES, HEAL_ELEMENTS

    family = effect["effect_class"]
    healing = family in HEAL_ELEMENTS
    if family not in DAMAGE_FAMILIES and not healing:
        raise ValueError("Native amount requires a damage/healing family")
    if family == 24:
        raise ValueError("Native life-steal requires authoritative triggering context")
    specification = damage_parameter_specification(effect["parameters"], level)
    kind, value = specification["base_kind"], specification["base"]
    if not healing and not kind and value < 0:
        raise ValueError("Unsupported negative native damage parameter")
    result = dict(
        # Old consumers see no invented flat percent or Light-healing amount.
        amount=0 if kind or healing else value,
        nativeBase=dict(
            version=1,
            kind=kind,
            value=value,
            sourceBindingKnown=(
                source_binding_known is True
                and effect.get("application_flag") == "NONE"
            ),
        ),
        nativeCoefficientMask=specification["coefficient_mask"],
        nativeDamageFlags=list(effect.get("native_effect_flags", ())),
        nativeLocalization=bool(effect.get("native_localization_enabled", False)),
    )
    if healing:
        result["nativeHealing"] = dict(version=1, element=HEAL_ELEMENTS[family])
    return result


def legacy_heal_fallback(effect, descriptor, *, source_known, conditional, eligibility):
    """Preserve only the pre-existing classic non-Light semantic estimate.

    This is the legacy approximation, not new native amount authority. Unknown
    percentage/Light contexts remain typed and closed; proven guards stay typed.
    """
    return (
        effect.get("effect_class") in (25, 259, 253, 258, 251)
        and descriptor["nativeBase"]["kind"] == 0
        and (not source_known or (conditional and not eligibility))
    )


def source_binding_proof(effects, roots, level, *, max_nodes=128):
    """Conservative AND of bounded ancestry paths, not a context interpreter.

    Direct immediate NONE roots preserve the spell caster. Audited class330
    preserves it when native actor_rebind is zero; cell branches additionally
    need an actual point/fcE aim. Other parents, retained triggers, application
    flags and transmitted level overrides remain unproved.
    """
    from wakfu_server.combat_definitions import effect_profile
    from wakfu_server.combat_effect_groups import decode_group_mode
    from wakfu_server.combat_effect_targets import native_selector_policy

    all_relations = frozenset(("self", "ally", "enemy"))
    pending, visited, result = (
        [(reference, True, all_relations) for reference in roots],
        set(),
        {},
    )
    exhausted = False
    while pending:
        if len(visited) % 16 == 0:
            from ..native.native_deadline import check

            check()
        reference, inherited, allowed = pending.pop()
        effect = effects.get(str(reference))
        if not isinstance(effect, Mapping) or effect.get("variant") != 0:
            continue
        if (
            not effect.get("minimum_level", -32768)
            <= level
            <= effect.get("maximum_level", 32767)
        ):
            continue
        if reference not in result and len(result) >= max_nodes:
            exhausted = True
            break
        masks = effect.get("target_masks")
        immediate = (
            isinstance(masks, (list, tuple))
            and len(masks) == 7
            and not any(masks[index] for index in (0, 1, 3, 4, 5))
        )
        try:
            relations = native_selector_policy(effect)["relations"]
        except (ValueError, TypeError, KeyError):
            relations, inherited = all_relations, False
        known = (
            inherited
            and immediate
            and effect.get("application_flag") == "NONE"
            and relations <= allowed
        )
        result[reference] = result.get(reference, True) and known
        marker = reference, known, allowed
        if marker in visited:
            continue
        visited.add(marker)
        child_known = False
        if known and effect.get("effect_class") == 330:
            try:
                flags = effect.get("native_effect_flags")
                profile = effect_profile(effect, level)
                raw = effect["parameters"]
                mode = decode_group_mode(
                    profile["parameters"],
                    raw_target_parameter=raw[4] if len(raw) >= 6 else None,
                )
                selector = effect.get("native_target_selector")
                same_cell = (
                    effect.get("area_class") == "anD"
                    and effect.get("area_native") == "point"
                    and isinstance(selector, Mapping)
                    and selector.get("class") == "fcE"
                    and type(selector.get("mask")) is int
                    and bool(selector["mask"] & 1)
                )
                child_known = (
                    mode.actor_rebind == 0
                    and same_cell
                    and isinstance(flags, (list, tuple))
                    and 16 not in flags
                    and profile["probability"] == 100
                    and not selector["mask"] & ~(1 | 2 | 4 | 8 | 128 | 256)
                )
            except (ValueError, TypeError, KeyError, IndexError):
                child_known = False
        pending.extend(
            (child, child_known, allowed & relations)
            for child in effect.get("children", ())
        )
    if exhausted:
        return {reference: False for reference in result}
    return result


def health_eligibility_proof(effects, roots, level, bindings, *, max_nodes=128):
    """Recognize only inherited not-carried guards with the SAME recipient.

    Point/fcE/area anchors and parent relation supersets are required on every
    path. This is one audited predicate, never a general criterion evaluator.
    """
    import re
    from wakfu_server.combat_effect_targets import native_selector_policy

    all_relations = frozenset(("self", "ally", "enemy"))
    pending = [(reference, 0, all_relations) for reference in roots]
    seen, result, references = set(), {}, set()
    while pending:
        if len(seen) % 16 == 0:
            from ..native.native_deadline import check

            check()
        reference, inherited, allowed = pending.pop()
        if len(seen) >= max_nodes * 4:
            return {}
        effect = effects.get(str(reference))
        if (
            not isinstance(effect, Mapping)
            or effect.get("variant") != 0
            or not effect.get("minimum_level", -32768)
            <= level
            <= effect.get("maximum_level", 32767)
        ):
            continue
        references.add(reference)
        if len(references) > max_nodes:
            return {}
        selector = effect.get("native_target_selector")
        try:
            policy = native_selector_policy(effect)
            relations = policy["relations"]
            scope = (
                bindings.get(reference) is True
                and isinstance(selector, Mapping)
                and policy["in_area"] is True
                and effect.get("area_class") == "anD"
                and effect.get("area_native") == "point"
                and relations <= allowed
                and type(selector.get("mask")) is int
                and not selector["mask"] & ~(1 | 2 | 4 | 8 | 128 | 256)
            )
        except (ValueError, KeyError, TypeError):
            relations, scope = all_relations, False
        raw_criterion = effect.get("criteria")
        criterion = raw_criterion.strip() if type(raw_criterion) is str else ""
        state = inherited
        if raw_criterion is not None and type(raw_criterion) is not str:
            state = 2
        if criterion:
            recognized = re.fullmatch(
                r"""not\s+IsCarried\(\s*["']target["']\s*\)""", criterion
            )
            state = 1 if recognized and inherited != 2 else 2
        if not scope:
            state = 2
        result[reference] = result.get(reference, True) and state == 1 and scope
        marker = reference, state, allowed
        if marker in seen:
            continue
        seen.add(marker)
        pending.extend(
            (child, state, allowed & relations) for child in effect.get("children", ())
        )
    return result


def protect_health_geometry(area, in_area):
    """Old readers clamp amount0 to1: hide ALL recipient geometry from them."""
    if type(in_area) is not bool:
        raise ValueError("Typed native health requires explicit selector geometry")
    return dict(
        fixedCells=[],
        nativeHealthGeometry=dict(version=1, nativeInArea=in_area, **area),
    )


def advisory_area_row(row):
    """Restore a private area view only for recognized typed health metadata."""
    if "nativeHealthGeometry" not in row:
        return row
    base, healing, geometry = (
        row.get(key) for key in ("nativeBase", "nativeHealing", "nativeHealthGeometry")
    )
    if (
        not isinstance(base, dict)
        or type(base.get("version")) is not int
        or base["version"] != 1
        or type(base.get("kind")) is not int
        or base["kind"] not in range(7)
        or base.get("sourceBindingKnown") is not True
        or type(base.get("value")) is not int
        or not -(1 << 31) <= base["value"] < (1 << 31)
        or type(row.get("nativeCoefficientMask")) is not int
        or row["nativeCoefficientMask"] not in range(4)
        or not isinstance(row.get("nativeDamageFlags"), (list, tuple))
        or any(type(flag) is not int for flag in row["nativeDamageFlags"])
        or not isinstance(geometry, dict)
        or type(geometry.get("version")) is not int
        or geometry["version"] != 1
        or type(geometry.get("nativeInArea")) is not bool
        or type(geometry.get("nativeAreaCenterOnCaster")) is not bool
        or type(geometry.get("nativeAreaUseTargetRadius")) is not bool
        or geometry["nativeAreaCenterOnCaster"] == geometry["nativeAreaUseTargetRadius"]
    ):
        return None
    if row.get("kind") == "heal":
        if (
            not isinstance(healing, dict)
            or type(healing.get("version")) is not int
            or healing["version"] != 1
            or type(healing.get("element")) is not int
            or healing["element"] not in range(1, 7)
        ):
            return None
    elif row.get("kind") != "damage" or healing is not None:
        return None
    fixed = geometry.get("fixedCells")
    if (
        not isinstance(fixed, (list, tuple))
        or len(fixed) > 4096
        or any(
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(
                type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                for value in point
            )
            for point in fixed
        )
    ):
        return None
    restored = dict(
        row, **{key: value for key, value in geometry.items() if key != "version"}
    )
    if "nativeDirectionalArea" in restored:
        from .jondo_area import directional_geometry

        if directional_geometry(restored) is None:
            return None
    return restored
