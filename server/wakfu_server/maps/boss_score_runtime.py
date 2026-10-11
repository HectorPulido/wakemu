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


def finalize(db, fight):
    profile = getattr(fight, "boss_score_profile", None)
    if profile is None:
        return None
    persist(db, fight)
    survived = any(
        identity in fight.actors and fight._in_play(fight.actors[identity])
        for identity in profile["player_ids"]
    )
    return boss_score.finalize(
        db,
        fight.id,
        completed_rounds=max(0, fight.native_timeline_round - 1),
        survived=survived,
        winning_team=fight.winner,
        boss_defeated=all(
            int(identity) in fight.actors
            and fight.actors[int(identity)].hp <= 0
            and not getattr(fight.actors[int(identity)], "pve_withdrawn", False)
            for identity in profile["bosses"]
        ),
    )
