"""Original exploration GenericActivable travel plans, without world mutations.

Only the packaged original placements and their artifact possession groups are
admitted. The caller owns current-session/idle admission, script publication,
the native deferred deadline, and the ordinary compare-and-set map transition.
"""

import ast
from contextlib import contextmanager
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path
import re
import struct
from typing import TypedDict


class ArtifactTravelPlan(TypedDict):
    source_map: int
    interactive_element_id: int
    native_definition_id: int
    origin: dict
    destination: dict
    direction: int
    delay_ms: int
    script_packets: tuple
    missing_visual_scripts: tuple
    native_group_id: int
    native_action_id: int
    native_effect_reference: int
    artifact_reference: int


class ExplorationArtifactFailure(ValueError):
    """Keep server diagnostics separate from an allowlisted public cause."""

    def __init__(self, message, *, public_code=None):
        super().__init__(message)
        self.public_code = public_code


class UnsupportedExplorationArtifact(ExplorationArtifactFailure):
    """The original action requires a behavior that has not been recovered."""


_BOOK = json.loads(Path(__file__).with_suffix(".json").read_text(encoding="utf-8"))
if _BOOK.get("schema_version") != 1:
    raise ValueError("Unsupported exploration artifact action catalog")
_PLACEMENTS = {(row["map_id"], row["id"]): row for row in _BOOK["placements"]}
_PROGRAMS = {row["descriptor_id"]: row for row in _BOOK["programs"]}
if len(_PLACEMENTS) != 61 or len(_PROGRAMS) != 60:
    raise ValueError("Incomplete original exploration artifact action catalog")
_POSITION = re.compile(r"\{\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*(-?\d+)\s*\}")
_COMPARISONS = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Gt: lambda a, b: a > b,
    ast.GtE: lambda a, b: a >= b,
    ast.Lt: lambda a, b: a < b,
    ast.LtE: lambda a, b: a <= b,
}


def sources():
    return tuple(deepcopy(row) for row in _PLACEMENTS.values())


def source(map_id, object_id):
    row = _PLACEMENTS.get((map_id, object_id))
    return None if row is None else deepcopy(row)


def _action(row, action_id):
    program = _PROGRAMS.get(row["descriptor"])
    matches = (
        []
        if program is None
        else [
            (group, action)
            for group in program["groups"]
            for action in group["actions"]
            if action["wire_action"] == action_id
        ]
    )
    if len(matches) != 1:
        raise ValueError("Unknown original exploration artifact action")
    return matches[0]


def recognizes(character, body):
    """Classify an actual12870 source, without consuming unrelated quest actions."""
    if type(body) is not bytes or len(body) != 12:
        return False
    object_id, action_id, _ = struct.unpack(">qHH", body)
    row = _PLACEMENTS.get((character.get("map_id"), object_id))
    if row is None:
        return False
    from wakfu_server.exploration_secrets import ITEM_REFS

    try:
        group, _ = _action(row, action_id)
    except ValueError:
        return True  # A known source still rejects an invented action explicitly.
    return group["cod"] in ITEM_REFS


def _criterion(expression, character, *, mission_free):
    """Keep original coordinate branches; waive only artifact acquisition quests."""
    if not isinstance(expression, str) or len(expression) > 32768:
        raise ValueError("Malformed original artifact criterion")
    if not expression.strip():
        return True
    from wakfu_server.combat_local_criteria import parse_local_criterion

    tree = parse_local_criterion(expression)

    def check(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, bool):
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.Not, ast.USub)):
            check(node.operand)
            return
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            for item in node.values:
                check(item)
            return
        if isinstance(node, ast.Compare) and all(
            type(op) in _COMPARISONS for op in node.ops
        ):
            check(node.left)
            for item in node.comparators:
                check(item)
            return
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            if node.func.id in ("GetX", "GetY", "GetZ", "IsInFight") and not node.args:
                return
            if (
                node.func.id == "IsAchievementActive"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and type(node.args[0].value) is int
                and node.args[0].value in (3093, 3616)
            ):
                return
        raise ValueError("Unsupported original exploration artifact criterion")

    def boolean(value):
        if type(value) is not bool:
            raise ValueError("Original artifact predicate requires boolean authority")
        return value

    def visit(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp):
            value = visit(node.operand)
            if isinstance(node.op, ast.Not):
                return not boolean(value)
            if type(value) is not int:
                raise ValueError("Original artifact coordinate requires an integer")
            return -value
        if isinstance(node, ast.BoolOp):
            values = [boolean(visit(item)) for item in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare):
            values = [visit(node.left)] + [visit(item) for item in node.comparators]
            if any(type(value) is not int for value in values):
                raise ValueError("Original artifact comparison requires integers")
            return all(
                _COMPARISONS[type(op)](a, b)
                for op, a, b in zip(node.ops, values, values[1:])
            )
        name = node.func.id
        if name == "IsInFight":
            return False  # resolve rejects the caller's blocked/combat state first.
        if name == "IsAchievementActive":
            if not mission_free:
                raise ValueError(
                    "Original artifact quest requires owned mission authority"
                )
            return True
        coordinate = character.get({"GetX": "x", "GetY": "y", "GetZ": "z"}[name])
        if type(coordinate) is not int:
            raise ValueError("Missing authoritative artifact approach position")
        return coordinate

    check(tree)  # Validate every branch, including unreachable predicates.
    return boolean(visit(tree))


def _verify_source(row):
    from wakfu_server import native_catalog

    return _verified_source(native_catalog.release(), row["map_id"], row["id"])


@lru_cache(maxsize=128)
def _verified_source(revision, map_id, object_id):
    from wakfu_server import native_catalog
    from wakfu_server.native_catalog_compatibility import require_source_revision
    from wakfu_server.paths import DATA_ROOT

    row = _PLACEMENTS[map_id, object_id]
    require_source_revision(
        _BOOK["catalog_revision"],
        (
            "native-map-objects.json",
            "native-interactive-states.json",
            f"combat-maps/{map_id}.json",
        ),
    )
    original = native_catalog.record(
        DATA_ROOT / "native-map-objects.json", "$", str(object_id)
    )
    state = native_catalog.record(
        DATA_ROOT / "native-interactive-states.json", "objects", str(object_id)
    )
    if (
        native_catalog.release() != revision
        or original is None
        or original.get("type") != "GenericActivableInteractiveElement"
        or original.get("map_id") != map_id
        or any(original.get(axis) != row[axis] for axis in ("x", "y", "z"))
        or original.get("payload_hex") != row["payload_hex"]
    ):
        raise ValueError("Exploration artifact differs from its original world source")
    expected_state = row.get("state_payload_hex")
    if expected_state is None:
        if state is not None:
            raise ValueError("Unexpected original exploration artifact state")
    elif (
        state is None
        or state.get("type") != original["type"]
        or state.get("map_id") != map_id
        or state.get("payload_hex") != expected_state
    ):
        raise ValueError("Exploration artifact differs from its original native state")
    return True


def _walkable(map_id, position):
    from wakfu_server import native_catalog

    return tuple(position) in _walkable_cells(native_catalog.release(), map_id)


@lru_cache(maxsize=64)
def _walkable_cells(revision, map_id):
    from wakfu_server.combat_terrain import map_geometry

    return frozenset(tuple(row) for row in map_geometry(map_id)["cells"])


def _teleport(effect):
    parameters = effect.get("parameters")
    if not isinstance(parameters, list) or len(parameters) not in (3, 4):
        raise ValueError("Unsupported original artifact teleport parameters")
    match = (
        _POSITION.fullmatch(parameters[0]) if isinstance(parameters[0], str) else None
    )
    if match is None or any(
        not isinstance(value, str) or not re.fullmatch(r"-?\d+", value)
        for value in parameters[1:]
    ):
        raise ValueError("Malformed original artifact teleport destination")
    x, y, z = map(int, match.groups())
    map_id, direction = map(int, parameters[1:3])
    delay_ms = int(parameters[3]) if len(parameters) == 4 else 0
    if (
        not 0 < map_id < 2**31
        or not 0 <= direction < 8
        or not 0 <= delay_ms < 2**31
        or not -(2**31) <= x < 2**31
        or not -(2**31) <= y < 2**31
        or not -32768 <= z < 32768
    ):
        raise ValueError("Invalid original artifact teleport bounds")
    return dict(map_id=map_id, instance_id=0, x=x, y=y, z=z), direction, delay_ms


def _script_packet(actor_id, object_id, reference):
    # cio13270 ignores the actor header; each shipped artifact Lua reads userId.
    variables = ((b"userId", actor_id), (b"elementId", object_id))
    payload = struct.pack(">qiBi", actor_id, reference, 1, len(variables))
    for name, value in variables:
        payload += struct.pack(">i", len(name)) + name + struct.pack(">q", value)
    return 13270, payload


def resolve(character, body, *, source_allowed, position_allowed=None, blocked=False):
    """Plan actual12870 under an owned current position, never mutate or sleep.

    Nonzero masks retain original exported QV approaches. Zero-mask native
    coordinate programs bind the exact selected endpoint to approved Movement;
    neither an arbitrary radius nor a replacement altitude is invented.
    """
    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Invalid original exploration artifact action length")
    if type(blocked) is not bool or blocked or character.get("instance_id", 0) != 0:
        raise ValueError("Exploration artifact requires an idle public-world actor")
    if character.get("health_dead") is True:
        raise ValueError("Exploration artifact requires a living owned actor")
    if any(
        type(character.get(key)) is not int or character[key] <= 0
        for key in ("id", "account_id", "map_id")
    ):
        raise ValueError("Missing owned exploration artifact character")
    object_id, action_id, parameter = struct.unpack(">qHH", body)
    if parameter != 0:
        raise ValueError("Unsupported original exploration artifact action parameter")
    row = source(character["map_id"], object_id)
    if row is None:
        raise ValueError("Unknown original exploration artifact source")
    group, action = _action(row, action_id)
    from wakfu_server.exploration_secrets import (
        ITEM_REFS,
        account_quantity,
        projected_transport_access,
    )

    reference = group["cod"]
    if (
        reference not in ITEM_REFS
        or type(group["coe"]) is not int
        or group["coe"] != 1
        or group["cof"] is not False
        or group["cnd"] != 0
        or action["raw_cob"] != 1.0
    ):
        raise ValueError("Unqualified original artifact possession group")
    if account_quantity(character, (reference,)) < group["coe"]:
        raise ValueError("Exploration artifact is not owned by this account")
    effects = action["effects"]
    if not effects or any(effect["effect_type"] not in (1, 3) for effect in effects):
        raise UnsupportedExplorationArtifact(
            "Unsupported original exploration artifact effect"
        )
    if not any(effect["effect_type"] == 3 for effect in effects):
        raise UnsupportedExplorationArtifact(
            "Original Martillo script2947 is unavailable; wall behavior has not been recovered",
            public_code="hammer_unavailable",
        )
    if group["cog"] != 0:
        raise UnsupportedExplorationArtifact(
            "Original artifact cooldown requires an unsupported native contract"
        )
    _verify_source(row)
    mission_free = projected_transport_access(character, reference, group["coe"])
    if not _criterion(action["criterion"], character, mission_free=mission_free):
        raise ValueError("Original exploration artifact action criterion failed")
    selected = [
        effect
        for effect in effects
        if _criterion(effect["criterion"], character, mission_free=mission_free)
    ]
    teleports = [effect for effect in selected if effect["effect_type"] == 3]
    if len(teleports) != 1:
        raise ExplorationArtifactFailure(
            "Original artifact position selects no unique destination",
            public_code="position",
        )
    teleport = teleports[0]
    position = tuple(character.get(axis) for axis in ("x", "y", "z"))
    if any(type(value) is not int for value in position):
        raise ExplorationArtifactFailure(
            "Missing authoritative artifact source position", public_code="position"
        )
    coordinate_branch = bool(re.search(r"\bGet[XYZ]\(\)", teleport["criterion"]))
    if row["approach_mask"] == 0 and coordinate_branch:
        if (
            not callable(position_allowed)
            or position_allowed(character) is not True
            or not _walkable(row["map_id"], position)
        ):
            raise ExplorationArtifactFailure(
                "Original artifact endpoint lacks approved native movement authority",
                public_code="position",
            )
    elif not callable(source_allowed) or source_allowed(character, row) is not True:
        raise ExplorationArtifactFailure(
            "Original artifact source approach is not authorized",
            public_code="position",
        )
    destination, direction, delay_ms = _teleport(teleport)
    if not _walkable(
        destination["map_id"], tuple(destination[axis] for axis in ("x", "y", "z"))
    ):
        raise ValueError(
            "Original artifact destination is not a verified native walkable surface"
        )
    packets, missing = [], []
    for effect in selected:
        script = _BOOK["native_scripts"].get(str(effect["action_reference"]))
        if script is None:
            raise ValueError("Original artifact script provenance is missing")
        if script["present"] is not True:
            missing.append(effect["action_reference"])
            continue  # An absent optional visual cannot invent an asset or reward.
        parameters = effect["parameters"]
        if effect["effect_type"] == 1:
            if parameters not in ([], ["true"], ["false"]):
                raise UnsupportedExplorationArtifact(
                    "Unsupported original artifact script parameters"
                )
            broadcast = parameters == ["true"]
            scope = (
                "original_explicit"
                if parameters
                else "wakemu_actor_only_unknown_native_default"
            )
        else:
            broadcast, scope = False, "wakemu_actor_only_native_teleport_visual"
        packets.append(
            dict(
                packet=_script_packet(
                    character["id"], object_id, effect["action_reference"]
                ),
                broadcast=broadcast,
                broadcast_authority=scope,
                native_effect_reference=effect["action_reference"],
                native_effect_type=effect["effect_type"],
            )
        )
    return ArtifactTravelPlan(
        source_map=row["map_id"],
        interactive_element_id=object_id,
        native_definition_id=row["descriptor"],
        origin={
            key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
        },
        destination=destination,
        direction=direction,
        delay_ms=delay_ms,
        script_packets=tuple(packets),
        missing_visual_scripts=tuple(missing),
        native_group_id=group["id"],
        native_action_id=action["native_id"],
        native_effect_reference=teleport["action_reference"],
        artifact_reference=reference,
    )


def projection_required(map_id, object_id):
    """Only the reviewed Varita menu needs an acquisition-gate-free action."""
    row = _PLACEMENTS.get((map_id, object_id))
    return row is not None and (map_id, object_id, row["descriptor"]) == (
        1118,
        27550,
        1145,
    )


def binding(map_id, object_id):
    if not projection_required(map_id, object_id):
        return None
    row = source(map_id, object_id)
    _verify_source(row)
    return dict(
        source=dict(row, native_type="GenericActivableInteractiveElement"),
        activation_parameters=b"{1;desc.mru.entrer}",
        route_key="exploration_artifact_action",
    )


def attachment(row, scope):
    if scope.get("instance_id", 0) != 0:
        return None
    current = binding(scope.get("map_id"), row["id"])
    if current is None:
        return None
    from wakfu_server.seasonal_native_gateway import projected_attachment

    return projected_attachment(row, current)


def activation(character, body):
    """Translate the one projected menu action to its original numeric index1."""
    if type(body) is not bytes or len(body) != 12:
        return None
    object_id, action_id, parameter = struct.unpack(">qHH", body)
    if not projection_required(character.get("map_id"), object_id):
        return None
    if action_id != 0:
        return None  # An original numeric action1 remains an ordinary request.
    if character.get("instance_id", 0) != 0 or parameter != 0:
        raise ValueError("Invalid projected exploration artifact activation")
    return struct.pack(">qHH", object_id, 1, 0)


@contextmanager
def _locked_owner(store, account_id, generation, character_id):
    """Share authoritative admission fences before visuals and before travel."""
    from wakfu_server.simple_item_actions import _idle
    from wakfu_server.exploration_secrets import SETTING

    with store.connection() as db:
        if (
            db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
            ).fetchone()
            is None
        ):
            raise ValueError("Exploration artifact account is unavailable")
        store.lock_character(db, account_id, generation, character_id)
        if (
            db.execute(
                "SELECT value FROM settings WHERE name=%s FOR SHARE",
                (SETTING,),
            ).fetchone()
            is None
        ):
            raise ValueError("Exploration artifact access policy is unavailable")
        actual = store.character(account_id, character_id, db)
        _idle(db, character_id, store.now())
        if db.execute(
            "SELECT 1 FROM environment_interaction_tickets WHERE character_id=%s AND state='active'",
            (character_id,),
        ).fetchone():
            raise ValueError("Another native environment occupation is active")
        yield db, actual


def admit(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    source_allowed,
    position_allowed=None,
    blocked=False,
):
    """Authorize the current idle owner before publishing any native script."""
    with _locked_owner(store, account_id, generation, character_id) as (_, actual):
        return resolve(
            actual,
            body,
            source_allowed=source_allowed,
            position_allowed=position_allowed,
            blocked=blocked,
        )


def transition(
    store,
    account_id,
    generation,
    character_id,
    body,
    *,
    expected_plan,
    source_allowed,
    position_allowed=None,
    blocked=False,
):
    """Revalidate an admitted deferred action and its idle owner atomically.

    Combat admission and account/session replacement use these same ownership
    locks. A deferred visual never authorizes stale coordinates or an artifact
    whose projection was disabled while its native animation was running.
    """
    with _locked_owner(store, account_id, generation, character_id) as (db, actual):
        current = resolve(
            actual,
            body,
            source_allowed=source_allowed,
            position_allowed=position_allowed,
            blocked=blocked,
        )
        for key in (
            "origin",
            "destination",
            "direction",
            "delay_ms",
            "source_map",
            "interactive_element_id",
            "native_definition_id",
            "native_group_id",
            "native_action_id",
            "native_effect_reference",
            "artifact_reference",
        ):
            if current[key] != expected_plan.get(key):
                raise ExplorationArtifactFailure(
                    "Deferred exploration artifact action authority changed",
                    public_code="position" if key == "origin" else None,
                )
        return store.transition_map_in_transaction(
            db,
            account_id,
            generation,
            character_id,
            current["origin"],
            current["destination"],
        )
