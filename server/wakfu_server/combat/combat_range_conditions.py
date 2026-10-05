"""Native eLB totals and eKf/eKn range counts over explicit owned facts."""
from dataclasses import dataclass
from .combat_parameters import _float32


def total_hp_percent(current, maxima):
    """eLB: Java int sums, then float32 ratio*100; no floor or cap."""
    total = maximum = 0
    for key in ("HP", "VIRTUAL_HP"):
        if key not in current or key not in maxima:
            raise ValueError("Missing native total HP characteristic snapshot")
        if type(current[key]) is not int or type(maxima[key]) is not int:
            raise ValueError("Invalid native total HP characteristic snapshot")
        total = ((total + current[key] + 2**31) % 2**32) - 2**31
        maximum = ((maximum + maxima[key] + 2**31) % 2**32) - 2**31
    if maximum == 0:
        return 0.0
    return float(_float32(_float32(_float32(total) / _float32(maximum)) * 100.0))


@dataclass(frozen=True)
class RangeFighter:
    position: tuple
    physical_radius: int
    affiliation: int
    in_play: bool
    excluded_property: bool
    carried_barrel: bool
    timeline_excluded: bool = False
    states: tuple = ()  # (reference, exact level, native caster ID), registered Qf carriers only.
    breed_id: int | None = None  # Exact native eGj.aXA signed short; unknown is not0.


def range_count(
    rows,
    *,
    affiliation,
    center,
    minimum,
    maximum,
    aligned=False,
    los=False,
    visible=None,
    relation="enemy",
    in_play=True,
    state_reference=None,
    state_level=-1,
    state_caster=None
):
    """eKf filters opposing/inPlay/not carried barrel; eKn filters42/range."""
    if center is None:
        return 0
    if type(affiliation) is not int or not -128 <= affiliation < 128:
        raise ValueError("Missing native range caster affiliation")
    if not isinstance(rows, tuple) or any(
        not isinstance(row, RangeFighter) for row in rows
    ):
        raise ValueError("Missing complete native range fighter roster")
    if (
        any(type(v) is not int for v in (minimum, maximum))
        or type(aligned) is not bool
        or type(los) is not bool
    ):
        raise ValueError("Invalid native range parameters")
    count = 0
    for row in rows:
        if (
            any(
                type(v) is not bool
                for v in (
                    row.excluded_property,
                    row.carried_barrel,
                    row.timeline_excluded,
                )
            )
            or ((relation == "enemy" or in_play) and type(row.in_play) is not bool)
            or type(row.affiliation) is not int
            or not -128 <= row.affiliation < 128
            or type(row.physical_radius) is not int
            or not 0 <= row.physical_radius <= 127
        ):
            raise ValueError("Missing native range fighter membership/footprint")
        if row.excluded_property:
            continue
        if relation == "enemy" and (
            row.affiliation == affiliation or not row.in_play or row.carried_barrel
        ):
            continue
        if relation == "ally" and (
            row.affiliation != affiliation
            or (in_play and not row.in_play)
            or row.timeline_excluded
            or row.carried_barrel
        ):
            continue
        if relation == "state":
            if in_play and not row.in_play:
                continue
            if not any(
                ref == state_reference
                and (state_level < 0 or level == state_level)
                and (state_caster is None or caster == state_caster)
                for ref, level, caster in row.states
            ):
                continue
        elif relation not in ("enemy", "ally"):
            raise ValueError("Unknown native range candidate filter")
        if maximum > 0:
            distance = sum(
                max(0, abs(a - b) - row.physical_radius)
                for a, b in zip(row.position[:2], center[:2])
            )
            if not minimum <= distance <= maximum:
                continue
            if (
                aligned
                and row.position[0] != center[0]
                and row.position[1] != center[1]
            ):
                continue
            if los:
                if not callable(visible):
                    raise ValueError("Missing native Sf range line of sight")
                result = visible(center, row.position)
                if type(result) is not bool:
                    raise ValueError("Unknown native Sf range line of sight")
                if not result:
                    continue
        count += 1
    return count


def enemy_count(rows, **kwargs):
    return range_count(rows, relation="enemy", **kwargs)


def creation_in_play(preview, actor):
    """Fresh fdy is sax; own lethal damage records departure explicitly.

    Caller must first attest exact native creation or registered summon identity.
    Revival/zero-HP imported actors without this lifecycle remain unknown.
    """
    departed = any(
        row.get("kind") == "death" and row.get("actor_id") == actor.id
        for row in preview.events
    )
    if departed and actor.hp == 0:
        return False
    if not departed and actor.hp > 0:
        return True
    return None  # Only predicates requiring membership reject this unknown fact.


def registered_state_carriers(fight, actor):
    """eLr scans Qf eZk, not pending application descriptors or state levels."""
    from .combat_retained_runtime import native_retained_condition_effects

    registered = {
        uid
        for _, family, uid in native_retained_condition_effects(fight, actor.id)
        if family == 310
    }
    return tuple(
        (state.reference, state.level, state.caster_id)
        for state in actor.state_ledger.entries
        if state.uid in registered
    )


def attest_state_area_population(fight):
    """eLr appends actual Qs/Qq Qf managers, independently of fighters."""
    from .combat_effect_area_queries import _rows
    from .combat_effect_area import native_effect_areas
    from .combat_state_managers import state_manager

    result = []
    for row in _rows(fight):
        if row.get("native_running_effect_manager") is False:
            continue  # Original Qq.bax null: eLr skips this manager.
        if "state_ledger" in row:
            manager = state_manager(fight, row["uid"])
            result.append((manager.position, registered_state_carriers(fight, manager)))
            continue
        definition = native_effect_areas().get(str(row["reference"]))
        if (
            definition is None
            or definition.get("native_hour_contract") is not True
            or definition["effect_ids"]
            or definition["entry_masks"]
            or definition["exit_masks"]
            or row.get("native_state_carriers")
        ):
            raise ValueError("Missing complete native Qq state-manager population")
    return tuple(result)


def area_state_count(
    rows,
    *,
    center,
    minimum,
    maximum,
    reference,
    level=-1,
    caster=None,
    aligned=False,
    los=False,
    visible=None
):
    """eLr→eKn: Qq bcL=0; range/alignment/LOS use actual center coordinates.

    Qs managers are appended regardless of the fighter in-play selector. Their
    state caster filter uses the retained carrier's real source, not area owner.
    """
    if center is None:
        return 0
    count = 0
    for position, states in rows:
        if not any(
            ref == reference
            and (level < 0 or n == level)
            and (caster is None or owner == caster)
            for ref, n, owner in states
        ):
            continue
        if maximum > 0:
            distance = sum(abs(a - b) for a, b in zip(position[:2], center[:2]))
            if not minimum <= distance <= maximum:
                continue
            if aligned and position[0] != center[0] and position[1] != center[1]:
                continue
            if los:
                if not callable(visible):
                    raise ValueError("Missing native Qq range line of sight")
                seen = visible(center, position)
                if type(seen) is not bool:
                    raise ValueError("Unknown native Qq range line of sight")
                if not seen:
                    continue
        count += 1
    return count


def fighters_breed_count(rows, *, center, maximum, breed):
    """eKt: all fUQ actors of exact breed; eKn excludes sem and counts range.

    No HP, affiliation, KO, carried or timeline filter is inherited by eKt.
    Nonpositive radius ignores distance, but still requires a center.
    """
    if type(maximum) is not int or type(breed) is not int:
        raise ValueError("Native breed range requires evaluated long values")
    if not isinstance(rows, tuple) or any(
        not isinstance(r, RangeFighter) for r in rows
    ):
        raise ValueError("Missing complete native breed fighter roster")
    if center is None:
        return 0
    if len(center) != 3 or any(type(v) is not int for v in center):
        raise ValueError("Missing native breed range center position")
    count = 0
    for row in rows:
        if type(row.breed_id) is not int or not -32768 <= row.breed_id < 32768:
            raise ValueError("Missing exact native eGj.aXA breed")
        if row.breed_id != breed:
            continue
        if type(row.excluded_property) is not bool:
            raise ValueError("Missing native sem range property")
        if row.excluded_property:
            continue
        if maximum > 0:
            if (
                type(row.physical_radius) is not int
                or not 0 <= row.physical_radius <= 127
                or len(row.position) != 3
                or any(type(v) is not int for v in row.position)
            ):
                raise ValueError("Missing native breed fighter footprint/position")
            distance = sum(
                max(0, abs(a - b) - row.physical_radius)
                for a, b in zip(row.position[:2], center[:2])
            )
            if distance > maximum:
                continue
        count += 1
    return count


def own_team_state_carriers(states, affiliation, caster_affiliations):
    """eKS.pZW: same affiliation of the Qe.bbb caster, not its recipient."""
    if type(affiliation) is not int or not -128 <= affiliation <= 127:
        raise ValueError("Missing native state-query caster affiliation")
    if not isinstance(caster_affiliations, dict):
        raise ValueError("Missing complete native state caster population")
    result = []
    for row in states:
        reference, level, caster_id = row
        if caster_id is None:
            continue  # Actual null Qe.bbb is not amO.
        if caster_id not in caster_affiliations:
            raise ValueError("Missing registered state caster affiliation")
        team = caster_affiliations[caster_id]
        if type(team) is not int or not -128 <= team <= 127:
            raise ValueError("Invalid registered state caster affiliation")
        if team == affiliation:
            result.append(row)
    return tuple(result)
