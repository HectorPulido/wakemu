"""Project reviewed battle regions without changing a logical walking stage.

A dynamic obstacle can connect a vestibule to its arena after destruction.
The pinned encounter region keeps group formation and admission in the reviewed
arena; it never adds movement blockers, changes actor positions or grants entry.
"""


def encounter_room(room):
    """Return the pinned combat-only projection, or the unchanged legacy room."""
    descriptor = room.get("encounter_region")
    if descriptor is None:
        return room
    if (
        type(descriptor) is not dict
        or set(descriptor) != {"schema_version", "cells", "anchor", "provenance"}
        or type(descriptor["schema_version"]) is not int
        or descriptor["schema_version"] != 1
        or type(descriptor["provenance"]) is not str
        or not descriptor["provenance"].strip()
    ):
        raise ValueError("Dungeon encounter region requires reviewed pinned evidence")

    def points(value):
        if (
            type(value) is not list
            or not value
            or any(
                type(p) is not list
                or len(p) != 3
                or any(type(axis) is not int for axis in p)
                for p in value
            )
        ):
            raise ValueError("Dungeon encounter region coordinates must be integral")
        selected = frozenset(map(tuple, value))
        if len(selected) != len(value):
            raise ValueError("Dungeon encounter region repeats a native cell")
        return selected

    cells = points(descriptor["cells"])
    logical = points(room["cells"])
    anchor = descriptor["anchor"]
    if (
        type(anchor) is not list
        or len(anchor) != 3
        or any(type(axis) is not int for axis in anchor)
        or tuple(anchor) not in cells
        or not cells <= logical
    ):
        raise ValueError("Dungeon encounter region leaves its pinned logical room")
    return dict(room, cells=descriptor["cells"], anchor=anchor)
