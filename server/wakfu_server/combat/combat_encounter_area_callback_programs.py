"""Immutable manifests for original area drop/callback programs."""
from copy import deepcopy
from functools import lru_cache
import math

_FIELDS = frozenset(
    (
        "policy",
        "authority",
        "catalog_revision",
        "map_id",
        "monster_references",
        "boss_reference",
        "boss_constructor_state",
        "programs",
    )
)
_ROLES = ("constructor", "event", "state", "lock_removal")
_FAMILIES = (315, 400, 304, 321)


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


def _parameters(rows, count):
    if (
        type(count) is not int
        or count < 0
        or len(rows) != count
        or [row["ordinal"] for row in rows] != list(range(count))
    ):
        raise ValueError("Incomplete immutable callback parameter inventory")
    result = []
    for row in rows:
        if any(
            type(row[key]) not in (int, float) or not math.isfinite(row[key])
            for key in ("base", "per_level")
        ):
            raise ValueError("Invalid immutable native parameter pair")
        result.extend((row["base"], row["per_level"]))
    return result


@lru_cache(maxsize=32)
def _version(identity):
    with _database().connection() as db:
        version = db.execute(
            "SELECT * FROM encounter_area_callback_program_versions " "WHERE policy=%s",
            (identity,),
        ).fetchone()
        programs = db.execute(
            "SELECT * FROM encounter_area_callback_programs "
            "WHERE policy=%s ORDER BY area_reference",
            (identity,),
        ).fetchall()
        steps = db.execute(
            "SELECT * FROM encounter_area_callback_program_steps "
            "WHERE policy=%s ORDER BY area_reference,ordinal",
            (identity,),
        ).fetchall()
        parameters = db.execute(
            "SELECT * FROM encounter_area_callback_program_parameters "
            "WHERE policy=%s ORDER BY area_reference,effect_reference,ordinal",
            (identity,),
        ).fetchall()
    if version is None or not programs:
        raise ValueError("Unknown immutable area callback manifest")
    record = dict(version)
    references = list(record.pop("area_references"))
    record["monster_references"] = list(record["monster_references"])
    record["programs"] = []
    used_parameters = set()
    for row in programs:
        program = dict(row)
        if program.pop("policy") != identity:
            raise ValueError("Callback program belongs to another version")
        area = program["area_reference"]
        getter = program["drop_getter_reference"]
        getter_rows = [
            p
            for p in parameters
            if p["area_reference"] == area and p["effect_reference"] == getter
        ]
        program["getter_parameters"] = _parameters(
            getter_rows, program["getter_parameter_count"]
        )
        used_parameters.update(
            (p["effect_reference"], p["ordinal"]) for p in getter_rows
        )
        native_steps = [dict(step) for step in steps if step["area_reference"] == area]
        if (
            [step["ordinal"] for step in native_steps] != list(range(4))
            or tuple(step["role"] for step in native_steps) != _ROLES
            or tuple(step["effect_family"] for step in native_steps) != _FAMILIES
        ):
            raise ValueError("Changed original ordered area drop program")
        for step in native_steps:
            if step.pop("policy") != identity or step.pop("area_reference") != area:
                raise ValueError("Callback step belongs to another area")
            step_rows = [
                p
                for p in parameters
                if p["area_reference"] == area
                and p["effect_reference"] == step["effect_reference"]
            ]
            step["parameters"] = _parameters(step_rows, step["parameter_count"])
            used_parameters.update(
                (p["effect_reference"], p["ordinal"]) for p in step_rows
            )
            step["native_effect_flags"] = list(step["native_effect_flags"])
            step["emitted_events"] = list(step["emitted_events"])
        program["steps"] = native_steps
        record["programs"].append(program)
    if (
        set(record) != _FIELDS
        or not record["policy"]
        or not record["authority"]
        or len(record["catalog_revision"]) != 64
        or type(record["map_id"]) is not int
        or record["monster_references"] != sorted(set(record["monster_references"]))
        or not record["monster_references"]
        or record["boss_reference"] not in record["monster_references"]
        or type(record["boss_constructor_state"]) is not int
        or record["boss_constructor_state"] <= 0
        or references != [p["area_reference"] for p in record["programs"]]
        or len(set(references)) != len(references)
        or len(steps) != 4 * len(programs)
        or used_parameters
        != {(p["effect_reference"], p["ordinal"]) for p in parameters}
    ):
        raise ValueError("Malformed immutable area callback manifest")
    return record


def callback_program_policy_from_record(record):
    if (
        not isinstance(record, dict)
        or set(record) != _FIELDS
        or record != _version(record.get("policy"))
    ):
        raise ValueError("Frozen area callback program manifest changed")
    return deepcopy(record)


def freeze_encounter_area_callback_programs(fight, *, roles):
    from wakfu_server import native_catalog

    if hasattr(fight, "native_encounter_area_callback_programs"):
        record = fight.native_encounter_area_callback_programs
        frozen = None if record is None else callback_program_policy_from_record(record)
    else:
        if fight.phase != "placement" and not (
            fight.phase == "active"
            and getattr(fight, "native_start_event_delivered", False) is not True
        ):
            raise ValueError("Callback manifest requires fresh pre1003 admission")
        if roles.map_id is None or not roles.monster_references:
            fight.native_encounter_area_callback_programs = None
            return None
        with _database().connection() as db:
            row = db.execute(
                "SELECT policy FROM encounter_area_callback_program_active "
                "WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        frozen = None if row is None else deepcopy(_version(row["policy"]))
    if frozen is not None and (
        frozen["map_id"] != roles.map_id
        or frozen["monster_references"] != list(roles.monster_references)
        or frozen["catalog_revision"] != native_catalog.release()
    ):
        raise ValueError("Callback manifest differs from admission or catalog")
    fight.native_encounter_area_callback_programs = frozen
    return deepcopy(frozen)


def encounter_area_callback_programs(fight):
    record = getattr(fight, "native_encounter_area_callback_programs", None)
    if record is None:
        return ()
    frozen = callback_program_policy_from_record(record)
    from .combat_encounter_roles import frozen_roles

    roles = frozen_roles(fight)
    if (
        roles is None
        or roles.map_id != frozen["map_id"]
        or list(roles.monster_references) != frozen["monster_references"]
    ):
        raise ValueError("Area callback program escaped frozen encounter scope")
    return tuple(deepcopy(frozen["programs"]))
