"""Immutable reconstructed population for reviewed native damage-event groups.

The native event, selectors, criteria and retained caster remain authoritative.
An admitted controller supplies a fresh population only for its exact groups.
"""
from copy import deepcopy
from functools import lru_cache

_FIELDS = frozenset(
    (
        "policy",
        "authority",
        "map_id",
        "monster_references",
        "boss_reference",
        "carrier_state",
        "catalog_revision",
        "effects",
    )
)
_EFFECT_KEYS = (
    "effect_reference",
    "effect_family",
    "selector_mask",
    "parameter_count",
    "native_parameters",
    "criterion",
    "area_class",
    "listener_reference",
    "owner_effect_reference",
    "event_id",
    "channel",
)


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


def _same_record(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _same_record(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _same_record(left, right) for left, right in zip(actual, expected)
        )
    return actual == expected


@lru_cache(maxsize=32)
def _version(identity):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_event_population_versions WHERE policy=%s",
            (identity,),
        ).fetchone()
        effects = db.execute(
            "SELECT * FROM encounter_event_population_effects WHERE policy=%s "
            "ORDER BY effect_reference",
            (identity,),
        ).fetchall()
    if row is None or not effects:
        raise ValueError("Unknown immutable encounter event population policy")
    record = dict(row)
    references = list(record.pop("effect_references"))
    record["monster_references"] = list(record["monster_references"])
    record["effects"] = [
        {
            key: list(effect[key]) if key == "native_parameters" else effect[key]
            for key in _EFFECT_KEYS
        }
        for effect in effects
    ]
    if (
        set(record) != _FIELDS
        or not isinstance(record["policy"], str)
        or not record["policy"]
        or not isinstance(record["authority"], str)
        or not record["authority"]
        or type(record["map_id"]) is not int
        or not isinstance(record["catalog_revision"], str)
        or len(record["catalog_revision"]) != 64
        or not record["monster_references"]
        or any(type(ref) is not int or ref <= 0 for ref in record["monster_references"])
        or record["monster_references"] != sorted(set(record["monster_references"]))
        or type(record["boss_reference"]) is not int
        or record["boss_reference"] not in record["monster_references"]
        or type(record["carrier_state"]) is not int
        or record["carrier_state"] <= 0
        or references != [effect["effect_reference"] for effect in record["effects"]]
        or references != sorted(set(references))
        or any(
            type(effect[key]) is not int or effect[key] <= 0
            for effect in record["effects"]
            for key in (
                "effect_reference",
                "listener_reference",
                "owner_effect_reference",
            )
        )
        or any(
            type(effect["effect_family"]) is not int
            or effect["effect_family"] != 330
            or type(effect["selector_mask"]) is not int
            or effect["selector_mask"] != 0
            or type(effect["parameter_count"]) is not int
            or effect["parameter_count"] != 0
            or effect["native_parameters"] != []
            or effect["area_class"] != "anD"
            or not isinstance(effect["criterion"], str)
            or not effect["criterion"].strip()
            or type(effect["event_id"]) is not int
            or effect["event_id"] not in (5, 6, 7, 8)
            or type(effect["channel"]) is not int
            or effect["channel"] != 2
            for effect in record["effects"]
        )
    ):
        raise ValueError("Malformed immutable encounter event population policy")
    return record


def event_population_from_record(record):
    if (
        not isinstance(record, dict)
        or set(record) != _FIELDS
        or not isinstance(record.get("policy"), str)
        or not _same_record(record, _version(record["policy"]))
    ):
        raise ValueError("Frozen encounter event population policy changed")
    return deepcopy(record)


def freeze_event_population_policy(fight, *, roles):
    from wakfu_server import native_catalog

    if fight.phase != "placement":
        raise ValueError("Event population policy requires fresh placement")
    if hasattr(fight, "native_encounter_event_population"):
        record = fight.native_encounter_event_population
        frozen = None if record is None else event_population_from_record(record)
    else:
        with _database().connection() as db:
            row = db.execute(
                "SELECT policy FROM encounter_event_population_active "
                "WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        frozen = None if row is None else deepcopy(_version(row["policy"]))
    if frozen is not None and (
        frozen["map_id"] != roles.map_id
        or frozen["monster_references"] != list(roles.monster_references)
        or frozen["catalog_revision"] != native_catalog.release()
    ):
        raise ValueError("Event population policy differs from admission or catalog")
    fight.native_encounter_event_population = frozen
    return deepcopy(frozen)


def permits_event_group_population(fight, effect, invocation):
    record = getattr(fight, "native_encounter_event_population", None)
    if record is None:
        return False
    frozen = event_population_from_record(record)
    from .combat_encounter_roles import frozen_roles

    roles = frozen_roles(fight)
    if (
        roles is None
        or roles.map_id != frozen["map_id"]
        or list(roles.monster_references) != frozen["monster_references"]
    ):
        raise ValueError("Event population escaped its frozen encounter scope")
    rule = next(
        (
            row
            for row in frozen["effects"]
            if row["effect_reference"] == invocation.reference
        ),
        None,
    )
    if rule is None:
        return False
    if (
        effect.get("effect_class") != rule["effect_family"]
        or effect.get("parameter_count") != rule["parameter_count"]
        or type(effect.get("parameters")) not in (list, tuple)
        or tuple(effect["parameters"]) != tuple(rule["native_parameters"])
        or effect.get("criteria") != rule["criterion"]
        or effect.get("area_class") != rule["area_class"]
        or effect.get("native_target_selector")
        != {"class": "fcE", "mask": rule["selector_mask"]}
    ):
        raise ValueError("Original event population group descriptor changed")
    if (
        invocation.wakemu_fresh_child_selection is not True
        or invocation.native_explicit_target is not True
        or invocation.native_preselected_target is not False
        or invocation.wakemu_rebound_child_selection is not False
    ):
        return False
    context = invocation.native_trigger_context
    if (
        not isinstance(context, dict)
        or context.get("native_events_verified") is not True
        or context.get("channel") != rule["channel"]
        or rule["event_id"] not in context.get("event_ids", ())
        or type(context.get("uid")) is not int
        or context["uid"] <= 0
        or type(context.get("generic_effect")) is not int
        or context["generic_effect"] <= 0
    ):
        return False
    caster, boss = fight.actors.get(invocation.caster_id), fight.actors.get(
        invocation.target_id
    )
    if (
        caster is None
        or boss is None
        or caster is boss
        or caster.hp <= 0
        or boss.hp <= 0
        or caster.controlled is not True
        or caster.team != roles.player_team
        or boss.controlled is not False
        or boss.team != roles.npc_team
        or context.get("caster_id") != caster.id
        or context.get("target_id") != boss.id
        or context.get("manager_actor_id") != boss.id
    ):
        return False
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(boss.id, {})
    if (
        receipt.get("ref") != frozen["boss_reference"]
        or receipt.get("initialized") is not True
    ):
        return False
    if not any(
        state.uid == invocation.state_uid
        and state.reference == frozen["carrier_state"]
        and state.caster_id == boss.id
        and state.target_id == boss.id
        and rule["owner_effect_reference"] in state.effect_ids
        for state in boss.state_ledger.entries
    ):
        return False
    for retained in getattr(fight, "native_owned_group_effects", {}).values():
        original = retained.get("invocation", {}) if isinstance(retained, dict) else {}
        if (
            original.get("reference") == rule["listener_reference"]
            and original.get("state_uid") == invocation.state_uid
            and original.get("caster_id") == boss.id
            and original.get("target_id") == boss.id
        ):
            from .combat_effect_groups import native_group_route

            return native_group_route(effect) == "actors"
    return False
