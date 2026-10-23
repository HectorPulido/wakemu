"""Frozen DB authority for reviewed native event-child chosen-PV binding.

Native selectors and clone enums stay unchanged. Only exact admitted leaves
preserve their transmitted PV against the server's fresh-selector policy.
"""
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
        "carrier_state",
        "effects",
    )
)
_EFFECT_KEYS = (
    "effect_reference",
    "effect_family",
    "selector_mask",
    "parameter_count",
    "criterion",
    "area_class",
    "native_parameters",
    "listener_reference",
    "event_id",
)


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=32)
def _version(identity):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_recipient_binding_versions WHERE policy=%s",
            (identity,),
        ).fetchone()
        effects = db.execute(
            "SELECT * FROM encounter_recipient_binding_effects WHERE policy=%s "
            "ORDER BY effect_reference",
            (identity,),
        ).fetchall()
    if row is None or not effects:
        raise ValueError("Unknown immutable encounter recipient binding policy")
    record = dict(row)
    references = list(record.pop("effect_references"))
    record["monster_references"] = list(record["monster_references"])
    record["effects"] = [
        dict(
            (key, list(effect[key]) if key == "native_parameters" else effect[key])
            for key in _EFFECT_KEYS
        )
        for effect in effects
    ]
    if (
        set(record) != _FIELDS
        or not record["policy"]
        or not record["authority"]
        or len(record["catalog_revision"]) != 64
        or type(record["map_id"]) is not int
        or record["monster_references"] != sorted(set(record["monster_references"]))
        or not record["monster_references"]
        or any(type(ref) is not int or ref <= 0 for ref in record["monster_references"])
        or record["boss_reference"] not in record["monster_references"]
        or type(record["carrier_state"]) is not int
        or record["carrier_state"] <= 0
        or references != [effect["effect_reference"] for effect in record["effects"]]
        or any(
            effect["effect_family"] not in (82, 83, 84, 85, 304)
            or effect["area_class"] not in ("anA", "anD")
            or effect["selector_mask"] < 0
            or len(effect["native_parameters"]) != 2 * effect["parameter_count"]
            or effect["listener_reference"] <= 0
            or effect["event_id"] not in (5, 6, 7, 8)
            for effect in record["effects"]
        )
    ):
        raise ValueError("Malformed immutable encounter recipient binding policy")
    return record


def binding_policy_from_record(record):
    if (
        not isinstance(record, dict)
        or set(record) != _FIELDS
        or record != _version(record.get("policy"))
    ):
        raise ValueError("Frozen encounter recipient binding policy changed")
    return deepcopy(record)


def freeze_encounter_recipient_binding_policy(fight, *, roles):
    from wakfu_server import native_catalog

    if fight.phase != "placement":
        raise ValueError("Recipient binding policy requires fresh placement")
    if hasattr(fight, "native_encounter_recipient_binding"):
        record = fight.native_encounter_recipient_binding
        frozen = None if record is None else binding_policy_from_record(record)
    else:
        with _database().connection() as db:
            row = db.execute(
                "SELECT policy FROM encounter_recipient_binding_active "
                "WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        frozen = None if row is None else deepcopy(_version(row["policy"]))
    if frozen is not None and (
        frozen["map_id"] != roles.map_id
        or frozen["monster_references"] != list(roles.monster_references)
        or frozen["catalog_revision"] != native_catalog.release()
    ):
        raise ValueError("Recipient binding policy differs from admission or catalog")
    fight.native_encounter_recipient_binding = frozen
    return deepcopy(frozen)


def permits_native_recipient_binding(fight, effect, invocation):
    record = getattr(fight, "native_encounter_recipient_binding", None)
    if record is None:
        return False
    frozen = binding_policy_from_record(record)
    from .combat_encounter_roles import frozen_roles

    roles = frozen_roles(fight)
    if (
        roles is None
        or roles.map_id != frozen["map_id"]
        or list(roles.monster_references) != frozen["monster_references"]
    ):
        raise ValueError("Recipient binding escaped its frozen encounter scope")
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
    parameters = effect.get("parameters")
    if (
        not isinstance(parameters, (list, tuple))
        or any(type(value) not in (int, float) for value in parameters)
        or tuple(parameters) != tuple(rule["native_parameters"])
        or effect.get("effect_class") != rule["effect_family"]
        or effect.get("parameter_count") != rule["parameter_count"]
        or effect.get("criteria") != rule["criterion"]
        or effect.get("area_class") != rule["area_class"]
        or effect.get("native_target_selector")
        != {"class": "fcE", "mask": rule["selector_mask"]}
    ):
        raise ValueError("Original encounter recipient binding descriptor changed")
    if (
        invocation.wakemu_fresh_child_selection is not True
        or invocation.native_explicit_target is not True
        or invocation.native_preselected_target is not False
        or invocation.wakemu_rebound_child_selection is not False
    ):
        return False
    source = invocation.native_trigger_context
    if not isinstance(source, dict) or source.get("native_events_verified") is not True:
        return False
    caster, target = fight.actors.get(invocation.caster_id), fight.actors.get(
        invocation.target_id
    )
    if (
        caster is None
        or target is None
        or caster is target
        or caster.controlled is not True
        or caster.team != roles.player_team
        or target.controlled is not False
        or target.team != roles.npc_team
        or source.get("caster_id") != caster.id
        or source.get("target_id") != target.id
        or source.get("manager_actor_id") != target.id
        or source.get("channel") != 2
        or rule["event_id"] not in source.get("event_ids", ())
        or type(source.get("uid")) is not int
        or source["uid"] <= 0
        or type(source.get("generic_effect")) is not int
        or source["generic_effect"] <= 0
    ):
        return False
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(
        target.id, {}
    )
    if (
        receipt.get("ref") != frozen["boss_reference"]
        or receipt.get("initialized") is not True
    ):
        return False
    return any(
        entry.uid == invocation.state_uid
        and entry.reference == frozen["carrier_state"]
        and entry.target_id == target.id
        and rule["listener_reference"] in entry.effect_ids
        for entry in target.state_ledger.entries
    )
