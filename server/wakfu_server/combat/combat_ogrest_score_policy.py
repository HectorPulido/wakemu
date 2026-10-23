"""Ogrest score ownership; victory uses the earned native final exit cell.

The reviewed community guide permits zero-score victory; item eligibility
starts at one million. No success marker or synthetic boss death is supplied.
"""
from copy import deepcopy
from .combat_boss_score_policy import OGREST_SCORE


def install_ogrest_score_profile(dispatcher, context):
    from wakfu_server.maps import boss_score
    from .combat_companions import registered_companion_ids
    from .combat_terminal_metadata import registered_summon_actor_ids

    fight = dispatcher.native_retention.fight
    if (
        context is not getattr(fight, "native_ogrest_phase_context", None)
        or context.get("policy") != OGREST_SCORE.name
        or fight.phase != "active"
        or fight.turn_id != 1
        or fight.native_start_event_delivered is not True
    ):
        raise ValueError("Ogrest score lacks its completed owned director opening")
    boss = fight.actors[context["boss_id"]]
    dependants = registered_companion_ids(fight) | registered_summon_actor_ids(fight)
    players = sorted(
        identity
        for identity, actor in fight.actors.items()
        if actor.controlled and identity not in dependants and actor.team != boss.team
    )
    if not players or any(
        fight.actors[identity].team != fight.actors[players[0]].team
        for identity in players
    ):
        raise ValueError("Ogrest score requires one actual owned player team")
    previous = getattr(fight, "boss_score_profile", None)
    events = getattr(fight, "boss_score_events", {})
    if not isinstance(events, dict) or events:
        raise ValueError("Ogrest score must be frozen before damage")
    if previous is not None and (
        previous.get("policy") != boss_score.POLICY
        or previous.get("player_ids") != players
        or previous.get("player_team") != fight.actors[players[0]].team
        or set(previous.get("bosses", {})) != {str(boss.id)}
        or previous["bosses"][str(boss.id)].get("reference") != OGREST_SCORE.reference
        or previous.get("encounter_controller") not in (None, OGREST_SCORE.name)
        or previous.get("round_limit") not in (18, 20)
    ):
        raise ValueError("Ogrest score ownership differs from its actual director")
    profile = deepcopy(previous) if previous is not None else {}
    profile.update(
        policy=boss_score.POLICY,
        encounter_controller=OGREST_SCORE.name,
        bosses={
            str(boss.id): dict(
                reference=OGREST_SCORE.reference,
                round_limit=18,
                allow_early_boss_defeat=False,
            )
        },
        player_ids=players,
        player_team=fight.actors[players[0]].team,
        round_limit=18,
        minimum_score=0,
        loot_minimum_score=1000000,
        terminal_table_limit=20,
        terminal_source=OGREST_SCORE.terminal_source,
        includes_armor=True,
        includes_owned_summons=True,
        allow_early_boss_defeat=False,
    )
    fight.boss_score_profile = profile
    if not hasattr(fight, "boss_score_events"):
        fight.boss_score_events = {}
    return profile
