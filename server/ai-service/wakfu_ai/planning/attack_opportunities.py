"""Cheap advisory move-then-cast opportunities; native previews decide legality."""

from ..native.native_deadline import check

_MAX_PROFILES = 32
_MAX_COMPARISONS = 4096
_MAX_ROUTES = 8


def _roles(spell, evidence):
    key = (spell.get("spellId"), spell.get("level"))
    roles = set(evidence.get(key, ()))
    hint = spell.get("advisoryCapabilities")
    if (
        isinstance(hint, dict)
        and type(hint.get("spellId")) is int
        and type(hint.get("level")) is int
        and (hint["spellId"], hint["level"]) == key
        and isinstance(hint.get("tags"), list)
    ):
        roles.update(tag for tag in hint["tags"] if isinstance(tag, str))
    if "heal" in roles:
        roles.add("healing")
    if "armor" in roles:
        roles.add("protection")
    return roles


def _alignment(record):
    # A known enabled flag can prefer its alignment even when the other
    # flag is unavailable. Unknown alternatives still survive in the full
    # movement stream; neither flag establishes native cast legality.
    linear, diagonal = record.get("linear"), record.get("diagonal")
    if linear is True or diagonal is True:
        return linear is True, diagonal is True
    return None


def _matches(position, target, profiles):
    dx, dy = abs(position[0] - target[0]), abs(position[1] - target[1])
    for minimum, maximum, alignment in profiles:
        if not minimum <= dx + dy <= maximum:
            continue
        if alignment is None or alignment == (False, False):
            return True
        linear, diagonal = alignment
        if (linear and (dx == 0 or dy == 0)) or (diagonal and dx == dy):
            return True
    return False


def attack_opportunity_routes(
    routes,
    actors,
    actor_id,
    spells,
    *,
    range_hints,
    capability_evidence=None,
    route_priority,
):
    """Offer up to eight complete native-edge routes opening a useful cast.

    The caller keeps every original route and skips this preference when
    retreating or holding position. Only observed/advisory capabilities and
    actual owned spell range hints contribute; unknown metadata fails open
    through the original stream. XY range/alignment are ordering hints only:
    heights, LOS, target criteria, costs and effects require native preview.

    ``route_priority`` is the existing navigation tuple with hazard exposure
    first. Suggestions never promote a greater-exposure route ahead of the
    lowest-exposure alternatives. Work stops after a fixed advisory comparison
    budget; this does not remove any route from the caller's original stream.
    """
    check()
    source = actors.get(actor_id)
    if not source or not routes:
        return ()
    evidence = capability_evidence or {}
    profiles = []
    seen = set()
    for spell in spells:
        check()
        ranges = range_hints(spell)
        roles = _roles(spell, evidence)
        hostile = bool(roles & {"damage", "control"})
        support = bool(roles & {"healing", "protection"})
        if not ranges or not (hostile or support):
            continue
        casting = spell.get("casting") or {}
        conditional = casting.get("conditional")
        records = [casting] + (conditional if isinstance(conditional, list) else [])
        branches = tuple(
            (
                minimum,
                maximum,
                _alignment(records[i])
                if i < len(records) and isinstance(records[i], dict)
                else None,
            )
            for i, (minimum, maximum) in enumerate(ranges)
        )
        descriptor = (branches, hostile, "healing" in roles, "protection" in roles)
        if descriptor not in seen:
            seen.add(descriptor)
            profiles.append(descriptor)
            if len(profiles) == _MAX_PROFILES:
                break
    if not profiles:
        return ()
    safe_routes = []
    least_exposure = None
    for index, route in enumerate(routes):
        if index % 256 == 0:
            check()
        priority = route_priority(route)
        if least_exposure is None or priority[0] < least_exposure:
            least_exposure = priority[0]
            safe_routes = [(priority, route)]
        elif priority[0] == least_exposure:
            safe_routes.append((priority, route))
    check()
    targets = sorted(actors.values(), key=lambda actor: actor["id"])
    check()
    selected = {}
    comparisons = 0
    for branches, hostile, healing, protection in profiles:
        check()
        for target_index, target in enumerate(targets):
            if target_index % 256 == 0:
                check()
            if target["id"] == actor_id or target["hp"] <= 0:
                continue
            enemy = target["team"] != source["team"]
            useful = (
                hostile
                if enemy
                else (protection or (healing and target["hp"] < target["max_hp"]))
            )
            if not useful or _matches(source["position"], target["position"], branches):
                continue
            best = None
            for priority, route in safe_routes:
                if comparisons % 256 == 0:
                    check()
                if comparisons >= _MAX_COMPARISONS:
                    return tuple(sorted(selected, key=lambda route: selected[route]))
                comparisons += 1
                if _matches(route[-1], target["position"], branches):
                    candidate = (priority, route)
                    if best is None or candidate < best:
                        best = candidate
            if best is not None:
                priority, route = best
                selected[route] = priority
                if len(selected) == _MAX_ROUTES:
                    return tuple(sorted(selected, key=lambda route: selected[route]))
    check()
    return tuple(sorted(selected, key=lambda route: selected[route]))
