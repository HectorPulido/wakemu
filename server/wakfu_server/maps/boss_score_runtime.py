"""Transaction-preview staging for the explicit local boss survival policy."""
from copy import deepcopy
from . import boss_score


def install(fight, snapshot):
    if snapshot is None:
        return
    initial_active = (
        fight.phase == "active"
        and fight.turn_id == 1
        and not getattr(fight, "native_start_event_delivered", False)
        and not getattr(fight, "native_turn_event_deliveries", {})
        and not getattr(fight, "boss_score_events", {})
    )
    if (fight.phase != "placement" and not initial_active) or snapshot.get(
        "policy"
    ) != boss_score.POLICY:
        raise ValueError("Boss score must be installed before publication")
    fight.boss_score_profile = deepcopy(snapshot)
    fight.boss_score_events = {}


def stage_damage(fight, *, action_id, runner_uid, source, target, result):
    profile = getattr(fight, "boss_score_profile", None)
    if profile is None or str(target.id) not in profile["bosses"]:
        return
    if source.team != profile["player_team"] or target.team == source.team:
        return
    owner = source.id
    registered = False
    scene_helper = None
    if (
        owner not in profile["player_ids"]
        and profile.get("scene_helper_score_scope") is not None
    ):
        from wakfu_server.combat_encounter_scene_helpers import (
            helper_score_owner_receipt,
        )

        scene_helper = helper_score_owner_receipt(fight, source)
        if scene_helper is not None:
            owner = scene_helper["owner_actor_id"]
            boss_score.validate_scene_helper_score_proof(
                profile, fight.id, source.id, owner, scene_helper
            )
    visited = set()
    while owner not in profile["player_ids"]:
        if owner in visited:
            return
        visited.add(owner)
        actor = fight.actors.get(owner)
        row = getattr(fight, "native_summon_registrations", {}).get(owner)
        provenance = getattr(actor, "native_summon_source", None)
        if (
            actor is None
            or not isinstance(row, dict)
            or row.get("retired")
            or row.get("actor_id") != owner
            or not isinstance(provenance, dict)
            or provenance.get("native_relation_source")
            != "big.new_bje.fdt_initial_registration"
            or provenance.get("caster_id") != row.get("caster_id")
            or actor.team != profile["player_team"]
        ):
            return
        owner = row["caster_id"]
        registered = True
    round_number = getattr(fight, "native_timeline_round", 0)
    if not 1 <= round_number <= profile["round_limit"]:
        return
    event = dict(
        event_id=f"{action_id}:{runner_uid}:{target.id}",
        source_id=source.id,
        target_id=target.id,
        owner_actor_id=owner,
        post_mitigation_damage=result["hp_requested"] + result["virtual_hp_absorbed"],
        armor_absorbed=result["armor_absorbed"],
        round_number=round_number,
        source_is_registered_summon=registered,
    )
    if scene_helper is not None:
        event["source_scene_helper"] = scene_helper
    events = fight.boss_score_events
    previous = events.get(event["event_id"])
    if previous is not None and previous != event:
        raise ValueError("Boss score staged event changed")
    events[event["event_id"]] = event


def persist(db, fight):
    """Checkpoint transaction and receipts commit or roll back together."""
    if getattr(fight, "boss_score_profile", None) is None:
        return
    boss_score.freeze_snapshot(db, fight.id, fight.boss_score_profile)
    for event in fight.boss_score_events.values():
        boss_score.record_damage(db, fight.id, **event)


def finish_survival(fight):
    profile = getattr(fight, "boss_score_profile", None)
    objective = getattr(fight, "native_encounter_objective_policy", None)
    if objective is not None:
        from wakfu_server.combat_encounter_objective_policy import (
            require_admitted_policy,
        )

        require_admitted_policy(objective)
        return False  # Its earned native objective owns the terminal boundary.
    from wakfu_server.combat_boss_score_policy import OGREST_SCORE, native_score_policy

    if native_score_policy(profile) is not None:
        return False  # Reviewed native terminal callbacks own these encounters.
    if profile is not None and any(
        row.get("reference") == OGREST_SCORE.reference
        for row in profile.get("bosses", {}).values()
    ):
        # An older profile without the owned exit director has no authority to
        # replace Ogrest's actual final-cell producer with survival alone.
        return False
    if profile is None or fight.native_timeline_round <= profile["round_limit"]:
        return False
    alive = any(
        identity in fight.actors and fight._in_play(fight.actors[identity])
        for identity in profile["player_ids"]
    )
    fight.phase = "finished"
    fight.winner = profile["player_team"] if alive else 1 - profile["player_team"]
    fight._event("finished", winner=fight.winner, reason="local_boss_round_budget")
    return True


def staged_score(fight):
    """Sum the same validated per-runner receipts persisted by this module."""
    profile = fight.boss_score_profile
    total = 0
    for key, event in fight.boss_score_events.items():
        if (
            key != event["event_id"]
            or str(event["target_id"]) not in profile["bosses"]
            or event["owner_actor_id"] not in profile["player_ids"]
            or type(event["round_number"]) is not int
            or not 1 <= event["round_number"] <= profile["round_limit"]
            or (
                event["source_id"] != event["owner_actor_id"]
                and event["source_is_registered_summon"] is not True
                and event.get("source_scene_helper") is None
            )
        ):
            raise ValueError("Staged boss score receipt changed ownership")
        if event.get("source_scene_helper") is not None:
            boss_score.validate_scene_helper_score_proof(
                profile,
                fight.id,
                event["source_id"],
                event["owner_actor_id"],
                event["source_scene_helper"],
            )
        amounts = (event["post_mitigation_damage"], event["armor_absorbed"])
        if any(type(amount) is not int or amount < 0 for amount in amounts):
            raise ValueError("Invalid staged boss score damage")
        total += sum(amounts)
    return total


def finalize(db, fight):
    profile = getattr(fight, "boss_score_profile", None)
    if profile is None:
        return None
    persist(db, fight)
    survived = any(
        identity in fight.actors and fight._in_play(fight.actors[identity])
        for identity in profile["player_ids"]
    )
    terminal_authority = None
    from wakfu_server.combat_boss_score_policy import OGREST_SCORE, native_score_policy

    if native_score_policy(profile) == OGREST_SCORE:
        from wakfu_server.combat_ogrest_phase_controller import (
            ogrest_terminal_authority,
        )

        terminal_authority = ogrest_terminal_authority(fight)
    result = boss_score.finalize(
        db,
        fight.id,
        completed_rounds=max(0, fight.native_timeline_round - 1),
        survived=survived,
        winning_team=fight.winner,
        terminal_authority=terminal_authority,
        boss_defeated=all(
            int(identity) in fight.actors
            and fight.actors[int(identity)].hp <= 0
            and not getattr(fight.actors[int(identity)], "pve_withdrawn", False)
            for identity in profile["bosses"]
        ),
    )
    if getattr(fight, "native_encounter_objective_policy", None) is not None:
        from wakfu_server.combat_encounter_objective_facts import (
            enqueue_objective_results,
        )

        enqueue_objective_results(db, fight)
    return result
