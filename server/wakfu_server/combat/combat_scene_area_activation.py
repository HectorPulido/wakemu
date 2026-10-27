"""Typed, source-scoped scene callbacks for native area consumers.

The original server producer of event10009 is unrecovered. A scene controller
may declare an explicit reconstructed objective/interaction/native-event rule.
It must publish its actual committed event receipt before this adapter can
activate the installed trap. No turn, movement or global event allowlist is
substituted for that missing source.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class OwnedSceneEventReceipt:
    """One completed authoritative scene action, owned by its real publisher."""

    fight_id: int
    actor_id: int
    turn_id: int
    sequence: int
    source_uid: int
    kind: str
    reference: int
    policy: str
    authority: str


def validate_scene_activation(rule, *, reference):
    """Unknown source rules remain absent; only the original841 consumer opts in."""
    if rule is None:
        return
    if (
        reference != 841
        or not isinstance(rule, dict)
        or set(rule) != {"kind", "reference", "event_id"}
        or rule.get("kind") not in ("interaction", "objective", "native_event")
        or type(rule.get("reference")) is not int
        or rule["reference"] <= 0
        or type(rule.get("event_id")) is not int
        or rule["event_id"] != 10009
    ):
        raise ValueError("Missing declared scene activation source")


def activate_declared_scene_traps(dispatcher, actor_id, receipt):
    """Deliver10009 only for an owned, committed event matching a frozen rule.

    The controller retains this exact typed object in
    fight.native_scene_event_receipts[source_uid] during the action boundary.
    This function cannot create receipts or advance scene objectives itself.
    """
    fight = dispatcher.native_retention.fight
    if not isinstance(receipt, OwnedSceneEventReceipt):
        raise ValueError("An actual owned scene event receipt is required")
    numeric = (
        receipt.fight_id,
        receipt.actor_id,
        receipt.turn_id,
        receipt.sequence,
        receipt.source_uid,
        receipt.reference,
    )
    if (
        any(type(value) is not int for value in numeric)
        or type(actor_id) is not int
        or actor_id == 0
        or receipt.source_uid == 0
        or receipt.actor_id != actor_id
        or receipt.fight_id != fight.id
        or receipt.turn_id != fight.turn_id
        or receipt.sequence != fight.sequence
        or receipt.kind not in ("interaction", "objective", "native_event")
        or not isinstance(receipt.policy, str)
        or not receipt.policy.startswith("wakemu.")
        or not isinstance(receipt.authority, str)
        or not receipt.authority
        or getattr(fight, "native_scene_event_receipts", {}).get(receipt.source_uid)
        is not receipt
    ):
        raise ValueError("Scene event differs from its actual committed boundary")
    actor = fight.actors.get(actor_id)
    callbacks = getattr(dispatcher, "native_area_events", None)
    if (
        fight.phase != "active"
        or actor is None
        or actor.hp <= 0
        or not fight._in_play(actor)
        or callbacks is None
    ):
        return ()
    from .combat_area_authority import area_guards
    from .combat_effect_area_geometry import contains_area_actor
    from .combat_environment_glyphs import verify_environment_glyph
    from .combat_encounter_glyph_bootstrap import TRAP_SOURCE

    areas = getattr(fight, "native_effect_areas", {})
    outcomes = []
    for source in tuple(getattr(fight, "native_environment_glyph_constructors", ())):
        rule = source.get("activation")
        if rule is None:
            continue
        validate_scene_activation(rule, reference=source.get("reference"))
        if (
            rule["kind"] != receipt.kind
            or rule["reference"] != receipt.reference
            or source.get("source") != TRAP_SOURCE
            or not source.get("authority")
            or not source.get("source_url")
            or source.get("policy") != receipt.policy
            or source.get("authority") != receipt.authority
        ):
            continue
        row = areas.get(source["uid"])
        if (
            row is None
            or row.get("executing") is not False
            or row.get("remaining_activations", 0) == 0
        ):
            continue
        verify_environment_glyph(fight, row)
        if area_guards(fight, row["uid"]) != dict(baG=False, baK=False, baF=True):
            continue
        if not contains_area_actor(row, actor.position, actor.physical_radius):
            continue
        definition = callbacks._definition(row)
        if (
            definition.get("type") != "TRAP"
            or tuple(definition.get("entry_masks", ())) != (10009,)
            or tuple(definition.get("effect_ids", ())) != (147092,)
        ):
            raise ValueError("Scene trap differs from the original10009 consumer")
        # This is per actual area UID and committed event, not per prototype.
        key = f"{receipt.source_uid}:{receipt.sequence}"
        delivered = row.setdefault("native_scene_activation_receipts", {})
        if key in delivered:
            continue
        delivered[key] = dict(
            kind=receipt.kind,
            reference=receipt.reference,
            actor_id=actor_id,
            turn_id=receipt.turn_id,
        )
        outcomes.extend(callbacks._deliver_event(row, definition, actor, 10009))
    return tuple(outcomes)
