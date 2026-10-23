"""Historical Rushu role diagnostics and bounded original-effect components.

The original player0/boss1 Growl and naked6150 terminal premises are preserved
as explicitly invoked diagnostics. Current player1/boss0 acceptance lives in
test_rushu_prepared_native_terminal.py.
"""
from pathlib import Path
from datetime import datetime, timezone
from random import Random
import json
import struct
import time
import traceback
import unittest
from unittest.mock import patch


class RushuReconstructedNativePhaseTests(unittest.TestCase):
    def diagnose_historical_player0_vestiges_and_growl(self):
        self._run_recipe()

    def diagnose_historical_naked6150_zero_score_terminal(self):
        self._run_recipe(terminal=True)

    def diagnose_native_7293_resource_branch(self):
        self._run_recipe(component=7293)

    def diagnose_native_7293_with_original_growl_area(self):
        self._run_recipe(component=7293, component_area=True)

    def diagnose_native_324818_with_original_growl_area(self):
        self._run_recipe(component=324818, component_area=True)

    def diagnose_native_7295_with_original_growl_area(self):
        self._run_recipe(component=7295, component_area=True)

    def diagnose_native_325743_leaf_on_original_growl(self):
        self._run_recipe(component=325743, component_area=True)

    def diagnose_real_player_7271_release_observation(self):
        self._run_recipe(drop_probe=True)

    def diagnose_paid_7009_off_axis_native_7295(self):
        self._run_recipe(defense_probe=True)

    def _run_recipe(
        self,
        *,
        terminal=False,
        component=None,
        component_area=False,
        drop_probe=False,
        defense_probe=False
    ):
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_tank_witness_fixture import native_tank_fixture
        from test_ultimate_encounter_scene_recipes import (
            UltimateEncounterSceneRecipeTests,
        )
        from ultimate_encounter_scene_recipes import encounter_fixture_factory
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_effective_control import effective_server_controlled
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_rushu_scene_layout import reconstructed_scene
        from wakfu_server.combat_rushu_encounter_setup import (
            install_rushu_encounter_setup,
            POLICY,
        )
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_reproduction_state import encode_state, decode_state
        from collections import deque
        from copy import deepcopy

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/ultimate-scenes-20261021"
            / ("rushu-reconstructed-native-phase-" + stamp + ".json")
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        receipt = dict(
            status="pending",
            boundaries=[],
            callbacks=[],
            events=[],
            defense=[],
            acknowledgements=[],
            movements=[],
        )
        boundary_output = output.with_suffix(".boundaries.jsonl")
        started_at = time.monotonic()
        receipt["boundary_journal"] = str(boundary_output)
        selected = {
            324322,
            324427,
            324430,
            319077,
            319078,
            319079,
            319183,
            323843,
            324323,
            324324,
            324325,
            324326,
            324486,
            324489,
            325500,
            319402,
            319410,
            319413,
            325750,
        }
        execute = EffectDispatcher.execute
        replay = NativeEventReplay.__call__

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in selected:
                receipt["callbacks"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        level=invocation.level,
                        result=result,
                        turn_id=dispatcher.native_retention.fight.turn_id,
                    )
                )
            return result

        def observe_event(replay_runtime, event, **kwargs):
            result = replay(replay_runtime, event, **kwargs)
            if 1037 in event.event_ids or 2243 in event.event_ids:
                receipt["events"].append(
                    dict(
                        manager=event.manager_actor_id,
                        event_ids=event.event_ids,
                        outcomes=list(result),
                        turn_id=replay_runtime.retention.fight.turn_id,
                    )
                )
            return result

        try:
            geometry = json.loads(
                (
                    Path(__file__).parent
                    / "fixtures/ultimate_encounter_scene_recipes.json"
                ).read_text()
            )["maps"]["1332"]
            scene = reconstructed_scene(geometry)
            scene["level"] = 230
            tank, facts = native_tank_fixture(validator, feca=True)
            fixture, preparation = encounter_fixture_factory(
                validator,
                scene,
                player_level=200,
                player_breed=1,
                player_deck=[6972],
                caster_cell=scene["source"],
                production_bootstrap=True,
                character_constructor=tank.__globals__["_healthy_owned_character"],
            )
            receipt.update(scene=preparation, player_fixture=facts)
            with original_bootstrap_publication():
                fight, character, monsters, deck = fixture(
                    5306,
                    scene["level"],
                    scene["anchor"],
                    native_lifecycle=False,
                )
            source = snapshot(fight)
            staged = deepcopy(fight)
            factory, _ = server_runtime(
                character, monsters, deck, action_id=1, critical=False, rng=Random(0)
            )
            dispatcher, packets = factory(
                staged, {"native_retained_container": {"present": False}}
            )
            self.assertTrue(
                install_rushu_encounter_setup(
                    dispatcher,
                    map_id=1332,
                    monsters=monsters,
                    layout=scene,
                    seed=fight.id,
                )
            )
            self.assertEqual(snapshot(fight), source)
            glyphs = [
                row
                for row in staged.native_effect_areas.values()
                if row["reference"] in {1650, *range(1652, 1667)}
            ]
            self.assertEqual(len(glyphs), 16)
            self.assertEqual(
                {row["reference"] for row in glyphs}, {1650, *range(1652, 1667)}
            )
            self.assertFalse(
                install_rushu_encounter_setup(
                    dispatcher,
                    map_id=1332,
                    monsters=monsters,
                    layout=scene,
                    seed=fight.id,
                )
            )
            self.assertTrue(packets)
            self.assertEqual(staged.native_border_constructor["reference"], 378)
            self.assertTrue(
                any(
                    row["reference"] == 378
                    for row in staged.native_effect_areas.values()
                )
            )
            self.assertFalse(
                any(
                    row["reference"] == 910
                    for row in staged.native_effect_areas.values()
                )
            )
            # The fixture holds a PublicationLease outside the reproduction
            # value graph. Qualify the new plain receipt without claiming the
            # unrelated live publication handle can be serialized.
            restored = deepcopy(staged)
            restored.native_encounter_area_setups = decode_state(
                json.loads(
                    json.dumps(encode_state(staged.native_encounter_area_setups))
                )
            )
            self.assertEqual(
                staged.native_encounter_area_setups,
                restored.native_encounter_area_setups,
            )
            restored_dispatcher, restored_packets = factory(
                restored, {"native_retained_container": {"present": False}}
            )
            self.assertFalse(
                install_rushu_encounter_setup(
                    restored_dispatcher,
                    map_id=1332,
                    monsters=monsters,
                    layout=scene,
                    seed=fight.id,
                )
            )
            self.assertFalse(restored_packets)
            receipt["setup"] = deepcopy(staged.native_encounter_area_setups[POLICY])
            target = next(
                tuple(row["cell"])
                for row in staged.native_effect_areas.values()
                if row["reference"] == 1666
            )
            if defense_probe:
                target = (-39, 5, -4)
                self.assertIn(target, scene["cells"])
                self.assertNotIn(target, {tuple(row["cell"]) for row in glyphs})
            # Exercise production setup from a fresh original preview too;
            # the direct constructor branch above verifies typed receipt/replay.
            original = deepcopy(fight)
            self.assertEqual(
                original.native_encounter_scene_layout["terrain_effect_id"], 378
            )
            fight, initial_packets = prepare_server_initialization(
                character,
                monsters,
                original,
                character["account_id"],
                deck,
                action_id=2,
                rng=Random(0),
                fight_start=True,
                player_characters={7: character},
                deck_blobs={7: deck},
            )
            receipt["initial_packets"] = len(initial_packets)
            receipt["score_profile"] = deepcopy(
                getattr(fight, "boss_score_profile", None)
            )
            self.assertEqual((fight.actors[7].hp, fight.actors[7].max_hp), (6150, 6150))
            self.assertEqual(character["breed"], 1)
            self.assertEqual(character["map_id"], 1332)
            self.assertEqual(fight.actors[7].team, 0)
            self.assertEqual(fight.actors[-200].team, 1)
            self.assertIn(
                7000, {e.reference for e in fight.actors[-200].state_ledger.entries}
            )
            self.assertTrue(fight.walkable <= scene["cells"])
            rng = Random(0)
            if component is not None:
                # Explicit component diagnostic: execute the installed internal
                # ability without publishing phase events or changing tables.
                from wakfu_server.combat_triggered_spell import (
                    native_triggered_spell_request,
                )
                from wakfu_server.combat_effect_dispatch import EffectInvocation
                from wakfu_server.combat_maximum_resource import (
                    NativeMaximumReductionHandler,
                )

                component_dispatcher, component_packets = factory(
                    fight, {"native_retained_container": {"present": False}}
                )
                if component_area:
                    before_areas = set(fight.native_effect_areas)
                    with fight.effect_resolution():
                        component_dispatcher.execute(
                            EffectInvocation(
                                323843,
                                fight.actors[7].effective_level,
                                7,
                                None,
                                (-40, 6, -4),
                                native_retained_container={"present": False},
                                native_preselected_target=True,
                                native_target_cell_argument=True,
                            )
                        )
                    receipt["component_area_uids"] = sorted(
                        set(fight.native_effect_areas) - before_areas
                    )
                    self.assertTrue(receipt["component_area_uids"])
                    self.assertTrue(
                        any(
                            fight.native_effect_areas[uid]["reference"] == 1688
                            for uid in receipt["component_area_uids"]
                        )
                    )
                if component == 325743:
                    # Direct typed-target leaf diagnostic. The full internal
                    # ability may kill the PC before its global iterator reaches
                    # a faW; this probe makes no global-order or phase claim.
                    target_uid = next(
                        uid
                        for uid in receipt["component_area_uids"]
                        if fight.native_effect_areas[uid]["reference"] == 1688
                    )
                    row = fight.native_effect_areas[target_uid]
                    receipt["component"] = dict(
                        reference=325743,
                        table_before=fight.native_table_turn,
                        scope="explicit_native_leaf_on_registered_faw_no_phase_or_selector_claim",
                        target=target_uid,
                        target_reference=row["reference"],
                        target_contract=row["native_area_contract"],
                        target_hp_before=row["native_faw_hp_current"],
                        player_hp_before=fight.actors[7].hp,
                    )
                    with fight.effect_resolution():
                        result = component_dispatcher.execute(
                            EffectInvocation(
                                325743,
                                1,
                                -200,
                                target_uid,
                                tuple(row["cell"]),
                                native_preselected_target=True,
                                native_retained_container={"present": False},
                            )
                        )
                    receipt["component"].update(
                        result=result,
                        target_hp_after=row["native_faw_hp_current"],
                        player_hp_after=fight.actors[7].hp,
                    )
                    self.assertIs(result, True)
                    self.assertEqual(
                        fight.actors[7].hp, receipt["component"]["player_hp_before"]
                    )
                    self.assertEqual(
                        fight.native_table_turn, receipt["component"]["table_before"]
                    )
                    receipt["status"] = "actual_registered_faw_damage_leaf_only"
                    return
                if component == 324818:
                    # Isolate the actual selected current-stat leaf. Its
                    # table15 parent is intentionally not forged or published.
                    from wakfu_server.combat_stat_handler import NativeStatHandler

                    stat_prepare = NativeStatHandler.prepare
                    boss = fight.actors[-200]
                    receipt["component"] = dict(
                        reference=324818,
                        table_before=fight.native_table_turn,
                        invocations=[],
                        scope="native_leaf_only_no_phase_progression",
                    )

                    def inspect_stat(owner, definition, values, source):
                        row = owner.fight.native_effect_areas.get(source.target_id)
                        receipt["component"]["invocations"].append(
                            dict(
                                reference=source.reference,
                                caster=source.caster_id,
                                target=source.target_id,
                                target_area=None
                                if row is None
                                else dict(
                                    reference=row["reference"],
                                    contract=row.get("native_area_contract"),
                                    owner=row.get("owner_id"),
                                    cell=row["cell"],
                                ),
                            )
                        )
                        return stat_prepare(owner, definition, values, source)

                    with patch.object(NativeStatHandler, "prepare", inspect_stat):
                        with fight.effect_resolution():
                            component_dispatcher.execute(
                                EffectInvocation(
                                    324818,
                                    1,
                                    boss.id,
                                    boss.id,
                                    boss.position,
                                    native_retained_container={"present": False},
                                )
                            )
                    self.assertEqual(
                        fight.native_table_turn, receipt["component"]["table_before"]
                    )
                    self.assertTrue(
                        any(
                            row["target_area"] is not None
                            for row in receipt["component"]["invocations"]
                        )
                    )
                    receipt[
                        "status"
                    ] = "internal_component_only_no_phase_progression_claim"
                    return
                handler = component_dispatcher.handlers[426].native_wrapped_handler
                creator_reference = {7293: 324324, 7295: 324326}[component]
                effect = component_dispatcher.effects[str(creator_reference)]
                boss = fight.actors[-200]
                native = handler.authority(fight, boss)
                request = native_triggered_spell_request(
                    effect["parameters"],
                    1,
                    caster_id=boss.id,
                    target_cell=boss.position,
                    caster_is_native_fighter=native.targeting["is_eGj"],
                )
                invocation = EffectInvocation(
                    creator_reference,
                    1,
                    boss.id,
                    boss.id,
                    boss.position,
                    native_retained_container={"present": False},
                )
                receipt["component"] = dict(
                    spell=component,
                    table_before=fight.native_table_turn,
                    invocations=[],
                )
                reduction = NativeMaximumReductionHandler.__call__
                from wakfu_server.combat_damage_handler import NativeDamageHandler

                damage_call = NativeDamageHandler.__call__
                from wakfu_server import combat_wall_area

                original_wall = combat_wall_area.verified_wall_constructor

                def inspect_wall(row, definition, **kwargs):
                    receipt["component"]["wall_constructors"] = receipt[
                        "component"
                    ].get("wall_constructors", []) + [
                        dict(
                            uid=row.get("uid"),
                            reference=row.get("reference"),
                            contract=row.get("native_area_contract"),
                            native_type_id=row.get("native_type_id"),
                            native_running_effect_manager=row.get(
                                "native_running_effect_manager"
                            ),
                            constructor=row.get("native_wall_constructor"),
                            definition_type=definition.get("type"),
                            definition_class=definition.get("native_class"),
                            definition_reference=definition.get("reference"),
                        )
                    ]
                    return original_wall(row, definition, **kwargs)

                def inspect_reduction(owner, definition, values, source):
                    receipt["component"]["invocations"].append(
                        dict(
                            reference=source.reference,
                            caster=source.caster_id,
                            target=source.target_id,
                            cell=source.cell,
                            caster_area=source.caster_id in fight.native_effect_areas,
                            target_area=source.target_id in fight.native_effect_areas,
                        )
                    )
                    return reduction(owner, definition, values, source)

                def inspect_damage(owner, definition, values, source):
                    row = owner.fight.native_effect_areas.get(source.target_id)
                    actor = owner.fight.actors.get(source.target_id)
                    observed = dict(
                        reference=source.reference,
                        target=source.target_id,
                        contract=None
                        if row is None
                        else row.get("native_area_contract"),
                        area_reference=None if row is None else row.get("reference"),
                        hp_before=(
                            actor.hp
                            if actor is not None
                            else None
                            if row is None
                            else row.get("native_faw_hp_current")
                        ),
                    )
                    receipt["component"].setdefault("damage_invocations", []).append(
                        observed
                    )
                    result = damage_call(owner, definition, values, source)
                    observed.update(
                        result=result,
                        hp_after=(
                            actor.hp
                            if actor is not None
                            else None
                            if row is None
                            else row.get("native_faw_hp_current")
                        ),
                    )
                    return result

                with patch.object(
                    NativeMaximumReductionHandler, "__call__", inspect_reduction
                ), patch.object(
                    combat_wall_area, "verified_wall_constructor", inspect_wall
                ), patch.object(
                    NativeDamageHandler, "__call__", inspect_damage
                ):
                    with fight.effect_resolution():
                        handler.executor(request, effect, invocation)
                if component == 7295:
                    self.assertTrue(
                        any(
                            row["contract"] == "faW"
                            and row["area_reference"] == 1688
                            and row.get("result") is True
                            for row in receipt["component"].get(
                                "damage_invocations", ()
                            )
                        ),
                        receipt["component"],
                    )
                self.assertEqual(
                    fight.native_table_turn, receipt["component"]["table_before"]
                )
                receipt["status"] = "internal_component_only_no_phase_progression_claim"
                return

            def stats(actor, current):
                if getattr(actor, "native_summon_source", None) is not None:
                    return registered_summon_stats(actor, current, 1332)
                values = dict(
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                    fight=current,
                )
                if actor.controlled:
                    return actual_actor_stats(character, actor, current.id, **values)
                return actual_monster_actor_stats(
                    monsters[actor.id], actor, current.id, **values
                )

            runtime = RuntimeMessages(
                fight,
                runtime_stats_serializer=stats,
                turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                    character,
                    monsters,
                    p,
                    deck,
                    rng=rng,
                    native_events=True,
                    area_callbacks=True,
                    **kw
                ),
                turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                    character, monsters, p, deck, rng=rng, **kw
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    character,
                    monsters,
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            with patch.object(EffectDispatcher, "execute", observe), patch.object(
                NativeEventReplay,
                "__call__",
                observe_event,
            ):
                runtime.turn_started()
                for _boundary in range(64):
                    for _ack in range(32):
                        if runtime.awaiting_ack is None:
                            break
                        barrier = runtime.awaiting_ack
                        runtime.acknowledge_turn(struct.pack(">i", barrier))
                        receipt["acknowledgements"].append(barrier)
                    else:
                        self.fail("Native Rushu ACK chain exceeded32 barriers")
                    current = runtime.fight
                    # Preserve progress even if a later native callback takes
                    # minutes or rejects. This observes; it never advances play.
                    with boundary_output.open("a") as journal:
                        journal.write(
                            json.dumps(
                                dict(
                                    elapsed_seconds=round(
                                        time.monotonic() - started_at, 3
                                    ),
                                    turn_id=current.turn_id,
                                    table_turn=getattr(
                                        current, "native_table_turn", None
                                    ),
                                    phase=current.phase,
                                    current_id=None
                                    if current.current is None
                                    else current.current.id,
                                    areas=len(current.native_effect_areas),
                                    player_hp=current.actors[7].hp,
                                    boss_hp=current.actors[-200].hp,
                                )
                            )
                            + "\n"
                        )
                    receipt["boundaries"].append(
                        dict(
                            turn_id=current.turn_id,
                            table_turn=getattr(current, "native_table_turn", None),
                            phase=current.phase,
                            current_id=None
                            if current.current is None
                            else current.current.id,
                            actors={
                                str(actor.id): dict(
                                    hp=actor.hp,
                                    max_hp=actor.max_hp,
                                    team=actor.team,
                                    position=actor.position,
                                    resources={
                                        str(key): actor.effect_stats[key]
                                        for key in (2, 3, 4)
                                    },
                                    states=[
                                        (entry.reference, entry.level)
                                        for entry in actor.state_ledger.entries
                                    ],
                                    grants=list(granted_spells(current, actor.id)),
                                )
                                for actor in current.actors.values()
                            },
                            areas=[
                                dict(reference=row["reference"], cell=row["cell"])
                                for row in current.native_effect_areas.values()
                            ],
                        )
                    )
                    positive = any(
                        row["reference"] == 323843
                        and row["caster"] == 7
                        and row["result"]
                        for row in receipt["callbacks"]
                    )
                    if (
                        drop_probe
                        and positive
                        and current.current is not None
                        and current.current.id == 7
                    ):
                        actor = current.current
                        occupied = {
                            point
                            for other in current.actors.values()
                            if other.hp > 0
                            for point in footprint(
                                other.position, other.physical_radius
                            )
                        }
                        area_columns = {
                            tuple(point)
                            for row in current.native_effect_areas.values()
                            for point in row.get("native_cells_xy", ())
                        }
                        cells = sorted(
                            end
                            for start, end in current.edges
                            if start == actor.position
                            and end[:2] not in occupied
                            and end[:2] not in area_columns
                        )
                        self.assertTrue(cells, "No legal adjacent release target")
                        self.assertIn(7271, granted_spells(current, actor.id))
                        receipt["drop_observation"] = dict(
                            target=cells[0],
                            table_turn=current.native_table_turn,
                            states_before=[
                                (entry.reference, entry.level)
                                for entry in actor.state_ledger.entries
                            ],
                            area_uids_before=sorted(current.native_effect_areas),
                        )
                        tx = prepare_server_spell(
                            struct.pack(">qqiih", actor.id, 7271, *cells[0]),
                            character,
                            monsters,
                            current,
                            actor.owner_id,
                            deck,
                            action_id=runtime.action_id + 1,
                            line_of_sight=lambda origin, target, state: authoritative_visible(
                                1332,
                                origin,
                                target,
                                state,
                                blocking_footprints={
                                    a.id: footprint(a.position, a.physical_radius)
                                    for a in state.actors.values()
                                    if a.hp > 0
                                },
                            ),
                            critical=False,
                            rng=rng,
                        )
                        commit_spell_transaction(runtime, tx, stats_serializer=stats)
                        after = runtime.fight
                        states_after = [
                            (entry.reference, entry.level)
                            for entry in after.actors[7].state_ledger.entries
                        ]
                        released = not any(
                            reference == 7025 and level <= 10
                            for reference, level in states_after
                        )
                        receipt["drop_observation"].update(
                            states_after=states_after,
                            costs=tx.plan["costs"],
                            released=released,
                            added_areas=[
                                dict(
                                    uid=uid,
                                    reference=row["reference"],
                                    cell=row["cell"],
                                )
                                for uid, row in after.native_effect_areas.items()
                                if uid
                                not in receipt["drop_observation"]["area_uids_before"]
                            ],
                        )
                        receipt["status"] = (
                            "actual_player_7271_released_vestige"
                            if released
                            else "actual_player_7271_committed_without_vestige_release"
                        )
                        return
                    if (
                        not terminal
                        and positive
                        and getattr(current, "native_table_turn", 0) >= 6
                    ):
                        break
                    if current.phase != "active" or current.current is None:
                        break
                    if getattr(current, "native_table_turn", 1) >= (
                        22 if terminal else 11
                    ):
                        break
                    actor = current.current
                    if (
                        actor.id == 7
                        and not any(
                            entry.reference == 6364
                            for entry in actor.state_ledger.entries
                        )
                        and 7009 in granted_spells(current, actor.id)
                        and actor.ap >= 2
                        and actor.effect_stats[4] >= 1
                    ):
                        before = snapshot(current)
                        tx = prepare_server_spell(
                            struct.pack(">qqiih", actor.id, 7009, *actor.position),
                            character,
                            monsters,
                            current,
                            actor.owner_id,
                            deck,
                            action_id=runtime.action_id + 1,
                            line_of_sight=lambda origin, target, state: authoritative_visible(
                                1332,
                                origin,
                                target,
                                state,
                                blocking_footprints={
                                    a.id: footprint(a.position, a.physical_radius)
                                    for a in state.actors.values()
                                    if a.hp > 0
                                },
                            ),
                            critical=False,
                            rng=rng,
                        )
                        self.assertEqual(snapshot(current), before)
                        self.assertEqual(
                            (tx.plan["costs"]["ap"], tx.plan["costs"]["wp"]), (2, 1)
                        )
                        commit_spell_transaction(runtime, tx, stats_serializer=stats)
                        receipt["defense"].append(
                            dict(turn_id=runtime.fight.turn_id, costs=tx.plan["costs"])
                        )
                        current = runtime.fight
                        actor = current.current
                    if actor.id == 7 and actor.position != target and actor.mp > 0:
                        occupied = {
                            point
                            for other in current.actors.values()
                            if other.id != 7 and other.hp > 0
                            for point in footprint(
                                other.position, other.physical_radius
                            )
                        }
                        previous = {actor.position: None}
                        pending = deque((actor.position,))
                        adjacency = {}
                        for start, end in sorted(current.edges):
                            adjacency.setdefault(start, []).append(end)
                        while pending and target not in previous:
                            cell = pending.popleft()
                            for end in adjacency.get(cell, ()):
                                if end not in previous and end[:2] not in occupied:
                                    previous[end] = cell
                                    pending.append(end)
                        self.assertIn(target, previous)
                        path = []
                        cursor = target
                        while previous[cursor] is not None:
                            path.append(cursor)
                            cursor = previous[cursor]
                        path.reverse()
                        path = path[: actor.mp]
                        old_position, old_mp = actor.position, actor.mp
                        apply_client(
                            runtime,
                            actor.owner_id,
                            struct.pack(">q", actor.id)
                            + b"".join(struct.pack(">iih", *cell) for cell in path),
                            lambda selected: stats(selected, runtime.fight),
                            runtime_stats_serializer=stats,
                            area_provider=lambda candidate, **boundary: prepare_area_movement(
                                character,
                                monsters,
                                candidate,
                                deck,
                                rng=rng,
                                **boundary
                            ),
                        )
                        receipt["movements"].append(
                            dict(
                                origin=old_position,
                                path=path,
                                old_mp=old_mp,
                                new_mp=runtime.fight.actors[7].mp,
                            )
                        )
                        current = runtime.fight
                        actor = current.current
                    if defense_probe and actor.id == 7 and actor.position == target:
                        from wakfu_server.combat_triggered_spell import (
                            native_triggered_spell_request,
                        )
                        from wakfu_server.combat_effect_dispatch import EffectInvocation
                        from wakfu_server.combat_damage_handler import (
                            NativeDamageHandler,
                        )

                        self.assertTrue(receipt["defense"])
                        self.assertTrue(receipt["movements"])
                        self.assertIn(
                            6364,
                            {entry.reference for entry in actor.state_ledger.entries},
                        )
                        self.assertNotIn(
                            7025,
                            {entry.reference for entry in actor.state_ledger.entries},
                        )
                        boss = current.actors[-200]
                        boss_count = next(
                            (
                                entry.level
                                for entry in boss.state_ledger.entries
                                if entry.reference == 7092
                            ),
                            None,
                        )
                        self.assertEqual(boss_count, 4)
                        defensive_factory, _ = server_runtime(
                            character,
                            monsters,
                            deck,
                            action_id=runtime.action_id + 1,
                            critical=False,
                            rng=rng,
                        )
                        defensive_dispatcher, _ = defensive_factory(
                            current, {"native_retained_container": {"present": False}}
                        )
                        internal = defensive_dispatcher.handlers[
                            426
                        ].native_wrapped_handler
                        effect = defensive_dispatcher.effects["324326"]
                        native = internal.authority(current, boss)
                        request = native_triggered_spell_request(
                            effect["parameters"],
                            1,
                            caster_id=boss.id,
                            target_cell=boss.position,
                            caster_is_native_fighter=native.targeting["is_eGj"],
                        )
                        invocation = EffectInvocation(
                            324326,
                            1,
                            boss.id,
                            boss.id,
                            boss.position,
                            native_retained_container={"present": False},
                        )
                        receipt["defensive_component"] = dict(
                            scope="paid_7009_and_real_off_axis_movement_then_native_internal7295",
                            table_before=current.native_table_turn,
                            player_hp_before=actor.hp,
                            player_position=actor.position,
                            boss_vestige_count=boss_count,
                            damage_invocations=[],
                        )
                        original_damage = NativeDamageHandler.__call__
                        from wakfu_server import combat_damage_handler as damage_module

                        original_amount = damage_module.damage_amount

                        def observe_amount(
                            base, family, source_stats, target_stats, **kwargs
                        ):
                            amount = original_amount(
                                base, family, source_stats, target_stats, **kwargs
                            )
                            receipt["defensive_component"].setdefault(
                                "damage_calculations", []
                            ).append(
                                dict(
                                    base=base,
                                    family=family,
                                    source_stats=dict(source_stats),
                                    target_stats=dict(target_stats),
                                    arithmetic=kwargs,
                                    calculated_amount=amount,
                                )
                            )
                            return amount

                        def observe_defensive_damage(
                            owner, definition, values, selected
                        ):
                            before_hp = owner.fight.actors[7].hp
                            result = original_damage(
                                owner, definition, values, selected
                            )
                            receipt["defensive_component"]["damage_invocations"].append(
                                dict(
                                    reference=selected.reference,
                                    target=selected.target_id,
                                    player_hp_before=before_hp,
                                    player_hp_after=owner.fight.actors[7].hp,
                                    result=result,
                                )
                            )
                            return result

                        with patch.object(
                            NativeDamageHandler, "__call__", observe_defensive_damage
                        ), patch.object(damage_module, "damage_amount", observe_amount):
                            with current.effect_resolution():
                                internal.executor(request, effect, invocation)
                        receipt["defensive_component"].update(
                            player_hp_after=current.actors[7].hp
                        )
                        self.assertEqual(
                            current.native_table_turn,
                            receipt["defensive_component"]["table_before"],
                        )
                        self.assertGreater(current.actors[7].hp, 0)
                        self.assertTrue(
                            any(
                                row["reference"] == 325743 and row["target"] == 7
                                for row in receipt["defensive_component"][
                                    "damage_invocations"
                                ]
                            )
                        )
                        receipt[
                            "status"
                        ] = "real_paid_defense_survived_native_internal7295_no_phase_claim"
                        return
                    if effective_server_controlled(current, actor):
                        runtime.end_server_turn(actor.id, current.turn_id)
                    else:
                        runtime.end_turn(
                            actor.owner_id, actor.id, current_wire_turn(current)
                        )
            self.assertTrue(receipt["defense"])
            self.assertTrue(receipt["movements"])
            self.assertGreaterEqual(getattr(runtime.fight, "native_table_turn", 0), 6)
            if terminal:
                from wakfu_server.maps.boss_score_runtime import staged_score

                self.assertEqual(staged_score(runtime.fight), 0)
                self.assertGreaterEqual(
                    getattr(runtime.fight, "native_table_turn", 0), 21
                )
                self.assertEqual(runtime.fight.phase, "finished")
                self.assertEqual(runtime.fight.winner, 1)
                self.assertFalse(
                    any(
                        entry.reference == 7110
                        for entry in runtime.fight.actors[-200].state_ledger.entries
                    )
                )
                self.assertTrue(
                    any(
                        area["reference"] == 1235
                        for row in receipt["boundaries"]
                        if row["table_turn"] >= 15
                        for area in row["areas"]
                    ),
                    "Native phase15 lava was never created",
                )
                self.assertTrue(
                    any(
                        row["reference"] == 325500 and row["result"]
                        for row in receipt["callbacks"]
                    ),
                    receipt["boundaries"][-1],
                )
                for reference in (319402, 319410, 319413, 325750):
                    self.assertTrue(
                        any(
                            row["reference"] == reference and row["result"]
                            for row in receipt["callbacks"]
                        ),
                        reference,
                    )
            else:
                self.assertEqual(runtime.fight.phase, "active")
                self.assertGreater(runtime.fight.actors[7].hp, 0)
            self.assertTrue(
                any(
                    row["table_turn"] == 5
                    and any(
                        state[0] == 7092 and state[1] > 0
                        for state in row["actors"]["-200"]["states"]
                    )
                    for row in receipt["boundaries"]
                )
            )
            before_replay = snapshot(runtime.fight)
            replay_dispatcher, replay_packets = factory(
                runtime.fight, {"native_retained_container": {"present": False}}
            )
            self.assertFalse(
                install_rushu_encounter_setup(
                    replay_dispatcher, map_id=1332, monsters=monsters, layout=scene
                )
            )
            self.assertFalse(replay_packets)
            self.assertEqual(snapshot(runtime.fight), before_replay)
            self.assertTrue(any(1037 in row["event_ids"] for row in receipt["events"]))
            self.assertTrue(
                any(
                    row["reference"] == 319078 and row["caster"] == 7 and row["result"]
                    for row in receipt["callbacks"]
                ),
                receipt["boundaries"][-1],
            )
            self.assertTrue(
                any(
                    row["reference"] == 323843 and row["caster"] == 7 and row["result"]
                    for row in receipt["callbacks"]
                ),
                receipt["callbacks"],
            )
            receipt["status"] = (
                "actual_native_phases_and_zero_score_failure_at_table21"
                if terminal
                else "actual_owner_growl_and_native_table5_guard_survived"
            )
        except Exception as error:
            receipt.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(limit=24),
            )
            raise
        finally:
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")


if __name__ == "__main__":
    unittest.main()
