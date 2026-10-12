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
        match := re.fullmatch(
            r"cross-h(-?\d+)b(-?\d+)-g(-?\d+)d(-?\d+)", description or ""
        )
    ):
        # anw.bEj=true: arms stay in world XY independently of direction
        # and owner reference. Native p/bEl includes the center even when
        # an arm length is negative; its positive-index loop is then empty.
        return frozenset(
            {(0, 0)}
            | {
                (dx * n, dy * n)
                for length, (dx, dy) in zip(
                    map(int, match.groups()), ((1, 0), (-1, 0), (0, -1), (0, 1))
                )
                for n in range(1, length + 1)
            }
        )
    elif kind == "anx" and (
        match := re.fullmatch(
            r"crossDiag-h(-?\d+)b(-?\d+)-g(-?\d+)d(-?\d+)", description or ""
        )
    ):
        # anx.bEj=true: even unequal arms are fixed XY diagonals, not rotated.
        return frozenset(
            {(0, 0)}
            | {
                (dx * n, dy * n)
                for length, (dx, dy) in zip(
                    map(int, match.groups()), ((-1, -1), (1, 1), (-1, 1), (1, -1))
                )
                for n in range(1, length + 1)
            }
        )
    else:
        raise UnsupportedEffectArea(f"Unaudited effect area: {kind}/{description}")
    return frozenset(
        (x, y)
        for x in range(-high, high + 1)
        for y in range(-high, high + 1)
        if low <= abs(x) + abs(y) <= high
    )


from .combat_effect_area_targets import target_available


def target_relation(caster, target):
    """Distinct relations: allies exclude the caster; IDs establish self."""
    if target.id == caster.id:
        return "self"
    return "ally" if target.team == caster.team else "enemy"


def select_effect_targets(
    effect,
    caster,
    center,
    actors,
    *,
    relations,
    orientation=None,
    native_radius=False,
    available=None,
):
    """Select living actors in an audited area under an explicit policy.

    Empty centers are valid: a point then selects no actor, while an area
    can select surrounding actors. Cell effects are not invented as actors.
    """
    relations = frozenset(relations)
    if not relations <= {"self", "ally", "enemy"}:
        raise ValueError("Unknown target relation")
    available = target_available if available is None else available
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
        # amQ with a selector calls anc.b/amX.a with amP.bcL, including
        # isotropic point/circle/ring/cross shapes. Null-selector anc.a uses
        # centre membership only; preserve that separate native route.
        radius = getattr(actor, "physical_radius", None) if native_radius else 0
        if type(radius) is not int or not -128 <= radius <= 127:
            raise ValueError(
                "Native area membership requires signed-byte physical radius"
            )
        radius = max(0, radius)
        x, y = actor.position[0] - center[0], actor.position[1] - center[1]
        return any(
            (x + dx, y + dy) in offsets
            for dx in range(-radius, radius + 1)
            for dy in range(-radius, radius + 1)
        )

    return tuple(
        actor
        for actor in actors
        if available(actor)
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
        | 16
        | 32
        | 64
        | 128
        | 256
        | 4096
        | 16384
        | 8192
        | (1 << 34)
        | (1 << 40)
        | (1 << 41)
        | (1 << 42)
        | (1 << 43)
        | (1 << 44)
        | (1 << 45)
        | (1 << 46)
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


def _native_target_valid(mask, caster, actor, contexts, *, include_fah=True):
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
    # fcE uses Sn()>0, not PLAYER_CHARACTER; positive summons also qualify.
    if mask & 16 and (not value("is_eGj") or actor.id <= 0):
        return False
    # fcE bit41 requires an actual eGj with Sn() <= 0.
    if mask & (1 << 41) and (not value("is_eGj") or actor.id > 0):
        return False
    # eGj.baF is fdy IN_PLAY membership, distinct from a raw HP field.
    if mask & (1 << 40) and (not value("is_eGj") or not value("baF")):
        return False
    if mask & (1 << 42) and (
        not source_value("is_eGj") or actor.id != source_value("dpu_id")
    ):
        return False
    if mask & (1 << 45) and (
        not source_value("is_eGj") or actor.id != source_value("dpr_id")
    ):
        return False
    if mask & (1 << 34):
        if not source_value("is_eGj"):
            return False
        if value("is_eGj") and value("dTE") and value("dpu_id") == caster.id:
            return False  # Native exclusion is own summons, not every summon.
    if mask & 32 and (not value("is_eGj") or not value("dTE")):
        return False
    if mask & (1 << 44) and (not value("is_eGj") or value("dTE")):
        return False  # fcE requires an actual eGj which is not a summon.
    if mask & 4096:
        if not value("is_eGj") or not value("dTE"):
            return False
        if value("dpu_id") != caster.id or value("baG") or value("baK"):
            return False
    if mask & 16384:
        if not value("is_eGj") or not value("baG"):
            return False  # fcE requires target eGj.baG(); distinct from bit4096.
    if mask & (1 << 47) and not value("is_eGj"):
        return False
    if mask & (1 << 43):
        if not value("is_Qq"):
            return False
        # A native Qq can have a proven NULL owner (e.g. faP border).
        if "q_owner_id" not in target:
            raise UnsupportedTargetSelector("Missing native Qq target owner")
        owner = target["q_owner_id"]
        if owner is not None and (
            type(owner) is not int or not -(1 << 63) <= owner < (1 << 63)
        ):
            raise UnsupportedTargetSelector("Invalid native Qq target owner")
        if owner != caster.id:
            return False
    if mask & (1 << 46):
        if not source_value("is_Qq"):
            return False
        # Qq.bch is the direct native owner pointer, not an owner chain.
        if "q_owner_id" not in source:
            raise UnsupportedTargetSelector("Missing native Qq source owner")
        owner = source["q_owner_id"]
        if owner is not None and (
            type(owner) is not int or not -(1 << 63) <= owner < (1 << 63)
        ):
            raise UnsupportedTargetSelector("Invalid native Qq source owner")
        if owner != actor.id:
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
    if (
        include_fah
        and actor.id != caster.id
        and value("is_eHH")
        and not mask & 8192
        and value("buX")
    ):
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
            # faH enumerates the supplied PV collection and applies fcE;
            # eZR.i owns the later corpse gate. HP is not that collection.
            available=lambda _actor: True,
        )
    else:
        candidates = tuple(
            actor
            for actor in actors
            if target_relation(caster, actor) in policy["relations"]
        )
    return tuple(
        actor
        for actor in candidates
        if _native_target_valid(mask, caster, actor, native_context)
    )
