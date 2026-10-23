"""Bounded ordinary200 strategy into Ombrage's native clock; no phase gifts."""
from collections import deque
from copy import deepcopy
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
from random import Random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]

# Explicit opt-in for one genuine in-process continuation and isolated Store.
OMBRAGE_ACTUAL_CHECKPOINT = None
OMBRAGE_HOLD_ACTUAL_CHECKPOINT = False
OMBRAGE_LOADED_IMPLEMENTATION_BINDER = None


def release_actual_ombrage_checkpoint():
    global OMBRAGE_ACTUAL_CHECKPOINT
    checkpoint, OMBRAGE_ACTUAL_CHECKPOINT = OMBRAGE_ACTUAL_CHECKPOINT, None
    if checkpoint is not None:
        for function, args, kwargs in reversed(checkpoint["cleanups"]):
            function(*args, **kwargs)


def back_path(
    fight,
    identity,
    *,
    require_back=True,
    maximum_range=2,
    require_los=False,
    actor_authority=None,
    require_linear=False,
    goal_predicate=None,
    origin=None,
    movement_prefix=(),
    mp_reserve=0,
):
    """Plan on actual directed edges, then let the owned movement validate it."""
    from wakfu_server.combat_ordinary_authority import native_facing
    from wakfu_server.combat_obstacle_condition import footprint

    actor, boss = fight.actors[identity], fight.actors[-200]
    start_cell = tuple(actor.position if origin is None else origin)
    movement_budget = actor.mp - len(movement_prefix) - mp_reserve

    def acceptable(cell, path=()):
        if (
            require_linear
            and cell[0] != boss.position[0]
            and cell[1] != boss.position[1]
        ):
            return False
        if (
            not 1
            <= sum(abs(a - b) for a, b in zip(cell, boss.position))
            <= maximum_range
        ):
            return False
        if (
            require_back
            and native_facing(SimpleNamespace(position=cell), boss) != "BACK"
        ):
            return False
        if require_los:
            from wakfu_server.combat_casting_los import native_casting_ray

            if not native_casting_ray(
                fight,
                actor_authority,
                1229,
                cell,
                boss.position,
                source_height=actor.native_los_height,
                target_height=boss.native_los_height,
                ignored_slots=(
                    *fight.native_qi_visibility_ignored_slots,
                    actor.native_obstacle_id,
                ),
            ):
                return False
        if goal_predicate is not None and not goal_predicate(cell, path):
            return False
        return True

    def payable(path):
        if not movement_prefix and not path:
            return actor.mp >= mp_reserve
        try:
            candidate = deepcopy(fight)
            candidate.move(actor.owner_id, identity, (*movement_prefix, *path))
        except ValueError:
            return False
        return candidate.actors[identity].mp >= mp_reserve

    if acceptable(start_cell) and payable(()):
        return ()
    blocked = set().union(
        *(
            footprint(other.position, other.physical_radius)
            for other in fight.actors.values()
            if other.hp > 0 and other.id != identity
        )
    )
    outgoing = {}
    for start, end in fight.edges:
        outgoing.setdefault(tuple(start), []).append(tuple(end))
    pending, seen = deque([(start_cell, ())]), {start_cell}
    while pending:
        cell, path = pending.popleft()
        if path and acceptable(cell, path) and payable(path):
            return path
        if len(path) >= movement_budget:
            continue
        for destination in sorted(outgoing.get(cell, ())):
            if destination not in seen and destination[:2] not in blocked:
                seen.add(destination)
                pending.append((destination, (*path, destination)))
    return None


class OmbrageNativePaidClockTests(PostgresCase):
    def test_paid_back_hits_reach_original_eighty_percent_clock(self):
        self._run_strategy()

    def test_first_native_vulnerability_paid_damage_component(self):
        self._run_strategy(damage_component=True)

    def test_paid_stabilization_opens_early_native_vulnerability_component(self):
        self._run_strategy(damage_component=True, stabilization_component=True)

    def test_paid_iop_stabilization_full_first_window_budget_component(self):
        self._run_strategy(window_component=True)

    def test_paid_first_damage_then_original_three_table_deadline(self):
        self._run_strategy(window_component=True, deadline_only=True)

    def test_native_self_area_4779_recipient_preview(self):
        self._run_strategy(recipient_component=True)

    def test_native_endgame_budget_and_bounded_earned_clock(self):
        self._run_strategy(window_component=True, endgame_component=True)

    def _run_strategy(
        self,
        *,
        damage_component=False,
        stabilization_component=False,
        window_component=False,
        deadline_only=False,
        recipient_component=False,
        endgame_component=False,
    ):
        global OMBRAGE_ACTUAL_CHECKPOINT
        if OMBRAGE_HOLD_ACTUAL_CHECKPOINT and OMBRAGE_ACTUAL_CHECKPOINT is not None:
            raise ValueError(
                "Release the prior live Ombrage checkpoint before creating another case"
            )
        from native_paid_party_fixture import (
            NativePartyBuild,
            NativeGear,
            native_paid_party_fixture,
            native_endgame_iop_build,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_supreme_scene_policies import resolve_supreme_scene
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_damage_handler import NativeDamageHandler
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.combat_characteristic_percentage import (
            characteristic_percentage,
        )
        from tools.combat_audit_turns import advance_actual_turn

        scene = resolve_supreme_scene(
            4770,
            json.loads(
                (ROOT / ".runtime/ultimate-scenes-20261021/map-1229.json").read_text()
            ),
        )
        scene.update(reference=4770, level=200)
        # Every declared piece has original1068/eZO three-element mastery.
        # Persist a real native fire/earth/air selection before equipment use.
        gear = tuple(
            NativeGear(ref, slot, damage_mask=26)
            for ref, slot in (
                (20722, 3),
                (20723, 5),
                (20724, 13),
                (20725, 0),
                (20726, 12),
                (20727, 4),
                (20728, 7),
                (20729, 15),
                (20730, 8),
            )
        )
        build = NativePartyBuild(
            breed=8,
            level=200,
            active_spells=(
                4777,
                4780,
                4781,
                4789,
                *((4790,) if window_component else ()),
                *((4779,) if recipient_component else ()),
            ),
            aptitudes=(
                (1, 40),
                (16, 10),
                (26, 40),
                (23, 10),
                (12, 49),
                (2, 1),
                (3, 1),
                (8, 1),
            ),
            gear=gear,
        )
        if endgame_component:
            from dataclasses import replace

            build = native_endgame_iop_build()
            build = replace(build, active_spells=(*build.active_spells, 4790))
            gear = build.gear
        # This fallback is source-qualified across every native conditional
        # branch; actual casts still select/validate their current native rule.
        if window_component:
            stabilizer_casting, _ = native_casting_table(4790, 200)
            self.assertTrue(stabilizer_casting["line_of_sight"])
            self.assertTrue(stabilizer_casting["linear"])
        blind_casting, _ = native_casting_table(4781, 200)
        self.assertFalse(blind_casting["line_of_sight"])
        self.assertTrue(
            all(not row["line_of_sight"] for row in blind_casting["conditional"])
        )
        receipt = dict(
            status="pending",
            endgame_component=endgame_component,
            recipient_component=recipient_component,
            deadline_only=deadline_only,
            window_component=window_component,
            damage_component=damage_component,
            stabilization_component=stabilization_component,
            stabilization_casts=[],
            paid_hits=[],
            movements=[],
            boundaries=[],
            source_events=[],
            rejected=[],
            damage_calculations=[],
            option_previews=[],
        )
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = (
            ROOT / f".runtime/ultimate-scenes-20261021/ombrage-paid-clock-{stamp}.json"
        )
        original_execute = EffectDispatcher.execute
        original_calculate = NativeDamageHandler._calculate
        active_preview = {}
        rng = Random(0)
        admission_binding = None

        def calculate(handler, effect, invocation, **kwargs):
            result = original_calculate(handler, effect, invocation, **kwargs)
            if (
                damage_component
                and invocation.target_id == -200
                or recipient_component
                and invocation.target_id in handler.fight.actors
            ) and invocation.caster_id in receipt.get("player_ids", ()):
                source, target = (
                    handler.fight.actors[invocation.caster_id],
                    handler.fight.actors[invocation.target_id],
                )
                receipt["damage_calculations"].append(
                    dict(
                        stage=dict(active_preview),
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        effect=invocation.reference,
                        level=invocation.level,
                        family=effect["effect_class"],
                        parameters=effect.get("parameters"),
                        context=result[0],
                        interpreted=result[1],
                        calculated_amount=result[2],
                        source_stats=dict(source.effect_stats),
                        target_stats=dict(target.effect_stats),
                        target_states=[
                            (row.reference, row.level)
                            for row in target.state_ledger.entries
                        ],
                    )
                )
            return result

        def observe(dispatcher, invocation, **kwargs):
            result = original_execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (
                266415,
                266896,
                266789,
                267288,
                266810,
                266787,
                266788,
                267286,
                267287,
                266725,
                266726,
                266730,
                266731,
                266733,
                266735,
                268103,
                266530,
                266531,
                266532,
            ):
                observed_fight = dispatcher.native_retention.fight
                observed_boss = observed_fight.actors.get(-200)
                receipt["source_events"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        result=bool(result),
                        table=getattr(observed_fight, "native_table_turn", None),
                        turn=observed_fight.turn_id,
                        boss_present=observed_boss is not None,
                        boss_wp=None
                        if observed_boss is None
                        else observed_boss.effect_stats[4],
                        boss_states=[]
                        if observed_boss is None
                        else [
                            (row.reference, row.level)
                            for row in observed_boss.state_ledger.entries
                        ],
                    )
                )
            return result

        if endgame_component and OMBRAGE_HOLD_ACTUAL_CHECKPOINT:
            self.assertTrue(
                callable(OMBRAGE_LOADED_IMPLEMENTATION_BINDER),
                "Retained Ombrage requires a loaded-code binder before admission",
            )
            admission_binding = OMBRAGE_LOADED_IMPLEMENTATION_BINDER(
                store=self.store, rng=rng, runtime_class=RuntimeMessages
            )
        try:
            with original_bootstrap_publication() as publication, patch.object(
                EffectDispatcher, "execute", observe
            ), patch.object(NativeDamageHandler, "_calculate", calculate):
                builds = [build] * 6
                if stabilization_component:
                    builds[1] = NativePartyBuild(
                        breed=1,
                        level=200,
                        active_spells=(6985,),
                        aptitudes=build.aptitudes,
                        gear=gear,
                    )
                (
                    fight,
                    characters,
                    monsters,
                    decks,
                    resources,
                    _,
                    premise,
                ) = native_paid_party_fixture(
                    self.store,
                    scene,
                    tuple(builds),
                    scene["party_placement_cells"],
                    name_prefix="ombrage-paid-clock",
                    encounter_layout=scene,
                )
                if window_component or recipient_component:
                    frozen_listener = getattr(
                        fight, "native_encounter_table_listener_policy", None
                    )
                    receipt["frozen_listener_policy"] = deepcopy(frozen_listener)
                    self.assertIsInstance(
                        frozen_listener,
                        dict,
                        "Actual admission did not freeze the original Ombrage timer policy",
                    )
                    self.assertEqual(
                        frozen_listener["policy"],
                        "wakemu-ombrage-damage-deadline-table-listener-v1",
                    )
                receipt.update(
                    premise=premise,
                    publication=publication,
                    player_ids=tuple(characters),
                    admitted_initial_resources={
                        identity: dict(
                            ap=fight.actors[identity].ap,
                            mp=fight.actors[identity].mp,
                            wp=fight.actors[identity].effect_stats[4],
                        )
                        for identity in characters
                    },
                )
                if endgame_component:
                    from wakfu_server.combat_tackle_movement import native_tackle_loss

                    lock = fight.actors[-200].effect_stats[7]
                    receipt["endgame_admitted_stats"] = {
                        identity: dict(
                            level=actor.effective_level,
                            dodge=actor.effect_stats[8],
                            melee_mastery=actor.effect_stats.get(103, 0),
                            ap=actor.ap,
                            mp=actor.mp,
                            tackle_losses={
                                facing: native_tackle_loss(
                                    [lock],
                                    actor.effect_stats[8],
                                    actor.effective_level,
                                    facing,
                                )
                                for facing in ("FRONT", "SIDE", "BACK")
                            },
                        )
                        for identity, actor in fight.actors.items()
                        if identity in characters
                    }
                    self.assertTrue(
                        all(
                            row["level"] == 245
                            and row["tackle_losses"]["BACK"] == (0, 0)
                            for row in receipt["endgame_admitted_stats"].values()
                        )
                    )
                first = next(iter(characters))
                common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
                planning_authority = server_runtime(
                    characters[first],
                    monsters,
                    decks[first],
                    action_id=1,
                    critical=False,
                    **common,
                )[1].actor_authority

                def stats(actor, current):
                    if getattr(actor, "native_summon_source", None) is not None:
                        return registered_summon_stats(actor, current, 1229)
                    values = dict(
                        wp_current=actor.effect_stats[4],
                        wp_maximum=actor.effect_maxima[4],
                        fight=current,
                    )
                    if actor.id in characters:
                        return actual_actor_stats(
                            characters[actor.id], actor, current.id, **values
                        )
                    return actual_monster_actor_stats(
                        monsters[actor.id], actor, current.id, **values
                    )

                runtime = RuntimeMessages(
                    fight,
                    runtime_stats_serializer=stats,
                    turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                        characters[first],
                        monsters,
                        phase,
                        decks[first],
                        native_events=True,
                        area_callbacks=True,
                        **common,
                        **kw,
                    ),
                    turn_end_provider=lambda phase, **kw: prepare_server_turn_end(
                        characters[first], monsters, phase, decks[first], **common, **kw
                    ),
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        characters[first],
                        monsters,
                        decks[first],
                        action_id=action_id,
                        critical=False,
                        **common,
                    )[0],
                )
                if endgame_component:
                    self.ombrage_live = dict(
                        runtime=runtime,
                        characters=characters,
                        monsters=monsters,
                        decks=decks,
                        resources=resources,
                        rng=rng,
                        stats=stats,
                        common=common,
                        planning_authority=planning_authority,
                        receipt=receipt,
                        output=output,
                        observer=observe,
                        calculator=calculate,
                        store=self.store,
                        runtime_source_pins={
                            str(
                                path.relative_to(ROOT / "server/wakfu_server")
                            ): hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in sorted(
                                (ROOT / "server/wakfu_server").rglob("*.py")
                            )
                        },
                        advance_actual_turn=advance_actual_turn,
                        prepare_server_spell=prepare_server_spell,
                        commit_spell_transaction=commit_spell_transaction,
                        apply_client=apply_client,
                        prepare_area_movement=prepare_area_movement,
                    )
                    self.ombrage_live["admission_component_active"] = True
                    if admission_binding is not None:
                        admission_binding(self.ombrage_live)
                runtime.turn_started()
                for boundary in range(
                    40
                    if endgame_component
                    else 24
                    if window_component
                    else 12
                    if damage_component or recipient_component
                    else 48
                ):
                    for _ in range(32):
                        if runtime.awaiting_ack is None:
                            break
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                    else:
                        self.fail("Bounded actual ACK chain exhausted")
                    current = runtime.fight
                    boss = current.actors[-200]
                    areas = {
                        row["reference"]
                        for row in current.native_effect_areas.values()
                        if row.get("owner_id") == -200
                    }
                    # Record every actual area, irrespective of row owner schema.
                    receipt["areas"] = [
                        dict(row) for row in current.native_effect_areas.values()
                    ]
                    receipt["boundaries"].append(
                        dict(
                            turn=current.turn_id,
                            table=getattr(current, "native_table_turn", None),
                            phase=current.phase,
                            current=None
                            if current.current is None
                            else current.current.id,
                            boss_hp=boss.hp,
                            boss_max_hp=boss.max_hp,
                            boss_position=boss.position,
                            boss_wp=boss.effect_stats[4],
                            boss_direction=boss.direction,
                            states=[
                                (entry.reference, entry.level)
                                for entry in boss.state_ledger.entries
                            ],
                            player_hp={
                                identity: current.actors[identity].hp
                                for identity in characters
                            },
                            player_resources={
                                identity: dict(
                                    ap=current.actors[identity].ap,
                                    mp=current.actors[identity].mp,
                                    wp=current.actors[identity].effect_stats[4],
                                )
                                for identity in characters
                            },
                        )
                    )
                    if (
                        window_component
                        and not endgame_component
                        and getattr(current, "native_table_turn", 1) >= 2
                    ):
                        table = getattr(current, "native_table_turn", 1)
                        journal = getattr(current, "native_npc_phase_deliveries", {})
                        key = f"wakemu-ombrage-damage-deadline-table-listener-v1:-200:{table}"
                        self.assertIn(key, journal)
                        receipt["deadline_publications"] = dict(journal)
                        grades = [
                            row.level
                            for row in boss.state_ledger.entries
                            if row.reference == 5659
                        ]
                        self.assertEqual(grades, [4 - table] if table < 4 else [])
                        if "actual_window_damage" not in receipt:
                            damaging = [
                                row
                                for row in receipt["paid_hits"]
                                if row["before_hp"] > row["after_hp"]
                            ]
                            self.assertGreaterEqual(
                                len({row["actor"] for row in damaging}),
                                1 if deadline_only else 2,
                            )
                            self.assertTrue(
                                all(row["before_facing"] == "BACK" for row in damaging)
                            )
                            self.assertTrue(receipt["stabilization_casts"])
                            receipt.update(
                                first_window_complete=not deadline_only,
                                measured_damage_scope="one_paid_hit_then_pass"
                                if deadline_only
                                else "full_first_window",
                                actual_window_damage=sum(
                                    row["before_hp"] - row["after_hp"]
                                    for row in damaging
                                ),
                                actual_eighty_percent_threshold=boss.max_hp * 80 // 100,
                                remaining_eighty_percent_damage=max(
                                    0, boss.hp - boss.max_hp * 80 // 100
                                ),
                                first_window_player_resources=receipt["boundaries"][-1][
                                    "player_resources"
                                ],
                            )
                            self.assertLess(
                                receipt["actual_window_damage"],
                                30000,
                                "The intended native deadline failure requires less than original30000damage",
                            )
                        if table >= 4:
                            wp_events = [
                                row
                                for row in receipt["source_events"]
                                if row["reference"] == 266735
                                and row["table"] == 4
                                and row["result"]
                                and row["boss_wp"] >= 20
                            ]
                            self.assertTrue(
                                wp_events,
                                "Original failed damage deadline did not add20WP",
                            )
                            self.assertTrue(
                                any(
                                    row["reference"] == 268103
                                    and row["table"] == 4
                                    and row["result"]
                                    for row in receipt["source_events"]
                                )
                            )
                            receipt["status"] = (
                                "first_paid_damage_and_original_failed_damage_deadline_observed"
                                if deadline_only
                                else "full_first_paid_back_window_and_original_failed_damage_deadline_observed"
                            )
                            return
                        if current.phase != "active" or current.current is None:
                            self.fail(
                                "Native encounter ended before its original table4 deadline"
                            )
                        # Preserve the measured first window. Subsequent owned
                        # turns pass normally, without further damage or gifts.
                        advance_actual_turn(runtime)
                        continue
                    if (
                        endgame_component
                        and getattr(current, "native_table_turn", 1) >= 2
                        and "first_endgame_window_damage" not in receipt
                    ):
                        damage = sum(
                            row["before_hp"] - row["after_hp"]
                            for row in receipt["paid_hits"]
                        )
                        receipt["first_endgame_window_damage"] = damage
                        self.assertTrue(
                            receipt.get("endgame_two_hit_budget")
                            or characteristic_percentage(boss.hp, boss.max_hp) <= 80
                        )
                        receipt[
                            "same_fight_continuation"
                        ] = "original30000damage_deadline_over_three_tables"
                    if (
                        endgame_component
                        and characteristic_percentage(boss.hp, boss.max_hp) == 80
                        and any(
                            row.reference == 5650 for row in boss.state_ledger.entries
                        )
                    ):
                        # Native GS.B floors80.91% to80. Continuing HP damage
                        # instead of this BACK gate spends the next deadline.
                        from tools.ombrage_live_phase_handoff import continue_handoff

                        handoff = continue_handoff(
                            self.ombrage_live,
                            output.with_name(
                                output.stem + "-native-phase-handoff.json"
                            ),
                            maximum_boundaries=min(16, 40 - boundary),
                            within_admitted_component=True,
                        )
                        receipt["native_integer_eighty_handoff"] = handoff
                        receipt["status"] = handoff["status"]
                        receipt["areas"] = handoff["last"]["areas"]
                        return
                    if deadline_only and any(
                        row["before_hp"] > row["after_hp"]
                        for row in receipt["paid_hits"]
                    ):
                        if current.phase != "active" or current.current is None:
                            self.fail(
                                "Native encounter ended before its original table4 deadline"
                            )
                        advance_actual_turn(runtime)
                        continue
                    if {1349, 1357} <= areas:
                        phase_states = {
                            entry.reference for entry in boss.state_ledger.entries
                        }
                        self.assertTrue({5654, 5663} <= phase_states)
                        self.assertTrue({5650, 5657}.isdisjoint(phase_states))
                        phase_areas = [
                            row
                            for row in current.native_effect_areas.values()
                            if row.get("owner_id") == -200
                            and row["reference"] in (1349, 1357)
                        ]
                        self.assertTrue(
                            all(
                                row["effect_reference"]
                                in (
                                    266788,
                                    267287,
                                    267306,
                                    267308,
                                    267347,
                                    267349,
                                    267388,
                                    267390,
                                )
                                for row in phase_areas
                            )
                        )
                        receipt["qualified_phase_areas"] = [
                            dict(row) for row in phase_areas
                        ]
                        receipt[
                            "status"
                        ] = "original_clock_produced_after_paid_phase_progression"
                        self.assertTrue(receipt["paid_hits"])
                        self.assertLessEqual(
                            characteristic_percentage(boss.hp, boss.max_hp), 80
                        )
                        return
                    if (
                        getattr(current, "native_table_turn", 1) >= 3
                        and receipt["paid_hits"]
                        and boss.hp == boss.max_hp
                    ):
                        opened = any(
                            any(reference == 5661 for reference, _ in hit["states"])
                            for hit in receipt["paid_hits"]
                        )
                        self.fail(
                            "Two tables produced no paid HP damage; actual vulnerability observed="
                            + str(opened)
                        )
                    if (
                        current.phase != "active"
                        or current.current is None
                        or getattr(current, "native_table_turn", 1)
                        > (2 if damage_component else 6)
                    ):
                        break
                    identity = current.current.id
                    if recipient_component and identity in characters:
                        paths = {
                            2: (
                                (2, 2, 0),
                                (2, 1, 0),
                                (2, 0, 0),
                                (2, -1, 0),
                                (2, -2, 0),
                                (1, -2, 0),
                                (0, -2, 0),
                            ),
                            4: (
                                (-3, 0, 0),
                                (-2, 0, 0),
                                (-1, 0, 0),
                                (-1, -1, 0),
                                (0, -1, 0),
                            ),
                        }
                        if identity in paths:
                            actor = current.actors[identity]
                            origin, mp, ap = actor.position, actor.mp, actor.ap
                            apply_client(
                                runtime,
                                actor.owner_id,
                                struct.pack(">q", identity)
                                + b"".join(
                                    struct.pack(">iih", *cell)
                                    for cell in paths[identity]
                                ),
                                lambda value: stats(value, runtime.fight),
                                runtime_stats_serializer=stats,
                                area_provider=lambda candidate, **kw: prepare_area_movement(
                                    characters[first],
                                    monsters,
                                    candidate,
                                    decks[first],
                                    **common,
                                    **kw,
                                ),
                            )
                            receipt["movements"].append(
                                dict(
                                    actor=identity,
                                    origin=origin,
                                    destination=runtime.fight.actors[identity].position,
                                    before_mp=mp,
                                    after_mp=runtime.fight.actors[identity].mp,
                                    before_ap=ap,
                                    after_ap=runtime.fight.actors[identity].ap,
                                )
                            )
                            if identity == 4:
                                current = runtime.fight
                                original = {
                                    key: (
                                        value.hp,
                                        value.ap,
                                        value.mp,
                                        value.effect_stats[4],
                                    )
                                    for key, value in current.actors.items()
                                }
                                rng_before = rng.getstate()
                                active_preview.update(
                                    reference=4779, kind="recipient_preview"
                                )
                                try:
                                    tx = prepare_server_spell(
                                        struct.pack(
                                            ">qqiih",
                                            identity,
                                            (identity << 32) | 4779,
                                            *current.actors[identity].position,
                                        ),
                                        characters[identity],
                                        monsters,
                                        current,
                                        characters[identity]["account_id"],
                                        decks[identity],
                                        action_id=runtime.action_id + 1,
                                        critical=None,
                                        **common,
                                        line_of_sight=lambda origin, target, phase: authoritative_visible(
                                            1229,
                                            origin,
                                            target,
                                            phase,
                                            blocking_footprints={
                                                a.id: footprint(
                                                    a.position, a.physical_radius
                                                )
                                                for a in phase.actors.values()
                                                if a.hp > 0
                                            },
                                        ),
                                    )
                                finally:
                                    rng.setstate(rng_before)
                                self.assertEqual(tx.plan["costs"]["ap"], 6)
                                self.assertEqual(tx.plan["costs"]["wp"], 1)
                                self.assertEqual(
                                    original,
                                    {
                                        key: (
                                            value.hp,
                                            value.ap,
                                            value.mp,
                                            value.effect_stats[4],
                                        )
                                        for key, value in current.actors.items()
                                    },
                                )
                                self.assertEqual(rng.getstate(), rng_before)
                                receipt.update(
                                    status="native_self_area_4779_recipient_preview_observed",
                                    recipient_preview=dict(
                                        reference=4779,
                                        source=current.actors[identity].position,
                                        target=current.actors[identity].position,
                                        costs=tx.plan["costs"],
                                        rng_unchanged=True,
                                        offensive_commit=False,
                                        actors={
                                            key: dict(
                                                position=value.position,
                                                before_hp=original[key][0],
                                                preview_hp=tx.fight.actors[key].hp,
                                                hp_delta=original[key][0]
                                                - tx.fight.actors[key].hp,
                                            )
                                            for key, value in current.actors.items()
                                        },
                                    ),
                                )
                                return
                        advance_actual_turn(runtime)
                        continue
                    if (
                        stabilization_component or window_component
                    ) and identity in characters:
                        is_stabilizer = characters[identity]["breed"] == 1 or (
                            window_component and not receipt["stabilization_casts"]
                        )
                        if is_stabilizer:
                            stabilizer_reference = 4790 if window_component else 6985

                            def preserves_back_path(cell, approach):
                                # Keep Actor/QI in their actual current state.
                                # Coordinate planning validates the combined
                                # native path from that unchanged actor origin.
                                return (
                                    back_path(
                                        current,
                                        identity,
                                        require_back=True,
                                        maximum_range=1,
                                        require_los=True,
                                        actor_authority=planning_authority,
                                        origin=cell,
                                        movement_prefix=approach,
                                        mp_reserve=1 if endgame_component else 0,
                                    )
                                    is not None
                                )

                            path = back_path(
                                current,
                                identity,
                                require_back=False,
                                maximum_range=3 if window_component else 1,
                                require_los=True,
                                actor_authority=planning_authority,
                                require_linear=window_component,
                                goal_predicate=preserves_back_path
                                if window_component
                                else None,
                            )
                            if path is not None:
                                if path:
                                    origin, mp = (
                                        current.actors[identity].position,
                                        current.actors[identity].mp,
                                    )
                                    apply_client(
                                        runtime,
                                        current.actors[identity].owner_id,
                                        struct.pack(">q", identity)
                                        + b"".join(
                                            struct.pack(">iih", *cell) for cell in path
                                        ),
                                        lambda value: stats(value, runtime.fight),
                                        runtime_stats_serializer=stats,
                                        area_provider=lambda candidate, **kw: prepare_area_movement(
                                            characters[first],
                                            monsters,
                                            candidate,
                                            decks[first],
                                            **common,
                                            **kw,
                                        ),
                                    )
                                    receipt["movements"].append(
                                        dict(
                                            actor=identity,
                                            origin=origin,
                                            destination=runtime.fight.actors[
                                                identity
                                            ].position,
                                            before_mp=mp,
                                            after_mp=runtime.fight.actors[identity].mp,
                                        )
                                    )
                                current = runtime.fight
                                actor, boss = (
                                    current.actors[identity],
                                    current.actors[-200],
                                )
                                before_ap, before_wp = actor.ap, actor.effect_stats[4]
                                active_preview.update(
                                    reference=stabilizer_reference,
                                    kind="paid_stabilization",
                                )
                                transaction = prepare_server_spell(
                                    struct.pack(
                                        ">qqiih",
                                        identity,
                                        (identity << 32) | stabilizer_reference,
                                        *boss.position,
                                    ),
                                    characters[identity],
                                    monsters,
                                    current,
                                    characters[identity]["account_id"],
                                    decks[identity],
                                    action_id=runtime.action_id + 1,
                                    critical=None,
                                    **common,
                                    line_of_sight=lambda origin, target, phase: authoritative_visible(
                                        1229,
                                        origin,
                                        target,
                                        phase,
                                        blocking_footprints={
                                            a.id: footprint(
                                                a.position, a.physical_radius
                                            )
                                            for a in phase.actors.values()
                                            if a.hp > 0
                                        },
                                    ),
                                )
                                self.assertEqual(
                                    transaction.plan["costs"]["ap"],
                                    2 if window_component else 4,
                                )
                                self.assertEqual(
                                    transaction.plan["costs"]["wp"],
                                    0 if window_component else 1,
                                )
                                commit_spell_transaction(
                                    runtime, transaction, stats_serializer=stats
                                )
                                target = runtime.fight.actors[-200]
                                self.assertIn(
                                    11,
                                    planning_authority.properties(
                                        runtime.fight, target
                                    ),
                                )
                                if window_component:
                                    self.assertTrue(
                                        any(
                                            row.reference == 2871 and row.level == 50
                                            for row in target.state_ledger.entries
                                        )
                                    )
                                receipt["stabilization_casts"].append(
                                    dict(
                                        actor=identity,
                                        reference=stabilizer_reference,
                                        before_ap=before_ap,
                                        after_ap=runtime.fight.actors[identity].ap,
                                        before_wp=before_wp,
                                        after_wp=runtime.fight.actors[
                                            identity
                                        ].effect_stats[4],
                                        native_costs=transaction.plan["costs"],
                                        target_property11=True,
                                        target_states=[
                                            (row.reference, row.level)
                                            for row in target.state_ledger.entries
                                        ],
                                        table=getattr(
                                            runtime.fight, "native_table_turn", None
                                        ),
                                    )
                                )
                            if not window_component:
                                advance_actual_turn(runtime)
                                continue
                        if not receipt["stabilization_casts"]:
                            advance_actual_turn(runtime)
                            continue
                    phase_entry_pending = characteristic_percentage(
                        boss.hp, boss.max_hp
                    ) <= 80 and (
                        receipt.get("back_eighty_percent_gate_removed", False)
                        or not any(
                            entry.reference == 5650
                            for entry in boss.state_ledger.entries
                        )
                    )
                    if identity in characters and not phase_entry_pending:
                        for _ in range(8):
                            current = runtime.fight
                            actor, boss = current.actors[identity], current.actors[-200]
                            grants = granted_spells(current, identity)
                            auxiliaries = tuple(
                                reference
                                for reference in (8403, 8402)
                                if reference in grants
                                and (not endgame_component or reference != 8402)
                                and (
                                    actor.effect_stats[4] > 0
                                    if reference == 8403
                                    else actor.mp > 0
                                )
                            )
                            if actor.hp <= 0 or (actor.ap < 2 and not auxiliaries):
                                break
                            invulnerable = any(
                                entry.reference == 5657
                                for entry in boss.state_ledger.entries
                            )
                            require_back = (
                                window_component
                                or invulnerable
                                or characteristic_percentage(boss.hp, boss.max_hp) <= 80
                            )
                            path = back_path(
                                current,
                                identity,
                                require_back=require_back,
                                maximum_range=1 if invulnerable and auxiliaries else 3,
                                require_los=True,
                                actor_authority=planning_authority,
                            )
                            if endgame_component and not invulnerable:
                                # Preserve original close-combat mastery before
                                # accepting a nearer-to-caster ranged fallback.
                                melee = back_path(
                                    current,
                                    identity,
                                    require_back=True,
                                    maximum_range=2,
                                    require_linear=True,
                                    require_los=True,
                                    actor_authority=planning_authority,
                                )
                                if (
                                    melee is None
                                    and characteristic_percentage(boss.hp, boss.max_hp)
                                    > 80
                                ):
                                    melee = back_path(
                                        current,
                                        identity,
                                        require_back=False,
                                        maximum_range=2,
                                        require_linear=True,
                                        require_los=True,
                                        actor_authority=planning_authority,
                                    )
                                if melee is not None:
                                    path = melee
                            if path is None and invulnerable and auxiliaries:
                                # A spent/blocked adjacent auxiliary position must
                                # not discard a still-legal ranged AP back hit.
                                path = back_path(
                                    current,
                                    identity,
                                    require_back=require_back,
                                    maximum_range=3,
                                    require_los=True,
                                    actor_authority=planning_authority,
                                )
                            if path is None and actor.ap >= 4:
                                # Original4781 explicitly ignores LOS in both
                                # casting branches. Do not impose another
                                # spell's LOS requirement on this paid option.
                                path = back_path(
                                    current,
                                    identity,
                                    require_back=require_back,
                                    maximum_range=3,
                                    require_los=False,
                                )
                            if path is None:
                                receipt["rejected"].append(
                                    dict(
                                        actor=identity,
                                        reason="No reachable attack cell matching available native casting options",
                                    )
                                )
                                break
                            if path:
                                origin, mp = actor.position, actor.mp
                                apply_client(
                                    runtime,
                                    actor.owner_id,
                                    struct.pack(">q", identity)
                                    + b"".join(
                                        struct.pack(">iih", *cell) for cell in path
                                    ),
                                    lambda value: stats(value, runtime.fight),
                                    runtime_stats_serializer=stats,
                                    area_provider=lambda candidate, **kw: prepare_area_movement(
                                        characters[first],
                                        monsters,
                                        candidate,
                                        decks[first],
                                        **common,
                                        **kw,
                                    ),
                                )
                                receipt["movements"].append(
                                    dict(
                                        actor=identity,
                                        origin=origin,
                                        destination=runtime.fight.actors[
                                            identity
                                        ].position,
                                        before_mp=mp,
                                        after_mp=runtime.fight.actors[identity].mp,
                                    )
                                )
                            current = runtime.fight
                            boss = current.actors[-200]
                            tx = None
                            rng_before = rng.getstate()
                            references = (
                                (*auxiliaries, 4780, 4777, 4781, 4789)
                                if invulnerable
                                else (
                                    (4777, 4780, 4781, 4789, *auxiliaries)
                                    if window_component
                                    else (4780, 4777, 4781, 4789, *auxiliaries)
                                )
                            )
                            comparing = (
                                damage_component
                                or (
                                    endgame_component
                                    and actor.ap >= 8
                                    and not receipt.get("endgame_preview")
                                )
                            ) and not invulnerable
                            if endgame_component and comparing:
                                references = (4777,)
                            options = []

                            def prepare(reference):
                                return prepare_server_spell(
                                    struct.pack(
                                        ">qqiih",
                                        identity,
                                        grants[reference]["uid"]
                                        if reference in grants
                                        else (identity << 32) | reference,
                                        *boss.position,
                                    ),
                                    characters[identity],
                                    monsters,
                                    current,
                                    characters[identity]["account_id"],
                                    decks[identity],
                                    action_id=runtime.action_id + 1,
                                    critical=None,
                                    **common,
                                    line_of_sight=lambda origin, target, phase: authoritative_visible(
                                        1229,
                                        origin,
                                        target,
                                        phase,
                                        blocking_footprints={
                                            a.id: footprint(
                                                a.position, a.physical_radius
                                            )
                                            for a in phase.actors.values()
                                            if a.hp > 0
                                        },
                                    ),
                                )

                            for reference in references:
                                rng.setstate(rng_before)
                                active_preview.update(
                                    reference=reference,
                                    kind="preview" if comparing else "paid_preparation",
                                )
                                try:
                                    proposal = prepare(reference)
                                except ValueError as error:
                                    receipt["rejected"].append(
                                        dict(
                                            actor=identity,
                                            spell=reference,
                                            reason=str(error),
                                        )
                                    )
                                else:
                                    if not comparing:
                                        tx = proposal
                                        break
                                    costs = proposal.plan["costs"]
                                    options.append(
                                        dict(
                                            reference=reference,
                                            damage=boss.hp
                                            - proposal.fight.actors[-200].hp,
                                            costs=costs,
                                            critical=proposal.plan.get("critical"),
                                        )
                                    )
                                finally:
                                    if comparing:
                                        rng.setstate(rng_before)
                                        self.assertEqual(rng.getstate(), rng_before)
                            if comparing and options:
                                from fractions import Fraction

                                # Compare one fixed native RNG state. Only the
                                # selected option is prepared again and paid.
                                chosen = max(
                                    options,
                                    key=lambda row: (
                                        Fraction(
                                            row["damage"],
                                            max(
                                                1,
                                                sum(
                                                    row["costs"].get(k, 0)
                                                    for k in ("ap", "mp", "wp")
                                                ),
                                            ),
                                        ),
                                        row["damage"],
                                    ),
                                )
                                receipt["option_previews"].append(
                                    dict(
                                        actor=identity,
                                        options=options,
                                        selected=chosen["reference"],
                                        rng_unchanged=rng.getstate() == rng_before,
                                        native_vulnerability=any(
                                            row.reference == 5661
                                            for row in boss.state_ledger.entries
                                        ),
                                    )
                                )
                                self.assertTrue(
                                    any(
                                        row.reference == 5661
                                        for row in boss.state_ledger.entries
                                    )
                                )
                                self.assertEqual(rng.getstate(), rng_before)
                                reference = chosen["reference"]
                                active_preview.update(
                                    reference=reference,
                                    kind="selected_paid_preparation",
                                )
                                tx = prepare(reference)
                                self.assertEqual(
                                    boss.hp - tx.fight.actors[-200].hp, chosen["damage"]
                                )
                                if endgame_component:
                                    self.assertEqual(chosen["costs"]["ap"], 4)
                                    self.assertGreater(chosen["damage"], 0)
                                    receipt["endgame_preview"] = dict(
                                        actor=identity, **chosen
                                    )
                            if tx is None:
                                rng.setstate(rng_before)
                                break
                            before = boss.hp
                            before_boss_position, before_boss_direction = (
                                boss.position,
                                boss.direction,
                            )
                            from wakfu_server.combat_ordinary_authority import (
                                native_facing,
                            )

                            before_facing = native_facing(
                                current.actors[identity], boss
                            )
                            stabilized = 11 in planning_authority.properties(
                                current, boss
                            )
                            ap = current.actors[identity].ap
                            mp, wp = (
                                current.actors[identity].mp,
                                current.actors[identity].effect_stats[4],
                            )
                            costs = tx.plan["costs"]
                            commit_spell_transaction(
                                runtime, tx, stats_serializer=stats
                            )
                            receipt["paid_hits"].append(
                                dict(
                                    actor=identity,
                                    spell=reference,
                                    before_hp=before,
                                    after_hp=runtime.fight.actors[-200].hp,
                                    before_ap=ap,
                                    after_ap=runtime.fight.actors[identity].ap,
                                    before_mp=mp,
                                    after_mp=runtime.fight.actors[identity].mp,
                                    before_wp=wp,
                                    after_wp=runtime.fight.actors[
                                        identity
                                    ].effect_stats[4],
                                    native_costs=costs,
                                    temporary_grant_uid=grants.get(reference, {}).get(
                                        "uid"
                                    ),
                                    table=getattr(
                                        runtime.fight, "native_table_turn", None
                                    ),
                                    before_boss_position=before_boss_position,
                                    after_boss_position=runtime.fight.actors[
                                        -200
                                    ].position,
                                    before_boss_direction=before_boss_direction,
                                    boss_direction=runtime.fight.actors[-200].direction,
                                    boss_max_hp=runtime.fight.actors[-200].max_hp,
                                    before_facing=before_facing,
                                    target_stabilized=stabilized,
                                    after_facing=native_facing(
                                        runtime.fight.actors[identity],
                                        runtime.fight.actors[-200],
                                    ),
                                    states=[
                                        (e.reference, e.level)
                                        for e in runtime.fight.actors[
                                            -200
                                        ].state_ledger.entries
                                    ],
                                )
                            )
                            self.assertGreater(
                                sum(
                                    costs.get(resource, 0)
                                    for resource in ("ap", "mp", "wp")
                                ),
                                0,
                            )
                            if reference in (8402, 8403):
                                self.assertEqual(costs.get("ap", 0), 0)
                                self.assertEqual(
                                    costs.get("mp" if reference == 8402 else "wp", 0), 1
                                )
                                self.assertIn(reference, grants)
                            phase_boss = runtime.fight.actors[-200]
                            if (
                                before_facing == "BACK"
                                and characteristic_percentage(
                                    phase_boss.hp, phase_boss.max_hp
                                )
                                <= 80
                                and any(
                                    row["reference"] == 266532
                                    and row["result"]
                                    and row["turn"] == runtime.fight.turn_id
                                    for row in receipt["source_events"]
                                )
                            ):
                                receipt["back_eighty_percent_gate_removed"] = True
                            if stabilization_component and invulnerable and stabilized:
                                self.assertEqual(
                                    phase_boss.direction, before_boss_direction
                                )
                                self.assertEqual(
                                    phase_boss.position, before_boss_position
                                )
                            if deadline_only and phase_boss.hp < before:
                                break
                            if comparing:
                                if stabilization_component:
                                    self.assertTrue(receipt["stabilization_casts"])
                                    back_hits = [
                                        row
                                        for row in receipt["paid_hits"]
                                        if row["before_facing"] == "BACK"
                                    ]
                                    self.assertGreaterEqual(len(back_hits), 4)
                                    self.assertTrue(
                                        all(
                                            row["target_stabilized"]
                                            for row in back_hits
                                        )
                                    )
                                self.assertLess(phase_boss.hp, before)
                                if not endgame_component:
                                    receipt[
                                        "status"
                                    ] = "first_native_vulnerability_damage_attributed_and_paid"
                                    return
                            if endgame_component:
                                budget = [
                                    row
                                    for row in receipt["paid_hits"]
                                    if row["actor"] == identity and row["spell"] == 4777
                                ]
                                if (
                                    len(budget) == 2
                                    and "endgame_two_hit_budget" not in receipt
                                ):
                                    self.assertTrue(
                                        all(
                                            row["before_facing"] == "BACK"
                                            for row in budget
                                        )
                                    )
                                    self.assertEqual(
                                        sum(
                                            row["native_costs"]["ap"] for row in budget
                                        ),
                                        8,
                                    )
                                    receipt["endgame_two_hit_budget"] = dict(
                                        actor=identity,
                                        damage=sum(
                                            row["before_hp"] - row["after_hp"]
                                            for row in budget
                                        ),
                                        paid_ap=8,
                                        before_ap=budget[0]["before_ap"],
                                        after_ap=budget[-1]["after_ap"],
                                    )
                            if characteristic_percentage(
                                phase_boss.hp, phase_boss.max_hp
                            ) <= 80 and (
                                receipt.get("back_eighty_percent_gate_removed", False)
                                or not any(
                                    entry.reference == 5650
                                    for entry in phase_boss.state_ledger.entries
                                )
                            ):
                                # Let the real boss start/end produce its clock;
                                # extra attacks during the phase handoff waste
                                # the original three-turn damage/WP window.
                                break
                            if runtime.fight.phase != "active":
                                break
                    if (
                        endgame_component
                        and identity in characters
                        and runtime.fight.phase == "active"
                    ):
                        current = runtime.fight
                        actor, boss = current.actors[identity], current.actors[-200]
                        if (
                            sum(
                                abs(a - b)
                                for a, b in zip(actor.position, boss.position)
                            )
                            == 1
                            and actor.mp > 0
                        ):
                            upcoming = (
                                current.order[current.turn_index + 1 :]
                                + current.order[: current.turn_index]
                            )
                            next_owner = next(
                                (
                                    key
                                    for key in upcoming
                                    if key in characters
                                    and key != identity
                                    and current.actors[key].hp > 0
                                ),
                                None,
                            )
                            candidates = []
                            for origin, destination in current.edges:
                                if origin != actor.position:
                                    continue
                                try:
                                    candidate = deepcopy(current)
                                    candidate.move(
                                        actor.owner_id, identity, (destination,)
                                    )
                                except ValueError:
                                    continue
                                distance = (
                                    0
                                    if next_owner is None
                                    else sum(
                                        abs(a - b)
                                        for a, b in zip(
                                            destination,
                                            current.actors[next_owner].position,
                                        )
                                    )
                                )
                                candidates.append((distance, destination))
                            if candidates:
                                _, destination = max(candidates)
                                origin, before_mp, before_ap = (
                                    actor.position,
                                    actor.mp,
                                    actor.ap,
                                )
                                apply_client(
                                    runtime,
                                    actor.owner_id,
                                    struct.pack(">qiih", identity, *destination),
                                    lambda value: stats(value, runtime.fight),
                                    runtime_stats_serializer=stats,
                                    area_provider=lambda candidate, **kw: prepare_area_movement(
                                        characters[first],
                                        monsters,
                                        candidate,
                                        decks[first],
                                        **common,
                                        **kw,
                                    ),
                                )
                                receipt["movements"].append(
                                    dict(
                                        actor=identity,
                                        origin=origin,
                                        destination=destination,
                                        before_mp=before_mp,
                                        after_mp=runtime.fight.actors[identity].mp,
                                        before_ap=before_ap,
                                        after_ap=runtime.fight.actors[identity].ap,
                                        next_owner=next_owner,
                                        reason="vacate_melee_away_from_next_owner_approach",
                                    )
                                )
                    if (
                        runtime.fight.phase == "active"
                        and runtime.fight.current is not None
                    ):
                        advance_actual_turn(runtime)
                self.fail(
                    (
                        "Native endgame earned phase did not qualify within40actualboundaries: "
                        if endgame_component
                        else "First window/deadline component did not qualify within24actualboundaries: "
                        if window_component
                        else "First vulnerability damage component did not qualify within12actualboundaries: "
                        if damage_component
                        else "Paid Ombrage strategy did not reach original clock within48actualboundaries: "
                    )
                    + repr(receipt["boundaries"][-1])
                )
        except Exception as error:
            import traceback

            receipt.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            try:
                if hasattr(self, "ombrage_live"):
                    self.ombrage_live["admission_component_active"] = False
                    verifier = self.ombrage_live.get("loaded_implementation_verifier")
                    if verifier is not None:
                        receipt["loaded_implementation_attestation"] = verifier()
            finally:
                if OMBRAGE_HOLD_ACTUAL_CHECKPOINT and hasattr(self, "ombrage_live"):
                    OMBRAGE_ACTUAL_CHECKPOINT = self.ombrage_live
                    OMBRAGE_ACTUAL_CHECKPOINT["cleanups"] = self._cleanups
                    self._cleanups = []
                    receipt["retained_live_objects_and_isolated_store"] = True
                output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
