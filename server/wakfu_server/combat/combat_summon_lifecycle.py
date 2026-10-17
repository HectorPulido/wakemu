"""Summon roster/timeline and settled-retirement publication boundary.

Builders own native identity allocation, spellbooks and QI preparation. This
boundary publishes their validated registration and the existing source-attested
retirement result. Historical comparisons use an isolated archived engine.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from .combat_state import Actor


@dataclass(frozen=True)
class PreparedSummonRegistration:
    authority: object
    fight: object
    actor: object
    registration: object
    row: dict
    records: dict
    next_base: list | None
    order: tuple
    turn_index: int

    def publish(self):
        from .combat_timeline_snapshot import insert
        from .combat_global_pv_collections import register_global_fighter

        fight, actor, registration = self.fight, self.actor, self.registration
        if 114 not in registration.fight_properties:
            insert(fight, actor.id, self.order.index(actor.id))
        fight.actors[actor.id] = actor
        if hasattr(fight, "native_global_pv_collections"):
            register_global_fighter(
                fight, actor.id, controller_id=registration.controller_id
            )
        fight.native_summon_registrations = {
            **self.records,
            actor.id: self.row,
        }
        fight.order, fight.turn_index = list(self.order), self.turn_index
        if self.next_base is not None:
            fight.native_base_turn_order = self.next_base


def prepare_registration(
    authority, preview, actor, registration, *, new_order, new_turn_index
):
    from .combat_summon import SummonRegistration, fresh_summon_slot_owned

    from .combat_summon_placement import native_summon_placement

    if (
        preview.phase != "active"
        or not isinstance(actor, Actor)
        or not isinstance(registration, SummonRegistration)
        or actor.id != registration.actor_id
        or actor.id in preview.actors
        or actor.id <= 0
        or registration.caster_id not in preview.actors
        or registration.controller_id not in (*preview.actors, actor.id)
        or not native_summon_placement(preview, actor)
    ):
        raise ValueError("Invalid owned summon registration")
    # Native big.a/fdt registers QK identities even at a shared cell.
    # Spell criteria own placement legality; creation can precede a carry
    # transition in the same ordered group. Validate its exact QI slot
    # below instead of imposing an additional living-cell restriction.
    metadata = registration.authority
    authority._fresh_relationships(actor, vars(registration), metadata)
    if (
        metadata.is_summon is not True
        or metadata.summon_root_id is None
        or metadata.is_player is not False
        or metadata.is_carried is not False
        or metadata.targeting.get("bcN") != actor.native_obstacle_id
        or type(actor.native_obstacle_id) is not int
        or not 0 <= actor.native_obstacle_id <= 126
        or not fresh_summon_slot_owned(preview, actor)
        or actor.effect_stats is None
        or actor.effect_maxima is None
        or actor.effect_minima is None
        or actor.effect_frozen is None
        or actor.physical_radius is None
        or actor.spell_ap_cost_modifiers is None
        or actor.spell_range_modifiers is None
    ):
        raise ValueError("Summon requires complete native actor authority/snapshot")
    # fbX.C consults ffe114 NOT_PRESENT_IN_TIMELINE before fem.a.
    expected = Counter(preview.order)
    if 114 not in registration.fight_properties:
        expected[actor.id] += 1
    if (
        Counter(new_order) != expected
        or type(new_turn_index) is not int
        or not 0 <= new_turn_index < len(new_order)
        or new_order[new_turn_index] != preview.current.id
    ):
        raise ValueError("Missing native timeline insertion preserving current actor")
    controller = (
        actor
        if registration.controller_id == actor.id
        else preview.actors[registration.controller_id]
    )
    if (
        actor.controlled != controller.controlled
        or actor.owner_id != controller.owner_id
    ):
        raise ValueError("Summon controller/account mismatch")
    base_order = getattr(preview, "native_base_turn_order", None)
    next_base = None
    if base_order is not None:
        # Tc.pw counts duplicate IDs before the current-round insertion.
        # SX.n/feq.b insert into the base list at slot minus that count.
        if (
            getattr(preview, "native_timeline_policy", None) != "feq"
            or len(base_order) != len(set(base_order))
            or set(base_order) != set(preview.order)
        ):
            raise ValueError("Missing native extra-turn base timeline authority")
        next_base = list(base_order)
        if 114 not in registration.fight_properties:
            slot = list(new_order).index(actor.id)
            prefix = preview.order[:slot]
            base_slot = slot - (len(prefix) - len(set(prefix)))
            next_base.insert(base_slot, actor.id)
    row = dict(vars(registration))
    row["authority"] = dict(vars(metadata))
    records = getattr(preview, "native_summon_registrations", {})
    if actor.id in records:
        raise ValueError("Duplicate summon registration")
    return PreparedSummonRegistration(
        authority,
        preview,
        actor,
        registration,
        row,
        records,
        next_base,
        tuple(new_order),
        new_turn_index,
    )


def register_summon(
    authority, fight, actor, registration, *, new_order, new_turn_index
):
    plan = prepare_registration(
        authority,
        fight,
        actor,
        registration,
        new_order=new_order,
        new_turn_index=new_turn_index,
    )
    return plan.publish()


@dataclass(frozen=True)
class PreparedSummonRetirements:
    fight: object
    preview: object
    retired: tuple

    def publish(self):
        fight, preview = self.fight, self.preview
        for name in (
            "native_qi_slots",
            "native_qi_touched_cells",
            "native_qi_byte_topology",
            "native_global_pv_collections",
        ):
            setattr(fight, name, getattr(preview, name))
        for name in (
            "native_captured_rosters",
            "native_captured_roster_updates",
            "native_captured_descriptor_actor_ids",
        ):
            if hasattr(preview, name):
                setattr(fight, name, getattr(preview, name))
        fight.native_summon_retirements = preview.native_summon_retirements
        if hasattr(fight, "native_pointer_checkpoint"):
            fight.native_pointer_checkpoint.commit_topology_from(
                preview.native_pointer_checkpoint, fight
            )
        for actor_id in self.retired:
            fight.actors[actor_id].native_obstacle_id = -1
        fight.events, fight.sequence = preview.events, preview.sequence
        return self.retired


def prepare_retirements(fight):
    from .combat_summon_retirement import (
        retired_summon_ids,
        _registration,
        _ko_current,
        _retire_one,
    )
    from .combat_global_pv_collections import global_fighter_guards

    registrations = getattr(fight, "native_summon_registrations", {})
    if not isinstance(registrations, dict):
        raise ValueError("Malformed native summon registration checkpoint")
    if not registrations:
        return None
    from .combat_pve_departure import retired_pve_actor_ids

    # Withdrawal already certified native QI/fdy removal. Its retained summon
    # registration is history, not a new ordinary-death settlement candidate.
    existing = retired_summon_ids(fight) | retired_pve_actor_ids(fight)
    candidates = []
    for actor_id in registrations:
        if actor_id in existing:
            continue
        actor = fight.actors.get(actor_id)
        if actor is None:
            raise ValueError("Registered summon actor is missing at death settlement")
        if actor.hp > 0:
            continue
        if global_fighter_guards(fight, actor_id) == dict(
            baF=True, baG=False, baK=False
        ):
            continue
        _registration(fight, actor_id)
        if _ko_current(actor) == 0:
            candidates.append(actor_id)
    if not candidates:
        return None
    if getattr(fight, "_resolution_depth", 0) != 0:
        raise ValueError("Summon retirement cannot run inside a nested effect chain")
    preview = deepcopy(fight)
    retired = tuple(
        actor_id for actor_id in candidates if _retire_one(preview, actor_id)
    )
    return PreparedSummonRetirements(fight, preview, retired) if retired else None


def settle_summons(fight):
    plan = prepare_retirements(fight)
    return () if plan is None else plan.publish()
