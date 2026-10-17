"""Prepare an individual PvE withdrawal without ending the shared encounter.

This module only prepares private/native messages and a detached candidate.
The registry must commit durable withdrawal and HP before adopting it. The
original runtime stays untouched if encoding, ownership or persistence fails.
"""
from copy import copy, deepcopy
from dataclasses import dataclass
import struct

from . import combat_death


@dataclass(frozen=True)
class Withdrawal:
    fight: object
    runtime: object
    private_runtime: object
    private_packets: tuple
    public_packets: tuple
    initial_actor: object
    removed_actor_ids: tuple
    turn_changed: bool


def _clone_runtime(runtime, fight):
    # NativeDelivery is an immutable tuple subclass requiring constructor
    # metadata; deepcopy cannot reconstruct it. Pending packets are already
    # immutable wire pairs, so copy the sequence into an ordinary owned list.
    clone = copy(runtime)
    state = dict(vars(runtime), fight=fight, pending=list(runtime.pending))
    clone.__dict__.update(deepcopy(state, {id(fight): fight}))
    return clone


def live_owner_accounts(fight):
    """Count living primary players, grouping heroes by their account."""
    from .combat_terminal_metadata import registered_summon_actor_ids

    summons = registered_summon_actor_ids(fight)
    if any(
        actor.id not in summons
        and (
            getattr(actor, "native_summon_source", None) is not None
            or getattr(actor, "is_summon", False) is True
        )
        for actor in fight.actors.values()
    ):
        raise ValueError("PvE owner roster contains an unregistered native summon")
    return frozenset(
        actor.owner_id
        for actor in fight.actors.values()
        if actor.controlled
        and actor.id not in summons
        and actor.hp > 0
        and not getattr(actor, "pve_withdrawn", False)
    )


def has_other_live_owner(fight, session):
    """Validate the requester before choosing an individual or full exit."""
    from .combat_terminal_metadata import registered_summon_actor_ids

    summons = registered_summon_actor_ids(fight)
    actor = fight.actors.get(session.character_id)
    if (
        actor is None
        or not actor.controlled
        or actor.id in summons
        or actor.owner_id != session.account_id
        or getattr(actor, "pve_withdrawn", False)
    ):
        raise ValueError("Invalid PvE exit owner")
    other_live = live_owner_accounts(fight) - {session.account_id}
    return bool(other_live)


def plan(session, fight, runtime):
    """Remove one live owner's actors; keep surviving owners and NPCs active.

    A private normal cvF triggers that client's native12925 continuation. It
    must never enter the shared broadcast. The removed actor remains in the
    historical roster at zero HP for checkpoints, while health persistence
    uses ``initial_actor`` rather than treating surrender as lethal damage.
    """
    actor = fight.actors.get(session.character_id)
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != session.account_id
        or fight.phase not in ("placement", "active")
        or (runtime is not None and getattr(runtime, "fight", None) is not fight)
    ):
        raise ValueError("Invalid PvE withdrawal owner or runtime")
    from .combat_terminal_metadata import registered_summon_actor_ids

    other_accounts = live_owner_accounts(fight) - {session.account_id}
    summons = registered_summon_actor_ids(fight)
    remaining = [
        member
        for member in fight.actors.values()
        if member.controlled
        and member.id not in summons
        and member.owner_id in other_accounts
        and member.hp > 0
        and not getattr(member, "pve_withdrawn", False)
    ]
    if not remaining:
        raise ValueError("Last PvE owner requires full abandonment")
    if any(member.team != actor.team for member in remaining):
        raise ValueError("Individual withdrawal only supports same-team PvE")
    if runtime is None:
        from .combat_abandon import placement_runtime

        runtime = placement_runtime(fight, runtime)
    candidate = deepcopy(fight)
    candidate_runtime = _clone_runtime(runtime, candidate)
    original_current = None if fight.current is None else fight.current.id
    from .combat_terminal_metadata import registered_summon_actor_ids

    summons = registered_summon_actor_ids(candidate)
    removed_set = {
        member.id
        for member in candidate.actors.values()
        if member.controlled
        and member.owner_id == session.account_id
        and member.id not in summons
    }
    # Native summons retain caster/controller identities, including recursive
    # summon chains. NPC owner IDs alone cannot establish summon ownership.
    while True:
        discovered = {
            member.id
            for member in candidate.actors.values()
            if getattr(member, "native_summon_source", {}).get("caster_id")
            in removed_set
        }
        if discovered <= removed_set:
            break
        removed_set.update(discovered)
    removed = tuple(
        member.id for member in candidate.actors.values() if member.id in removed_set
    )
    public = []
    for identity in removed:
        target = candidate.actors[identity]
        from .combat_pve_departure import retire_pve_actor

        retire_pve_actor(
            candidate,
            target,
            root_actor_id=session.character_id,
            owner_id=session.account_id,
        )
        target.pve_withdrawn = True
        if target.hp > 0:
            from .combat_hp_raw import hp_raw_present, set_hp_raw_current

            if hp_raw_present(target):
                set_hp_raw_current(target, 0)
            else:
                target.hp = 0
            if target.effect_stats is not None:
                if (
                    not isinstance(target.effect_stats, dict)
                    or 1 not in target.effect_stats
                ):
                    raise ValueError(
                        "Missing withdrawn actor HP characteristic snapshot"
                    )
                if not hp_raw_present(target):
                    target.effect_stats[1] = 0
            candidate._event(
                "withdrawn", actor_id=identity, owner_id=session.account_id
            )
        # Withdrawal finalizes both living actors and existing reversible KO.
        public.extend(
            combat_death.death_messages(candidate_runtime, identity, fighter_state=2)
        )
    turn_changed = False
    if candidate.phase == "active":
        candidate._settle_deaths()
        turn_changed = original_current != candidate.current.id
        # A pending aUM animation barrier must be maintained by the registry:
        # only remove the withdrawing owner from its required ACK membership.
        # If no barrier is pending, deliver the new active actor immediately.
        if turn_changed and candidate_runtime.awaiting_ack is None:
            candidate_runtime.turn_deadline = candidate_runtime.deadline_turn = None
            public.extend(candidate_runtime.turn_started())
        elif turn_changed:
            # The successor packets refer to a different actor now. Rebuild
            # without exposing it before the remaining owners acknowledge.
            previous_ack = candidate_runtime.awaiting_ack
            candidate_runtime.awaiting_ack = None
            candidate_runtime.pending = list(
                candidate_runtime.turn_started(arm_deadline=False)
            )
            candidate_runtime.awaiting_ack = previous_ack

    # Death and successor packets form one public allocation boundary. Some
    # existing turn helpers return prepared deliveries; reassigning the whole
    # ordinary list once avoids collisions with preceding raw death events.
    public = tuple(candidate_runtime.prepare_delivery(public)) if public else ()
    private = _clone_runtime(candidate_runtime, deepcopy(candidate))
    private.fight.phase = "finished"
    private.fight.winner = None
    private.awaiting_ack = None
    private.pending = []
    private.turn_deadline = private.deadline_turn = None
    private.abandon_owner = (session.account_id, session.character_id)
    private.abandon_returned = False
    from .combat_terminal_metadata import registered_summon_actor_ids

    summon_ids = registered_summon_actor_ids(private.fight)
    for member in private.fight.actors.values():
        if member.id != session.character_id and member.id not in summon_ids:
            member.pve_withdrawn = True
    # This detached private continuation uses singleton abandon validation;
    # the public encounter retains the durable withdrawal flag.
    private.fight.actors[session.character_id].pve_withdrawn = False
    losers = [session.character_id]
    winners = [
        member.id for member in fight.actors.values() if member.team != actor.team
    ]
    if not winners or max(len(losers), len(winners)) > 127:
        raise ValueError("Unsupported PvE withdrawal result layout")
    payload = private._prefix() + b"\x00"
    for identities in (losers, winners, []):
        payload += struct.pack(">b", len(identities)) + b"".join(
            struct.pack(">q", identity) for identity in identities
        )
    private_packets = tuple(
        private.prepare_delivery([(12238, payload), private._flush()])
    )
    return Withdrawal(
        candidate,
        candidate_runtime,
        private,
        private_packets,
        tuple(public),
        deepcopy(actor),
        removed,
        turn_changed,
    )
