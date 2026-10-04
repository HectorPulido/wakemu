"""Audited XY areas and explicit runtime target policies.

Native proof: anD/anu/anw/anH.bEl and amX.a use XY offsets; short Z
arguments do not participate in membership. Policies are supplied by the
caller: neither eVn.aZR (catalogue 'variant') nor seven target_masks are
translated here. The latter also contain event/state filters.
"""
import re
from .combat_area_geometry import (
    native_area_shape,
    oriented_area_offsets,
    native_area_contains,
)


class UnsupportedEffectArea(ValueError):
    pass


def area_offsets(effect, *, origin=None, reference=None, direction=None):
    """Return audited isotropic native offsets; reject unknown geometry."""
    kind, description = effect.get("area_class"), effect.get("area_native")
    shape = native_area_shape(effect)
    if shape is not None:
        if shape[1]:
            return frozenset(shape[0])
        if origin is None or reference is None:
            raise UnsupportedEffectArea(
                "Native directional area requires origin/reference"
            )
        return frozenset(
            oriented_area_offsets(
                effect, origin=origin, reference=reference, direction=direction
            )
        )
    if (kind, description) == ("anD", "point"):
        return frozenset({(0, 0)})
    if (kind, description) == ("anA", "empty"):
        return frozenset()
    if kind == "anu" and (match := re.fullmatch(r"circle-(\d+)", description or "")):
        low, high = 0, int(match[1])
    elif kind == "anH" and (
        match := re.fullmatch(r"ring-(\d+)-(\d+)", description or "")
    ):
        low, high = sorted((int(match[1]), int(match[2])))
    elif kind == "any" and (
        match := re.fullmatch(r"crossRing-(\d+)-(\d+)", description or "")
    ):
        low, high = sorted(map(int, match.groups()))
        return frozenset(
            (x, y)
            for n in range(low, high + 1)
            for x, y in ((0, -n), (0, n), (n, 0), (-n, 0))
        )
    elif kind == "anw" and (
        match := re.fullmatch(r"cross-h(\d+)b(\d+)-g(\d+)d(\d+)", description or "")
    ):
        lengths = tuple(map(int, match.groups()))
        if len(set(lengths)) != 1:
            raise UnsupportedEffectArea("Asymmetric cross needs native rotation")
        radius = lengths[0]
        return frozenset(
            {(n, 0) for n in range(-radius, radius + 1)}
            | {(0, n) for n in range(-radius, radius + 1)}
        )
    else:
        raise UnsupportedEffectArea(f"Unaudited effect area: {kind}/{description}")
    return frozenset(
        (x, y)
        for x in range(-high, high + 1)
        for y in range(-high, high + 1)
        if low <= abs(x) + abs(y) <= high
    )


def target_relation(caster, target):
    """Distinct relations: allies exclude the caster; IDs establish self."""
    if target.id == caster.id:
        return "self"
    return "ally" if target.team == caster.team else "enemy"


def select_effect_targets(
    effect, caster, center, actors, *, relations, orientation=None, native_radius=False
):
    """Select living actors in an audited area under an explicit policy.

    Empty centers are valid: a point then selects no actor, while an area
    can select surrounding actors. Cell effects are not invented as actors.
    """
    relations = frozenset(relations)
    if not relations <= {"self", "ally", "enemy"}:
        raise ValueError("Unknown target relation")
    shape = native_area_shape(effect)
    offsets = None if shape is not None else area_offsets(effect)

    def inside(actor):
        if shape is not None:
            return native_area_contains(
                effect,
                origin=center,
                reference=caster.position if orientation is None else orientation,
                point=actor.position,
                direction=getattr(caster, "direction", None),
                radius=getattr(actor, "physical_radius", None) if native_radius else 0,
            )
        return (actor.position[0] - center[0], actor.position[1] - center[1]) in offsets

    return tuple(
        actor
        for actor in actors
        if actor.hp > 0
        and inside(actor)
        and target_relation(caster, actor) in relations
    )


class UnsupportedTargetSelector(ValueError):
    pass


def native_selector_policy(effect):
    """Decode proven fcE flags; unknown predicates remain explicit blockers.

    fcE.a returns VALID without flag1, so even an empty native area can
    target self (mask2). Null selector instead uses the area via amQ.a.
    Missing export metadata is unknown, never equivalent to null.
    """
    if "native_target_selector" not in effect:
        raise UnsupportedTargetSelector("Missing native target selector metadata")
    selector = effect["native_target_selector"]
    if selector is None:
        return dict(relations=frozenset({"self", "ally", "enemy"}), in_area=True)
    if selector.get("class") != "fcE" or type(selector.get("mask")) is not int:
        raise UnsupportedTargetSelector(f"Unknown native target selector: {selector}")
    mask = selector["mask"]
    known_flags = (
        1
        | 2
        | 4
        | 8
        | 32
        | 64
        | 128
        | 256
        | 4096
        | 8192
        | (1 << 47)
        | (1 << 49)
        | (1 << 50)
        | (1 << 51)
    )
    if mask < 0 or mask & ~known_flags:
        raise UnsupportedTargetSelector(
            f"Unaudited native target selector flags: {mask & ~known_flags}"
        )
    relations = {"self", "ally", "enemy"}
    if mask & 2:
        relations &= {"self"}
    if mask & 256:
        relations -= {"self"}
    if mask & 4:
        relations &= {"self", "ally"}
    if mask & 8:
        relations &= {"enemy"}
    if mask & 128:
        relations &= {"ally"}
    return dict(relations=frozenset(relations), in_area=bool(mask & 1))


def _native_value(context, key):
    if key not in context or context[key] is None:
        raise UnsupportedTargetSelector(
            f"Missing actor native targeting context: {key}"
        )
    return context[key]


def _native_target_valid(mask, caster, actor, contexts):
    """fcE + faH predicates, with exact native-method context names."""
    try:
        target = contexts[actor.id]
        source = contexts[caster.id]
    except (KeyError, TypeError):
        raise UnsupportedTargetSelector(
            "Missing native context for caster or target"
        ) from None
    value = lambda key: _native_value(target, key)
    source_value = lambda key: _native_value(source, key)
    if mask & (4 | 8 | 128) and (not value("is_amO") or not source_value("is_amO")):
        return False
    if mask and not value("bEe"):
        return False  # eGj.bEe = !CANNOT_BE_EFFECT_TARGET (native property42).
    if mask & 64 and not value("is_Qq"):
        return False
    if mask & 32 and (not value("is_eGj") or not value("dTE")):
        return False
    if mask & 4096:
        if not value("is_eGj") or not value("dTE"):
            return False
        if value("dpu_id") != caster.id or value("baG") or value("baK"):
            return False
    if mask & (1 << 47) and not value("is_eGj"):
        return False
    if mask & (1 << 49) and value("is_Qq"):
        return False
    if mask & (1 << 50) and value("bcN") < 0:
        return False
    if mask and not mask & (1 << 51) and value("is_Qq") and not value("bcR"):
        return False
    if (
        mask & 1
        and source_value("is_eGj")
        and value("is_eGj")
        and value("UNTARGETTABLE_BY_OTHER")
    ):
        return False  # fcE does not exempt self from this predicate.
    if actor.id != caster.id and value("is_eHH") and not mask & 8192 and value("buX"):
        return False  # faH filtering after selection; meaning kept native.
    return True


def select_native_effect_targets(
    effect, caster, center, actors, *, native_context=None
):
    """Select targets using native fcE predicates and explicit actor context.

    native_context maps actor IDs to audited native properties. Missing
    properties raise UnsupportedTargetSelector; actor types/states are never
    inferred from IDs, teams or an absent status collection.
    """
    policy = native_selector_policy(effect)
    selector = effect["native_target_selector"]
    mask = 0 if selector is None else selector["mask"]
    actors = tuple(actors)
    if policy["in_area"]:
        candidates = select_effect_targets(
            effect,
            caster,
            caster.position if selector is None else center,
            actors,
            relations=policy["relations"],
            orientation=center if selector is None else caster.position,
            native_radius=selector is not None,
        )
    else:
        candidates = tuple(
            actor
            for actor in actors
            if actor.hp > 0 and target_relation(caster, actor) in policy["relations"]
        )
    return tuple(
        actor
        for actor in candidates
        if _native_target_valid(mask, caster, actor, native_context)
    )
