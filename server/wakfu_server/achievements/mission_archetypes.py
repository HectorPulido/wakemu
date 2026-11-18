"""Compile reviewed mission archetypes into the existing authenticated toolkit.

Archetypes describe event joins, not guesses based on translated objective text.
Native definitions supply IDs, thresholds and rewards; a reviewed declaration
supplies the actual producer reference and activation. No player data is changed.
"""

from collections import Counter
from copy import deepcopy

from . import counter_missions, mission_toolkit_contract as contract

# These are the event units emitted by the existing domain producers. Delivery,
# dialogue and visit retain their producer's documented scope restrictions.
ARCHETYPES = {
    "monster_harvest": "monster_harvest",
    "resource_harvest": "resource_harvest",
    "plant": "planting",
    "craft": "craft_completed",
    "defeat": "monster_defeat",
    "dungeon": "dungeon_completed",
    "deliver": "item_delivery",
    "talk": "dialogue",
    "visit": "map_enter",
}


def _fields(value, required, optional=()):
    if (
        not isinstance(value, dict)
        or not set(required) <= set(value)
        or set(value) - set(required) - set(optional)
    ):
        raise ValueError("Unsupported mission archetype fields")


def _scope(row):
    return {key: deepcopy(row[key]) for key in ("maps", "instances") if key in row}


def _scoped(parent, child):
    result = _scope(parent)
    for key, values in _scope(child).items():
        if key in result and not set(values) <= set(result[key]):
            raise ValueError("Objective/activation scope exceeds its mission scope")
        result[key] = values
    return result


def referenced_quests(document):
    """Identify the small native-definition set needed to compile a batch."""
    _fields(document, ("schema", "id", "evidence", "missions"))
    if document["schema"] != "mission-archetypes-v1":
        raise ValueError("Unsupported mission archetype schema")
    if not isinstance(document["missions"], list) or not document["missions"]:
        raise ValueError("Mission archetype batch is empty")
    identities = set()
    for mission in document["missions"]:
        _fields(
            mission, ("quest_id", "activation", "objectives"), ("maps", "instances")
        )
        identities.add(mission["quest_id"])
        activation = mission["activation"]
        if not isinstance(activation, dict):
            raise ValueError("Missing reviewed mission activation")
        identities.update(activation.get("requires_completed", ()))
        if not isinstance(mission["objectives"], list):
            raise ValueError("Invalid mission archetype objectives")
        for objective in mission["objectives"]:
            if not isinstance(objective, dict):
                raise ValueError("Invalid mission archetype objective")
            if "child_quest_id" in objective:
                identities.add(objective["child_quest_id"])
    if any(type(identity) is not int or identity <= 0 for identity in identities):
        raise ValueError("Invalid mission archetype quest identity")
    return sorted(identities)


def compile_profile(document, definitions):
    """Compile full mission declarations; partial or recurring quests fail closed.

    A mission has an explicit activation (producer event or existing/manual
    acceptance), and every native objective needs a producer or child link.
    Direct objectives consume one operation. Native counter thresholds and IDs
    are copied exclusively from their pinned definitions, never a manifest.
    """
    identities = referenced_quests(document)
    native = contract.definitions_by_id(definitions)
    if set(identities) - set(native):
        raise ValueError("Missing native definitions for mission archetypes")
    profile = {
        "version": 1,
        "id": document["id"],
        "evidence": deepcopy(document["evidence"]),
        "bindings": [],
        "links": [],
        "activations": [],
    }
    counters = counter_missions.bindings(list(native.values()))
    by_objective = {
        (row[0], row[1]): (row[2], row[3])
        for values in counters.values()
        for row in values
    }
    seen, archetypes, modes = set(), Counter(), Counter()
    for mission in document["missions"]:
        quest = mission["quest_id"]
        if quest in seen:
            raise ValueError("Duplicate mission archetype quest")
        seen.add(quest)
        definition = native[quest]
        if definition.get("aqb") is not False:
            raise ValueError("Hidden mission cannot use a visible mission archetype")
        if any(definition.get(key) != 0 for key in ("cjU", "cjL", "getDuration")):
            raise ValueError(
                "Recurring/timed missions require their cycle-aware adapter"
            )
        expected = {row["d"]: row for row in definition["cjJ"]}
        provided = [row.get("objective_id") for row in mission["objectives"]]
        if len(set(provided)) != len(provided) or set(provided) != set(expected):
            raise ValueError(
                "Archetype batch must cover every native mission objective exactly once"
            )
        activation = mission["activation"]
        mode = activation.get("mode")
        modes[mode] += 1
        if mode == "event":
            _fields(
                activation,
                ("mode", "event"),
                ("requires_completed", "maps", "instances"),
            )
            row = {
                "id": f"accept-{quest}",
                "quest_id": quest,
                "event": deepcopy(activation["event"]),
                **_scoped(mission, activation),
            }
            if "requires_completed" in activation:
                row["requires_completed"] = list(activation["requires_completed"])
            profile["activations"].append(row)
        elif mode in ("existing", "manual"):
            _fields(activation, ("mode", "evidence"))
            if (
                not isinstance(activation["evidence"], str)
                or not activation["evidence"].strip()
            ):
                raise ValueError(
                    "Existing/manual acceptance requires explicit provenance"
                )
            profile["evidence"].append(activation["evidence"])
        else:
            raise ValueError("Unsupported mission archetype activation mode")
        for objective in mission["objectives"]:
            identity = objective["objective_id"]
            if "child_quest_id" in objective:
                _fields(objective, ("objective_id", "child_quest_id"))
                profile["links"].append(
                    {
                        "parent_quest_id": quest,
                        "objective_id": identity,
                        "child_quest_id": objective["child_quest_id"],
                    }
                )
                archetypes["child_quest"] += 1
                continue
            _fields(
                objective,
                ("objective_id", "archetype", "reference", "count"),
                ("maps", "instances", "count_threshold"),
            )
            archetype = objective["archetype"]
            if archetype not in ARCHETYPES:
                raise ValueError("Unsupported mission event archetype")
            if type(objective["reference"]) is not int or objective["reference"] <= 0:
                raise ValueError("Archetype needs a reviewed producer reference")
            row = {
                "id": f"objective-{quest}-{identity}",
                "quest_id": quest,
                "objective_id": identity,
                "event": {
                    "kind": ARCHETYPES[archetype],
                    "reference": objective["reference"],
                },
                "count": objective["count"],
                **_scoped(mission, objective),
            }
            if expected[identity].get("ckf"):
                if (quest, identity) not in by_objective:
                    raise ValueError(
                        "Native objective has an unsupported counter expression"
                    )
                row["variable_id"] = by_objective[quest, identity][0]
            if "count_threshold" in objective:
                row["count_threshold"] = objective["count_threshold"]
            profile["bindings"].append(row)
            archetypes[archetype] += 1
    validated = contract.validate(profile, native)
    return validated, {
        "missions": len(seen),
        "objectives": sum(archetypes.values()),
        "archetypes": dict(sorted(archetypes.items())),
        "acceptance_modes": dict(sorted(modes.items())),
        "manual_acceptance_required": modes.get("manual", 0),
        "existing_acceptance_required": modes.get("existing", 0),
    }


def install(db, document, *, activate=False):
    """Publish through the existing immutable toolkit in one transaction."""
    from . import mission_toolkit
    from . import rewards

    identities = referenced_quests(document)
    revision = mission_toolkit._revision(db)
    rows = db.execute(
        "SELECT definition_id,data FROM native_quest_metadata_definitions "
        "WHERE revision=%s AND definition_id=ANY(%s)",
        (revision, identities),
    ).fetchall()
    native = {row["definition_id"]: row["data"]["native"] for row in rows}
    profile, summary = compile_profile(document, native)
    for mission in document["missions"]:
        for reward in native[mission["quest_id"]]["cjK"]:
            rewards.validate(reward)
    with db.transaction():
        publication = mission_toolkit.install(db, profile, activate=activate)
    return {**summary, "publication": publication}
