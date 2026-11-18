"""Exact source-triggered quest encounters using ordinary native combat.

Clicking an ambush source creates no quest victory. A frozen owner/group receipt
binds the actual normal fight; only its original, durably defeated roster can
advance the original source objective. Other breeds or ordinary world kills do
not qualify. Configuration is dormant until explicitly published.
"""

import ast
from collections import Counter
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import secrets
import struct

from psycopg.types.json import Jsonb

from . import (
    storage,
    mission_progress,
    mission_dependencies,
    native_effective_eligibility,
)
from .service import _owner

SCHEMA = "owned-quest-source-encounters-v1"
SETTING = "owned_quest_source_encounters"
SOURCE = (
    Path(__file__).with_name("quest_source_profiles") / "astrub-fields-ambushes.json"
)


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def _validate_owned_source(row):
    from wakfu_server import generic_transports
    from wakfu_server.dungeon_runtime_config import canonical_hash

    scope = row["owned_dungeon"]
    if (
        row["mode"] != "gather"
        or not isinstance(scope, dict)
        or set(scope)
        != {
            "definition_id",
            "entry_map_id",
            "entry_source_id",
            "destination_id",
            "source_sha256",
        }
        or any(
            type(scope[k]) is not int or scope[k] <= 0
            for k in (
                "definition_id",
                "entry_map_id",
                "entry_source_id",
                "destination_id",
            )
        )
    ):
        raise ValueError("Malformed owned native quest read scope")
    source = generic_transports.source(scope["entry_map_id"], scope["entry_source_id"])
    if (
        source is None
        or canonical_hash(source) != scope["source_sha256"]
        or not any(
            d["destination_id"] == scope["destination_id"]
            and d["map_id"] == row["source"]["map_id"]
            for d in source["destinations"]
        )
    ):
        raise ValueError("Owned quest read lost its actual native dungeon entrance")


def _validate_opening(row):
    import re

    scenario = row["scenario"]
    opening = scenario["opening"]
    if (
        type(opening) is not dict
        or set(opening)
        != {
            "event",
            "duration_ms",
            "owner_position",
            "script_sha256",
            "script_source",
            "evidence",
        }
        or type(opening["event"]) is not int
        or opening["event"] <= 0
        or type(opening["duration_ms"]) is not int
        or not 0 < opening["duration_ms"] <= 60000
        or not opening["evidence"]
        or type(opening["owner_position"]) is not list
        or len(opening["owner_position"]) != 3
        or any(type(v) is not int for v in opening["owner_position"])
    ):
        raise ValueError("Malformed native quest-source cinematic")
    path = opening["script_source"]
    if type(path) is not str or Path(path).name != path or not path.endswith(".json"):
        raise ValueError("Quest source cinematic escapes the reviewed native directory")
    native = json.loads(SOURCE.with_name(path).read_text())
    if (
        native.get("schema") != "native-script-source-v1"
        or native.get("scenario_id") != scenario["id"]
        or type(native.get("script")) is not str
    ):
        raise ValueError("Quest source cinematic lacks its frozen native program")
    text = native["script"]
    raw = text.encode("utf-8")
    if sha256(raw).hexdigest() != opening["script_sha256"]:
        raise ValueError("Quest source cinematic script changed")
    start = re.search(
        r"function\s+event_"
        + str(scenario["id"])
        + "_"
        + str(opening["event"])
        + r"\s*\(\s*\)",
        text,
    )
    begin = re.search(
        r"function\s+event_"
        + str(scenario["id"])
        + "_"
        + str(scenario["begin_event"])
        + r"\s*\(([^)]*)\)",
        text,
    )
    if (
        start is None
        or begin is None
        or len(begin[1].split(",")) != scenario.get("actor_slots", 8) + 3
    ):
        raise ValueError("Quest source cinematic lost its original event signature")
    body = text[start.end() :].split("\nfunction ", 1)[0]
    if (
        re.search(
            r"invoke_custom\(\s*"
            + str(opening["duration_ms"])
            + r'\s*,\s*1\s*,\s*"skipCinematic"\s*,\s*'
            + str(opening["event"]),
            body,
        )
        is None
    ):
        raise ValueError("Quest source cinematic duration is not native")
    coordinates = r"\s*,\s*".join(map(str, opening["owner_position"]))
    if (
        re.search(
            r'"Mobile.moveMobile"\s*,\s*playerId\s*,\s*' + coordinates + r"\s*[,)]",
            body,
        )
        is None
    ):
        raise ValueError("Quest source cinematic endpoint is not native")


@lru_cache(maxsize=8)
def _read_document(path):
    value = json.loads(path.read_text())
    if value.get("schema") != SCHEMA or not value.get("provenance"):
        raise ValueError("Missing reviewed quest-source declaration")
    definitions = {row["d"]: row for row in value["definitions"]}
    seen = set()
    for row in value["bindings"]:
        source, action = row["source"], row["action"]
        identity = source["id"]
        if (
            type(identity) is not int
            or identity <= 0
            or identity in seen
            or source["type"]
            not in (
                "GenericActivableInteractiveElement",
                "PositionTrigger",
            )
            or source["auto"] is not False
            or row["mode"] not in ("encounter", "gather")
            or not row["evidence"]
            or row["native_definition_sha256"] != digest(definitions[row["quest_id"]])
            or row["objective_id"]
            not in {item["d"] for item in definitions[row["quest_id"]]["cjJ"]}
            or type(row["native_occupation_ms"]) is not int
            or not 0 <= row["native_occupation_ms"] <= 60000
        ):
            raise ValueError("Quest source lost its exact native action")
        if source["type"] == "PositionTrigger":
            from wakfu_server import native_interactive_activation

            native_cells = {
                tuple(cell) for cell in native_interactive_activation.decode(source)
            }
            trigger_cells = row.get("activation_cells")
            if (
                row["mode"] != "encounter"
                or action.get("wire_action") != 5
                or action.get("parameter") != 0
                or not native_cells
                or not isinstance(trigger_cells, list)
                or {tuple(cell) for cell in trigger_cells} != native_cells
                or row.get("approaches") not in (None, [])
            ):
                raise ValueError("Quest source lost its literal native trigger polygon")
        elif (
            type(action.get("wire_action")) is not int
            or not 0 <= action["wire_action"] <= 65535
            or not row.get("approaches")
            or action not in row["group"]["actions"]
            or row["group"] not in row["descriptor"]["groups"]
            or row["descriptor"]["descriptor_id"] != source["descriptor_id"]
            or row["native_occupation_ms"] != row["group"]["cog"]
        ):
            raise ValueError("Quest source lost its exact native action group")
        else:
            for point in row["approaches"]:
                if (
                    len(point) != 3
                    or any(type(v) is not int for v in point)
                    or abs(point[0] - source["x"]) + abs(point[1] - source["y"]) != 1
                ):
                    raise ValueError(
                        "Quest source approach is not native adjacent terrain"
                    )
        if row["mode"] == "encounter":
            if (
                not row["roster"]
                or row["scenario"] is None
                or not 1 <= sum(member["count"] for member in row["roster"]) <= 8
            ):
                raise ValueError("Quest source lacks its reviewed real encounter")
            launch = [
                effect for effect in action["effects"] if effect["effect_type"] == 10
            ]
            if len(launch) != 1 or launch[0]["parameters"] != [
                str(row["scenario"]["id"])
            ]:
                raise ValueError("Quest source lost its original scenario launch")
            for member in row["roster"]:
                if set(member) != {"reference", "count"} or any(
                    type(member[k]) is not int or member[k] <= 0 for k in member
                ):
                    raise ValueError(
                        "Quest encounter does not declare native species/count"
                    )
        elif row["roster"] or row["scenario"] is not None:
            raise ValueError("Ordinary gathering cannot impersonate an ambush")
        if row["mode"] == "encounter":
            slots = row["scenario"].get("actor_slots", 8)
            if (
                type(slots) is not int
                or not 1 <= slots <= 8
                or sum(m["count"] for m in row["roster"]) > slots
            ):
                raise ValueError("Quest scenario has invalid original actor slots")
            opening = row["scenario"].get("opening")
            if opening is not None:
                _validate_opening(row)
        if "prelude_objective_id" in row:
            if (
                row["mode"] != "encounter"
                or row["prelude_objective_id"] == row["objective_id"]
                or row["prelude_objective_id"]
                not in {o["d"] for o in definitions[row["quest_id"]]["cjJ"]}
                or (
                    source["type"] != "PositionTrigger"
                    and not any(e["effect_type"] == 1 for e in row["action"]["effects"])
                )
            ):
                raise ValueError("Quest source prelude is not its native read action")
        if "native_feedback" in row:
            expected_feedback = [
                e["action_reference"]
                for e in row["action"]["effects"]
                if e["effect_type"] == 1
            ]
            if (
                type(row["native_feedback"]) is not list
                or not row["native_feedback"]
                or row["native_feedback"] != expected_feedback
                or any(
                    type(value) is not int or value <= 0
                    for value in row["native_feedback"]
                )
            ):
                raise ValueError(
                    "Quest-source feedback is not its exact native type1 effect"
                )
        if row.get("owned_dungeon") is not None:
            _validate_owned_source(row)
        seen.add(identity)
    return value


@lru_cache(maxsize=1)
def document():
    """Keep the original source and its already-published receipt digest stable."""
    return _read_document(SOURCE)


@lru_cache(maxsize=1)
def registered_documents():
    paths = (
        SOURCE.with_name("ereboria-pirate-ambush.v1.json"),
        SOURCE.with_name("ereboria-goomy-continuation.v1.json"),
        SOURCE.with_name("whispering-lieutenant-4872.v1.json"),
        SOURCE.with_name("astrub-magnum-well.v1.json"),
        SOURCE.with_name("wild-estate-burger.v1.json"),
        SOURCE.with_name("kelba-2550-crates.v1.json"),
    )
    documents = (document(), *(_read_document(path) for path in paths if path.exists()))
    seen_ids, seen_objects = set(), set()
    for value in documents:
        for row in value["bindings"]:
            key = row["source"]["map_id"], row["source"]["id"]
            if row["id"] in seen_ids or key in seen_objects:
                raise ValueError("Conflicting registered quest-source identity")
            seen_ids.add(row["id"])
            seen_objects.add(key)
    return documents


def _all_bindings():
    return tuple(row for value in registered_documents() for row in value["bindings"])


def _document_for(row):
    matches = [
        value
        for value in registered_documents()
        if any(item["id"] == row["id"] for item in value["bindings"])
    ]
    if len(matches) != 1:
        raise ValueError("Quest source has no unique immutable declaration")
    return matches[0]


def _source_digest(row):
    return digest(_document_for(row))


def _source_body(row):
    return struct.pack(
        ">qHH",
        row["source"]["id"],
        row["action"]["wire_action"],
        row["action"].get("parameter", 0),
    )


def publish(db, value, revision):
    """Explicit additive source publication, with no player progress writes."""
    if (
        value not in registered_documents()
        or revision != value["native_metadata_revision"]
    ):
        raise ValueError("Quest source publication differs from reviewed native source")
    from wakfu_server import world_static, monsters, dungeon_monster_admission
    from wakfu_server.combat_geometry import published_geometry

    for definition in value["definitions"]:
        row = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
            (revision, definition["d"]),
        ).fetchone()
        if row is None or row["data"]["native"] != definition:
            raise ValueError("Quest source native definition changed")
        native_effective_eligibility.criterion(definition)
    admission = dungeon_monster_admission.current_policy()
    for row in value["bindings"]:
        source = row["source"]
        actual = world_static._MAPS.get(source["map_id"], {}).get(source["id"])
        if actual is None or any(
            actual.get(k) != source[k]
            for k in ("id", "map_id", "type", "x", "y", "z", "payload_hex")
        ):
            raise ValueError("Quest source differs from installed world object")
        geometry = published_geometry(source["map_id"])
        if source["type"] == "PositionTrigger":
            from wakfu_server import native_interactive_activation

            if {tuple(cell) for cell in row["activation_cells"]} != {
                tuple(cell) for cell in native_interactive_activation.decode(source)
            }:
                raise ValueError("Quest source trigger polygon differs from native")
        elif not {tuple(point) for point in row["approaches"]} <= geometry.cells:
            raise ValueError("Quest source has no actual native approach")
        opening = (row.get("scenario") or {}).get("opening")
        if (
            opening is not None
            and tuple(opening["owner_position"]) not in geometry.cells
        ):
            raise ValueError("Quest cinematic endpoint has no native walkable terrain")
        for member in row["roster"]:
            native = monsters.reference(member["reference"])
            if not native["native_abilities"] or native["min_level"] <= 0:
                raise ValueError("Quest encounter has no native fighting species")
            dungeon_monster_admission.require(
                admission,
                native["ref"],
                native["min_level"],
                native["min_level"],
                native=native,
            )
    previous = db.execute(
        "SELECT value FROM settings WHERE name=%s", (SETTING,)
    ).fetchone()
    old = {} if previous is None else previous["value"]
    if old.get("enabled") is not True:
        old = {}
    elif old.get("schema") != SCHEMA:
        raise ValueError("Existing quest-source publication has an unknown schema")
    sources = dict(old.get("sources", {}))
    if old.get("enabled") is True and old.get("source_sha256"):
        sources[old["source_sha256"]] = old["native_revision"]
    sources[digest(value)] = revision
    db.execute(
        "INSERT INTO settings(name,value) VALUES(%s,%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
        (
            SETTING,
            Jsonb(
                dict(
                    schema=SCHEMA,
                    enabled=True,
                    source_sha256=old.get("source_sha256", digest(value)),
                    native_revision=old.get("native_revision", revision),
                    sources=sources,
                )
            ),
        ),
    )
    return dict(quests=len(value["definitions"]), sources=len(value["bindings"]))


def _publication(db, row=None):
    saved = db.execute(
        "SELECT value FROM settings WHERE name=%s", (SETTING,)
    ).fetchone()
    if saved is None or saved["value"].get("enabled") is not True:
        return None
    publication = saved["value"]
    native = document() if row is None else _document_for(row)
    sources = dict(publication.get("sources", {}))
    if publication.get("source_sha256"):
        sources[publication["source_sha256"]] = publication.get("native_revision")
    if publication.get("schema") != SCHEMA:
        raise ValueError("Quest source publication lost its immutable source")
    if sources.get(digest(native)) != native["native_metadata_revision"]:
        return None
    return publication


def recognizes(map_id, body):
    if type(body) is not bytes or len(body) != 12:
        return False
    identity, action, parameter = struct.unpack(">qHH", body)
    return any(
        row["source"]["map_id"] == map_id
        and row["source"]["id"] == identity
        and (action, parameter)
        == (
            row["action"]["wire_action"],
            row["action"].get("parameter", 0),
        )
        for row in _all_bindings()
    )


def source_guard(expression, state, *, is_hero):
    """Restricted native source booleans, including an actual company role."""
    from wakfu_server.combat_local_criteria import parse_local_criterion
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    if type(is_hero) is not bool:
        raise ValueError("Missing authoritative quest-source company role")
    if expression == "":
        return True
    tree = parse_local_criterion(expression)
    queries = queries_from_state(state)

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not visit(node.operand)
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = [visit(item) for item in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and not node.keywords
        ):
            name = node.func.id
            if name == "IsHero" and not node.args:
                return is_hero
            if (
                name
                in (
                    "IsAchievementRunning",
                    "IsAchievementActive",
                    "IsAchievementComplete",
                    "IsAchievementObjectiveComplete",
                )
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant)
                and type(node.args[0].value) is int
                and node.args[0].value > 0
            ):
                value = queries[name](node.args[0].value)
                if type(value) is bool:
                    return value
        raise ValueError("Unsupported native quest-source predicate")

    return visit(tree)


def _hero(db, character):
    row = db.execute(
        "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s",
        (character["account_id"],),
    ).fetchone()
    return row is not None and row["leader_id"] != character["id"]


def _eligible(db, store, character, row):
    from wakfu_server.dungeon_criteria import evaluate
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    state = storage.load_locked(db, character["id"])
    if (
        row["quest_id"] not in state["running"]
        or row["objective_id"] in state["objectives"]
    ):
        return None
    definition = next(
        native
        for native in _document_for(row)["definitions"]
        if native["d"] == row["quest_id"]
    )
    native = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision=%s AND definition_id=%s",
        (_document_for(row)["native_metadata_revision"], row["quest_id"]),
    ).fetchone()
    if (
        native is None
        or digest(native["data"]["native"]) != row["native_definition_sha256"]
    ):
        raise ValueError("Quest-source native objective authority changed")
    objective = next(
        item for item in definition["cjJ"] if item["d"] == row["objective_id"]
    )
    authority = queries_from_state(state)
    if not all(
        evaluate(store, expression, character=character, queries=authority)
        for expression in (
            native_effective_eligibility.criterion(definition),
            objective["ckc"],
            objective["cke"],
        )
    ):
        return None
    hero = _hero(db, character)
    if not source_guard(row["action"]["criterion"], state, is_hero=hero):
        return None
    if row["mode"] == "prelude" and row["source"]["type"] == "PositionTrigger":
        # The authenticated movement crossing is the native trigger itself.
        # Its prelude step is independent of the following type-10 encounter
        # effect, whose native criterion requires this prelude to be complete.
        effects = []
    else:
        effects = [
            effect
            for effect in row["action"]["effects"]
            if effect["effect_type"] == (10 if row["mode"] == "encounter" else 1)
        ]
        if not effects or not any(
            source_guard(effect["criterion"], state, is_hero=hero) for effect in effects
        ):
            return None
    return state, definition


def defer_dungeon_completion(db, store, instance_id):
    """Keep an accepted native read in its original owned dungeon reachable."""
    reads = [
        row
        for row in _all_bindings()
        if row.get("owned_dungeon") is not None
        and row["mode"] == "gather"
        and _publication(db, row) is not None
    ]
    if not reads:
        return False
    members = db.execute(
        "SELECT c.*,i.definition_id AS read_definition_id,i.entry_map_id AS read_entry_map_id,"
        "i.entry_object_id AS read_entry_source_id,i.entry_destination_id AS read_destination_id,"
        "i.start_map_id AS read_asset_map_id FROM dungeon_instances i "
        "JOIN dungeon_instance_members m USING(instance_id) "
        "JOIN characters c ON c.id=m.character_id "
        "WHERE i.instance_id=%s AND i.status IN ('active','completed') "
        "AND m.status='active' AND c.instance_id=i.instance_id AND c.map_id=i.start_map_id",
        (instance_id,),
    ).fetchall()
    for character in members:
        for row in reads:
            scope = row["owned_dungeon"]
            if (
                character["read_asset_map_id"] == row["source"]["map_id"]
                and all(
                    character["read_" + key] == scope[key]
                    for key in (
                        "definition_id",
                        "entry_map_id",
                        "entry_source_id",
                        "destination_id",
                    )
                )
                and _eligible(db, store, character, row) is not None
            ):
                return True
    return False


def _advance(db, store, character, row, *, event_key, evidence):
    qualified = _eligible(db, store, character, row)
    if qualified is None:
        return []
    before, definition = qualified
    now_ms = int(store.now().timestamp() * 1000)
    planned = mission_progress.advance_objective(
        before,
        definition,
        row["objective_id"],
        character=character,
        store=store,
        now_ms=now_ms,
    )
    if not planned[2]:
        return []
    if not storage.record_event(db, character["id"], event_key, evidence):
        raise ValueError("Quest source receipt conflicts with missing progress")
    result = mission_dependencies.settle(
        db,
        store,
        character,
        before,
        planned,
        {definition["d"]: definition},
        (),
        now_ms=now_ms,
    )
    return result["packets"]


def _spawn_key(binding):
    return "quest-source-created:" + binding["id"]


def _source_position(
    character, row, body, *, db=None, generation=None, approved_positions=()
):
    from wakfu_server import world_static
    from wakfu_server.combat_geometry import published_geometry

    source = row["source"]
    owned = row.get("owned_dungeon")
    if owned is not None:
        if db is None or generation is None or not character.get("instance_id"):
            raise ValueError("Quest read requires its actual owned dungeon membership")
        member = db.execute(
            "SELECT i.definition_id,i.entry_map_id,i.entry_object_id,i.entry_destination_id,i.start_map_id "
            "FROM dungeon_instances i JOIN dungeon_instance_members m USING(instance_id) "
            "WHERE i.instance_id=%s AND i.status IN ('active','completed') "
            "AND m.character_id=%s AND m.status='active' AND m.session_generation=%s",
            (character["instance_id"], character["id"], generation),
        ).fetchone()
        if (
            member is None
            or member["definition_id"] != owned["definition_id"]
            or member["entry_map_id"] != owned["entry_map_id"]
            or member["entry_object_id"] != owned["entry_source_id"]
            or member["entry_destination_id"] != owned["destination_id"]
            or member["start_map_id"] != source["map_id"]
        ):
            raise ValueError("Quest read belongs to a different original dungeon run")
    elif character.get("instance_id", 0) != 0:
        raise ValueError("Public quest source cannot enter a private context")
    actual = world_static.interaction(dict(character, instance_id=0), body)
    position = tuple(character[k] for k in ("x", "y", "z"))
    if any(actual[k] != source[k] for k in ("id", "map_id", "type", "x", "y", "z")):
        raise ValueError("Quest source differs from its installed native object")
    if source["type"] == "PositionTrigger":
        from wakfu_server import native_interactive_activation

        polygon = {tuple(cell) for cell in row["activation_cells"]}
        if (
            actual["action"] != "WALKON"
            or actual["action_id"] != row["action"]["wire_action"]
            or actual["parameter"] != row["action"].get("parameter", 0)
            or polygon
            != {tuple(cell) for cell in native_interactive_activation.decode(source)}
        ):
            raise ValueError("Quest source lost its native WALKON polygon")
        if position not in polygon:
            if (
                not isinstance(approved_positions, (tuple, list, set, frozenset))
                or not 1 <= len(approved_positions) <= 257
                or any(
                    not isinstance(cell, tuple)
                    or len(cell) != 3
                    or any(type(value) is not int for value in cell)
                    for cell in approved_positions
                )
                or position not in approved_positions
                or not polygon.intersection(approved_positions)
            ):
                raise ValueError("Quest trigger is outside its actual movement path")
        return
    if (
        position not in set(map(tuple, row["approaches"]))
        or abs(character["x"] - source["x"]) + abs(character["y"] - source["y"]) > 1
        or position not in published_geometry(source["map_id"]).cells
    ):
        raise ValueError("Quest source is outside its actual native approach")


def _feedback(db, character, row):
    """Readable clues use their original conditional Lua, without granting facts."""
    if not row.get("native_feedback"):
        return []
    from wakfu_server.exploration_artifact_actions import _script_packet

    state = storage.load_locked(db, character["id"])
    hero = _hero(db, character)
    if not source_guard(row["action"]["criterion"], state, is_hero=hero):
        return []
    return [
        _script_packet(character["id"], row["source"]["id"], effect["action_reference"])
        for effect in row["action"]["effects"]
        if effect["effect_type"] == 1
        and effect["action_reference"] in row["native_feedback"]
        and source_guard(effect["criterion"], state, is_hero=hero)
    ]


def interact(
    store,
    groups,
    account_id,
    generation,
    location,
    body,
    *,
    loaded,
    blocked,
    approved_positions=(),
):
    """Authenticate the real source; ambushes return an ordinary attack target."""
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard

    if blocked or not loaded or not recognizes(location["map_id"], body):
        raise ValueError("Quest-source interaction is unavailable")
    identity = struct.unpack_from(">q", body)[0]
    row = next(row for row in _all_bindings() if row["source"]["id"] == identity)
    with groups.lock, store.connection() as db:
        _leased_owner(store, db, account_id, generation, location)
        _guard(db, location["id"])
        character = store.character(account_id, location["id"], db)
        _owner(db, character)
        if _publication(db, row) is None:
            return dict(handled=False, character=character, packets=[], target=None)
        _source_position(
            character,
            row,
            body,
            db=db,
            generation=generation,
            approved_positions=approved_positions,
        )
        packets = _feedback(db, character, row)
        if "prelude_objective_id" in row:
            prelude_mode = (
                "prelude" if row["source"]["type"] == "PositionTrigger" else "gather"
            )
            packets.extend(
                _advance(
                    db,
                    store,
                    character,
                    dict(
                        row,
                        objective_id=row["prelude_objective_id"],
                        mode=prelude_mode,
                    ),
                    event_key="quest-source-prelude:" + row["id"],
                    evidence=dict(
                        schema=SCHEMA,
                        kind="actual_source_read",
                        source_object=identity,
                        owner=character["id"],
                    ),
                )
            )
        if _eligible(db, store, character, row) is None:
            return dict(handled=True, character=character, packets=packets, target=None)
        opening = (row.get("scenario") or {}).get("opening")
        opening_shown = False
        if opening is not None:
            from . import tutorial_presentation_once

            opening_shown = tutorial_presentation_once.claim(
                db, character["id"], row["scenario"]["id"], opening["event"]
            )
            if opening_shown:
                packets.append(
                    (
                        13411,
                        struct.pack(
                            ">BiiB", 0, opening["event"], row["scenario"]["id"], 0
                        ),
                    )
                )
        now_ms = int(store.now().timestamp() * 1000)
        token = secrets.token_hex(16)
        ticket = dict(
            schema=SCHEMA,
            token=token,
            owner=character["id"],
            account_id=account_id,
            generation=str(generation),
            binding=row["id"],
            source_sha256=_source_digest(row),
            position={
                key: character[key] for key in ("map_id", "instance_id", "x", "y", "z")
            },
            due_ms=now_ms
            + row["native_occupation_ms"]
            + (opening["duration_ms"] + 250 if opening_shown else 0),
            opening_shown=opening_shown,
        )
        if row["source"]["type"] == "PositionTrigger":
            ticket["activation_path"] = [list(cell) for cell in approved_positions]
        if not storage.record_event(
            db, character["id"], "quest-source-operation:" + token, ticket
        ):
            raise ValueError("Quest-source operation token collided")
        return dict(
            handled=True,
            character=character,
            packets=packets,
            target=None,
            ticket=ticket,
        )


def _finish_action(db, store, groups, character, row):
    identity = row["source"]["id"]
    if row["mode"] == "gather":
        group = row["group"]
        reference, quantity, consumes = group["cod"], group["coe"], group["cof"]
        if (
            type(reference) is not int
            or reference < 0
            or type(quantity) is not int
            or quantity < 0
            or type(consumes) is not bool
            or reference
            and quantity <= 0
        ):
            raise ValueError("Quest source has invalid native item operands")
        packets, payment = [], []
        if reference:
            from wakfu_server.combat_inventory_date_conditions import (
                complete_owned_item_quantity,
            )

            if complete_owned_item_quantity(character, (reference,)) < quantity:
                raise ValueError("Quest source requires its actual native item")
            if consumes:
                from wakfu_server.native_generic_rewards import _payment

                character, packets, payment = _payment(
                    db,
                    store,
                    character,
                    dict(group_cod=reference, group_coe=quantity),
                )
        packets += _advance(
            db,
            store,
            character,
            row,
            event_key="quest-source-gather:" + row["id"],
            evidence=dict(
                schema=SCHEMA,
                kind="actual_source_gather",
                source_object=identity,
                owner=character["id"],
                **({"native_item_payment": payment} if reference else {}),
            ),
        )
        return dict(handled=True, character=character, packets=packets, target=None)
    old = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], _spawn_key(row)),
    ).fetchone()
    if old is not None:
        receipt = old["payload"]
        group = db.execute(
            "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            tuple(receipt["group_key"]),
        ).fetchone()
        if (
            group is None
            or group["members"] != receipt["members"]
            or group["status"] != "available"
        ):
            raise ValueError("Quest-source original group is not available for retry")
        members = group["members"]
    else:
        receipt = _spawn(db, store, groups, character, row)
        members = receipt["members"]
    from wakfu_server.combat_monster_world import spawn_group

    return dict(
        handled=True,
        character=character,
        packets=[],
        target=members[0],
        scene_packet=(
            12608,
            spawn_group(members, group_id=receipt["group_key"][2]),
        ),
        binding=row["id"],
    )


def acknowledge_opening(store, account_id, generation, location, ticket, event):
    """Accept only the native end/skip of this owner's actually offered movie."""
    from wakfu_server.paid_containers import _leased_owner

    if (
        not isinstance(ticket, dict)
        or ticket.get("schema") != SCHEMA
        or ticket.get("opening_shown") is not True
        or (ticket.get("owner"), ticket.get("account_id"), ticket.get("generation"))
        != (location["id"], account_id, str(generation))
    ):
        raise ValueError("Quest-source cinematic is not offered to this owner")
    row = next((r for r in _all_bindings() if r["id"] == ticket.get("binding")), None)
    opening = None if row is None else (row.get("scenario") or {}).get("opening")
    if (
        opening is None
        or opening["event"] != event
        or ticket.get("source_sha256") != _source_digest(row)
    ):
        raise ValueError("Quest-source cinematic callback is not its original end")
    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, location)
        current = store.character(account_id, location["id"], db)
        saved = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (current["id"], "quest-source-operation:" + ticket["token"]),
        ).fetchone()
        if saved is None or saved["payload"] != ticket:
            raise ValueError("Quest-source movie lost its actual issued operation")
        _source_position(
            current,
            row,
            _source_body(row),
            db=db,
            generation=generation,
            approved_positions=ticket.get("activation_path", ()),
        )
        storage.record_event(
            db,
            current["id"],
            "quest-source-opening-ended:" + ticket["token"],
            dict(
                kind="native_source_movie_ended",
                binding=row["id"],
                owner=current["id"],
                event=event,
            ),
        )


def complete_operation(
    store, groups, account_id, generation, location, ticket, *, loaded, blocked
):
    """Only the owner's live server ticket can finish the reviewed source delay.

    The native client already executes its local generic-IE animation before
    cpF. No guessed occupation packet or duplicated local script is emitted.
    """
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard

    if (
        type(ticket) is not dict
        or ticket.get("schema") != SCHEMA
        or (ticket.get("owner"), ticket.get("account_id"), ticket.get("generation"))
        != (location["id"], account_id, str(generation))
    ):
        raise ValueError("Quest-source operation belongs to another lease")
    with groups.lock, store.connection() as db:
        _leased_owner(store, db, account_id, generation, location)
        character = store.character(account_id, location["id"], db)
        saved = db.execute(
            "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], "quest-source-operation:" + ticket["token"]),
        ).fetchone()
        if saved is None or saved["payload"] != ticket:
            raise ValueError("Quest-source operation lost its immutable start")
        old = db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (character["id"], "quest-source-operation-ended:" + ticket["token"]),
        ).fetchone()
        if old is not None:
            return dict(handled=True, character=character, packets=[], target=None)
        row = next(
            binding for binding in _all_bindings() if binding["id"] == ticket["binding"]
        )
        if ticket["source_sha256"] != _source_digest(row):
            raise ValueError("Quest-source operation lost its immutable declaration")
        opening = (row.get("scenario") or {}).get("opening")
        opening_ended = False
        if opening is not None and ticket.get("opening_shown") is True:
            acknowledged = db.execute(
                "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                (character["id"], "quest-source-opening-ended:" + ticket["token"]),
            ).fetchone()
            opening_ended = acknowledged is not None
        not_before = ticket["due_ms"] - (
            opening["duration_ms"] + 250 if opening_ended else 0
        )
        if int(store.now().timestamp() * 1000) < not_before:
            return dict(
                handled=True,
                character=character,
                packets=[],
                target=None,
                ticket=ticket,
            )
        cancelled = (
            blocked
            or not loaded
            or _publication(db, row) is None
            or any(character[key] != value for key, value in ticket["position"].items())
        )
        if not cancelled:
            _guard(db, character["id"])
            cancelled = _eligible(db, store, character, row) is None
        if cancelled:
            result = dict(handled=True, character=character, packets=[], target=None)
        else:
            _source_position(
                character,
                row,
                _source_body(row),
                db=db,
                generation=generation,
                approved_positions=ticket.get("activation_path", ()),
            )
            relocation = _finish_opening(db, character, row)
            result = _finish_action(db, store, groups, character, row)
            if relocation is not None:
                result["packets"].insert(0, relocation)
                result["relocated"] = True
        if not storage.record_event(
            db,
            character["id"],
            "quest-source-operation-ended:" + ticket["token"],
            dict(
                schema=SCHEMA,
                owner=character["id"],
                binding=row["id"],
                token=ticket["token"],
                cancelled=cancelled,
            ),
        ):
            raise ValueError("Quest-source completion raced its actual effects")
        return result


def _finish_opening(db, character, row):
    opening = (row.get("scenario") or {}).get("opening")
    if opening is None:
        return None
    from wakfu_server.combat_geometry import published_geometry

    position = tuple(opening["owner_position"])
    if position not in published_geometry(character["map_id"]).cells:
        raise ValueError("Native source cinematic ends outside its real surface")
    previous = tuple(character[k] for k in ("x", "y", "z"))
    changed = db.execute(
        "UPDATE characters SET x=%s,y=%s,z=%s WHERE id=%s AND account_id=%s AND map_id=%s "
        "AND instance_id=0 AND x=%s AND y=%s AND z=%s",
        (
            *position,
            character["id"],
            character["account_id"],
            character["map_id"],
            *previous,
        ),
    )
    if changed.rowcount != 1:
        raise ValueError("Native source cinematic lost its committed owner position")
    character.update(zip(("x", "y", "z"), position))
    return 13530, struct.pack(">qiihBi", character["id"], *position, 7, -1)


def ordinary_source_formation(
    geometry, origin, references, profiles, occupied, columns
):
    """Keep a native walking approach to the primary target for its whole group.

    Other members need legal native anchors; they do not each need their own
    simultaneous attack edge to the source owner's one standing cell.
    """
    from wakfu_server.actor_approach import (
        ApproachUnavailable,
        approach_path,
        combat_approach,
    )
    from wakfu_server.combat_geometry import reachable
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_server.combat_walk_surface_policy import (
        native_npc_point_placement_allowed,
        native_player_point_placement_allowed,
    )

    origin = tuple(origin)
    occupied = set(occupied)
    component = reachable(origin, geometry.cells, geometry.outgoing) & reachable(
        origin, geometry.cells, geometry.incoming
    )
    by_xy = {}
    for cell in geometry.cells:
        by_xy.setdefault(cell[:2], []).append(cell)
    occupied.update(
        surface
        for point in footprint(origin, profiles["default_actor_radius"])
        for surface in by_xy.get(point, ())
        if abs(surface[2] - origin[2]) <= 1
    )
    player_point = profiles["default_actor_radius"] == 0
    player_allowed = (
        (lambda cell: native_player_point_placement_allowed(columns, cell))
        if player_point
        else None
    )
    if player_point and not player_allowed(origin):
        raise ValueError("Quest-source owner lacks an ordinary native attack surface")
    candidates = sorted(
        geometry.cells,
        key=lambda cell: (
            abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]),
            abs(cell[2] - origin[2]),
            cell,
        ),
    )
    members = []
    for reference in references:
        radius = profiles["npc_profiles"][str(reference)]["physical_radius"]
        for cell in candidates:
            if (
                cell in occupied
                or cell not in component
                or abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) > 4
                or radius == 0
                and not native_npc_point_placement_allowed(columns, cell)
            ):
                continue
            points = set(footprint(cell, radius))
            body = {
                surface
                for point in points
                for surface in by_xy.get(point, ())
                if abs(surface[2] - cell[2]) <= 1
            }
            if (
                {surface[:2] for surface in body} != points
                or not body <= component
                or body & occupied
            ):
                continue
            member = dict(
                id=-(len(members) + 1), ref=reference, x=cell[0], y=cell[1], z=cell[2]
            )
            proposed = members + [member]
            approaches, blocked = combat_approach(
                geometry,
                proposed,
                proposed[0]["id"],
                profiles,
                final_cell_allowed=player_allowed,
            )
            if origin in blocked:
                continue
            try:
                approach_path(
                    geometry,
                    origin,
                    approaches.__contains__,
                    blocked=blocked | occupied,
                )
            except ApproachUnavailable:
                continue
            members.append(member)
            occupied.update(body)
            break
        else:
            raise ValueError(
                "Quest-source encounter has no ordinary native attack approach"
            )
    return [tuple(member[k] for k in ("x", "y", "z")) for member in members]


def _spawn(db, store, groups, character, row):
    from wakfu_server import monsters
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.combat_actor_snapshot import native_actor_catalog
    from wakfu_server.combat_sn_path import NativeSnColumns
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.combat_obstacle_condition import footprint

    geometry = published_geometry(character["map_id"])
    origin = tuple(character[k] for k in ("x", "y", "z"))
    profiles = native_actor_catalog()
    by_xy = {}
    for cell in geometry.cells:
        by_xy.setdefault(cell[:2], []).append(cell)
    occupied = {
        surface
        for group in groups.available(character["map_id"], 0)
        for member in group["members"]
        for point in footprint(
            (member["x"], member["y"]),
            profiles["npc_profiles"][str(member["ref"])]["physical_radius"],
        )
        for surface in by_xy.get(point, ())
        if abs(surface[2] - member["z"]) <= 1
    }
    references = [
        entry["reference"] for entry in row["roster"] for _ in range(entry["count"])
    ]
    positions = ordinary_source_formation(
        geometry,
        origin,
        references,
        profiles,
        occupied,
        NativeSnColumns.from_published(character["map_id"]),
    )
    magnitude = allocate_block(db, len(references))
    members = []
    for reference, cell in zip(references, positions):
        native = monsters.reference(reference)
        members.append(
            monsters.owned_instance(
                native["ref"],
                native["min_level"],
                -(magnitude + len(members)),
                map_id=character["map_id"],
                instance_id=0,
                x=cell[0],
                y=cell[1],
                z=cell[2],
            )
        )
    group_id = secrets.randbits(51) + 1
    key = (character["map_id"], 0, group_id)
    payload = dict(
        schema=SCHEMA,
        owner=character["id"],
        binding=row["id"],
        source_sha256=_source_digest(row),
        group_key=list(key),
        members=members,
    )
    if not storage.record_event(db, character["id"], _spawn_key(row), payload):
        raise ValueError("Quest-source group creation raced")
    for member in members:
        if not storage.record_event(
            db, character["id"], f"quest-source-actor:{-member['id']}", payload
        ):
            raise ValueError("Quest-source actor identity collided")
    groups.register_transaction(db, *key, members)
    return payload


def started_packet(db, character, fight, monsters):
    """Ordinary admissions stay untouched; source receipts select presentation."""
    if not candidate_monsters(monsters):
        return None
    saved = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], f"quest-source-fight:{fight.id}"),
    ).fetchone()
    if saved is None:
        return None
    return scenario_begin(db, character, saved["payload"]["binding"], fight)


def scenario_begin(db, character, binding, fight):
    """Native presentation references only the already-created actual fight."""
    row = next(item for item in _all_bindings() if item["id"] == binding)
    saved = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], f"quest-source-fight:{fight.id}"),
    ).fetchone()
    if saved is None or saved["payload"]["binding"] != binding:
        raise ValueError("Native scenario has no actual source-owned fight")
    receipt = saved["payload"]
    identities = [member["id"] for member in receipt["members"]]
    slots = row["scenario"].get("actor_slots", 8)
    if len(identities) > slots or not set(identities) <= set(fight.actors):
        raise ValueError("Native scenario roster differs from its ordinary fight")
    arguments = [
        receipt["group_key"][2],
        *identities,
        *([0] * (slots - len(identities))),
        fight.id,
        character["id"],
    ]
    return 13411, struct.pack(
        ">BiiB",
        0,
        row["scenario"]["begin_event"],
        row["scenario"]["id"],
        len(arguments),
    ) + b"".join(struct.pack(">q", identity) for identity in arguments)


def group_owners(db, groups):
    references = _references()
    candidates = [
        (group, member)
        for group in groups
        for member in group["members"]
        if member.get("ref") in references
        and type(member.get("id")) is int
        and member["id"] < 0
    ]
    if not candidates:
        return {}
    keys = [f"quest-source-actor:{-member['id']}" for _, member in candidates]
    rows = db.execute(
        "SELECT character_id,event_key,payload FROM character_achievement_events WHERE event_key=ANY(%s)",
        (keys,),
    ).fetchall()
    by_key = {row["event_key"]: row for row in rows}
    owners = {}
    for group, member in candidates:
        saved = by_key.get(f"quest-source-actor:{-member['id']}")
        if saved is None:
            continue
        receipt = saved["payload"]
        if (
            receipt.get("schema") != SCHEMA
            or receipt.get("owner") != saved["character_id"]
            or tuple(receipt.get("group_key", ())) != tuple(group["key"])
            or receipt.get("members") != list(group["members"])
        ):
            raise ValueError(
                "Quest-source owner receipt differs from its original group"
            )
        previous = owners.setdefault(tuple(group["key"]), saved["character_id"])
        if previous != saved["character_id"]:
            raise ValueError("Quest-source group has conflicting owners")
    return owners


def is_source_owned_group(db, key, members):
    """Identify the frozen group without relying on its current positions."""
    from wakfu_server.npc_actor_identity import MAXIMUM, MINIMUM

    if key[1] != 0:
        return False
    keys = [
        f"quest-source-actor:{-member['id']}"
        for member in members
        if type(member.get("id")) is int and MINIMUM <= -member["id"] <= MAXIMUM
    ]
    if not keys:
        return False
    return (
        db.execute(
            "SELECT 1 FROM character_achievement_events WHERE event_key=ANY(%s) "
            "AND payload->>'schema'=%s AND payload->'group_key'=%s "
            "AND payload->'owner'=to_jsonb(character_id) LIMIT 1",
            (keys, SCHEMA, Jsonb(list(key))),
        ).fetchone()
        is not None
    )


def visible_groups(db, groups, owner):
    owned = group_owners(db, groups)
    return [
        group
        for group in groups
        if tuple(group["key"]) not in owned or owned[tuple(group["key"])] == owner
    ]


def candidate_monsters(monsters):
    return any(member.get("ref") in _references() for member in monsters)


@lru_cache(maxsize=1)
def _references():
    return frozenset(
        entry["reference"] for binding in _all_bindings() for entry in binding["roster"]
    )


def admit(db, character, monsters, group_key):
    owners = group_owners(db, [dict(key=tuple(group_key), members=list(monsters))])
    owner = owners.get(tuple(group_key))
    if owner is None:
        return False
    if owner != character["id"]:
        raise ValueError("Quest-source encounter belongs to another character")
    return True


def bind_fight(db, store, character, fight_id, monsters, group_key):
    """Called by the normal durable fight constructor, never a client callback."""
    group = dict(key=tuple(group_key), members=list(monsters))
    owners = group_owners(db, [group])
    if tuple(group_key) not in owners:
        return
    if owners[tuple(group_key)] != character["id"]:
        raise ValueError("Quest-source encounter belongs to another character")
    actor = monsters[0]
    saved = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], f"quest-source-actor:{-actor['id']}"),
    ).fetchone()
    payload = saved["payload"]
    row = next(item for item in _all_bindings() if item["id"] == payload["binding"])
    if _publication(db, row) is None:
        raise ValueError("Quest-source encounter is not published")
    if _eligible(db, store, character, row) is None:
        raise ValueError("Quest-source fight no longer has its active objective")
    storage.record_event(
        db,
        character["id"],
        f"quest-source-fight:{fight_id}",
        dict(payload, fight_id=fight_id),
    )


def settle(db, store, character, fight, original_monsters):
    """Complete only the actual source owner's fully defeated original roster."""
    if not candidate_monsters(original_monsters):
        return []
    saved = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], f"quest-source-fight:{fight.id}"),
    ).fetchone()
    if saved is None:
        return []
    payload = saved["payload"]
    row = next(item for item in _all_bindings() if item["id"] == payload["binding"])
    if (
        payload.get("schema") != SCHEMA
        or payload.get("owner") != character["id"]
        or payload.get("source_sha256") != _source_digest(row)
        or payload.get("members") != list(original_monsters)
        or payload.get("fight_id") != fight.id
    ):
        raise ValueError("Quest-source settlement lost its original encounter")
    if fight.phase != "finished" or type(fight.winner) is not int:
        raise ValueError("Quest-source fight is not genuinely finished")
    owner = fight.actors.get(character["id"])
    if owner is None or not owner.controlled or owner.team != fight.winner:
        return []
    original = {member["id"] for member in original_monsters}
    deaths = {
        event.get("actor_id") for event in fight.events if event.get("kind") == "death"
    }
    from wakfu_server.combat_test_commands import administrative_victory

    operator_victory = administrative_victory(
        fight, account_id=character["account_id"], character_id=character["id"]
    )
    if (not original <= deaths and not operator_victory) or any(
        identity not in fight.actors
        or fight.actors[identity].controlled
        or fight.actors[identity].team == fight.winner
        or fight.actors[identity].hp != 0
        for identity in original
    ):
        raise ValueError("Quest-source victory lacks its real original enemy deaths")
    if Counter(member["ref"] for member in original_monsters) != Counter(
        {member["reference"]: member["count"] for member in row["roster"]}
    ):
        raise ValueError(
            "Quest-source victory differs from its reviewed native formation"
        )
    group = db.execute(
        "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        tuple(payload["group_key"]),
    ).fetchone()
    participant = db.execute(
        "SELECT p.team,f.status FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s AND p.character_id=%s AND p.account_id=%s",
        (fight.id, character["id"], character["account_id"]),
    ).fetchone()
    if (
        group is None
        or group["status"] != "defeated"
        or group["members"] != payload["members"]
        or participant is None
        or participant["status"] != "finished"
        or participant["team"] != fight.winner
    ):
        raise ValueError("Quest-source victory has no normal durable settlement")
    packets = _advance(
        db,
        store,
        character,
        row,
        event_key=f"quest-source-victory:{row['id']}",
        evidence=dict(
            schema=SCHEMA,
            kind=(
                "administrative_original_encounter_victory"
                if operator_victory
                else "genuine_original_encounter_victory"
            ),
            fight_id=fight.id,
            source_object=row["source"]["id"],
            group_key=payload["group_key"],
            original_actor_ids=sorted(original),
            owner=character["id"],
        ),
    )
    if not packets:
        return []
    terminal = (
        13411,
        struct.pack(
            ">BiiBq",
            0,
            row["scenario"]["win_event"],
            row["scenario"]["id"],
            1,
            payload["group_key"][2],
        ),
    )
    return [terminal, *packets]
