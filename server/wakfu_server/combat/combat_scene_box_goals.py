"""Source-bound box placement objectives after genuine native spell execution.

The native programs own movement, resources and original box deaths on goals.
This observer authenticates their normal victory and never changes HP or the
fight outcome.
"""

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

SCHEMA = "owned-box-goals-v1"


@lru_cache(maxsize=1)
def _native_constructors():
    raw = Path(__file__).with_name("native_passive_box_sources.json").read_bytes()
    if (
        sha256(raw).hexdigest()
        != "1234105448b318755df882feb4a417210af4e64ed56437a741e64d9077bdf03e"
    ):
        raise ValueError("Passive box constructor source changed")
    document = json.loads(raw)
    if document.get("schema") != "native-passive-box-sources-v1":
        raise ValueError("Unknown native passive box source schema")
    return document["constructors"]


def passive_admission(configuration, room_order, reference, level, native):
    """Admit an original passive box only inside its sealed goal scene.

    No ordinary NPC activation or empty-book permission is added globally.
    Native constructor states use the existing attested scene-state path.
    """
    rooms = [
        r
        for r in configuration.get("topology", {}).get("rooms", ())
        if r["order"] == room_order
    ]
    if len(rooms) != 1:
        return False
    room = rooms[0]
    descriptor = room.get("encounter_scene")
    if not descriptor or descriptor.get("box_goals") is None:
        return False
    selected = declaration(descriptor, room["cells"])
    if selected["box_reference"] != reference:
        return False
    source = _native_constructors().get(str(reference))
    if source is None:
        raise ValueError("Goal scene lacks an attested native passive constructor")
    from .combat_ordinary_authority import native_property_catalog
    from .combat_encounter_scene_states import native_state_source_digest
    from wakfu_server.spell_audit import states_catalog

    properties = native_property_catalog()["npc"].get(str(reference))
    stats = native.get("statistics", {})
    programs = [
        r
        for r in descriptor.get("state_programs", ())
        if reference in r.get("target_references", ())
    ]
    if (
        native.get("ref") != reference
        or selected["goal_area_reference"] != source["goal_area_reference"]
        or native.get("native_abilities") != source["native_abilities"]
        or native.get("min_level") != source["min_level"]
        or native.get("max_level") != source["max_level"]
        or not source["min_level"] <= level <= source["max_level"]
        or stats.get("HP", {}).get("base") != 1
        or any(stats.get(k, {}).get("base") != 0 for k in ("AP", "MP", "WP"))
        or properties
        != {k: source[k] for k in ("fight_properties", "world_properties")}
        or len(programs) != 1
        or programs[0]
        != dict(
            target_references=[reference],
            state_id=source["state_id"],
            level=source["state_level"],
            protected=source["initial_state_triples"][2] == 0,
            source_sha256=source["state_source_sha256"],
        )
        or native_state_source_digest(states_catalog(), source["state_id"])
        != source["state_source_sha256"]
    ):
        raise ValueError("Passive goal box changed its native constructor authority")
    return True


def declaration(descriptor, room_cells=None):
    value = descriptor.get("box_goals")
    if value is None:
        return None
    if (
        type(value) is not dict
        or set(value)
        != {
            "schema",
            "box_reference",
            "goal_area_reference",
            "goals",
            "spell_ids",
            "evidence",
        }
        or value["schema"] != SCHEMA
        or type(value["box_reference"]) is not int
        or value["box_reference"] <= 0
        or type(value["goal_area_reference"]) is not int
        or value["goal_area_reference"] <= 0
        or type(value["goals"]) is not list
        or not value["goals"]
        or any(
            type(p) is not list or len(p) != 3 or any(type(n) is not int for n in p)
            for p in value["goals"]
        )
        or len(set(map(tuple, value["goals"]))) != len(value["goals"])
        or type(value["spell_ids"]) is not list
        or not value["spell_ids"]
        or any(type(n) is not int or n <= 0 for n in value["spell_ids"])
        or len(set(value["spell_ids"])) != len(value["spell_ids"])
        or type(value["evidence"]) is not str
        or not value["evidence"].strip()
        or descriptor.get("full_room_scope") is not True
    ):
        raise ValueError("Box goals lack their explicit owned scene declaration")
    if room_cells is not None and not set(map(tuple, value["goals"])) <= set(
        map(tuple, room_cells)
    ):
        raise ValueError("Box goals leave their actual native board terrain")
    glyphs = descriptor.get("native_initial_glyphs", ())
    if len(glyphs) != len(value["goals"]) or {
        (row.get("reference"), tuple(row.get("cell", ())), row.get("level"))
        for row in glyphs
    } != {(value["goal_area_reference"], tuple(point), 0) for point in value["goals"]}:
        raise ValueError("Box goals differ from their original native goal glyphs")
    return value


def _goal_areas(fight, selected):
    """Read the same original registered goal entities that the client sees."""
    from .combat_environment_glyphs import verify_environment_glyph

    sources = [
        row
        for row in getattr(fight, "native_environment_glyph_constructors", ())
        if row.get("reference") == selected["goal_area_reference"]
    ]
    if len(sources) != len(selected["goals"]) or {
        tuple(row["cell"]) for row in sources
    } != set(map(tuple, selected["goals"])):
        raise ValueError("Box goals lost their actual original goal constructors")
    identities = []
    for source in sources:
        row = getattr(fight, "native_effect_areas", {}).get(source["uid"])
        if (
            row is None
            or row.get("owner_id") is not None
            or row.get("reference") != selected["goal_area_reference"]
            or tuple(row["cell"]) != tuple(source["cell"])
        ):
            raise ValueError("Box goals lost a registered original goal glyph")
        verify_environment_glyph(fight, row)
        identities.append(row["uid"])
    return sorted(identities)


def _native_goal_deaths(fight, selected, boxes, caster_id):
    from .combat_ordinary_death import registered_ordinary_death

    source = _native_constructors().get(str(selected["box_reference"]))
    if source is None or type(source.get("goal_death_effect_reference")) is not int:
        raise ValueError("Box goal lacks an attested native death program")
    result = []
    for binding in boxes:
        box = fight.actors[binding["actor_id"]]
        if not registered_ordinary_death(fight, box):
            raise ValueError("Goal box lacks a native registered corpse")
        matches = []
        for index in range(2, len(fight.events)):
            removal, kill, death = fight.events[index - 2 : index + 1]
            if death.get("kind") != "death" or death.get("actor_id") != box.id:
                continue
            if (
                removal.get("kind") == "state_removed"
                and removal.get("actor_id") == box.id
                and removal.get("reference") == source["state_id"]
                and removal.get("source") == "decurse321"
                and type(removal.get("uid")) is int
                and removal["uid"] > 0
                and kill.get("kind") == "kill_hp_minimum_update"
                and kill.get("effect_class") == 28
                and kill.get("generic_effect") == source["goal_death_effect_reference"]
                and kill.get("native_container")
                == dict(
                    present=True, type=1, is_state=True, state_id=source["state_id"]
                )
                and kill.get("target_id") == box.id
                and kill.get("source_id") == caster_id
                and kill.get("hp_before") == 1
                and kill.get("hp") == kill.get("minimum") == 0
                and type(kill.get("uid")) is int
                and kill["uid"] > 0
                and type(removal.get("sequence")) is int
                and removal["sequence"] + 1 == kill.get("sequence")
                and kill["sequence"] + 1 == death.get("sequence")
            ):
                matches.append(
                    dict(
                        actor_id=box.id,
                        state_uid=removal["uid"],
                        kill_uid=kill["uid"],
                        death_sequence=death["sequence"],
                        generic_effect=kill["generic_effect"],
                    )
                )
        if len(matches) != 1:
            raise ValueError("Goal box lost its exact native state-removal death")
        result.extend(matches)
    return result


def settle_cast(fight, *, caster_id, spell_id, action_id):
    """Observe the private cast preview; its transaction publishes the result."""
    record = getattr(fight, "native_encounter_scene", None)
    if record is None or record.get("descriptor", {}).get("box_goals") is None:
        return False
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_encounter_roles import assigned_roles

    descriptor = frozen_scene(fight)
    selected = declaration(descriptor, record["room_cells"])
    roles = assigned_roles(fight)
    actor = fight.actors.get(caster_id)
    if (
        (fight.phase != "finished" or fight.winner != roles.player_team)
        or spell_id not in selected["spell_ids"]
        or actor is None
        or actor.controlled is not True
        or actor.owner_id is None
        or actor.team != roles.player_team
        or getattr(actor, "is_summon", False)
        or getattr(actor, "native_summon_source", None) is not None
        or not fight._in_play(actor)
    ):
        return False
    bindings = record["scope"]["actor_bindings"]
    boxes = [row for row in bindings if row["ref"] == selected["box_reference"]]
    if len(boxes) != len(selected["goals"]) or len(boxes) != len(bindings):
        raise ValueError("Box goal encounter lost its exact original box roster")
    positions = []
    for binding in boxes:
        box = fight.actors.get(binding["actor_id"])
        if box is None or box.controlled or box.team != roles.npc_team:
            raise ValueError("Box goal encounter lost an original box identity")
        if box.hp != 0:
            return False
        positions.append(tuple(box.position))
    if len(set(positions)) != len(positions) or set(positions) != set(
        map(tuple, selected["goals"])
    ):
        return False
    if getattr(fight, "native_box_goal_receipt", None) is not None:
        return False
    goal_uids = _goal_areas(fight, selected)
    deaths = _native_goal_deaths(fight, selected, boxes, caster_id)
    fight.native_box_goal_receipt = dict(
        schema=SCHEMA,
        scene_sha256=record["sha256"],
        scope=deepcopy(record["scope"]),
        caster_id=caster_id,
        owner_id=actor.owner_id,
        spell_id=spell_id,
        action_id=action_id,
        boxes=[
            dict(
                actor_id=row["actor_id"],
                cell=list(fight.actors[row["actor_id"]].position),
            )
            for row in boxes
        ],
        winner=roles.player_team,
        goal_uids=goal_uids,
        native_goal_deaths=deaths,
    )
    return True


def qualified_result(fight, original_monsters):
    """Authenticate a persisted victory earned by the original goal-death program."""
    record = getattr(fight, "native_encounter_scene", None)
    if record is None or record.get("descriptor", {}).get("box_goals") is None:
        return False
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_encounter_roles import assigned_roles

    selected = declaration(frozen_scene(fight), record["room_cells"])
    roles = assigned_roles(fight)
    receipt = getattr(fight, "native_box_goal_receipt", None)
    expected = {(r["actor_id"], r["ref"]) for r in record["scope"]["actor_bindings"]}
    actual = {(r["id"], r["ref"]) for r in original_monsters}
    if (
        type(receipt) is not dict
        or fight.phase != "finished"
        or fight.winner != roles.player_team
        or receipt.get("schema") != SCHEMA
        or receipt.get("scene_sha256") != record["sha256"]
        or receipt.get("scope") != record["scope"]
        or receipt.get("winner") != roles.player_team
        or receipt.get("spell_id") not in selected["spell_ids"]
        or receipt.get("goal_uids") != _goal_areas(fight, selected)
        or actual != expected
        or len(actual) != len(original_monsters)
        or len(actual) != len(selected["goals"])
        or any(reference != selected["box_reference"] for _, reference in actual)
        or set(getattr(fight, "native_summon_registrations", {}))
        & {identity for identity, _ in actual}
    ):
        raise ValueError("Box goal result lost its authenticated native scene")
    caster = fight.actors.get(receipt.get("caster_id"))
    if (
        caster is None
        or not caster.controlled
        or caster.team != roles.player_team
        or caster.owner_id is None
        or caster.owner_id != receipt.get("owner_id")
        or getattr(caster, "is_summon", False)
        or getattr(caster, "native_summon_source", None) is not None
    ):
        raise ValueError("Box goal result lost its original controlled caster")
    boxes = receipt.get("boxes", ())
    if (
        len(boxes) != len(actual)
        or {row["actor_id"] for row in boxes} != {identity for identity, _ in actual}
        or set(tuple(row["cell"]) for row in boxes)
        != set(map(tuple, selected["goals"]))
        or any(
            row["actor_id"] not in fight.actors
            or fight.actors[row["actor_id"]].hp != 0
            or fight.actors[row["actor_id"]].controlled
            or fight.actors[row["actor_id"]].team != roles.npc_team
            or tuple(fight.actors[row["actor_id"]].position) != tuple(row["cell"])
            for row in boxes
        )
    ):
        raise ValueError("Box goal result lost its original native goal occupants")
    bindings = record["scope"]["actor_bindings"]
    if receipt.get("native_goal_deaths") != _native_goal_deaths(
        fight, selected, bindings, caster.id
    ):
        raise ValueError("Box goal result lost its original native death causality")
    return True
