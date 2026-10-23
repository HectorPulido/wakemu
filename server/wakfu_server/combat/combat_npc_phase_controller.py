"""Explicit Wakemu encounter publishers, separate from native effect semantics.

Nox's installed phase two retains 401610 on global1003, while the generic
combat opening producer intentionally publishes1003 only once. This policy
supplies the missing per-table boundary for that descriptor, never for classes.
Native Qf/eZX still select and execute the original UID snapshot and criteria.
"""
from dataclasses import dataclass

from .combat_event_replay import NativeExternalEvent
from .combat_boss_score_policy import NOX_SCORE, native_score_policy


@dataclass(frozen=True)
class NpcPhasePolicy:
    name: str
    reference: int
    constructor_state: int
    event_id: int
    channel: int
    listeners: frozenset[int]


NOX_TABLE_PHASE = NpcPhasePolicy(
    "wakemu-nox-table-phase-v2",
    5664,
    8969,
    1003,
    61,
    frozenset((401534, 401610, 401623)),
)

NOX_SCORE_POLICY = NOX_SCORE.name


@dataclass(frozen=True)
class ControllerStateEntry:
    policy: str
    actor_id: int
    reference: int
    level: int


def _enter_controller_state(dispatcher, entry):
    """Use the installed direct-eWu carrier and children for policy state entry."""
    from .combat_boss_score_policy import RUSHU_SCORE
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    allowed = {NOX_SCORE.name: (9031, 8988), RUSHU_SCORE.name: (7110,)}
    if not isinstance(
        entry, ControllerStateEntry
    ) or entry.reference not in allowed.get(entry.policy, ()):
        raise ValueError("Unreviewed controller state entry")
    actor = dispatcher.native_retention.fight.actors[entry.actor_id]
    handler = dispatcher.native_state_handler
    native = state_profile(handler.catalog, entry.reference, entry.level)
    if (
        native["duration"] != -1
        or native["realtime_duration"] != 0
        or native["level"] != entry.level
        or entry.level <= 0
    ):
        raise ValueError(
            "Native controller marker requires its installed indefinite grade"
        )
    invocation = EffectInvocation(
        2226,
        entry.level,
        actor.id,
        actor.id,
        actor.position,
        native_retained_container={"present": False},
    )
    context = StateCarrierContext(
        -1,
        0,
        False,
        None,
        None,
        False,
        False,
        False,
        0,
        native_time_payload(realtime_remaining=0),
    )
    if not dispatcher.native_retention.apply_state_reference(
        handler,
        invocation,
        entry.reference,
        entry.level,
        carrier_context=context,
    ):
        raise ValueError("Native success marker was not installed")


def _nox_extra_tables(actor):
    levels = [
        entry.level for entry in actor.state_ledger.entries if entry.reference == 8988
    ]
    if len(levels) > 1 or any(
        type(level) is not int or not 0 <= level <= 10 for level in levels
    ):
        raise ValueError("Nox score requires reviewed difficulty0..10")
    return levels[0] if levels else 0


def install_npc_phase_score(dispatcher):
    """Install a reconstructed score policy after native opening, before play."""
    fight = dispatcher.native_retention.fight
    receipts = getattr(fight, "native_npc_initialization_receipts", {})
    if any(row.get("ref") == 4378 for row in receipts.values()):
        from .combat_ogrest_phase_controller import install_ogrest_phase_profile
        from .combat_ogrest_score_policy import install_ogrest_score_profile

        context = install_ogrest_phase_profile(dispatcher)
        if context is not None:
            install_ogrest_score_profile(dispatcher, context)
    bosses = [
        identity
        for identity, row in receipts.items()
        if row.get("ref") == NOX_TABLE_PHASE.reference
        and row.get("initialized") is True
    ]
    if not bosses:
        if any(row.get("ref") == 5306 for row in receipts.values()):
            from .combat_rushu_score_policy import install_rushu_score_profile

            install_rushu_score_profile(dispatcher)
        return
    if (
        fight.phase != "active"
        or fight.turn_id != 1
        or fight.native_start_event_delivered is not True
    ):
        raise ValueError("Nox score requires the completed native opening preview")
    if len(bosses) != 1 or getattr(fight, "boss_score_profile", None) is not None:
        raise ValueError("Nox score requires one unprofiled native encounter")
    boss = fight.actors[bosses[0]]
    if boss.controlled or not any(
        item.get("state_id") == 8969
        for item in receipts[boss.id].get("resolved_states", ())
    ):
        raise ValueError("Nox score lacks its native constructor receipt")
    from .combat_companions import registered_companion_ids
    from .combat_terminal_metadata import registered_summon_actor_ids

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
        raise ValueError("Nox score requires one owned player team")
    extra = _nox_extra_tables(boss)
    difficulty = extra
    stele = getattr(fight, "native_dungeon_stele_receipt", None)
    if stele is not None:
        from wakfu_server.dungeon_stele_states import POLICY as STELE_POLICY

        if (
            stele.get("policy") != STELE_POLICY
            or stele.get("fight_id") != fight.id
            or stele.get("initialized") is not True
            or boss.id not in stele.get("actor_ids", ())
        ):
            raise ValueError("Nox score lacks its frozen stele carrier authority")
        difficulty = stele.get("difficulty_weight")
        if type(difficulty) is not int or difficulty < 0:
            raise ValueError("Nox score lacks its frozen difficulty weight")
        expected_extra = min(difficulty, 10)
        if extra not in (0, expected_extra):
            raise ValueError(
                "Native Nox table extension disagrees with selected steles"
            )
        if expected_extra and not extra:
            _enter_controller_state(
                dispatcher,
                ControllerStateEntry(
                    NOX_SCORE_POLICY,
                    boss.id,
                    8988,
                    expected_extra,
                ),
            )
        extra = expected_extra
    from wakfu_server.maps import boss_score
    from .combat_encounter_table_listeners import (
        freeze_table_listener_policy,
        frozen_table_listener_policy,
    )

    table_listener_policy = frozen_table_listener_policy(fight)
    if table_listener_policy is None:
        if hasattr(fight, "native_encounter_table_listener_policy"):
            raise ValueError("Nox score requires its frozen table listener policy")
        table_listener_policy = freeze_table_listener_policy(
            1435, (NOX_TABLE_PHASE.reference,)
        )

    fight.boss_score_profile = dict(
        policy=boss_score.POLICY,
        encounter_controller=NOX_SCORE_POLICY,
        bosses={
            str(boss.id): dict(
                reference=5664, round_limit=10 + extra, allow_early_boss_defeat=False
            )
        },
        player_ids=players,
        player_team=fight.actors[players[0]].team,
        round_limit=10 + extra,
        includes_armor=True,
        includes_owned_summons=True,
        allow_early_boss_defeat=False,
        difficulty=difficulty,
        extra_table_turns=extra,
        minimum_score=NOX_SCORE.minimum_score + 500000 * difficulty,
        table_listener_policy=table_listener_policy,
    )
    fight.boss_score_events = {}


def deliver_npc_score_result(dispatcher, *, actor_id):
    """Enter a reviewed success marker before actual owned boundary callbacks.

    This is an explicitly reconstructed server controller entry, not an
    invented spell or a claim that the catalog contains a9031 producer304.
    The shared direct-eWu carrier path executes the installed state definition.
    """
    fight = dispatcher.native_retention.fight
    profile = getattr(fight, "boss_score_profile", None)
    policy = native_score_policy(profile)
    if policy is None or policy.success_state is None:
        return False
    if fight.phase != "active" or fight.current is None or fight.current.id != actor_id:
        raise ValueError("Native score requires an actual owned turn boundary")
    boss_id = int(next(iter(profile["bosses"])))
    actor = fight.actors[boss_id]
    if (
        policy.name == NOX_SCORE_POLICY
        and _nox_extra_tables(actor) != profile["extra_table_turns"]
    ):
        raise ValueError("Nox difficulty changed after score policy publication")
    from wakfu_server.maps.boss_score_runtime import staged_score

    score = staged_score(fight)
    if score < profile["minimum_score"] or any(
        entry.reference == policy.success_state for entry in actor.state_ledger.entries
    ):
        return False
    _enter_controller_state(
        dispatcher,
        ControllerStateEntry(
            policy.name,
            boss_id,
            policy.success_state,
            1,
        ),
    )
    fight.native_npc_score_result = dict(
        policy=policy.name,
        actor_id=boss_id,
        boundary_actor_id=actor_id,
        score=score,
        minimum_score=profile["minimum_score"],
    )
    return True


def deliver_npc_table_phase(dispatcher, *, actor_id):
    """Publish once on the actual boss start in a caller-owned preview.

    The first table already received the genuine combat opening. Empty later
    snapshots are journaled too: a listener born after this boundary must wait
    until the next table rather than replay history during an extra turn.
    """
    fight = dispatcher.native_retention.fight
    if fight.phase != "active" or fight.current is None or fight.current.id != actor_id:
        raise ValueError("NPC phase requires the actual active turn")
    if getattr(fight, "native_ogrest_phase_context", None) is not None:
        from .combat_ogrest_phase_controller import deliver_ogrest_table_phase

        return deliver_ogrest_table_phase(dispatcher, actor_id=actor_id)
    receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(actor_id)
    policy = NOX_TABLE_PHASE
    if not receipt or receipt.get("ref") != policy.reference:
        from .combat_encounter_table_listeners import frozen_table_listener_policy

        frozen = frozen_table_listener_policy(fight)
        if (
            frozen is None
            or not receipt
            or receipt.get("ref") != frozen["boss_reference"]
        ):
            return ()
        policy = NpcPhasePolicy(
            frozen["policy"],
            frozen["boss_reference"],
            frozen["boss_constructor_state"],
            frozen["event_id"],
            frozen["channel"],
            frozenset(),
        )
    actor = fight.actors[actor_id]
    if (
        actor.controlled
        or receipt.get("initialized") is not True
        or not any(
            item.get("state_id") == policy.constructor_state
            for item in receipt.get("resolved_states", ())
        )
    ):
        raise ValueError("NPC phase lacks its native constructor receipt")
    table = getattr(fight, "native_table_turn", None)
    if not fight.native_start_event_delivered or type(table) is not int or table < 1:
        raise ValueError("NPC phase requires an established native table")
    if table == 1:
        return ()
    key = f"{policy.name}:{actor_id}:{table}"
    deliveries = getattr(fight, "native_npc_phase_deliveries", {})
    if key in deliveries:
        return ()
    snapshot = tuple(dispatcher.native_retention.view().entries)
    selected = frozenset(
        entry.uid
        for entry in snapshot
        if entry.manager_id == actor_id and entry.generic_effect in policy.listeners
    )
    outcomes = (
        dispatcher.replay_event(
            NativeExternalEvent(actor_id, (policy.event_id,), policy.channel),
            authority=dispatcher.native_clone_authority,
            eligible_uids=selected,
        )
        if policy.listeners
        else ()
    )
    from .combat_encounter_table_listeners import deliver_owned_table_listeners

    auxiliary, owners = deliver_owned_table_listeners(
        dispatcher,
        boss_id=actor_id,
        snapshot=snapshot,
    )
    # Primitive state is included by the existing checkpoint serializer. The
    # turn-start preview and normal ACK adoption own all-or-nothing publication.
    fight.native_npc_phase_deliveries = {
        **deliveries,
        key: dict(
            actor_id=actor_id,
            table_turn=table,
            event_id=policy.event_id,
            channel=policy.channel,
            eligible_uids=sorted(selected),
            owned_listeners=list(owners),
        ),
    }
    return tuple(outcomes) + auxiliary
