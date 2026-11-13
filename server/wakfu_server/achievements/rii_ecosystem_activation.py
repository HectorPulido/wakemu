"""Start Kheperalia's ecosystem quests in the observed order.

The official session shows 5145 completing before 5155 starts, and 5155
completing before 5156 starts. Callers own authorization and event receipts.
"""
from copy import deepcopy

from .mission_progress import auto_track


OBJECTIVES = {
    5145: (10597, 10579, 10578, 10620),
    5155: (10598, 10599, 10600, 10621),
    5156: (10602,),
}


def plan(state, definitions):
    """Start only the first unfinished mission in the observed sequence."""
    for identity, objectives in OBJECTIVES.items():
        definition = definitions.get(identity)
        if (
            not isinstance(definition, dict)
            or definition.get("d") != identity
            or definition.get("native_class") != "aJM"
            or definition.get("aqb") is not False
            or definition.get("cjI") != ""
            or definition.get("cjU") != 0
            or definition.get("getDuration") != 0
            or tuple(row.get("d") for row in definition.get("cjJ", ())) != objectives
        ):
            raise ValueError("Rii ecosystem quest differs from native definition")
    after = deepcopy(state)
    started = []
    for identity in OBJECTIVES:
        if identity in after["completed"]:
            continue
        if identity in after["running"]:
            break
        after["running"] = sorted(set(after["running"]) | {identity})
        auto_track(after, identity)
        started.append(identity)
        break
    return after, started
