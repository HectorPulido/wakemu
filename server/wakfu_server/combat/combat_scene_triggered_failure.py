"""Opt-in scene outcomes from an authentic native owned-state spell callback.

The original spell still executes, including its movement and death effects.
This declaration supplies only the reviewed encounter result after that spell.
"""

from copy import deepcopy

SCHEMA = "owned-native-escape-failure-v1"
SOURCE = "wakemu.reviewed_native_triggered_failure.v1"


def declaration(descriptor):
    if descriptor is None:
        return None
    if type(descriptor) is not dict:
        raise ValueError("Invalid native scene failure descriptor")
    value = descriptor.get("native_escape_failure")
    if value is None:
        return None
    if (
        type(value) is not dict
        or set(value)
        != {
            "schema",
            "actor_reference",
            "trigger_effect",
            "spell_reference",
            "state_reference",
            "losing_role",
            "evidence",
        }
        or value["schema"] != SCHEMA
        or any(
            type(value[key]) is not int or value[key] <= 0
            for key in (
                "actor_reference",
                "trigger_effect",
                "spell_reference",
                "state_reference",
            )
        )
        or value["losing_role"] != "original_controlled"
        or type(value["evidence"]) is not str
        or not value["evidence"].strip()
        or descriptor.get("full_room_scope") is not True
    ):
        raise ValueError("Native scene failure lacks its explicit source policy")
    return value


def _descendant(effects, root, wanted):
    pending, seen = [root], set()
    while pending:
        reference = pending.pop()
        if reference in seen:
            continue
        seen.add(reference)
        row = effects.get(str(reference))
        if row is None:
            raise ValueError("Native scene failure lost its compiled source chain")
        if reference == wanted:
            return True
        pending.extend(row.get("children", ()))
    return False


def _source_root(fight, actor, state, invocation, effects):
    context = invocation.native_trigger_context
    if context is not None:
        if (
            type(context) is not dict
            or context.get("native_events_verified") is not True
            or context.get("manager_actor_id") != actor.id
            or context.get("generic_effect") not in state.effect_ids
        ):
            raise ValueError("Native scene failure lacks its original callback actor")
        roots = [context["generic_effect"]]
    else:
        # Turn notifications have an authentic null Qe. Attest the existing
        # server boundary scope instead of fabricating a native source runner.
        from .combat_external_turn_recipient import qualified_boundary_actor

        boundary = invocation.native_turn_boundary_context
        if (
            boundary is None
            or qualified_boundary_actor(fight, turn_context=boundary) is not actor
        ):
            raise ValueError("Native scene failure lacks its original callback actor")
        roots = []
        for reference in state.effect_ids:
            row = effects.get(str(reference))
            masks = None if row is None else row.get("target_masks")
            if (
                row is not None
                and row.get("effect_class") == 330
                and isinstance(masks, (list, tuple))
                and len(masks) == 7
                and any(boundary["event_id"] in (mask or ()) for mask in masks)
            ):
                roots.append(reference)
    matches = [
        reference
        for reference in roots
        if _descendant(effects, reference, invocation.reference)
    ]
    if len(matches) != 1:
        raise ValueError("Native scene failure lost its owned state lineage")
    return matches[0]


def prepare_triggered(fight, request, effect, invocation, *, effects):
    """Capture source lineage before the original nested spell can remove it."""
    record = getattr(fight, "native_encounter_scene", None)
    if (
        record is None
        or record.get("descriptor", {}).get("native_escape_failure") is None
    ):
        return None
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_encounter_roles import assigned_roles

    policy = declaration(frozen_scene(fight))
    if (
        invocation.reference != policy["trigger_effect"]
        or request.spell_id != policy["spell_reference"]
    ):
        return None
    actor = fight.actors.get(request.caster_id)
    roles = assigned_roles(fight)
    bindings = record["scope"].get("actor_bindings", ())
    candidates = [b for b in bindings if b.get("ref") == policy["actor_reference"]]
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(
        request.caster_id, {}
    )
    if (
        fight.phase != "active"
        or effects.get(str(invocation.reference)) is not effect
        or effect.get("effect_class") != 426
        or request.caster_id != invocation.caster_id
        or actor is None
        or actor.controlled is not False
        or actor.team != roles.npc_team
        or not fight._in_play(actor)
        or len(candidates) != 1
        or candidates[0].get("actor_id") != actor.id
        or receipt.get("initialized") is not True
        or receipt.get("ref") != policy["actor_reference"]
        or not any(
            s.get("state_id") == policy["state_reference"]
            for s in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError("Native scene failure lacks its original callback actor")
    states = [
        state
        for state in actor.state_ledger.entries
        if state.uid == invocation.state_uid
        and state.reference == policy["state_reference"]
        and state.caster_id == actor.id
        and state.target_id == actor.id
    ]
    if len(states) != 1:
        raise ValueError("Native scene failure lost its owned state lineage")
    source_root = _source_root(fight, actor, states[0], invocation, effects)
    if getattr(fight, "native_encounter_objective_policy", None) is not None:
        raise ValueError("Native scene failure conflicts with its result director")
    return dict(
        source=SOURCE,
        schema=SCHEMA,
        fight_id=fight.id,
        scene_sha256=record["sha256"],
        scope=deepcopy(record["scope"]),
        actor_id=actor.id,
        actor_reference=policy["actor_reference"],
        state_uid=invocation.state_uid,
        state_reference=policy["state_reference"],
        trigger_effect=invocation.reference,
        spell_reference=request.spell_id,
        source_root=source_root,
        event_sequence=fight.sequence,
        losing_team=roles.player_team,
        winning_team=roles.npc_team,
    )


def settle_triggered(fight, captured):
    """Settle once after successful native execution, without changing actors."""
    if captured is None:
        return False
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_encounter_roles import assigned_roles

    policy = declaration(frozen_scene(fight))
    roles = assigned_roles(fight)
    record = getattr(fight, "native_encounter_scene", None)
    if policy is None or type(captured) is not dict or record is None:
        raise ValueError("Native scene result lost its captured callback source")
    actor = fight.actors.get(captured.get("actor_id"))
    bindings = [
        row
        for row in record["scope"].get("actor_bindings", ())
        if row.get("ref") == policy["actor_reference"]
    ]
    if (
        captured.get("source") != SOURCE
        or captured.get("schema") != SCHEMA
        or captured.get("fight_id") != fight.id
        or captured.get("scene_sha256") != record["sha256"]
        or captured.get("scope") != record["scope"]
        or captured.get("trigger_effect") != policy["trigger_effect"]
        or captured.get("spell_reference") != policy["spell_reference"]
        or captured.get("actor_reference") != policy["actor_reference"]
        or captured.get("state_reference") != policy["state_reference"]
        or type(captured.get("state_uid")) is not int
        or len(bindings) != 1
        or bindings[0].get("actor_id") != captured.get("actor_id")
        or actor is None
        or actor.controlled is not False
        or actor.team != roles.npc_team
        or type(captured.get("event_sequence")) is not int
        or not 0 <= captured["event_sequence"] <= fight.sequence
        or captured.get("losing_team") != roles.player_team
        or captured.get("winning_team") != roles.npc_team
        or fight.phase not in ("active", "finished")
    ):
        raise ValueError("Native scene result lost its captured callback source")
    previous = getattr(fight, "native_triggered_failure_receipt", None)
    if previous is not None:
        if previous != captured:
            raise ValueError("Encounter already settled another native failure")
        return False
    terminals = [
        event
        for event in fight.events
        if event.get("kind") == "finished"
        and event.get("sequence", -1) > captured["event_sequence"]
    ]
    if (
        fight.phase == "finished"
        and (len(terminals) != 1 or terminals[0].get("winner") != fight.winner)
    ) or (fight.phase == "active" and terminals):
        raise ValueError("Native callback has an ambiguous terminal result")
    fight.native_triggered_failure_receipt = deepcopy(captured)
    # The same original nested spell may have killed its carrier and produced
    # normal victory. Its explicitly declared escape outcome takes precedence.
    original_winner = fight.winner
    fight.phase = "finished"
    fight.winner = roles.npc_team
    result = dict(
        winner=fight.winner,
        reason="owned_scene_native_escape_failure",
        actor_id=captured["actor_id"],
        spell_id=captured["spell_reference"],
    )
    if terminals:
        # This native callback is still uncommitted. Adjudicate its one terminal
        # event before any journal/outbox consumer can see a competing victory.
        if original_winner != fight.winner:
            result["native_original_winner"] = original_winner
        terminals[0].update(result)
    else:
        fight._event("finished", **result)
    return True
