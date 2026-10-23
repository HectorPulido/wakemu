"""Explicit reconstructed Rushu score authority over real damage receipts.

The observed encounter has twenty turns and a three-million minimum. Native
7110 and the original21/start success/failure branches remain unchanged.
"""
from copy import deepcopy

CONTROLLER = "wakemu-rushu-score-v1"
REFERENCE = 5306
CONSTRUCTOR_STATE = 7000
MINIMUM_SCORE = 3000000
ROUND_LIMIT = 20


def install_rushu_score_profile(dispatcher):
    """Publish/upgrade the actual participant-bound profile after native1003.

    Production may already have frozen the generic durable boss score profile.
    Preserve its ownership and staged events; add only the explicit encounter
    result policy so generic survival cannot preempt native21/start.
    """
    fight = dispatcher.native_retention.fight
    receipts = getattr(fight, "native_npc_initialization_receipts", {})
    bosses = [
        identity
        for identity, row in receipts.items()
        if row.get("ref") == REFERENCE and row.get("initialized") is True
    ]
    if not bosses:
        return False
    if (
        len(bosses) != 1
        or fight.phase != "active"
        or fight.turn_id != 1
        or getattr(fight, "native_start_event_delivered", False) is not True
    ):
        raise ValueError("Rushu score requires its actual completed native opening")
    boss = fight.actors[bosses[0]]
    if boss.controlled or not any(
        item.get("state_id") == CONSTRUCTOR_STATE
        for item in receipts[boss.id].get("resolved_states", ())
    ):
        raise ValueError("Rushu score lacks its original constructor state")
    from .combat_companions import registered_companion_ids
    from .combat_terminal_metadata import registered_summon_actor_ids
    from wakfu_server.maps import boss_score

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
        raise ValueError("Rushu score requires one actual owned player team")
    team = fight.actors[players[0]].team
    previous = getattr(fight, "boss_score_profile", None)
    if previous is None:
        profile = dict(
            policy=boss_score.POLICY,
            bosses={
                str(boss.id): dict(
                    reference=REFERENCE,
                    round_limit=ROUND_LIMIT,
                    allow_early_boss_defeat=False,
                )
            },
            player_ids=players,
            player_team=team,
            round_limit=ROUND_LIMIT,
            includes_armor=True,
            includes_owned_summons=True,
            allow_early_boss_defeat=False,
        )
    else:
        profile = deepcopy(previous)
        if (
            profile.get("policy") != boss_score.POLICY
            or profile.get("round_limit") != ROUND_LIMIT
            or profile.get("player_ids") != players
            or profile.get("player_team") != team
            or set(profile.get("bosses", {})) != {str(boss.id)}
            or profile["bosses"][str(boss.id)].get("reference") != REFERENCE
            or profile["bosses"][str(boss.id)].get("round_limit") != ROUND_LIMIT
            or profile.get("allow_early_boss_defeat", False) is not False
            or profile["bosses"][str(boss.id)].get("allow_early_boss_defeat", False)
            is not False
            or profile.get("includes_armor") is not True
            or profile.get("includes_owned_summons") is not True
            or profile.get("encounter_controller") not in (None, CONTROLLER)
        ):
            raise ValueError(
                "Rushu score profile differs from actual encounter ownership"
            )
    events = getattr(fight, "boss_score_events", {})
    if not isinstance(events, dict) or events:
        raise ValueError("Rushu score must be frozen before any damage")
    profile.update(encounter_controller=CONTROLLER, minimum_score=MINIMUM_SCORE)
    from .combat_boss_party_level_policy import (
        LEVEL_FIELDS,
        freeze_level_profile,
        validate_level_profile,
    )

    if LEVEL_FIELDS.intersection(profile):
        validate_level_profile(profile)
    else:
        profile.update(freeze_level_profile(profile, fight.actors))
    if profile == previous:
        return False
    fight.boss_score_profile = profile
    # Existing staging belongs to the accepted opening; do not reset a profile
    # or replace its event dictionary during a generic encounter upgrade.
    if not hasattr(fight, "boss_score_events"):
        fight.boss_score_events = {}
    return True
