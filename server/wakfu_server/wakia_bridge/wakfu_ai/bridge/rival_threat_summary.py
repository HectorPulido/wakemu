"""Bounded optional native repertoire evidence, never cast or damage authority.

The caller must pass only visible actors. Every returned book is bound to this
fight revision; a later grant, resource change or conditional rule requires a
fresh projection. Missing evidence must retain the planner's threat fallback.
"""
import math
import time


def project(
    oracle,
    fight,
    actor,
    visible_actors,
    *,
    deadline,
    max_operations=64,
    max_spells_per_actor=16,
    clock=time.monotonic,
    affiliation=None,
    describe=None,
    casting=None
):
    """Describe owned damaging abilities fairly, without predicting legality.

    ``deadline`` is absolute monotonic time. Limits are cooperative between
    source calls; a synchronous provider cannot be interrupted by this helper.
    A ``complete`` book is still only current owned/static metadata, never proof
    that a future turn can cast, or that a target is in LOS, or an amount of damage.
    """
    if (
        type(max_operations) is not int
        or not 1 <= max_operations <= 4096
        or type(max_spells_per_actor) is not int
        or not 1 <= max_spells_per_actor <= 256
        or type(deadline) not in (int, float)
        or not math.isfinite(deadline)
    ):
        raise ValueError("Invalid rival projection budget")
    if affiliation is None:
        from ..native.native_control import effective_affiliation as affiliation
    if describe is None:
        from wakfu_server.combat_ai_capabilities import describe_spell as describe
    if casting is None:
        from wakfu_server.combat_native_spell_casting import (
            selected_casting_projection as casting,
        )

    own_team = affiliation(fight, actor)
    records, queues = [], []
    for rival in visible_actors:
        if rival.hp <= 0 or affiliation(fight, rival) == own_team:
            continue
        record = dict(actorId=rival.id, complete=False, abilities=[], unknown=[])
        records.append(record)
        queues.append((rival, record, None, 0))
    operations = 0
    # Ownership is read for each rival before any per-spell traversal. This
    # prevents one long book from starving every later visible opponent.
    for index, (rival, record, _, _) in enumerate(queues):
        if operations >= max_operations or clock() >= deadline:
            record["unknown"].append("budget_exhausted")
            continue
        operations += 1
        try:
            owned = oracle.owned_spells(fight, rival.id)
            # The source is synchronous and cannot be preempted. If it
            # returns after the deadline, do not publish a complete book or
            # spend more of the caller's budget classifying its spells.
            if clock() >= deadline:
                record["unknown"].append("budget_exhausted")
                continue
            if not isinstance(owned, dict) or any(
                type(spell) is not int
                or spell <= 0
                or type(level) is not int
                or level < 0
                for spell, level in owned.items()
            ):
                raise ValueError("Invalid owned spell metadata")
            ordered = sorted(owned.items())
            if len(ordered) > max_spells_per_actor:
                record["unknown"].append("book_limit")
            queues[index] = (rival, record, ordered[:max_spells_per_actor], 0)
        except (ValueError, KeyError, TypeError, AttributeError, OSError):
            record["unknown"].append("owned_spell_metadata_unavailable")
    while True:
        pending = [
            index
            for index, (_, _, book, offset) in enumerate(queues)
            if book is not None and offset < len(book)
        ]
        if not pending:
            break
        if operations >= max_operations or clock() >= deadline:
            for index in pending:
                queues[index][1]["unknown"].append("budget_exhausted")
            break
        for index in pending:
            rival, record, book, offset = queues[index]
            if operations >= max_operations or clock() >= deadline:
                break
            spell, level = book[offset]
            queues[index] = (rival, record, book, offset + 1)
            operations += 1
            try:
                capability = describe(spell, level)
                if clock() >= deadline:
                    record["unknown"].append("budget_exhausted")
                    continue
                if not isinstance(capability, dict) or not isinstance(
                    capability.get("tags"), list
                ):
                    raise ValueError("Missing capability evidence")
                if capability.get("conditional") or capability.get(
                    "unknownDependencies"
                ):
                    record["unknown"].append("conditional_or_unknown_effect")
                if "damage" not in capability["tags"]:
                    # Support, displacement or summons can still enable future
                    # damage; absence of a direct tag is not proof of safety.
                    record["unknown"].append("non_direct_damage_potential")
                    continue
                selected = casting(spell, level)
                if clock() >= deadline:
                    record["unknown"].append("budget_exhausted")
                    continue
                baseline = selected.baseline
                if (
                    len(baseline) < 9
                    or any(type(value) is not int for value in baseline[:5])
                    or any(type(value) is not bool for value in baseline[5:9])
                    or baseline[3] < 0
                    or baseline[4] < baseline[3]
                ):
                    raise ValueError("Invalid native casting projection")
                # Current category modifiers are relevant but not future buffs.
                # Never guess their value when the metadata is absent or malformed.
                categories = selected.cost_categories
                modifiers = getattr(rival, "spell_ap_cost_modifiers", None)
                if (
                    categories is None
                    or any(type(value) is not int for value in categories)
                    or (
                        categories
                        and (
                            not isinstance(modifiers, dict)
                            or any(
                                type(k) is not int or type(v) is not int
                                for k, v in modifiers.items()
                            )
                        )
                    )
                ):
                    raise ValueError("Unknown AP modifiers")
                from wakfu_server.combat_casting_range import int32

                adjustment = (
                    int32(sum(modifiers.get(category, 0) for category in categories))
                    if categories
                    else 0
                )
                ap = max(0, int32(baseline[0] + adjustment))
                if selected.rules or baseline[8]:
                    # A current actor's range and conditional context can change
                    # by its next turn. Preserve the static row with uncertainty.
                    record["unknown"].append("conditional_or_modifiable_range")
                record["abilities"].append(
                    dict(
                        spellId=spell,
                        level=level,
                        minimum=baseline[3],
                        maximum=baseline[4],
                        ap=ap,
                        mp=max(0, baseline[1]),
                        wp=max(0, baseline[2]),
                        needsLos=baseline[5],
                        inLine=baseline[6],
                        rangeModifiable=baseline[8],
                        conditional=bool(selected.rules),
                    )
                )
            except (
                ValueError,
                KeyError,
                IndexError,
                TypeError,
                AttributeError,
                OSError,
            ):
                record["unknown"].append("spell_metadata_unavailable")
    for rival, record, book, offset in queues:
        record["unknown"] = sorted(set(record["unknown"]))
        record["complete"] = (
            book is not None and offset == len(book) and not record["unknown"]
        )
    return dict(
        version=1, sourceRevision=getattr(fight, "sequence", None), actors=records
    )
