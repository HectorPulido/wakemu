"""Reviewed scene relationship reconstruction; the native source Qe stays null."""
from functools import lru_cache
from hashlib import sha256
import json
import re
from types import MappingProxyType

_FIELDS = frozenset(
    (
        "listener_reference",
        "receiver_state",
        "receiver_root",
        "controller_state",
        "controller_references",
        "source_chain",
        "event_id",
        "phase",
        "relation",
        "authority",
        "source_sha256",
    )
)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def native_participant_source_digest(rule):
    """Bind the declaration to the original carrier, masks and full child guards."""
    from .spell_audit import states_catalog
    from .combat_retained_runtime import native_retained_metadata

    if (
        type(rule) is not dict
        or set(rule) - _FIELDS
        or rule.get("relation") != "actual_owned_event_participant_as_external_caster"
        or rule.get("event_id") != 1002
        or rule.get("phase") != "end"
        or not isinstance(rule.get("authority"), str)
        or not rule["authority"].strip()
    ):
        raise ValueError("Invalid reviewed external participant relationship")
    for key in (
        "listener_reference",
        "receiver_state",
        "receiver_root",
        "controller_state",
    ):
        if type(rule.get(key)) is not int or rule[key] <= 0:
            raise ValueError("External participant lacks a native source identity")
    refs, chain = rule.get("controller_references"), rule.get("source_chain")
    if (
        type(refs) is not list
        or not refs
        or refs != sorted(set(refs))
        or any(type(ref) is not int or ref <= 0 for ref in refs)
        or type(chain) is not list
        or len(chain) < 2
        or chain[0] != rule["listener_reference"]
        or any(type(ref) is not int or ref <= 0 for ref in chain)
    ):
        raise ValueError("External participant lacks a complete native chain")
    catalog = states_catalog()
    effects, states = catalog["effects"], catalog["states"]
    root = effects[str(rule["receiver_root"])]
    receiver = states[str(rule["receiver_state"])]
    controller = states[str(rule["controller_state"])]
    rows = [effects[str(ref)] for ref in chain]
    metadata = native_retained_metadata()["effects"][str(chain[0])]
    first = rows[0]
    if (
        rule["receiver_root"] not in receiver["effect_ids"]
        or chain[0] not in root.get("children", ())
        or first.get("effect_class") != 330
        or metadata.get("subscription") is not True
        or metadata.get("event_global_subscription") is not True
        or metadata.get("event_reverse_subscription") is not False
        or metadata.get("event_caster_code") != 4
        or metadata.get("event_target_code") != 2
        or rule["event_id"] not in (first["target_masks"][5] or ())
        or "GetTriggeringEffectCaster()" not in first.get("criteria", "")
        or "GetEffectTargetOriginalController()" not in first.get("criteria", "")
    ):
        raise ValueError("External relationship differs from original source semantics")
    for parent, child in zip(rows, chain[1:]):
        if child not in parent.get("children", ()):
            raise ValueError("External participant child guard chain changed")
    descendants = {}
    pending = list(chain)
    while pending:
        reference = pending.pop()
        if str(reference) in descendants:
            continue
        row = effects[str(reference)]
        descendants[str(reference)] = row
        pending.extend(row.get("children", ()))
    guard_ids = {
        int(value)
        for row in descendants.values()
        for value in re.findall(
            r'HasEffectWithSpecificId\(\s*"[^"]+"\s*,\s*(\d+)\s*\)',
            row.get("criteria", ""),
        )
    }
    from .combat_npc_attack import npc_runtime_catalog

    guards = npc_runtime_catalog().source_effects
    document = dict(
        receiver=receiver,
        receiver_root=root,
        controller=controller,
        effects=descendants,
        metadata=metadata,
        guard_definitions={
            str(ref): (effects.get(str(ref)) or guards[str(ref)])
            for ref in sorted(guard_ids)
        },
    )
    return sha256(_canonical(document).encode()).hexdigest()


@lru_cache(maxsize=32)
def _validated(encoded):
    rule = json.loads(encoded)
    if set(rule) != _FIELDS or rule[
        "source_sha256"
    ] != native_participant_source_digest(rule):
        raise ValueError("Reviewed external participant source changed")
    return MappingProxyType(
        {
            key: tuple(value) if isinstance(value, list) else value
            for key, value in rule.items()
        }
    )


def validate_external_participants(rules):
    if type(rules) is not list or not rules:
        raise ValueError("Invalid external participant declarations")
    validated = tuple(_validated(_canonical(rule)) for rule in rules)
    if len({row["listener_reference"] for row in validated}) != len(validated):
        raise ValueError("Ambiguous external participant listener")
    return validated


def declared_external_participant(fight, invocation, *, actor_authority):
    """Return only a genuine scoped owned participant; do not create a Qe."""
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_external_turn_recipient import qualified_boundary_actor
    from .combat_summon import RegisteredSummonAuthority
    from .combat_state_managers import state_managers

    record = getattr(fight, "native_encounter_scene", None)
    if record is None:
        return None
    if (
        isinstance(record, dict)
        and isinstance(record.get("descriptor"), dict)
        and not record["descriptor"].get("external_event_participants")
    ):
        return None
    if isinstance(record, dict) and isinstance(record.get("descriptor"), dict):
        hints = record["descriptor"].get("external_event_participants")
        if isinstance(hints, list) and not any(
            isinstance(row, dict)
            and row.get("listener_reference") == invocation.reference
            for row in hints
        ):
            return None  # A nonmatching hint grants no relationship authority.
    scene = frozen_scene(fight)
    if scene is None or scene.get("external_event_participants") is None:
        return None
    rules = validate_external_participants(scene["external_event_participants"])
    rule = next(
        (row for row in rules if row["listener_reference"] == invocation.reference),
        None,
    )
    if rule is None:
        return None
    context = invocation.native_turn_boundary_context
    if invocation.native_trigger_context is not None or context is None:
        return None  # Native source runners retain their exact original semantics.
    if context["event_id"] != rule["event_id"] or context["phase"] != rule["phase"]:
        return None
    participant = qualified_boundary_actor(fight, turn_context=context)
    child = fight.actors.get(invocation.target_id)
    if (
        child is None
        or child.controlled
        or not isinstance(actor_authority, RegisteredSummonAuthority)
    ):
        raise ValueError(
            "External relationship lacks registered native child authority"
        )
    source = actor_authority(fight, child)  # Validates complete native307 provenance.
    registration = getattr(fight, "native_summon_registrations", {}).get(child.id)
    if (
        source.is_player is not False
        or source.is_summon is not True
        or source.native_actor_type != 1
        or not isinstance(registration, dict)
    ):
        raise ValueError("External relationship is not an actual native NPC summon")
    controller_id = registration["controller_id"]
    # A global1002 from another participant is valid delivery but not this
    # native original-controller relationship. Its original query stays-1.
    if participant.id != controller_id:
        return None
    if registration["caster_id"] != participant.id:
        raise ValueError(
            "External controller is not the original native summoning caster"
        )
    controller_source = actor_authority(fight, participant)
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(
        participant.id, {}
    )
    if (
        participant.controlled
        or controller_source.is_player is not False
        or controller_source.is_summon is not False
        or receipt.get("initialized") is not True
        or receipt.get("ref") not in rule["controller_references"]
        or not any(
            row.get("state_id") == rule["controller_state"]
            for row in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError(
            "External relationship lacks its real native controller constructor"
        )
    carriers = [
        state
        for manager in state_managers(fight)
        if manager.id == child.id
        for state in manager.state_ledger.entries
        if state.uid == invocation.state_uid
    ]
    if len(carriers) != 1 or carriers[0].reference != rule["receiver_state"]:
        raise ValueError(
            "External relationship lost its actual retained source carrier"
        )
    return participant.id


def replay_external_participant(dispatcher, source, *, entry, original):
    """Resolve casterCode4 using declared caller facts, not a forged source Qe."""
    from dataclasses import replace
    from .combat_event_replay import NativeExternalEvent, NativeCloneAuthority
    from .combat_ordinary_events import OrdinaryHealingEvents

    if (
        not isinstance(source, NativeExternalEvent)
        or source.turn_boundary_context is None
    ):
        return None
    record = getattr(dispatcher.native_retention.fight, "native_encounter_scene", None)
    if record is None:
        return None
    if (
        isinstance(record, dict)
        and isinstance(record.get("descriptor"), dict)
        and not record["descriptor"].get("external_event_participants")
    ):
        return None
    authority = dispatcher.native_clone_authority
    if not isinstance(authority, NativeCloneAuthority):
        raise ValueError("External relationship lacks real replay authority")
    lifecycle = getattr(authority.executable, "__self__", None)
    if (
        not isinstance(lifecycle, OrdinaryHealingEvents)
        or lifecycle.preview is not dispatcher.native_retention.fight
        or lifecycle.retention is not dispatcher.native_retention
    ):
        raise ValueError("External relationship replay authority changed")
    invocation = replace(
        original,
        target_id=entry.manager_id,
        native_trigger_context=None,
        native_turn_boundary_context=source.turn_boundary_context,
    )
    return declared_external_participant(
        lifecycle.preview, invocation, actor_authority=lifecycle.adapter.actor_authority
    )
