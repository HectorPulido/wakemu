"""Explicit reconstructed quest3797 duel: native loss is story continuation.

The original scene2307 hooks19114/19116/19123 are recovered. Its original
server map binding is not; this opt-in policy freezes the authenticated entry
map instead. Ordinary Aguabrial spawns never imply quest progress or victory.
"""
from copy import deepcopy
from .combat_quest_scene_authority import authenticated_quest_fact, canonical_digest

POLICY = "wakemu.aguabrial.earned_story_loss.v1"
SOURCE_PATHS = (
    "combat-state-definitions.json",
    "native-retained-effect-metadata.json",
    "native-npc-spell-effect-trees.json",
)


def authorize_aguabrial_scene(
    store, db, fight, *, account_id, generation, character_id, monster_references
):
    if tuple(monster_references) != (1723,):
        return None
    if fight.phase != "placement":
        raise ValueError("Aguabrial story requires actual placement admission")
    fact = authenticated_quest_fact(
        store,
        db,
        account_id=account_id,
        generation=generation,
        character_id=character_id,
        quest_id=3797,
        objective_id=7835,
        required_completed_objectives=(7834,),
    )
    if fact is None:
        return None
    actor = fight.actors.get(character_id)
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != account_id
        or getattr(actor, "pve_withdrawn", False)
    ):
        raise ValueError("Aguabrial challenger lacks actual player ownership")
    row = db.execute(
        "SELECT map_id FROM characters WHERE id=%s AND account_id=%s",
        (character_id, account_id),
    ).fetchone()
    if row is None or type(row["map_id"]) is not int:
        raise ValueError("Missing authenticated actual story entry map")
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
            initial_references=(1723,),
            catalog_revision=native_catalog.release(),
            source_paths=SOURCE_PATHS,
            roles=(ActorRoleSpec("boss", 1723, required_initial_states=(1128, 1137)),),
            terminal_policies=(POLICY,),
        ),
        map_id=row["map_id"],
        initial_references=(1723,),
    )
    source = dict(
        policy=POLICY,
        authority="explicit_source_backed_reconstruction",
        original_server_map="unrecovered",
        frozen_entry_map=row["map_id"],
        fight_id=fight.id,
        participant_id=character_id,
        participant_team=actor.team,
        quest=fact.record(),
        scenario_id=2307,
        fight_start_event=19114,
        story_ko_event=19116,
        story_exit_event=19123,
        lethal_effect=240347,
        admission_digest=contract["admission_digest"],
    )
    receipt = dict(source=source, source_digest=canonical_digest(source))
    existing = getattr(fight, "native_aguabrial_story_admission", None)
    if existing is not None and existing != receipt:
        raise ValueError("Cannot replace frozen Aguabrial story admission")
    fight.native_aguabrial_story_admission = receipt
    return deepcopy(receipt)


def story_admission(fight):
    receipt = getattr(fight, "native_aguabrial_story_admission", None)
    if receipt is None:
        return None
    from .combat_encounter_actor_contract import actor_contract_admission_digest

    if (
        not isinstance(receipt, dict)
        or set(receipt) != {"source", "source_digest"}
        or receipt["source_digest"] != canonical_digest(receipt["source"])
        or receipt["source"].get("policy") != POLICY
        or receipt["source"].get("fight_id") != fight.id
        or receipt["source"].get("admission_digest")
        != actor_contract_admission_digest(fight)
    ):
        raise ValueError("Frozen Aguabrial story admission changed")
    return receipt


def bind_aguabrial_start(fight):
    if story_admission(fight) is None:
        return False
    if fight.phase != "active":
        raise ValueError("Story birth requires actual native initialization")
    candidates = [
        identity
        for identity, row in getattr(
            fight, "native_npc_initialization_receipts", {}
        ).items()
        if row.get("ref") == 1723
    ]
    if len(candidates) != 1:
        raise ValueError("Aguabrial story native actor birth is ambiguous")
    from .combat_encounter_actor_contract import bind_actor_role

    bind_actor_role(fight, "boss", candidates[0])
    return True


def earned_story_continuation(fight):
    """Actual native240347 KO, never a loss flag or HP0 snapshot alone."""
    admission = story_admission(fight)
    if admission is None:
        return None
    from .combat_encounter_actor_contract import validate_actor_bindings

    bindings = validate_actor_bindings(fight)
    if "boss" not in bindings:
        raise ValueError("Story boss was not bound at its actual native birth")
    source = admission["source"]
    boss = fight.actors[bindings["boss"]["actor_id"]]
    actor = fight.actors.get(source["participant_id"])
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != source["quest"]["account_id"]
        or actor.team != source["participant_team"]
        or actor.team == boss.team
        or getattr(actor, "pve_withdrawn", False)
    ):
        return None
    from .combat_ordinary_death import registered_ordinary_death

    if actor.hp != 0 or not registered_ordinary_death(fight, actor):
        return None
    for index, event in enumerate(fight.events):
        if (
            event.get("kind") != "death"
            or event.get("actor_id") != actor.id
            or index == 0
        ):
            continue
        cause = fight.events[index - 1]
        if (
            cause.get("kind") != "kill_hp_minimum_update"
            or cause.get("effect_class") != 28
            or cause.get("generic_effect") != 240347
            or cause.get("source_id") != boss.id
            or cause.get("target_id") != actor.id
            or type(cause.get("uid")) is not int
            or cause["uid"] <= 0
            or type(cause.get("hp_before")) is not int
            or cause["hp_before"] <= 0
            or cause.get("hp") != 0
            or cause.get("minimum") != 0
        ):
            continue
        native = getattr(fight, "native_death_event_deliveries", {}).get(
            str(event.get("sequence"))
        )
        if (
            not isinstance(native, dict)
            or native.get("actor_id") != actor.id
            or native.get("policy") != "wakemu.owned-ko-and-death-v3"
            or native.get("event_id") != 1013
            or native.get("channel") != 6
        ):
            continue
        return dict(
            policy=POLICY,
            fight_id=fight.id,
            admission_digest=source["admission_digest"],
            participant_id=actor.id,
            account_id=actor.owner_id,
            boss_actor_id=boss.id,
            boss_reference=1723,
            death_sequence=event["sequence"],
            native_running_uid=cause["uid"],
            generic_effect=240347,
            scenario_id=2307,
            story_ko_event=19116,
            story_exit_event=19123,
            result="story_continuation_after_native_loss",
            combat_victory=False,
        )
    return None
