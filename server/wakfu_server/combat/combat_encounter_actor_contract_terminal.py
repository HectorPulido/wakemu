"""Qualified scene terminal intents composed with real native934 retirement.

This module never lowers HP, invents death, or ignores actors during victory.
The executor must perform the declared native operation on the private preview;
the actual native retirement receipt, QI and participation are checked afterward.
"""
from copy import deepcopy
from collections.abc import Mapping
from dataclasses import dataclass

from .combat_encounter_actor_contract import (
    _digest,
    actor_contract_admission_digest,
    actor_role_spec,
    contract_from_record,
    validate_actor_bindings,
)


@dataclass(frozen=True)
class NativeSceneRetirementExecution:
    actor_id: int
    effect_reference: int
    running_uid: int
    packets: tuple


@dataclass(frozen=True)
class ActorTerminalPlan:
    candidate: object
    packets: tuple
    admission_digest: str
    terminal_key: str
    retired_actor_ids: tuple[int, ...]


def _qualified_terminal_intent(fight, intent):
    from .combat_encounter_objective import verify_scene_terminal_intent

    return verify_scene_terminal_intent(fight, intent)


def _scope(fight, intent):
    receipt = _qualified_terminal_intent(fight, intent)
    digest = actor_contract_admission_digest(fight)
    record = fight.native_encounter_actor_contract
    spec = contract_from_record(record["declaration"])
    if (
        receipt.policy not in spec.terminal_policies
        or receipt.scene_contract_policy != spec.policy
        or receipt.admission_digest != digest
        or receipt.fight_id != fight.id
        or receipt.map_id != spec.map_id
        or receipt.catalog_revision != spec.catalog_revision
        or receipt.result != "success"
    ):
        raise ValueError("Terminal intent is outside the admitted actor contract")
    return receipt, digest


def _preserved(actor):
    """Resources/protections are facts, not a terminal-retirement cost."""
    return deepcopy(
        dict(
            hp=actor.hp,
            max_hp=actor.max_hp,
            hp_minimum=(getattr(actor, "effect_minima", None) or {}).get(1),
            hp_frozen=(
                1 in actor.effect_frozen if actor.effect_frozen is not None else None
            ),
            owner_id=actor.owner_id,
            controlled=actor.controlled,
        )
    )


def execute_actor_terminal(candidate, intent, *, retirement_executor):
    """Execute on a caller-owned detached transaction, never a live shared FSM.

    For an atomic public preparation API use prepare_actor_terminal. Each role
    is explicitly selected by its admitted contract; a living unrelated actor,
    an unbound same-breed actor or a protected player cannot be swept up.
    """
    receipt, digest = _scope(candidate, intent)
    validate_actor_bindings(candidate)
    record = candidate.native_encounter_actor_contract
    key = _digest(receipt.to_record())
    prior = record["terminal_receipts"].get(key)
    if prior is not None:
        if (
            prior.get("admission_digest") != digest
            or prior.get("intent") != receipt.to_record()
        ):
            raise ValueError("Consumed actor terminal receipt changed")
        from .combat_forced_retirement import retired_forced_fighter_ids

        if not set(prior["retired_actor_ids"]) <= retired_forced_fighter_ids(candidate):
            raise ValueError("Consumed terminal lost its native retirement history")
        return (), tuple(prior["retired_actor_ids"]), key
    spec = contract_from_record(record["declaration"])
    roles = [role for role in spec.roles if role.retire_on_success]
    if roles and not callable(retirement_executor):
        raise ValueError("Scene terminal requires its native934 executor")
    from .combat_global_pv_collections import global_fighter_guards
    from .combat_controller_registry import _row
    from .combat_qi_fight import current_registry
    from .combat_forced_retirement import retired_forced_fighter_ids
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    before = {
        identity: _preserved(actor) for identity, actor in candidate.actors.items()
    }
    previously_retired = retired_forced_fighter_ids(candidate)
    targets = []
    for role in roles:
        binding = record["bindings"].get(role.role)
        if binding is None:
            raise ValueError("Terminal actor role has no authenticated birth binding")
        actor = candidate.actors[binding["actor_id"]]
        if role.constructor == "ordinary_npc" and (
            actor.controlled or actor.owner_id is not None
        ):
            raise ValueError("Actor terminal cannot dismiss an original player actor")
        if role.minimum_hp is not None and (
            not isinstance(actor.effect_minima, dict)
            or actor.effect_minima.get(1) != role.minimum_hp
        ):
            raise ValueError("Terminal actor native HP minimum changed")
        if global_fighter_guards(candidate, actor.id) != dict(
            baF=True, baG=False, baK=False
        ):
            raise ValueError("Terminal role is not the original live scene actor")
        targets.append((role, binding, actor.id))
    if targets and candidate.phase != "active":
        raise ValueError(
            "Living actor retirement requires an active native transaction"
        )
    # Native callback bodies, areas and QI may mutate synchronously. The outer
    # resolution settles only after the complete declared terminal population.
    packets, retired = [], []
    used_uids = {
        row["uid"]
        for row in getattr(candidate, "native_forced_retirements", {}).values()
    }
    with candidate.effect_resolution():
        for role, binding, identity in targets:
            result = retirement_executor(candidate, role, deepcopy(binding), receipt)
            if (
                type(result) is not NativeSceneRetirementExecution
                or result.actor_id != identity
                or result.effect_reference != role.retirement_effect_reference
                or type(result.running_uid) is not int
                or result.running_uid <= 0
                or result.running_uid in used_uids
                or type(result.packets) is not tuple
                or not any(opcode == 13497 for opcode, _ in result.packets)
                or any(
                    type(opcode) is not int or not isinstance(body, bytes)
                    for opcode, body in result.packets
                )
            ):
                raise ValueError("Scene executor lacks actual native934 delivery")
            used_uids.add(result.running_uid)
            actor = candidate.actors[identity]
            native = getattr(candidate, "native_forced_retirements", {}).get(
                str(identity)
            )
            if (
                identity not in retired_forced_fighter_ids(candidate)
                or not isinstance(native, dict)
                or native.get("uid") != result.running_uid
                or native.get("hp_before") != before[identity]["hp"]
                or native.get("hp_after") != before[identity]["hp"]
                or actor.native_obstacle_id != -1
                or global_fighter_guards(candidate, identity)
                != dict(baF=False, baG=False, baK=True)
                or _row(candidate, identity)["current_controller"]
                != _row(candidate, identity)["original_controller"]
            ):
                raise ValueError(
                    "Scene retirement lacks actual native participation/QI history"
                )
            if _preserved(actor) != before[identity]:
                raise ValueError("Scene retirement changed protected actor resources")
            current_registry(candidate)
            if identity not in hidden_snapshot_actor_ids(candidate):
                raise ValueError("Retired scene actor would reappear on reconnect")
            packets.extend(result.packets)
            retired.append(identity)
    if any(identity in candidate.order for identity in retired):
        raise ValueError("Retired scene actor remains in the actual timeline")
    # Native Qs/Qf cleanup may legitimately heal or damage another actor. It
    # must not dismiss a different role or rewrite original player ownership.
    expected = set(retired)
    if retired_forced_fighter_ids(candidate) - previously_retired != expected:
        raise ValueError("Scene executor retired an actor outside its bound roles")
    for identity, snapshot in before.items():
        actor = candidate.actors[identity]
        if (
            actor.owner_id != snapshot["owner_id"]
            or actor.controlled is not snapshot["controlled"]
        ):
            raise ValueError("Scene executor changed original actor ownership")
    validate_actor_bindings(candidate)
    record["terminal_receipts"] = dict(
        record["terminal_receipts"],
        **{
            key: dict(
                admission_digest=digest,
                intent=receipt.to_record(),
                retired_actor_ids=retired,
            )
        }
    )
    return tuple(packets), tuple(retired), key


def prepare_actor_terminal(fight, intent, *, retirement_executor):
    """Prepare all terminal mutations privately; errors leave the source intact.

    The existing shared combat transaction owns publication/adoption of this
    candidate and its packets. No independent world mutation or network send is
    performed here. A native executor must bind its runtime to the candidate.
    """
    _scope(fight, intent)
    candidate = deepcopy(fight)
    packets, retired, key = execute_actor_terminal(
        candidate, intent, retirement_executor=retirement_executor
    )
    return ActorTerminalPlan(
        candidate, packets, actor_contract_admission_digest(candidate), key, retired
    )


def deliver_actor_objective_cleanup(dispatcher, intent):
    """Compose an earned objective with actual native934 on its existing preview.

    The existing dispatcher owns outbox delivery; returned actor IDs are only
    a result, never packets to append a second time. No policy is selected from
    a monster reference and no unknown scene becomes active through this hook.
    """
    fight = dispatcher.native_retention.fight
    if (
        intent is None
        or getattr(fight, "native_encounter_actor_contract", None) is None
    ):
        return ()

    def execute(candidate, role, binding, receipt):
        if candidate is not dispatcher.native_retention.fight:
            raise ValueError("Scene retirement dispatcher belongs to another preview")
        effect = dispatcher.effects.get(str(role.retirement_effect_reference))
        if (
            not isinstance(effect, Mapping)
            or effect.get("effect_class") != 934
            or effect.get("parameter_count") != 0
            or effect.get("parameters") != []
            or effect.get("children")
        ):
            raise ValueError(
                "Scene retirement needs its exact native934 leaf descriptor"
            )
        if role.retirement_caster_role == "boundary_actor":
            caster_id = receipt.boundary_actor_id
        elif role.retirement_caster_role == "boss":
            caster_id = receipt.boss_actor_id
        else:
            caster_binding = candidate.native_encounter_actor_contract["bindings"].get(
                role.retirement_caster_role[5:]
            )
            if caster_binding is None:
                raise ValueError("Native scene retirement caster was not bound")
            caster_id = caster_binding["actor_id"]
        caster = candidate.actors.get(caster_id)
        target = candidate.actors[binding["actor_id"]]
        if caster is None:
            raise ValueError("Native scene retirement has no actual caster")
        packets = dispatcher.native_retention.packets
        offset = len(packets)
        from .combat_effect_dispatch import EffectInvocation

        dispatcher.execute(
            EffectInvocation(
                role.retirement_effect_reference,
                caster.effective_level,
                caster.id,
                target.id,
                target.position,
                native_retained_container={"present": False},
            )
        )
        native = getattr(candidate, "native_forced_retirements", {}).get(str(target.id))
        if not isinstance(native, dict):
            raise ValueError(
                "Original native934 branch did not retire its declared actor"
            )
        return NativeSceneRetirementExecution(
            target.id,
            role.retirement_effect_reference,
            native["uid"],
            tuple(packets[offset:]),
        )

    _, identities, _ = execute_actor_terminal(
        fight, intent, retirement_executor=execute
    )
    return identities
