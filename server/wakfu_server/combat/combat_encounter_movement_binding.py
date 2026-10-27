"""Explicit DB-frozen reconstruction of an external committed-movement caster.

Native eZR.l/m(null) and child selectors are unchanged. Only an admitted
retained subscription can acquire its attested movement manager as caster.
"""

from .combat_encounter_source_revision import source_revision_matches

SOURCE_DEPENDENCIES = (
    "combat-state-definitions.json",
    "native-retained-effect-metadata.json",
)
from copy import deepcopy
from functools import lru_cache


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=32)
def _version(policy):
    with _database().connection() as db:
        row = db.execute(
            "SELECT * FROM encounter_movement_binding_versions WHERE policy=%s",
            (policy,),
        ).fetchone()
    if row is None:
        raise ValueError("Unknown immutable committed movement binding")
    result = dict(row)
    for key in (
        "monster_references",
        "native_parameters",
        "native_children",
        "native_effect_flags",
    ):
        result[key] = list(result[key])
    if (
        result["binding"] != "actual_committed_movement_manager_as_caster"
        or result["event_id"] != 1005
        or result["channel"] != 60
        or result["caster_code"] != 2
        or result["target_code"] != 2
        or result["effect_family"] != 330
        or result["selector_mask"] != 1
        or result["monster_references"] != sorted(set(result["monster_references"]))
        or result["boss_reference"] not in result["monster_references"]
        or len(result["catalog_revision"]) != 64
        or len(result["native_parameters"]) != 2 * result["parameter_count"]
    ):
        raise ValueError("Invalid immutable committed movement binding")
    return result


def _same_sequence(actual, expected):
    """Accept raw/compiled containers without coercing values or their types."""
    if not isinstance(actual, (list, tuple)) or not isinstance(expected, (list, tuple)):
        return False
    if len(actual) != len(expected):
        return False
    return all(
        _same_sequence(left, right)
        if isinstance(right, (list, tuple))
        else type(left) is type(right) and left == right
        for left, right in zip(actual, expected)
    )


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


def binding_from_record(record):
    if not isinstance(record, dict) or not _same_record(
        record, _version(record.get("policy"))
    ):
        raise ValueError("Frozen committed movement binding changed")
    return deepcopy(record)


def freeze_movement_binding(fight, *, roles):
    from wakfu_server import native_catalog

    if fight.phase != "placement":
        raise ValueError("Committed movement binding requires fresh placement")
    if hasattr(fight, "native_encounter_movement_binding"):
        previous = fight.native_encounter_movement_binding
        frozen = None if previous is None else binding_from_record(previous)
    else:
        with _database().connection() as db:
            row = db.execute(
                "SELECT policy FROM encounter_movement_binding_active "
                "WHERE map_id=%s AND monster_references=%s::integer[]",
                (roles.map_id, list(roles.monster_references)),
            ).fetchone()
        frozen = None if row is None else deepcopy(_version(row["policy"]))
    if frozen is not None and (
        frozen["map_id"] != roles.map_id
        or frozen["monster_references"] != list(roles.monster_references)
        or not source_revision_matches(frozen["catalog_revision"], SOURCE_DEPENDENCIES)
    ):
        raise ValueError("Committed movement binding differs from admission or catalog")
    fight.native_encounter_movement_binding = frozen
    return deepcopy(frozen)


def movement_caster(fight, source, *, entry, original, definition, effect):
    """Bind only the admitted committed boss step; preserve native null Qe."""
    frozen = getattr(fight, "native_encounter_movement_binding", None)
    if frozen is None:
        return None
    frozen = binding_from_record(frozen)
    if original.reference != frozen["listener_reference"]:
        return None
    from .combat_event_replay import NativeExternalEvent

    if not isinstance(source, NativeExternalEvent):
        return None
    context = source.movement_boundary_context
    if (
        source.event_ids != (frozen["event_id"],)
        or source.channel != frozen["channel"]
        or not isinstance(context, dict)
    ):
        return None
    from .combat_external_movement_recipient import committed_movement_actor
    from wakfu_server.combat_encounter_roles import frozen_roles

    participant = committed_movement_actor(fight, context)
    roles = frozen_roles(fight)
    if (
        roles is None
        or roles.map_id != frozen["map_id"]
        or list(roles.monster_references) != frozen["monster_references"]
    ):
        raise ValueError("Committed movement binding escaped frozen encounter scope")
    if (
        effect.get("effect_class") != frozen["effect_family"]
        or effect.get("native_target_selector")
        != {"class": "fcE", "mask": frozen["selector_mask"]}
        or not _same_sequence(effect.get("parameters"), frozen["native_parameters"])
        or not _same_sequence(effect.get("children"), frozen["native_children"])
        or effect.get("criteria") != frozen["criterion"]
        or effect.get("area_class") != frozen["area_class"]
        or effect.get("parameter_count") != frozen["parameter_count"]
        or not _same_sequence(
            effect.get("native_effect_flags"), frozen["native_effect_flags"]
        )
        or effect.get("native_execution_mode") != frozen["native_execution_mode"]
        or not _same_sequence(
            effect.get("target_masks"),
            [None, None, None, None, None, [frozen["event_id"]], None],
        )
        or definition.get("subscription") is not True
        or definition.get("event_reverse_subscription") is not True
        or definition.get("event_global_subscription") is not False
        or definition.get("owner_on_caster") is not False
        or definition.get("event_execution_count") != -1
        or definition.get("event_execution_count_per_level") != 0
        or definition.get("event_caster_code") != frozen["caster_code"]
        or definition.get("event_target_code") != frozen["target_code"]
    ):
        raise ValueError("Original committed movement subscription descriptor changed")
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(
        participant.id, {}
    )
    if (
        participant.controlled
        or participant.hp <= 0
        or participant.team != roles.npc_team
        or source.manager_actor_id != participant.id
        or entry.manager_id != participant.id
        or original.target_id != participant.id
        or entry.generic_effect != original.reference
        or receipt.get("ref") != frozen["boss_reference"]
        or receipt.get("initialized") is not True
        or not any(
            row.get("state_id") == frozen["boss_constructor_state"]
            for row in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError("Committed movement binding lacks its actual native boss")
    if original.caster_id == participant.id:
        return None  # Native null-source replay already has the actual mover.
    producer = fight.actors.get(original.caster_id)
    if (
        producer is None
        or producer.controlled is not True
        or producer.team != roles.player_team
        or type(producer.owner_id) is not int
        or producer.owner_id <= 0
    ):
        raise ValueError("Committed movement binding lacks its original state producer")
    if not any(
        state.uid == original.state_uid
        and state.reference == frozen["carrier_state"]
        and state.target_id == participant.id
        and state.caster_id == original.caster_id
        and original.reference in state.effect_ids
        for state in participant.state_ledger.entries
    ):
        raise ValueError(
            "Committed movement binding lacks its original carrier state UID"
        )
    retained = getattr(fight, "native_owned_group_effects", {}).get(entry.uid)
    if (
        not isinstance(retained, dict)
        or retained.get("invocation", {}).get("state_uid") != original.state_uid
        or retained.get("invocation", {}).get("reference") != original.reference
        or retained.get("invocation", {}).get("caster_id") != original.caster_id
        or retained.get("invocation", {}).get("target_id") != participant.id
    ):
        raise ValueError("Committed movement binding lacks its retained listener UID")
    key = ":".join(
        map(
            str,
            (
                frozen["policy"],
                fight.turn_id,
                participant.id,
                context["action_id"],
                *context["from_cell"],
                *context["to_cell"],
                entry.uid,
            ),
        )
    )
    journal = getattr(fight, "native_movement_caster_deliveries", {})
    # One action may commit multiple steps, including revisiting an edge.
    # The active publication scope attests each delivery; this is an audit
    # journal, not an invented action/turn/edge execution cap.
    key = f"{key}:{len(journal)}"
    fight.native_movement_caster_deliveries = {
        **journal,
        key: dict(
            policy=frozen["policy"],
            turn_id=fight.turn_id,
            actor_id=participant.id,
            action_id=context["action_id"],
            from_cell=list(context["from_cell"]),
            to_cell=list(context["to_cell"]),
            listener_uid=entry.uid,
            state_uid=original.state_uid,
            original_caster=original.caster_id,
            reconstructed_caster=participant.id,
        ),
    }
    return participant.id
