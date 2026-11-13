"""Start Rii's combat curriculum from Airyna's first accepted lesson.

The observed choice asks for the first lesson; starting its named quest at
that point is a reconstruction, not a captured original server side effect.
The caller authenticates the dialogue and owns the surrounding transaction.
"""
from copy import deepcopy

from .mission_progress import auto_track


def plan(state, definition):
    """Add only the native combat quest; return its changed state and flag."""
    if (
        definition.get("d") != 5143
        or definition.get("native_class") != "aJM"
        or definition.get("aqb") is not False
        or definition.get("cjI") != ""
        or definition.get("cjU") != 0
        or definition.get("getDuration") != 0
        or [row.get("d") for row in definition.get("cjJ", ())]
        != [10574, 10575, 10576, 10608, 10609, 10610, 10611]
    ):
        raise ValueError("Rii combat curriculum differs from native definition")
    after = deepcopy(state)
    if 5143 in after["running"] or 5143 in after["completed"]:
        return after, False
    after["running"] = sorted(set(after["running"]) | {5143})
    auto_track(after, 5143)
    return after, True
