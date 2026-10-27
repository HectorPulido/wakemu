"""Earned Abomination firecracker scene, explicitly reconstructed by Wakemu.

Original quest1714/objective3248, scenario1657 hooks13276/13348 and native
state2492/book2887 are source-attested. The original server callback is absent;
this policy binds that transition to the authenticated actual fight admission.
Ordinary spawns, compass locations and client-supplied quest claims grant none.
"""
from copy import deepcopy

from .combat_quest_scene_authority import (
    authenticated_quest_fact,
    canonical_digest,
)

POLICY = "wakemu.abomination.earned_firecracker.v1"
ACTIVATION = "(IsAfter(17,02,2026,10,00,00) and IsBefore(10,03,2026,10,00,00))"
SOURCE_PATHS = (
    "native-class-morph-profiles.json",
    "native-class-morph933-effect-closure.json",
    "native-class-morph933-level-zero.json",
    "native-class-morph933-casting-roots.json",
)


def authorize_admission(
    store, db, fight, *, account_id, generation, character_id, monster_references
):
    """Freeze the real attack13276 admission under its caller's transaction.

    Only the authenticated challenger receives the book. A running native
    quest is not invented for ordinary monster fights or off-season admission.
    """
    if tuple(monster_references) != (2880,):
        return None
    if fight.phase != "placement" or character_id not in fight.actors:
        raise ValueError("Abomination admission requires actual placement actor")
    fact = authenticated_quest_fact(
        store,
        db,
        account_id=account_id,
        generation=generation,
        character_id=character_id,
        quest_id=1714,
        objective_id=3248,
        activation_criterion=ACTIVATION,
    )
    if fact is None:
        return None
    actor = fight.actors[character_id]
    if not actor.controlled or actor.owner_id != account_id:
        raise ValueError("Quest challenger lacks actual player ownership")
    row = db.execute(
        "SELECT map_id FROM characters WHERE id=%s AND account_id=%s",
        (character_id, account_id),
    ).fetchone()
    if row is None or type(row["map_id"]) is not int:
        raise ValueError("Missing actual quest scene map ownership")
    from wakfu_server import native_catalog
    from .combat_encounter_actor_contract import (
        ActorRoleSpec,
        EncounterActorContract,
        freeze_actor_contract,
    )

    contract = freeze_actor_contract(
        fight,
        EncounterActorContract(
            policy=POLICY,
            version=1,
            authority="authorized_wakemu_native_content_reconstruction",
            map_id=row["map_id"],
            initial_references=(2880,),
            catalog_revision=native_catalog.release(),
            source_paths=SOURCE_PATHS,
            roles=(ActorRoleSpec("boss", 2880, required_initial_states=(2490, 2491)),),
            terminal_policies=(POLICY,),
        ),
        map_id=row["map_id"],
        initial_references=(2880,),
    )
    source = dict(
        policy=POLICY,
        source_kind="wakemu_reconstructed_quest_interaction",
        original_server_callback="unrecovered",
        quest=fact.record(),
        scenario_id=1657,
        interaction_event_id=13276,
        fight_start_event_id=13348,
        fight_id=fight.id,
        participant_id=character_id,
        admission_digest=contract["admission_digest"],
        native_target_reference=2880,
        grant_state=2492,
        grant_effect=108637,
        morph_profile=2887,
    )
    receipt = dict(
        source=source,
        source_digest=canonical_digest(source),
        status="admitted",
        carrier_uid=None,
    )
    prior = getattr(fight, "native_abomination_quest_grant", None)
    if prior is not None:
        if prior != receipt:
            raise ValueError("Cannot replace an earned Abomination admission")
        return deepcopy(prior)
    fight.native_abomination_quest_grant = receipt
    return deepcopy(receipt)


def _receipt(fight):
    row = getattr(fight, "native_abomination_quest_grant", None)
    if row is None:
        return None
    from .combat_encounter_actor_contract import actor_contract_admission_digest

    if (
        not isinstance(row, dict)
        or set(row) != {"source", "source_digest", "status", "carrier_uid"}
        or row["source_digest"] != canonical_digest(row["source"])
        or row["source"].get("policy") != POLICY
        or row["source"].get("fight_id") != fight.id
        or row["source"].get("admission_digest")
        != actor_contract_admission_digest(fight)
        or row["status"] not in ("admitted", "granted", "cleaned")
    ):
        raise ValueError("Earned Abomination scene receipt changed")
    return row


def apply_start(fight, runtime_factory, packets):
    """Consume actual event13348 once using the unchanged native2492 handler."""
    receipt = _receipt(fight)
    if receipt is None or receipt["status"] != "admitted":
        return False
    if fight.phase != "active":
        raise ValueError("Earned firecracker grant requires actual fight start")
    from .combat_encounter_actor_contract import (
        bind_actor_role,
        validate_actor_bindings,
    )

    candidates = [
        actor.id
        for actor in fight.actors.values()
        if getattr(fight, "native_npc_initialization_receipts", {})
        .get(actor.id, {})
        .get("ref")
        == 2880
    ]
    if len(candidates) != 1:
        raise ValueError("Quest scene lacks its actual native Abomination birth")
    bind_actor_role(fight, "boss", candidates[0])
    validate_actor_bindings(fight)
    actor = fight.actors.get(receipt["source"]["participant_id"])
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != receipt["source"]["quest"]["account_id"]
    ):
        raise ValueError("Quest participant changed ownership before start")
    if any(entry.reference == 2492 for entry in actor.state_ledger.entries):
        raise ValueError("Quest firecracker state existed before its earned source")
    dispatcher, outbox = runtime_factory(
        fight, {"native_retained_container": {"present": False}}
    )
    handler, retention = dispatcher.native_state_handler, dispatcher.native_retention
    if handler.fight is not fight or retention.fight is not fight:
        raise ValueError("Quest state runtime changed transaction ownership")
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    profile = state_profile(handler.catalog, 2492, 1)
    if tuple(profile["effects"]) != (108637,):
        raise ValueError("Original demon hunter state roots changed")
    carrier = StateCarrierContext(
        profile["duration"],
        profile["realtime_duration"],
        False,
        None,
        None,
        False,
        False,
        False,
        0,
        native_time_payload(realtime_remaining=profile["realtime_duration"]),
    )
    # 2226 is the existing direct-carrier context convention used by class
    # and summon initialization, not an asserted original quest304 producer.
    # This calls apply_reference directly; only state2492 child108637 executes.
    if not retention.apply_state_reference(
        handler,
        EffectInvocation(2226, 1, actor.id, actor.id, actor.position),
        2492,
        1,
        carrier_context=carrier,
    ):
        raise ValueError("Earned native demon hunter state was not applied")
    entries = [entry for entry in actor.state_ledger.entries if entry.reference == 2492]
    if len(entries) != 1:
        raise ValueError("Earned demon hunter carrier identity is ambiguous")
    fight.native_abomination_quest_grant = dict(
        receipt,
        status="granted",
        carrier_uid=entries[0].uid,
    )
    packets.extend(outbox)
    return True


def cleanup(fight, runtime_factory, packets):
    """Remove only this earned carrier through native owned-effect cleanup."""
    receipt = _receipt(fight)
    if receipt is None or receipt["status"] != "granted":
        return False
    actor = fight.actors.get(receipt["source"]["participant_id"])
    if actor is None:
        raise ValueError("Quest cleanup lost its actual participant")
    uid = receipt["carrier_uid"]
    entries = [entry for entry in actor.state_ledger.entries if entry.uid == uid]
    if entries:
        if entries[0].reference != 2492:
            raise ValueError("Quest cleanup carrier identity changed")
        dispatcher, outbox = runtime_factory(
            fight, {"native_retained_container": {"present": False}}
        )
        retention = dispatcher.native_retention
        if retention.fight is not fight:
            raise ValueError("Quest cleanup changed runtime ownership")
        retention.removal(retention.view()).remove((uid,))
        packets.extend(outbox)
    fight.native_abomination_quest_grant = dict(receipt, status="cleaned")
    return True
