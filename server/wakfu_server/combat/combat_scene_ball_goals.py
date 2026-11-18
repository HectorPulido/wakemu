"""Authenticate native ball-game goals without replacing spells or native deaths.

A sealed before/after witness belongs to the actual native28 execution. The
root observer publishes its typed result after every original effect finishes;
ordinary victories, public event dictionaries and interrupted attempts have no
ball-game authority. All placement joins are declared scene reconstruction.
"""
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

SCHEMA = "owned-native-ball-goals-v1"
SOURCE_SHA256 = "f64e97e2e40064b906e738ca2ccf4c466088c810bea76957c23f9e712147a46f"
FIELD = "native_ball_goal_receipt"
PENDING_FIELD = "native_ball_pending_result"


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def _terminal_effect_digest(effect):
    """Compare the pinned native export with its executable catalog projection."""
    from .combat_definitions import effect_profile

    source = dict(effect)
    # Executable catalogs also carry the original active/timing audit metadata.
    # NativeKillHandler validates execution and timing before this source check.
    source.pop("native_active_effect", None)
    source.pop("native_timing_checks", None)
    samples = ("probabilities", "parameters_by_level", "parameter0_by_level")
    if any(not isinstance(source.get(key), (list, tuple)) for key in samples):
        raise ValueError("Ball terminal lacks its native sampled definition")
    lengths = {len(source[key]) for key in samples}
    if len(lengths) != 1 or next(iter(lengths)) < 200:
        raise ValueError("Ball terminal has inconsistent native samples")
    # The pinned export samples levels1..200; the canonical catalog samples
    # through245. Verify every additional sample against the same raw formula.
    for index in range(200, next(iter(lengths))):
        values = effect_profile(source, index + 1)
        parameters = values["parameters"]
        if (
            source["probabilities"][index] != values["probability"]
            or list(source["parameters_by_level"][index]) != parameters
            or source["parameter0_by_level"][index]
            != (parameters[0] if parameters else None)
        ):
            raise ValueError("Ball terminal has conflicting native audit samples")
    for key in samples:
        source[key] = list(source[key][:200])
    return digest(source)


@lru_cache(maxsize=1)
def native_sources():
    raw = Path(__file__).with_name("native_bworkball_sources.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Native ball source has not been reviewed")
    value = json.loads(raw)
    if value.get("schema") != "native-bworkball-sources-v1":
        raise ValueError("Unknown native ball source schema")
    return value


def _points(value):
    if (
        not isinstance(value, list)
        or not value
        or any(
            not isinstance(p, list) or len(p) != 3 or any(type(n) is not int for n in p)
            for p in value
        )
        or len(set(map(tuple, value))) != len(value)
    ):
        raise ValueError("Ball goals require distinct explicit native floor cells")
    return set(map(tuple, value))


def declaration(descriptor, room_cells=None):
    if descriptor is None or descriptor.get("ball_goals") is None:
        return None
    value = descriptor["ball_goals"]
    fields = {
        "schema",
        "id",
        "quest_id",
        "objective_id",
        "match_index",
        "source_id",
        "ball_reference",
        "player_form_reference",
        "player_goal_cells",
        "opponent_goal_cells",
        "recruitment_cells",
        "native_source_sha256",
        "evidence",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value["schema"] != SCHEMA
        or not isinstance(value["id"], str)
        or not value["id"]
        or not value["evidence"]
        or descriptor.get("full_room_scope") is not True
        or any(
            type(value[k]) is not int or value[k] <= 0
            for k in (
                "quest_id",
                "objective_id",
                "match_index",
                "source_id",
                "ball_reference",
                "player_form_reference",
            )
        )
        or value["native_source_sha256"] != SOURCE_SHA256
        or (value["quest_id"], value["ball_reference"], value["player_form_reference"])
        != (1638, 2783, 2784)
        or (value["match_index"], value["source_id"], value["objective_id"])
        not in ((1, 20383, 3079), (2, 20407, 3080), (3, 20406, 3081))
    ):
        raise ValueError("Ball match lacks its exact native source/result identity")
    player, opponent, recruitment = (
        _points(value[k])
        for k in ("player_goal_cells", "opponent_goal_cells", "recruitment_cells")
    )
    if player & opponent or player & recruitment or opponent & recruitment:
        raise ValueError("Ball goal and recruitment footprints overlap")
    points = player | opponent | recruitment
    if room_cells is not None and not points <= set(map(tuple, room_cells)):
        raise ValueError("Ball game leaves its actual native room terrain")
    glyphs = descriptor.get("native_initial_glyphs", ())
    expected = {
        (ref, p, 0)
        for ref, cells in ((625, player), (626, opponent), (635, recruitment))
        for p in cells
    }
    actual = {
        (r.get("reference"), tuple(r.get("cell", ())), r.get("level")) for r in glyphs
    }
    if len(glyphs) != len(expected) or actual != expected:
        raise ValueError("Ball game lost its original goal/recruitment glyphs")
    programs = descriptor.get("controlled_state_programs", ())
    source = native_sources()["form"]
    if not any(
        r.get("state_id") == source["state_id"]
        and r.get("source_sha256") == source["state_sha256"]
        for r in programs
    ):
        raise ValueError("Ball game lacks its original player transformation")
    return value


def native_admission(configuration, room_order, reference, level, native):
    rooms = [
        r
        for r in configuration.get("topology", {}).get("rooms", ())
        if r["order"] == room_order
    ]
    if len(rooms) != 1:
        return False
    descriptor = rooms[0].get("encounter_scene")
    if descriptor is None or descriptor.get("ball_goals") is None:
        return False
    declaration(descriptor, rooms[0]["cells"])
    source = native_sources()
    original = source["monsters"].get(str(reference))
    constructor = source["constructors"].get(str(reference))
    if (
        original is None
        or constructor is None
        or reference not in (2780, 2781, 2782, 2783)
    ):
        return False
    if (
        level != 50
        or native != original
        or constructor["initial_state_triples"] != []
        or [r["spell_id"] for r in original["native_abilities"]]
        != [r["reference"] for r in constructor["abilities"]]
    ):
        raise ValueError("Ball actor differs from its original native constructor")
    return True


def declared_actor(descriptor, reference, count, native):
    """Recognize only an exact original constructor in the declared match."""
    if descriptor is None or descriptor.get("ball_goals") is None:
        return False
    declaration(descriptor)
    original = native_sources()["monsters"].get(str(reference))
    if original is None or reference not in (2780, 2781, 2782, 2783):
        return False
    if (
        type(count) is not int
        or not 1 <= count <= 5
        or reference == 2783
        and count != 1
        or native != original
    ):
        raise ValueError("Ball match roster differs from its original native actors")
    return True


def _scene(fight):
    from .combat_encounter_scene_policy import frozen_scene

    record = getattr(fight, "native_encounter_scene", None)
    if record is None or record.get("descriptor", {}).get("ball_goals") is None:
        return None, None
    selected = declaration(frozen_scene(fight), record["room_cells"])
    if (
        record["scope"].get("map_id") != 719
        or record["scope"].get("room_order") != selected["match_index"]
    ):
        raise ValueError("Ball match differs from its admitted original room")
    return record, selected


def _areas(fight, selected):
    from .combat_environment_glyphs import verify_environment_glyph

    expected = {
        (ref, p)
        for ref, key in (
            (625, "player_goal_cells"),
            (626, "opponent_goal_cells"),
            (635, "recruitment_cells"),
        )
        for p in map(tuple, selected[key])
    }
    constructors = [
        r
        for r in getattr(fight, "native_environment_glyph_constructors", ())
        if r.get("reference") in (625, 626, 635)
    ]
    if (
        len(constructors) != len(expected)
        or {(r["reference"], tuple(r["cell"])) for r in constructors} != expected
    ):
        raise ValueError("Ball match lost its original registered area constructors")
    result = []
    for source in constructors:
        row = getattr(fight, "native_effect_areas", {}).get(source["uid"])
        if (
            row is None
            or row.get("owner_id") is not None
            or row.get("reference") != source["reference"]
            or tuple(row.get("cell", ())) != tuple(source["cell"])
        ):
            raise ValueError("Ball match lost an actual original goal area")
        verify_environment_glyph(fight, row)
        result.append(
            dict(uid=row["uid"], reference=row["reference"], cell=list(row["cell"]))
        )
    return sorted(result, key=lambda r: r["uid"])


def _ball(fight, record, selected):
    rows = [
        r
        for r in record["scope"]["actor_bindings"]
        if r["ref"] == selected["ball_reference"]
    ]
    if len(rows) != 1:
        raise ValueError("Ball match requires its one admitted original ball")
    ball = fight.actors.get(rows[0]["actor_id"])
    if (
        ball is None
        or ball.id in getattr(fight, "native_summon_registrations", {})
        or getattr(ball, "native_summon_source", None) is not None
    ):
        raise ValueError("Ball match lost its registered original ball identity")
    return ball


@dataclass(frozen=True)
class _NativeTerminal:
    fight: object
    payload: dict
    event_offset: int


def prepare_terminal(fight, effect, invocation):
    """Called inside original28 execution, before its real HP/death mutation."""
    record, selected = _scene(fight)
    if selected is None or invocation.reference not in (106824, 106850):
        return None
    from .combat_active_spell import active_spell_id
    from .combat_encounter_roles import assigned_roles
    from .combat_effect_area_geometry import contains_area_cell

    roles = assigned_roles(fight)
    spell = active_spell_id(fight)
    expected = {
        106824: (4044, roles.player_team, 625),
        106850: (4045, roles.npc_team, 626),
    }
    wanted_spell, team, area_ref = expected[invocation.reference]
    caster, target = fight.actors.get(invocation.caster_id), fight.actors.get(
        invocation.target_id
    )
    ball = _ball(fight, record, selected)
    if (
        fight.phase != "active"
        or spell != wanted_spell
        or effect.get("effect_class") != 28
        or caster is None
        or caster.team != team
        or target is None
        or target.hp <= 0
        or _terminal_effect_digest(effect)
        != native_sources()["terminals"][str(invocation.reference)]["effect_sha256"]
    ):
        raise ValueError(
            "Ball terminal lacks its actual native spell/effect invocation"
        )
    areas = _areas(fight, selected)
    position = ball.position if spell == 4044 else caster.position
    goals = [
        row
        for row in areas
        if row["reference"] == area_ref
        and contains_area_cell(fight.native_effect_areas[row["uid"]], position)
    ]
    if not goals:
        raise ValueError("Ball touchdown has no actual corresponding goal contact")
    if spell == 4045:
        links = getattr(fight, "native_movement_links", {})
        if links.get(caster.id) != ball.id or links.get(ball.id) != caster.id:
            raise ValueError(
                "Opponent touchdown lacks the genuine received-ball relation"
            )
    return _NativeTerminal(
        fight,
        dict(
            schema=SCHEMA,
            fight_id=fight.id,
            scene_sha256=record["sha256"],
            scope=deepcopy(record["scope"]),
            match_id=selected["id"],
            objective_id=selected["objective_id"],
            source_id=selected["source_id"],
            caster_id=caster.id,
            ball_id=ball.id,
            target_id=target.id,
            spell_id=spell,
            generic_effect=invocation.reference,
            winner=team,
            goal_reference=area_ref,
            goal_cell=list(position),
            goal_uids=[r["uid"] for r in goals],
            areas=areas,
        ),
        len(fight.events),
    )


def _kills(fight, payload):
    """Match only original successful28 updates immediately followed by real death."""
    result = []
    for a, b in zip(fight.events, fight.events[1:]):
        if (
            a.get("kind") == "kill_hp_minimum_update"
            and a.get("effect_class") == 28
            and a.get("generic_effect") == payload["generic_effect"]
            and a.get("source_id") == payload["caster_id"]
            and a.get("target_id") == payload["target_id"]
            and type(a.get("uid")) is int
            and a["uid"] > 0
            and a.get("hp_before", 0) > 0
            and a.get("hp") == a.get("minimum") == 0
            and b.get("kind") == "death"
            and b.get("actor_id") == a["target_id"]
            and type(a.get("sequence")) is int
            and b.get("sequence") == a["sequence"] + 1
        ):
            result.append(
                dict(
                    uid=a["uid"],
                    target_id=a["target_id"],
                    kill_sequence=a["sequence"],
                    death_sequence=b["sequence"],
                )
            )
    return result


def record_terminal(fight, witness, *, uid):
    """Called only after the original native28 has successfully caused death."""
    if witness is None:
        return False
    if not isinstance(witness, _NativeTerminal) or witness.fight is not fight:
        raise ValueError("Ball terminal witness belongs to another native execution")
    proof = deepcopy(witness.payload)
    kills = [r for r in _kills(fight, proof) if r["uid"] == uid]
    if len(kills) != 1 or not any(
        e.get("sequence") == kills[0]["kill_sequence"]
        for e in fight.events[witness.event_offset :]
    ):
        raise ValueError(
            "Ball terminal lacks its actual current native kill/death witness"
        )
    proof["native_kill"] = kills[0]
    previous = getattr(fight, PENDING_FIELD, None)
    if previous is not None:
        if any(
            previous[k] != proof[k]
            for k in (
                "scene_sha256",
                "match_id",
                "caster_id",
                "spell_id",
                "winner",
                "ball_id",
            )
        ):
            raise ValueError("Ball root produced conflicting native match outcomes")
        return False
    setattr(fight, PENDING_FIELD, proof)
    return True


def settle_terminal(fight):
    """Run after the complete original root; no actor HP or position is changed."""
    proof = getattr(fight, PENDING_FIELD, None)
    if proof is None:
        return False
    record, selected = _scene(fight)
    if (
        selected is None
        or proof["scene_sha256"] != record["sha256"]
        or proof["scope"] != record["scope"]
        or proof["match_id"] != selected["id"]
        or proof["areas"] != _areas(fight, selected)
        or proof["native_kill"] not in _kills(fight, proof)
    ):
        raise ValueError("Ball root lost its sealed native outcome")
    existing = getattr(fight, FIELD, None)
    if existing is not None and existing != proof:
        raise ValueError("Ball attempt already has a different terminal result")
    if (
        fight.phase not in ("active", "finished")
        or fight.phase == "finished"
        and fight.winner != proof["winner"]
    ):
        raise ValueError("Ball result conflicts with its actual native terminal state")
    setattr(fight, FIELD, deepcopy(proof))
    setattr(fight, PENDING_FIELD, None)
    if fight.phase == "active":
        fight.phase, fight.winner = "finished", proof["winner"]
        fight._event(
            "finished",
            winner=fight.winner,
            reason="native_ball_touchdown",
            match_id=selected["id"],
        )
    return existing is None


def deliver_terminal(dispatcher):
    return settle_terminal(dispatcher.fight)


def qualified_result(fight, original_monsters):
    """Durable typed match authority; ordinary victory and aborted attempts fail."""
    record, selected = _scene(fight)
    if selected is None:
        return False
    proof = getattr(fight, FIELD, None)
    if proof is None:
        return False
    from .combat_encounter_roles import assigned_roles

    roles = assigned_roles(fight)
    actual = {(r["id"], r["ref"]) for r in original_monsters}
    expected = {(r["actor_id"], r["ref"]) for r in record["scope"]["actor_bindings"]}
    if (
        not isinstance(proof, dict)
        or proof.get("schema") != SCHEMA
        or proof.get("fight_id") != fight.id
        or proof.get("scene_sha256") != record["sha256"]
        or proof.get("scope") != record["scope"]
        or proof.get("match_id") != selected["id"]
        or proof.get("objective_id") != selected["objective_id"]
        or proof.get("source_id") != selected["source_id"]
        or proof.get("areas") != _areas(fight, selected)
        or actual != expected
        or len(actual) != len(original_monsters)
        or _ball(fight, record, selected).id != proof.get("ball_id")
        or proof.get("native_kill") not in _kills(fight, proof)
        or proof.get("spell_id") != 4044
        or proof.get("generic_effect") != 106824
        or proof.get("winner") != roles.player_team
        or fight.phase != "finished"
        or fight.winner != roles.player_team
    ):
        raise ValueError("Ball result lost its exact native admitted touchdown proof")
    return True
