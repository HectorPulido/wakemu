"""Bounded native-area inversion for additional, measured cast-ray aims."""
from ..native.native_deadline import check, clock_now
from .jondo_area import directional_geometry, directional_recipient
from .jondo_native_amount import advisory_area_row


MAX_INVERSE_WORK = 4096
MAX_CENTERS = 128
MAX_EXTRA_RAYS = 64


def inverse_aoe_pairs(
    spells,
    actors,
    cells,
    indices,
    origins,
    known_targets,
    *,
    actor_id,
    deadline,
    max_work=MAX_INVERSE_WORK,
    max_centers=MAX_CENTERS,
    max_pairs=MAX_EXTRA_RAYS
):
    """Rank exact exported area centers by distinct visible enemy recipients.

    This is an optional bounded extension, not an exhaustive area search.
    Body XYZ is inverted by native XY offsets without guessing another floor.
    Existing occupied/support/mechanic aims have already been observed.
    """
    caster = next(actor for actor in actors if actor["id"] == actor_id)
    enemies = [
        actor
        for actor in actors
        if actor["hp"] > 0
        and actor["team"] != caster["team"]
        and not actor.get("hidden", False)
    ]
    centers, fixed_hits, directional_rows, caster_rows, caster_fixed_rows = (
        {},
        {},
        {},
        {},
        {},
    )
    work, exhausted = 0, False
    for spell_index, spell in enumerate(spells):
        if not spell.get("needsLineOfSight", False):
            continue
        for row in spell.get("rows", ()):
            row = advisory_area_row(row)
            if row is None:
                continue
            directional = directional_geometry(row)
            offsets = (
                directional[0] if directional is not None else row.get("fixedCells")
            )
            if "nativeDirectionalArea" in row and directional is None:
                continue
            if (
                row.get("target") != "enemy"
                or row.get("nativeInArea") is not True
                or not isinstance(offsets, (list, tuple, frozenset))
                or not (0 if directional is not None else 1)
                < len(offsets)
                <= MAX_INVERSE_WORK
                or any(
                    not isinstance(offset, (list, tuple))
                    or len(offset) != 2
                    or any(type(value) is not int for value in offset)
                    for offset in offsets
                )
            ):
                continue
            if directional is not None:
                directional_rows.setdefault(spell_index, []).append(directional)
            if row.get("nativeAreaCenterOnCaster") is True:
                # Null selectors anchor on the caster and use AIM only as
                # orientation reference. Enemy-minus-offset is not that aim.
                caster_rows.setdefault(spell_index, []).append(
                    directional
                    if directional is not None
                    else (frozenset(map(tuple, offsets)), False, True)
                )
                if directional is None:
                    caster_fixed_rows.setdefault(spell_index, []).append(
                        frozenset(map(tuple, offsets))
                    )
                continue
            rotations = (
                ((1, 0), (0, 1), (-1, 0), (0, -1))
                if directional is not None
                else ((1, 0),)
            )
            for enemy in enemies:
                extras = (
                    enemy.get("extraCells", ())
                    if directional is None or directional[1]
                    else ()
                )
                body = dict.fromkeys((enemy["cell"], *extras))
                for body_cell in body:
                    x, y, z = cells[body_cell]
                    rotated = (
                        (rx * dx - ry * dy, ry * dx + rx * dy)
                        for rx, ry in rotations
                        for dx, dy in offsets
                    )
                    for dx, dy in rotated:
                        if work >= max_work or clock_now() >= deadline:
                            exhausted = True
                            break
                        work += 1
                        if work % 64 == 0:
                            check()
                        center = x - dx, y - dy, z
                        if center not in indices or center in known_targets:
                            continue
                        recipients, books = centers.setdefault(center, (set(), set()))
                        recipients.add(enemy["id"])
                        books.add(spell_index)
                        if directional is None:
                            fixed_hits.setdefault((center, spell_index), set()).add(
                                enemy["id"]
                            )
                    if exhausted:
                        break
                if exhausted:
                    break
            if exhausted:
                break
        if exhausted:
            break
    # A large body contributes one recipient, irrespective of how many body
    # cells overlap. Rank the complete bounded prefix before selecting centers.
    ranked = sorted(centers, key=lambda cell: (-len(centers[cell][0]), indices[cell]))[
        :max_centers
    ]
    result = []
    current = cells[caster["cell"]]
    # The current-cell action gets its measured centers before movement views.
    ordered_origins = ([current] if current in origins else []) + [
        origin for origin in origins if origin != current
    ]
    for origin in ordered_origins:
        if clock_now() >= deadline:
            break
        candidate_books = {center: set(centers[center][1]) for center in ranked}
        for book in caster_rows:
            spell = spells[book]
            minimum, maximum = max(1, spell.get("minRange", 0)), spell.get(
                "maxRange", 0
            )
            added = 0
            for distance in range(minimum, maximum + 1):
                if work >= max_work or clock_now() >= deadline or added >= max_centers:
                    break
                for dx in range(-distance, distance + 1):
                    dy = distance - abs(dx)
                    for step_y in (dy, -dy) if dy else (0,):
                        if (
                            work >= max_work
                            or clock_now() >= deadline
                            or added >= max_centers
                        ):
                            break
                        work += 1
                        if work % 64 == 0:
                            check()
                        if spell.get("inLine", False) and dx and step_y:
                            continue
                        center = origin[0] + dx, origin[1] + step_y, origin[2]
                        if center not in indices or center in known_targets:
                            continue
                        candidate_books.setdefault(center, set()).add(book)
                        added += 1
                    if (
                        work >= max_work
                        or clock_now() >= deadline
                        or added >= max_centers
                    ):
                        break
        eligible = []
        for center, books in candidate_books.items():
            if clock_now() >= deadline:
                break
            distance = abs(origin[0] - center[0]) + abs(origin[1] - center[1])
            recipients = set()
            for book in books:
                if clock_now() >= deadline:
                    break
                spell = spells[book]
                if spell.get("minRange", 0) <= distance <= spell.get(
                    "maxRange", 0
                ) and (
                    not spell.get("inLine", False)
                    or origin[0] == center[0]
                    or origin[1] == center[1]
                ):
                    recipients.update(fixed_hits.get((center, book), ()))
                    for enemy in enemies:
                        if clock_now() >= deadline:
                            break
                        try:
                            directional_hits = any(
                                directional_recipient(
                                    area,
                                    center=center,
                                    origin=origin,
                                    point=cells[enemy["cell"]],
                                    radius=enemy.get("physicalRadius"),
                                    direction=caster.get("direction"),
                                )
                                for area in directional_rows.get(book, ())
                                if clock_now() < deadline
                            )
                            isotropic_hit = any(
                                (
                                    cells[enemy["cell"]][0] - origin[0],
                                    cells[enemy["cell"]][1] - origin[1],
                                )
                                in raw
                                for raw in caster_fixed_rows.get(book, ())
                            )
                            if directional_hits or isotropic_hit:
                                recipients.add(enemy["id"])
                        except (TypeError, ValueError):
                            # Missing native radius/facing is unknown, not a hit.
                            continue
            if recipients:
                eligible.append((-len(recipients), distance, indices[center], center))
        eligible.sort()
        for _, _, _, center in eligible[:max_centers]:
            result.append((origin, center))
            if len(result) >= max_pairs:
                return result
    return result
