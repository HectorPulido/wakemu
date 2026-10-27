"""Earned Rift reward authority, independent from the actual winning team.

Only authenticated admitted native kills and non-withdrawn durable members
qualify. The configured rule is an explicit Wakemu override, not native math.
"""
import json
from psycopg.pq import TransactionStatus

POLICY = {
    "policy": "wakemu.rift.reached-wave-times-ten.v1",
    "version": 1,
    "wave_basis": "reached_wave",
    "multiplier_per_wave": 10,
    "outcomes": ["won", "lost"],
    "require_defeated_native_monsters": True,
    "withdrawals": "none",
}


def frozen_factor(db, run, result):
    """Freeze the configured reached-wave factor inside settlement, never on replay."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Earned Rift factor requires the settlement transaction")
    row = db.execute(
        "SELECT value FROM settings WHERE name='rift_earned_reward_policy'"
    ).fetchone()
    if (
        row is None
        or type(row["value"]) is not dict
        or json.dumps(row["value"], sort_keys=True)
        != json.dumps(POLICY, sort_keys=True)
    ):
        raise ValueError("Missing or unsupported earned Rift reward policy")
    wave = result.get("reached_wave")
    if (
        type(wave) is not int
        or not 1 <= wave <= 10000
        or wave != run["wave"]
        or result.get("outcome") not in ("won", "lost")
    ):
        raise ValueError("Earned Rift factor differs from actual terminal progress")
    return dict(
        policy=POLICY["policy"], version=1, reached_wave=wave, multiplier=wave * 10
    )


def defeated_sources(db, fight, run, *, rosters=None):
    """Validate original admitted enemies, including kills in the final partial wave."""
    from wakfu_server import combat_reward_context
    from wakfu_server.combat_encounter_roles import assigned_roles

    if rosters is None:
        from wakfu_server.rift_wave_bindings import rosters as bound_rosters

        rosters = bound_rosters(db, run, fight=fight)
    sources = getattr(fight, "rift_monsters", None)
    if not isinstance(sources, dict):
        raise ValueError("Rift reward lacks accumulated trusted native sources")
    bound = {}
    roles = assigned_roles(fight)
    from wakfu_server.rift_encounter_roles import roles_for_catalog

    expected_roles = roles_for_catalog(run["catalog"], run["policy"])
    if (roles.player_team, roles.npc_team) != (
        expected_roles.player_team,
        expected_roles.npc_team,
    ):
        raise ValueError("Rift reward source differs from its frozen encounter roles")
    for roster in rosters:
        ids, refs = roster["actor_ids"], roster["species_refs"]
        if not ids or len(ids) != len(refs):
            raise ValueError("Malformed durable rift reward roster")
        pairs = roster.get("actor_species_pairs")
        if pairs is None:
            raise ValueError(
                "Rift reward requires canonical actor/species associations"
            )
        if len(pairs) != len(ids) or {pair[0] for pair in pairs} != set(ids):
            raise ValueError("Rift reward association differs from admitted actors")
        for identity, ref in pairs:
            if (
                type(identity) is not int
                or identity >= 0
                or identity in bound
                or type(ref) is not int
                or ref <= 0
            ):
                raise ValueError("Invalid or duplicate durable rift enemy")
            bound[identity] = ref
    if set(sources) != set(bound):
        raise ValueError("Rift accumulated sources differ from admitted waves")
    killed = []
    for identity, reference in sorted(bound.items()):
        source, actor = sources[identity], fight.actors.get(identity)
        if (
            actor is None
            or actor.id != identity
            or actor.controlled
            or actor.team != roles.npc_team
            or combat_reward_context._summon(actor)
            or source.get("id") != identity
            or source.get("ref") != reference
            or source.get("instance_id") != run["instance_id"]
            or source.get("level") != actor.effective_level
        ):
            raise ValueError(
                "Rift original enemy differs from durable/native authority"
            )
        if actor.hp <= 0:
            killed.append(source)
    return tuple(killed)


def earned_recipients(db, fight, participants):
    """Build a narrow capability from the already locked durable settlement roster."""
    state = getattr(fight, "rift_wave_state", None)
    if state is None:
        return frozenset()
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Earned Rift recipients require a settlement transaction")
    if (
        type(state) is not dict
        or type(state.get("instance_id")) is not int
        or fight.phase != "finished"
    ):
        raise ValueError("Malformed terminal Rift identity")
    if state.get("outcome") in ("capacity_exhausted", "administrative_victory"):
        return frozenset()
    from wakfu_server.rift_runtime import _run
    from wakfu_server.rift_encounter_roles import roles_for_catalog
    from wakfu_server.combat_encounter_roles import assigned_roles
    from wakfu_server.combat_reward_context import _summon

    run = _run(db, state["instance_id"])
    roles = assigned_roles(fight)
    expected = roles_for_catalog(run["catalog"], run["policy"])
    if (
        run["fight_id"] != fight.id
        or run["status"] not in ("running", "won", "lost")
        or fight.winner not in (roles.player_team, roles.npc_team)
        or (roles.player_team, roles.npc_team)
        != (expected.player_team, expected.npc_team)
        or {row["character_id"] for row in participants} != set(run["members"])
    ):
        raise ValueError("Earned Rift settlement differs from its durable run")
    outcome = "won" if fight.winner == roles.player_team else "lost"
    if run["status"] != "running" and run["status"] != outcome:
        raise ValueError("Earned Rift terminal outcome changed")
    if not defeated_sources(db, fight, run):
        return frozenset()
    result = set()
    for row in participants:
        actor = fight.actors.get(row["character_id"])
        if (
            actor is None
            or not actor.controlled
            or _summon(actor)
            or actor.owner_id != row["account_id"]
            or actor.team != row["team"]
            or actor.team != roles.player_team
        ):
            raise ValueError("Earned Rift member differs from its actual participant")
        if row["withdrawn"] or getattr(actor, "pve_withdrawn", False):
            continue
        result.add((row["account_id"], row["session_generation"], row["character_id"]))
    return frozenset(result)
