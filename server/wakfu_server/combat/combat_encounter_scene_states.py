"""Reviewed encounter state authoring, distinct from native breed innates.

Declarations bind actual roster actors and immutable native state programs.
They grant no general permission to mutate raw cle or invent a caster.
"""
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json


def native_state_source_digest(catalog, reference):
    """Bind both the native state descriptor and its direct callback roots."""
    definition = catalog["states"].get(str(reference))
    if definition is None:
        raise ValueError("Missing native encounter state source")
    roots = {
        str(root): catalog["effects"][str(root)] for root in definition["effect_ids"]
    }
    return sha256(
        json.dumps(
            {"state": definition, "roots": roots},
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class SceneStatePlan:
    actor_id: int
    reference: int
    descriptor_level: int
    policy_id: str
    authority: str
    source_uri: str
    states: tuple
    source_digests: tuple
    repeat_roots: tuple


def prepare_scene_states(fight, monsters, declarations, *, catalog=None):
    """Preflight all declared states without actor, UID, or Qf writes."""
    if type(declarations) not in (list, tuple):
        raise ValueError("Missing explicit encounter scene declarations")
    if not declarations:
        return ()
    if getattr(fight, "native_encounter_scene_state_receipts", {}):
        raise ValueError("Encounter scene state constructor was already consumed")
    if catalog is None:
        from .combat_server_spell import states_catalog

        catalog = states_catalog()
    from .combat_summon_initial_states import NativeSummonInitialState
    from .combat_definitions import state_profile

    result, identities = [], set()
    for row in declarations:
        if type(row) is not dict:
            raise ValueError("Malformed encounter scene declaration")
        identity = row.get("actor_id")
        actor = fight.actors.get(identity) if type(identity) is int else None
        monster = monsters.get(identity)
        if (
            actor is None
            or monster is None
            or identity in identities
            or type(row.get("ref")) is not int
            or row["ref"] != monster["ref"]
            or row.get("descriptor_level") != actor.effective_level
            or type(row.get("descriptor_level")) is not int
            or actor.controlled
        ):
            raise ValueError("Scene state requires an actual ordinary roster actor")
        for key in ("policy_id", "authority", "source_uri"):
            if type(row.get(key)) is not str or not row[key].strip():
                raise ValueError("Missing reviewed encounter scene provenance")
        rows = row.get("states")
        if type(rows) not in (tuple, list) or not rows:
            raise ValueError("Missing encounter scene states")
        states, digests, repeat_roots, seen = [], [], [], set()
        for state in rows:
            if type(state) is not dict:
                raise ValueError("Malformed encounter scene state")
            reference, level = state.get("state_id"), state.get("level")
            if (
                type(reference) is not int
                or reference <= 0
                or reference in seen
                or type(level) is not int
                or not 0 <= level <= 32767
                or type(state.get("protected")) is not bool
            ):
                raise ValueError("Malformed encounter scene state values")
            digest = native_state_source_digest(catalog, reference)
            if state.get("source_sha256") != digest:
                raise ValueError("Encounter scene state program source changed")
            state_profile(catalog, reference, level)
            repeated = state.get("repeat_at_round_start", [])
            if (
                type(repeated) not in (list, tuple)
                or any(type(root) is not int for root in repeated)
                or len(set(repeated)) != len(repeated)
            ):
                raise ValueError("Malformed scene round listener roots")
            if repeated:
                from .combat_retained_runtime import native_retained_metadata

                metadata = native_retained_metadata()["effects"]
                for root in repeated:
                    effect = catalog["effects"].get(str(root), {})
                    native = metadata.get(str(root), {})
                    masks = effect.get("target_masks", ())
                    if (
                        root not in catalog["states"][str(reference)]["effect_ids"]
                        or len(masks) != 7
                        or 1003 not in (masks[5] or ())
                        or native.get("subscription") is not True
                        or native.get("event_global_subscription") is not True
                        or native.get("event_reverse_subscription") is not False
                        or native.get("event_caster_code") != 2
                        or native.get("event_target_code") != 2
                    ):
                        raise ValueError(
                            "Scene round listener lacks native global1003 source"
                        )
                repeat_roots.extend((reference, root) for root in repeated)
            states.append(
                NativeSummonInitialState(reference, level, state["protected"])
            )
            digests.append(digest)
            seen.add(reference)
        result.append(
            SceneStatePlan(
                identity,
                monster["ref"],
                actor.effective_level,
                row["policy_id"],
                row["authority"],
                row["source_uri"],
                tuple(states),
                tuple(digests),
                tuple(repeat_roots),
            )
        )
        identities.add(identity)
    return tuple(result)


def install_scene_states(fight, monsters, plans):
    """Install only in the caller-owned atomic fresh snapshot preview."""
    from .combat_npc_initialization import (
        _runtime,
        native_fresh_ordinary_instance_authority,
    )
    from .combat_summon_creation import native_fresh_summon_authority
    from .combat_summon_initialization import (
        detached_summon_scope,
        install_initial_states,
    )
    from .combat_native_death_status import initialize_fresh_bje_death_status

    receipts = dict(getattr(fight, "native_encounter_scene_state_receipts", {}))
    order = tuple(fight.actors)
    for plan in plans:
        actor = fight.actors[plan.actor_id]
        if plan.actor_id in receipts:
            raise ValueError("Encounter scene states already initialized")
        factory, _ = _runtime(monsters, actor.id)
        if actor.id not in getattr(fight, "native_npc_initialization_receipts", {}):
            initialize_fresh_bje_death_status(actor)
        base = native_fresh_summon_authority(actor, plan.reference)
        authority = replace(
            native_fresh_ordinary_instance_authority(base),
            is_summon=False,
            summon_root_id=actor.id,
            targeting=dict(
                base.targeting,
                bEe=42 not in actor.native_fight_properties,
                UNTARGETTABLE_BY_OTHER=21 in actor.native_fight_properties,
            ),
        )
        previous_uids = {entry.uid for entry in actor.state_ledger.entries}
        applications, team = [], actor.team
        del fight.actors[actor.id]
        actor.team = -1
        try:
            with detached_summon_scope(fight, actor, authority):
                install_initial_states(
                    fight,
                    actor,
                    plan.states,
                    runtime_factory=factory,
                    application_results=applications,
                )
            expected = [
                dict(state_id=p.state_id, level=p.level, applied=True)
                for p in plan.states
            ]
            if applications != expected:
                raise ValueError("Encounter scene state application rejected")
        finally:
            actor.team = team
            fight.actors[actor.id] = actor
            fight.actors = {key: fight.actors[key] for key in order}
        receipts[actor.id] = dict(
            kind="wakemu.reviewed_encounter_scene_states",
            actor_id=actor.id,
            ref=plan.reference,
            descriptor_level=plan.descriptor_level,
            policy_id=plan.policy_id,
            authority=plan.authority,
            source_uri=plan.source_uri,
            resolved_states=[asdict(state) for state in plan.states],
            source_digests=list(plan.source_digests),
            applications=applications,
            initialized=True,
            state_uids=[
                dict(state_id=entry.reference, uid=entry.uid)
                for entry in actor.state_ledger.entries
                if entry.uid not in previous_uids
            ],
            repeat_at_round_start=[
                dict(state_id=state, root=root) for state, root in plan.repeat_roots
            ],
        )
    fight.native_encounter_scene_state_receipts = receipts


def validates_scene_receipt(fight, actor_id):
    """Attest constructor-owned Qf for placement without asserting cle lineage."""
    receipt = getattr(fight, "native_encounter_scene_state_receipts", {}).get(actor_id)
    if receipt is None:
        return False
    actor = fight.actors.get(actor_id)
    if (
        actor is None
        or receipt.get("kind") != "wakemu.reviewed_encounter_scene_states"
        or receipt.get("actor_id") != actor_id
        or receipt.get("initialized") is not True
        or receipt.get("descriptor_level") != actor.effective_level
    ):
        raise ValueError("Missing encounter scene constructor proof")
    states = receipt.get("resolved_states")
    if (
        type(states) is not list
        or not states
        or len(receipt.get("source_digests", [])) != len(states)
        or any(
            type(receipt.get(k)) is not str or not receipt[k].strip()
            for k in ("policy_id", "authority", "source_uri")
        )
        or any(type(s) is not dict or s.get("native_rBr") is not True for s in states)
        or receipt.get("applications")
        != [
            dict(state_id=s["state_id"], level=s["level"], applied=True) for s in states
        ]
    ):
        raise ValueError("Incomplete encounter scene state applications")
    return True


def has_scene_round_interest(fight):
    """Constant source-receipt probe; no catalog/database work on other fights."""
    from .combat_npc_table_start_events import has_initial_table_interest
    from .combat_encounter_player_table_events import has_player_table_interest

    return (
        has_player_table_interest(fight)
        or has_initial_table_interest(fight)
        or any(
            row.get("repeat_at_round_start")
            for row in getattr(
                fight, "native_encounter_scene_state_receipts", {}
            ).values()
        )
    )


def deliver_scene_round_start(dispatcher, completed_receipt):
    """Reviewed global1003 producer after actual1004; Qf executes native bodies.

    Native roots and masks are original. Repeating their start-table delivery
    here is explicitly Wakemu scene policy, not a recovered server publisher.
    """
    from .combat_event_replay import NativeExternalEvent

    fight = dispatcher.native_retention.fight
    if not has_scene_round_interest(fight):
        return ()
    table = fight.native_timeline_round
    if (
        fight.phase != "active"
        or type(table) is not int
        or table < 2
        or fight.native_table_turn != table
        or completed_receipt.get("completed_round") != table - 1
        or completed_receipt.get("delivered") is not True
    ):
        raise ValueError("Scene table start requires actual completed round delivery")
    journal = getattr(fight, "native_encounter_scene_round_starts", {})
    key = str(table)
    if key in journal:
        return ()
    entries = tuple(dispatcher.native_retention.view().entries)
    deliveries = []
    for identity, receipt in getattr(
        fight, "native_encounter_scene_state_receipts", {}
    ).items():
        roots = receipt.get("repeat_at_round_start", ())
        if not roots:
            continue
        validates_scene_receipt(fight, identity)
        actor = fight.actors[identity]
        if actor.hp <= 0:
            continue
        initialized = {
            row["uid"]: row["state_id"] for row in receipt.get("state_uids", ())
        }
        carriers = {
            entry.uid: entry.reference
            for entry in actor.state_ledger.entries
            if initialized.get(entry.uid) == entry.reference
            and entry.target_id == identity
        }
        selected = set()
        for entry in entries:
            if entry.manager_id != identity:
                continue
            declaration = next(
                (r for r in roots if r["root"] == entry.generic_effect), None
            )
            if declaration is None:
                continue
            retained = getattr(fight, "native_owned_group_effects", {}).get(
                entry.uid, {}
            )
            state_uid = retained.get("invocation", {}).get("state_uid")
            if carriers.get(state_uid) != declaration["state_id"]:
                raise ValueError(
                    "Scene round listener lost its actual installed state UID"
                )
            selected.add(entry.uid)
        deliveries.append(dict(actor_id=identity, eligible_uids=sorted(selected)))
    from .combat_npc_table_start_events import initial_table_deliveries

    deliveries.extend(initial_table_deliveries(dispatcher))
    from .combat_encounter_player_table_events import player_table_deliveries

    deliveries.extend(player_table_deliveries(dispatcher))
    record = dict(
        completed_round=table - 1,
        table_turn=table,
        deliveries=deliveries,
        policy="wakemu.reviewed-scene-native-table-start-v1",
    )
    fight.native_encounter_scene_round_starts = {**journal, key: record}
    outcomes = []
    for delivery in deliveries:
        if delivery["eligible_uids"]:
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(delivery["actor_id"], (1003,), 61),
                    authority=dispatcher.native_clone_authority,
                    eligible_uids=frozenset(delivery["eligible_uids"]),
                )
            )
    return tuple(outcomes)
