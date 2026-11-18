"""Validate reviewed mission bindings against their native quest definitions.

Profiles are server-authored evidence declarations, never client event input.
A valid native counter is not evidence connecting it to a gameplay event: that
connection remains an explicit reviewed binding in the published profile.
"""

from copy import deepcopy

from . import counter_missions

EVENT_KINDS = frozenset(
    (
        "character_ready",
        "emote_performed",
        "party_pad_completed",
        "owned_dungeon_boss_completed",
        "owned_room_defeat",
        "monster_harvest",
        "resource_harvest",
        "resource_action_completed",
        "item_action_completed",
        "planting",
        "monster_defeat",
        "scoped_monster_defeat",
        "craft_completed",
        "transport_registered",
        "transport_interacted",
        "transport_entered",
        "item_delivery",
        "combat_loot",
        "chest_loot",
        "generic_item_acquired",
        "dialogue",
        "npc_spoken",
        "map_enter",
        "map_departure",
        "quest_completed",
        "dungeon_completed",
        "scenario_completed",
        "quest_item_read",
    )
)


def _positive(value, name):
    if type(value) is not int or not 0 < value < 2**31:
        raise ValueError("Invalid mission toolkit " + name)
    return value


def _label(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 1024:
        raise ValueError("Invalid mission toolkit " + name)
    return value


def _keys(value, required, optional=()):
    if (
        not isinstance(value, dict)
        or not set(required) <= set(value)
        or set(value) - set(required) - set(optional)
    ):
        raise ValueError("Unsupported mission toolkit fields")


def definitions_by_id(definitions):
    rows = (
        list(definitions.values())
        if isinstance(definitions, dict)
        else list(definitions)
    )
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid native mission definition")
        identity = _positive(row.get("d"), "quest id")
        if (
            identity in result
            or row.get("native_class") != "aJM"
            or not isinstance(row.get("cjJ"), list)
        ):
            raise ValueError("Invalid or duplicate native mission definition")
        objectives = [obj.get("d") for obj in row["cjJ"] if isinstance(obj, dict)]
        if len(objectives) != len(row["cjJ"]):
            raise ValueError("Invalid native mission objective")
        for objective in objectives:
            _positive(objective, "objective id")
        if len(set(objectives)) != len(objectives):
            raise ValueError("Duplicate native mission objective")
        result[identity] = row
    if isinstance(definitions, dict) and (
        any(type(key) is not int for key in definitions)
        or set(definitions) != set(result)
    ):
        raise ValueError("Native mission dictionary key differs from identity")
    return result


def _quest(definitions, identity, *, visible=True):
    _positive(identity, "quest id")
    row = definitions.get(identity)
    if row is None or (visible and row.get("aqb") is not False):
        raise ValueError("Unsupported native mission in toolkit profile")
    return row


def _objective(definitions, quest, objective):
    _positive(objective, "objective id")
    definition = _quest(definitions, quest)
    matches = [row for row in definition["cjJ"] if row["d"] == objective]
    if len(matches) != 1:
        raise ValueError("Toolkit objective differs from native definition")
    return matches[0]


def _event(row):
    _keys(row, ("kind",), ("reference",))
    if not isinstance(row["kind"], str) or row["kind"] not in EVENT_KINDS:
        raise ValueError("Unsupported mission toolkit event kind")
    if row["kind"] == "character_ready":
        if type(row.get("reference")) is not int or row["reference"] != 0:
            raise ValueError("Character-ready requires its canonical reference zero")
    elif (
        row["kind"] in ("combat_loot", "chest_loot", "generic_item_acquired")
        and "reference" not in row
    ):
        raise ValueError("Acquired loot requires its actual native item reference")
    elif "reference" in row:
        _positive(row["reference"], "event reference")


def _scope(row):
    if "maps" in row:
        maps = row["maps"]
        if not isinstance(maps, list) or not maps:
            raise ValueError("Invalid mission toolkit map scope")
        for identity in maps:
            _positive(identity, "map id")
        if len(set(maps)) != len(maps):
            raise ValueError("Duplicate mission toolkit map scope")
    if "instances" in row:
        instances = row["instances"]
        if not isinstance(instances, list) or not instances:
            raise ValueError("Invalid mission toolkit instance scope")
        if any(
            type(value) is not int or not 0 <= value < 2**63 for value in instances
        ):
            raise ValueError("Invalid mission toolkit instance id")
        if len(set(instances)) != len(instances):
            raise ValueError("Duplicate mission toolkit instance scope")


def overlapping(left, right):
    """Whether one trusted event and owned location can match both declarations."""
    first, second = left["event"], right["event"]
    if first["kind"] != second["kind"]:
        return False
    if (
        "reference" in first
        and "reference" in second
        and first["reference"] != second["reference"]
    ):
        return False
    for scope in ("maps", "instances"):
        if (
            scope in left
            and scope in right
            and not set(left[scope]).intersection(right[scope])
        ):
            return False
    return True


def validate(profile, definitions):
    """Return an isolated validated profile; unsupported native forms fail closed."""
    _keys(profile, ("version", "id", "evidence", "bindings", "links", "activations"))
    if type(profile["version"]) is not int or profile["version"] != 1:
        raise ValueError("Unsupported mission toolkit profile version")
    _label(profile["id"], "profile id")
    if not isinstance(profile["evidence"], list) or not profile["evidence"]:
        raise ValueError("Missing mission toolkit evidence")
    for evidence in profile["evidence"]:
        _label(evidence, "evidence")
    for field in ("bindings", "links", "activations"):
        if not isinstance(profile[field], list):
            raise ValueError("Invalid mission toolkit declaration list")
    by_id = definitions_by_id(definitions)
    counters = counter_missions.bindings(list(by_id.values()))
    ids = set()
    direct_thresholds = {}
    for row in profile["bindings"]:
        _keys(
            row,
            ("id", "quest_id", "objective_id", "event", "count"),
            ("variable_id", "maps", "instances", "count_threshold"),
        )
        _label(row["id"], "binding id")
        if row["id"] in ids:
            raise ValueError("Duplicate mission toolkit declaration id")
        ids.add(row["id"])
        objective = _objective(by_id, row["quest_id"], row["objective_id"])
        _event(row["event"])
        if row["event"]["kind"] == "character_ready":
            raise ValueError("Character-ready is activation-only")
        _scope(row)
        if row["count"] not in ("operation", "quantity"):
            raise ValueError("Unsupported mission toolkit count policy")
        if "count_threshold" in row:
            _positive(row["count_threshold"], "direct count threshold")
            if "variable_id" in row or objective.get("ckf"):
                raise ValueError(
                    "Server count threshold cannot replace a native counter"
                )
            definition = by_id[row["quest_id"]]
            if any(
                definition.get(key, 0) != 0 for key in ("cjU", "cjL", "getDuration")
            ):
                raise ValueError(
                    "Server objective counts require a nonrecurring mission"
                )
        target = row["quest_id"], row["objective_id"]
        threshold = row.get("count_threshold", 1)
        if target in direct_thresholds and direct_thresholds[target] != threshold:
            raise ValueError("Conflicting server thresholds for one native objective")
        direct_thresholds[target] = threshold
        if "variable_id" in row:
            variable = _positive(row["variable_id"], "variable id")
            matches = [
                item
                for item in counters.get(variable, ())
                if item[:3] == (row["quest_id"], row["objective_id"], variable)
            ]
            if len(matches) != 1:
                raise ValueError(
                    "Toolkit counter differs from supported native objective"
                )
        elif objective.get("ckf") or (
            row["count"] != "operation" and "count_threshold" not in row
        ):
            raise ValueError("Direct toolkit objective has unsupported native counter")
    for index, left in enumerate(profile["bindings"]):
        for right in profile["bindings"][index + 1 :]:
            if not overlapping(left, right):
                continue
            if (left["quest_id"], left["objective_id"]) == (
                right["quest_id"],
                right["objective_id"],
            ):
                raise ValueError(
                    "Overlapping toolkit bindings target the same objective"
                )
            if (
                "variable_id" in left
                and left.get("variable_id") == right.get("variable_id")
                and left["count"] != right["count"]
            ):
                raise ValueError(
                    "Conflicting toolkit count policies for native variable"
                )
    targets = set()
    for row in profile["links"]:
        _keys(row, ("parent_quest_id", "objective_id", "child_quest_id"))
        parent, objective, child = (
            row["parent_quest_id"],
            row["objective_id"],
            row["child_quest_id"],
        )
        source = _objective(by_id, parent, objective)
        _quest(by_id, child, visible=False)
        # Distinct children for one objective are explicit alternative variants.
        # Either genuine completion satisfies it; an identical edge is invalid.
        if (
            parent == child
            or (parent, objective, child) in targets
            or source.get("ckf")
        ):
            raise ValueError("Conflicting or unsupported mission toolkit dependency")
        targets.add((parent, objective, child))
    for row in profile["activations"]:
        _keys(
            row,
            ("id", "quest_id", "event"),
            (
                "maps",
                "instances",
                "requires_completed",
                "minimum_level",
                "admission_evidence",
            ),
        )
        _label(row["id"], "activation id")
        if row["id"] in ids:
            raise ValueError("Duplicate mission toolkit declaration id")
        ids.add(row["id"])
        _quest(by_id, row["quest_id"])
        _event(row["event"])
        if row["event"]["kind"] == "character_ready":
            if (
                type(row.get("minimum_level")) is not int
                or not 1 <= row["minimum_level"] <= 32767
            ):
                raise ValueError(
                    "Character-ready admission needs a reviewed real-level threshold"
                )
            _label(row.get("admission_evidence"), "character-ready admission evidence")
        elif "minimum_level" in row or "admission_evidence" in row:
            raise ValueError(
                "Reviewed character admission policy belongs to character-ready"
            )
        _scope(row)
        requirements = row.get("requires_completed", [])
        if not isinstance(requirements, list):
            raise ValueError("Invalid toolkit activation requirements")
        for identity in requirements:
            _quest(by_id, identity, visible=False)
        if len(set(requirements)) != len(requirements):
            raise ValueError("Duplicate toolkit activation requirement")
    return deepcopy(profile)


def validate_event(event):
    _keys(event, ("kind", "quantity"), ("reference",))
    _event({key: value for key, value in event.items() if key != "quantity"})
    if type(event["quantity"]) is not int or not 1 <= event["quantity"] <= 32767:
        raise ValueError("Invalid trusted mission event quantity")
    return event


def matches(declaration, event, character):
    """Match a reviewed event identity and authoritative character map."""
    wanted = declaration["event"]
    return (
        wanted["kind"] == event["kind"]
        and ("reference" not in wanted or wanted["reference"] == event.get("reference"))
        and (
            "maps" not in declaration or character.get("map_id") in declaration["maps"]
        )
        and (
            "instances" not in declaration
            or (
                type(character.get("instance_id")) is int
                and character["instance_id"] in declaration["instances"]
            )
        )
    )
