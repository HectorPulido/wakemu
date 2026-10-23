"""Immutable DB manifests for reconstructed encounter initialization programs."""
from copy import deepcopy
from functools import lru_cache

_FIELDS = frozenset(
    (
        "policy",
        "authority",
        "catalog_revision",
        "map_id",
        "monster_references",
        "boss_reference",
        "boss_constructor_state",
        "initial_level",
        "programs",
    )
)
_PROGRAM_KEYS = (
    "area_reference",
    "creator_reference",
    "program_reference",
    "state_reference",
    "state_effect_reference",
)


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=32)
def _version(identity):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_seed_program_versions WHERE policy=%s", (identity,)
        ).fetchone()
        programs = db.execute(
            "SELECT * FROM encounter_seed_program_rows WHERE policy=%s "
            "ORDER BY area_reference",
            (identity,),
        ).fetchall()
    if row is None or not programs:
        raise ValueError("Unknown immutable encounter seed program manifest")
    record = dict(row)
    references = list(record.pop("area_references"))
    record["monster_references"] = list(record["monster_references"])
    record["programs"] = [
        dict((key, program[key]) for key in _PROGRAM_KEYS) for program in programs
    ]
    if (
        set(record) != _FIELDS
        or not record["policy"]
        or not record["authority"]
        or len(record["catalog_revision"]) != 64
        or type(record["map_id"]) is not int
        or not record["monster_references"]
        or record["monster_references"] != sorted(set(record["monster_references"]))
        or any(type(ref) is not int or ref <= 0 for ref in record["monster_references"])
        or record["boss_reference"] not in record["monster_references"]
        or type(record["boss_constructor_state"]) is not int
        or record["boss_constructor_state"] <= 0
        or type(record["initial_level"]) is not int
        or not 1 <= record["initial_level"] <= 32767
        or references != [program["area_reference"] for program in record["programs"]]
        or any(
            any(
                type(program[key]) is not int or program[key] <= 0
                for key in _PROGRAM_KEYS
            )
            for program in record["programs"]
        )
        or any(
            len({program[key] for program in record["programs"]}) != len(programs)
            for key in (
                "area_reference",
                "creator_reference",
                "program_reference",
                "state_effect_reference",
            )
        )
    ):
        raise ValueError("Malformed immutable encounter seed program manifest")
    return record


def seed_program_policy_from_record(record):
    if (
        not isinstance(record, dict)
        or set(record) != _FIELDS
        or record != _version(record.get("policy"))
    ):
        raise ValueError("Frozen encounter seed program manifest changed")
    return deepcopy(record)


def freeze_encounter_seed_program_policy(fight, *, roles):
    from wakfu_server import native_catalog

    if hasattr(fight, "native_encounter_area_seed_policy"):
        record = fight.native_encounter_area_seed_policy
        frozen = None if record is None else seed_program_policy_from_record(record)
    else:
        if fight.phase != "placement" and not (
            fight.phase == "active"
            and getattr(fight, "native_start_event_delivered", False) is not True
        ):
            raise ValueError(
                "Encounter seed program manifest requires fresh pre1003 admission"
            )
        if roles.map_id is None or not roles.monster_references:
            fight.native_encounter_area_seed_policy = None
            return None
        with _database().connection() as db:
            row = db.execute(
                "SELECT policy FROM encounter_seed_program_active "
                "WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        frozen = None if row is None else deepcopy(_version(row["policy"]))
    if frozen is not None and (
        frozen["map_id"] != roles.map_id
        or frozen["monster_references"] != list(roles.monster_references)
        or frozen["catalog_revision"] != native_catalog.release()
    ):
        raise ValueError(
            "Encounter seed program manifest differs from admission or catalog"
        )
    fight.native_encounter_area_seed_policy = frozen
    return deepcopy(frozen)


def encounter_seed_programs(fight, *, boss_reference):
    record = getattr(fight, "native_encounter_area_seed_policy", None)
    if record is None:
        return ()
    frozen = seed_program_policy_from_record(record)
    from .combat_encounter_roles import frozen_roles

    roles = frozen_roles(fight)
    if (
        roles is None
        or roles.map_id != frozen["map_id"]
        or list(roles.monster_references) != frozen["monster_references"]
    ):
        raise ValueError("Encounter seed programs escaped frozen scope")
    if type(boss_reference) is not int or boss_reference != frozen["boss_reference"]:
        return ()
    return tuple(
        dict(program, level=frozen["initial_level"]) for program in frozen["programs"]
    )
