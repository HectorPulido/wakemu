"""Reconstructed Ogrest director; original states, groups and hazards execute natively.

The original server director is absent. Three-table timing and publication of
2171/2172/2173 are explicit Wakemu policy based on the reviewed encounter guide.
The installed4979 opening marks all phases complete; replace that manager only
inside the exact reconstructed normal4378 scene. Never mutate actor HP or a
state ledger directly, and never publish these events to unrelated encounters.
"""
from .combat_event_replay import NativeExternalEvent
from .combat_effect_dispatch import EffectInvocation
from .combat_ogrest_scene_layout import OGREST_LAYOUT_POLICY

POLICY = "wakemu-ogrest-six-phases-v1"
PHASE_STATES = tuple(range(4980, 4986))
PHASE_FLAGS = tuple(range(5003, 5009))
PURPLE = 4982
SCORE_TABLES = 18
TERMINAL_TABLES = (19, 20)
ORIGINAL_GROUPS = frozenset((235832, 235821, 235829, 235865, 235828))


def _state_level(actor, reference):
    levels = [
        state.level
        for state in actor.state_ledger.entries
        if state.reference == reference
    ]
    if len(levels) > 1:
        raise ValueError("Ogrest phase marker has ambiguous original carriers")
    return levels[0] if levels else None


def _remove_owned_state(dispatcher, actor, reference):
    """Use original Qm state/child unapplication callbacks on the actual UID."""
    from .combat_state_cleanup import RetainedCleanupAuthority

    matches = [
        entry for entry in actor.state_ledger.entries if entry.reference == reference
    ]
    if len(matches) > 1:
        raise ValueError("Ogrest controller cannot select an ambiguous state UID")
    if not matches:
        return
    running = matches[0]
    definition = dispatcher.native_state_handler.catalog["states"][str(reference)]
    if definition["protected"]:
        raise ValueError("Ogrest controller cannot remove a protected native state")
    retention = dispatcher.native_retention
    entry = retention.view().by_uid.get(running.uid)
    if entry is None or entry.effect_class != 310:
        raise ValueError("Ogrest controller requires the real retained state carrier")
    RetainedCleanupAuthority(retention, actor.id)._remove_state(entry, forced=True)
    if _state_level(actor, reference) is not None:
        raise ValueError("Native Ogrest state unapplication retained its carrier")


def _execute_original(dispatcher, boss, reference):
    if reference not in ORIGINAL_GROUPS:
        raise ValueError("Unreviewed Ogrest controller source group")
    return dispatcher.execute(
        EffectInvocation(
            reference,
            boss.effective_level,
            boss.id,
            boss.id,
            boss.position,
            native_preselected_target=True,
            native_retained_container={"present": False},
        )
    )


def _publish_phase(dispatcher, boss, event_id):
    if event_id not in (2171, 2172, 2173):
        raise ValueError("Unreviewed Ogrest phase event")
    outcomes = []
    for channel in (3, 30, 31):
        outcomes.extend(
            dispatcher.replay_event(
                NativeExternalEvent(boss.id, (event_id,), channel),
                authority=dispatcher.native_clone_authority,
            )
        )
    return tuple(outcomes)


def _verify_active_phase(boss):
    active = [
        reference
        for reference in PHASE_STATES
        if _state_level(boss, reference) is not None
    ]
    if len(active) != 1:
        raise ValueError("Ogrest director requires one original active Dofus")
    flag = PHASE_FLAGS[PHASE_STATES.index(active[0])]
    if _state_level(boss, flag) != 2:
        raise ValueError("Ogrest active Dofus lacks its original grade2 phase marker")
    return active[0]


def install_ogrest_phase_profile(dispatcher):
    """Install once after native opening, before the first actual owned turn."""
    fight = dispatcher.native_retention.fight
    layout = getattr(fight, "native_encounter_scene_layout", None)
    if not isinstance(layout, dict) or layout.get("policy") != OGREST_LAYOUT_POLICY:
        return None
    old = getattr(fight, "native_ogrest_phase_context", None)
    if old is not None:
        if old.get("policy") != POLICY:
            raise ValueError("Conflicting Ogrest director policy")
        return old
    receipts = getattr(fight, "native_npc_initialization_receipts", {})
    candidates = [
        identity
        for identity, row in receipts.items()
        if row.get("ref") == 4378 and row.get("initialized") is True
    ]
    if (
        len(candidates) != 1
        or layout.get("map_id") != 1156
        or fight.phase != "active"
        or fight.turn_id != 1
        or fight.native_start_event_delivered is not True
    ):
        raise ValueError("Ogrest director lacks its actual normal-scene opening")
    boss = fight.actors[candidates[0]]
    if boss.controlled or boss.hp <= 0 or _state_level(boss, 4979) != 1:
        raise ValueError("Ogrest director lacks its actual native manager4979")
    if any(_state_level(boss, flag) != 3 for flag in PHASE_FLAGS):
        raise ValueError("Ogrest original opening phase premises changed")
    original_uids = {
        str(state.reference): state.uid
        for state in boss.state_ledger.entries
        if state.reference in (4979, *PHASE_FLAGS)
    }
    for reference in (4979, *PHASE_FLAGS):
        _remove_owned_state(dispatcher, boss, reference)
    if not _execute_original(dispatcher, boss, 235832):
        raise ValueError("Original Purple pending-phase producer did not execute")
    if not _execute_original(dispatcher, boss, 235821):
        raise ValueError("Original first Dofus producer did not execute")
    if _verify_active_phase(boss) != PURPLE:
        raise ValueError("Ogrest must begin with the original Purple phase")
    _publish_phase(dispatcher, boss, 2171)
    context = dict(
        policy=POLICY,
        reference=4378,
        boss_id=boss.id,
        original_manager_uids=original_uids,
        phase_order=[PURPLE],
        current_phase=PURPLE,
        phase_start_table=1,
        delivered_tables=[],
        transitions=[],
        final_entered=False,
        terminal=None,
    )
    fight.native_ogrest_phase_context = context
    return context


def deliver_ogrest_table_phase(dispatcher, *, actor_id):
    """Advance only on this boss's genuine owned table boundary, exactly once."""
    fight = dispatcher.native_retention.fight
    context = getattr(fight, "native_ogrest_phase_context", None)
    if context is None:
        return ()
    if context.get("policy") != POLICY:
        raise ValueError("Unknown Ogrest phase context")
    if actor_id != context["boss_id"]:
        return ()
    if fight.phase != "active" or fight.current is None or fight.current.id != actor_id:
        raise ValueError("Ogrest phase requires its real current boss")
    table = fight.native_timeline_round
    if type(table) is not int or table < 1:
        raise ValueError("Ogrest phase requires an authoritative native table")
    if table in context["delivered_tables"]:
        return ()
    previous = context["delivered_tables"]
    if table != (previous[-1] + 1 if previous else 1):
        raise ValueError("Ogrest director cannot skip native tables")
    boss = fight.actors[actor_id]
    outcomes = []
    if table > TERMINAL_TABLES[-1]:
        context["terminal"] = dict(
            policy=POLICY,
            result="defeat",
            boss_id=boss.id,
            table=table,
            source="missed_owned_exit_window",
        )
        context["delivered_tables"].append(table)
        fight.phase = "finished"
        fight.winner = boss.team
        fight._event(
            "finished", winner=boss.team, reason="wakemu_ogrest_exit_window_expired"
        )
        return ()
    if table == 2:
        # Preserve the original artifact cleanup criterion and exact listener.
        selected = frozenset(
            entry.uid
            for entry in dispatcher.native_retention.view().entries
            if entry.manager_id == actor_id and entry.generic_effect == 235884
        )
        for channel in (6, 60, 61):
            outcomes.extend(
                dispatcher.replay_event(
                    NativeExternalEvent(actor_id, (1003,), channel),
                    authority=dispatcher.native_clone_authority,
                    eligible_uids=selected,
                )
            )
    if table > 1 and (table - 1) % 3 == 0 and table <= 19:
        old_phase = _verify_active_phase(boss)
        outcomes.extend(_publish_phase(dispatcher, boss, 2172))
        if not _execute_original(dispatcher, boss, 235865):
            raise ValueError("Original Ogrest phase completion did not execute")
        flag = PHASE_FLAGS[PHASE_STATES.index(old_phase)]
        if _state_level(boss, flag) != 3 or _state_level(boss, old_phase) is not None:
            raise ValueError("Native Ogrest completion did not release its Dofus")
        if table <= SCORE_TABLES:
            if not _execute_original(dispatcher, boss, 235829):
                raise ValueError("Native random unused-phase selection failed")
            if not _execute_original(dispatcher, boss, 235821):
                raise ValueError("Native selected-phase producer failed")
            selected_phase = _verify_active_phase(boss)
            if selected_phase in context["phase_order"]:
                raise ValueError(
                    "Native Ogrest phase selection repeated a completed phase"
                )
            context["phase_order"].append(selected_phase)
            context["current_phase"] = selected_phase
            context["phase_start_table"] = table
            outcomes.extend(_publish_phase(dispatcher, boss, 2171))
        else:
            if len(context["phase_order"]) != 6 or set(context["phase_order"]) != set(
                PHASE_STATES
            ):
                raise ValueError("Ogrest final phase requires all six actual phases")
            # Installing5020 before this same1001 would immediately run its
            # original kill listener before players can approach the new exit.
            # Complete the sixth phase now, publish final only after1001.
            context["current_phase"] = None
            context["pending_final"] = dict(table=table, completed=old_phase)
        if table <= SCORE_TABLES:
            context["transitions"].append(
                dict(table=table, completed=old_phase, entered=context["current_phase"])
            )
    if table <= SCORE_TABLES:
        outcomes.extend(_publish_phase(dispatcher, boss, 2173))
    context["delivered_tables"].append(table)
    return tuple(outcomes)


def deliver_ogrest_post_turn_start(dispatcher, *, actor_id):
    """Publish the original final state after the real NPC19 owned1001."""
    fight = dispatcher.native_retention.fight
    context = getattr(fight, "native_ogrest_phase_context", None)
    if context is None or context.get("pending_final") is None:
        return ()
    if actor_id != context["boss_id"] or fight.phase != "active":
        return ()
    pending = context["pending_final"]
    if (
        context.get("policy") != POLICY
        or fight.current is None
        or fight.current.id != actor_id
        or fight.native_timeline_round != 19
        or pending["table"] != 19
        or context["final_entered"]
        or context["delivered_tables"][-1:] != [19]
        or set(context["phase_order"]) != set(PHASE_STATES)
        or len(context["phase_order"]) != 6
    ):
        raise ValueError("Ogrest final publication lacks its earned owned boundary")
    boss = fight.actors[actor_id]
    from .combat_state_managers import registered_area_pv

    sources = []
    areas = getattr(fight, "native_effect_areas", {})
    for row in areas.values():
        if row.get("reference") != 1254 or row.get("owner_id") != boss.id:
            continue
        if (
            row.get("native_qq_guard_source") != "Qq.constructor"
            or registered_area_pv(fight, row["uid"]) is None
        ):
            raise ValueError("Ogrest exit source lacks its actual native constructor")
        sources.append(
            dict(
                uid=row["uid"],
                reference=1254,
                owner_id=boss.id,
                cell=list(row["cell"]),
                native_area_contract=row["native_area_contract"],
                native_qq_guard_source="Qq.constructor",
            )
        )
    if not sources:
        raise ValueError("Ogrest final publication requires its actual original1254")
    previous_areas = frozenset(areas)
    if not _execute_original(dispatcher, boss, 235828) or _state_level(boss, 5020) != 1:
        raise ValueError("Original Ogrest final-phase producer failed")
    source_ids = {row["uid"] for row in sources}
    exits = [
        dict(uid=row["uid"], source_uid=row["owner_id"])
        for uid, row in areas.items()
        if uid not in previous_areas
        and row.get("reference") == 1255
        and row.get("owner_id") in source_ids
        and row.get("effect_reference") == 238861
        and row.get("native_area_contract") == "faY"
        and row.get("native_qq_guard_source") == "Qq.constructor"
    ]
    if not exits:
        raise ValueError(
            "Ogrest final producer did not create its original exit lineage"
        )
    context["exit_source_areas"] = sources
    context["exit_areas"] = exits
    context["final_entered"] = True
    context["transitions"].append(
        dict(table=19, completed=pending["completed"], entered=None)
    )
    del context["pending_final"]
    return ()


def ogrest_exit_areas(fight):
    """Return actual238861 exits with captured original1254 creator lineage."""
    context = getattr(fight, "native_ogrest_phase_context", None)
    if context is None or context.get("policy") != POLICY:
        return ()
    sources = {row["uid"]: row for row in context.get("exit_source_areas", ())}
    bindings = {row["uid"]: row["source_uid"] for row in context.get("exit_areas", ())}
    valid = []
    for uid, source_uid in bindings.items():
        source = sources.get(source_uid)
        row = getattr(fight, "native_effect_areas", {}).get(uid)
        if (
            source is None
            or source.get("reference") != 1254
            or source.get("owner_id") != context["boss_id"]
            or source.get("native_area_contract") != "faY"
            or source.get("native_qq_guard_source") != "Qq.constructor"
            or row is None
            or row.get("uid") != uid
            or row.get("reference") != 1255
            or row.get("owner_id") != source_uid
            or row.get("effect_reference") != 238861
            or row.get("native_area_contract") != "faY"
            or row.get("native_qq_guard_source") != "Qq.constructor"
        ):
            raise ValueError("Ogrest exit lost its original1254 creator lineage")
        valid.append(row)
    return tuple(valid)


def finish_ogrest_player_turn(dispatcher, *, actor_id):
    """Reconstructed exit policy after an actual owned player end boundary."""
    fight = dispatcher.native_retention.fight
    context = getattr(fight, "native_ogrest_phase_context", None)
    profile = getattr(fight, "boss_score_profile", None)
    if (
        context is None
        or profile is None
        or profile.get("encounter_controller") != POLICY
        or actor_id not in profile.get("player_ids", ())
    ):
        return False
    if context.get("policy") != POLICY:
        raise ValueError("Ogrest terminal policy differs from its phase director")
    if context.get("terminal") is not None:
        return False
    if fight.phase != "active" or fight.current is None or fight.current.id != actor_id:
        raise ValueError("Ogrest exit requires the actual owned end-turn actor")
    table = fight.native_timeline_round
    if not context["final_entered"] or table not in TERMINAL_TABLES:
        return False
    boss = fight.actors[context["boss_id"]]
    actor = fight.actors[actor_id]
    if (
        not actor.controlled
        or actor.owner_id <= 0
        or actor.team == boss.team
        or not fight._in_play(actor)
    ):
        return False
    if (
        _state_level(boss, 5020) != 1
        or len(context["phase_order"]) != 6
        or set(context["phase_order"]) != set(PHASE_STATES)
    ):
        raise ValueError(
            "Ogrest exit lacks the six earned phases and native final state"
        )
    candidates = [
        row
        for row in ogrest_exit_areas(fight)
        if tuple(row["cell"]) == tuple(actor.position)
    ]
    if len(candidates) > 1:
        raise ValueError("Ogrest exit has ambiguous actual native glyph authority")
    if not candidates:
        return False
    area = candidates[0]
    from wakfu_server.maps.boss_score_runtime import staged_score

    context["terminal"] = dict(
        policy=POLICY,
        result="victory",
        boss_id=boss.id,
        actor_id=actor.id,
        table=table,
        area_uid=area["uid"],
        area_reference=1255,
        cell=list(actor.position),
        phase_order=list(context["phase_order"]),
        area_source=dict(
            next(
                row
                for row in context["exit_source_areas"]
                if row["uid"] == area["owner_id"]
            )
        ),
        effect_reference=238861,
        score=staged_score(fight),
        source="actual_owned_player_turn_end",
    )
    fight.phase = "finished"
    fight.winner = actor.team
    fight._event("finished", winner=actor.team, reason="wakemu_ogrest_native_exit_cell")
    return True


def ogrest_terminal_authority(fight):
    """Validate the durable-result input against the actual final fight, no cache."""
    profile = getattr(fight, "boss_score_profile", None)
    context = getattr(fight, "native_ogrest_phase_context", None)
    if profile is None or profile.get("encounter_controller") != POLICY:
        return None
    terminal = None if context is None else context.get("terminal")
    if not isinstance(terminal, dict):
        return None
    if terminal.get("result") == "defeat":
        return None  # A missed window never supplies successful exit authority.
    boss_id, actor_id = terminal.get("boss_id"), terminal.get("actor_id")
    actor = fight.actors.get(actor_id)
    boss = fight.actors.get(boss_id)
    area = getattr(fight, "native_effect_areas", {}).get(terminal.get("area_uid"))
    if (
        context.get("policy") != POLICY
        or terminal.get("policy") != POLICY
        or terminal.get("result") != "victory"
        or not context.get("final_entered")
        or terminal.get("table") not in TERMINAL_TABLES
        or terminal.get("table") != fight.native_timeline_round
        or terminal.get("source") != "actual_owned_player_turn_end"
        or terminal.get("area_reference") != 1255
        or terminal.get("phase_order") != context.get("phase_order")
        or set(terminal.get("phase_order", ())) != set(PHASE_STATES)
        or len(terminal.get("phase_order", ())) != 6
        or boss is None
        or _state_level(boss, 5020) != 1
        or actor is None
        or actor_id not in profile.get("player_ids", ())
        or not actor.controlled
        or not fight._in_play(actor)
        or tuple(terminal.get("cell", ())) != tuple(actor.position)
        or fight.phase != "finished"
        or fight.winner != actor.team
        or area is None
        or area.get("reference") != 1255
        or area not in ogrest_exit_areas(fight)
        or terminal.get("effect_reference") != 238861
        or terminal.get("area_source") not in context.get("exit_source_areas", ())
        or terminal["area_source"].get("uid") != area.get("owner_id")
        or tuple(area.get("cell", ())) != tuple(actor.position)
        or area.get("native_area_contract") != "faY"
        or area.get("native_qq_guard_source") != "Qq.constructor"
    ):
        raise ValueError(
            "Ogrest terminal receipt lost its original scene/actor/area authority"
        )
    from wakfu_server.maps.boss_score_runtime import staged_score

    if terminal.get("score") != staged_score(fight):
        raise ValueError("Ogrest terminal score differs from actual damage receipts")
    return dict(terminal)
