"""Real exported encounter terrain and source producer dependencies."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ultimate_encounter_scene_recipes import (
    encounter_fixture_factory,
    producer_paths,
    path_guards,
    projected_native_columns,
    room_scene,
)

DATA = json.loads(
    (
        Path(__file__).parent / "fixtures/ultimate_encounter_scene_recipes.json"
    ).read_text()
)


class UltimateEncounterSceneRecipeTests(unittest.TestCase):
    def scene(self, reference):
        row = next(r for r in DATA["configurations"] if reference in r["refs"])
        configuration = row["configuration"]
        geometry = DATA["maps"][str(configuration["route"]["start_map_id"])]
        return room_scene(configuration, geometry, reference)

    def test_actual_active_rosters_bind_four_bosses_to_their_real_maps(self):
        expected = {
            1988: (363, 195),
            3582: (959, 304),
            5306: (1332, 1092),
            5664: (1435, 341),
        }
        for ref, (map_id, count) in expected.items():
            with self.subTest(reference=ref):
                scene = self.scene(ref)
                self.assertEqual(scene["map_id"], map_id)
                self.assertEqual(len(scene["cells"]), count)
                self.assertIn(scene["anchor"], scene["cells"])
                self.assertTrue(scene["edges"])
                self.assertNotEqual(scene["map_id"], 1134)

    def test_map_names_cannot_admit_neocrow_into_an_unrelated_roster(self):
        configuration = DATA["configurations"][0]["configuration"]
        geometry = DATA["maps"][str(configuration["route"]["start_map_id"])]
        with self.assertRaisesRegex(ValueError, "absent from the frozen roster"):
            room_scene(configuration, geometry, 5797)

    def test_map_and_room_mutation_cannot_create_terrain_for_a_pass(self):
        original = DATA["configurations"][0]["configuration"]
        for alteration in ("map", "cell", "anchor"):
            configuration = deepcopy(original)
            geometry = DATA["maps"][str(configuration["route"]["start_map_id"])]
            if alteration == "map":
                configuration["route"]["start_map_id"] = 1134
            elif alteration == "cell":
                configuration["topology"]["rooms"][0]["cells"].append([9999, 9999, 0])
            else:
                configuration["topology"]["rooms"][0]["anchor"] = [9999, 9999, 0]
            with self.subTest(alteration=alteration), self.assertRaises(ValueError):
                room_scene(configuration, geometry, 1988)

    def test_black_crow_has_an_owned_spell_producer_for_removable_state552(self):
        paths = producer_paths(DATA["graph"], "state:552", {"spell:7501"})
        self.assertEqual(paths, (("spell:7501", "effect:332543", "state:552"),))

    def test_steel_beak_area913_has_a_real_owned4854_producer(self):
        paths = producer_paths(DATA["graph"], "area:913", {"spell:4854"})
        self.assertEqual(
            paths, (("spell:4854", "effect:152482", "effect:152483", "area:913"),)
        )
        criterion = dict(path_guards(DATA["graph"], paths[0]))["effect:152482"]
        self.assertIn("IsTargetCellFree()", criterion)
        self.assertIn(
            'GetEnemiesHumanCountInRange(1,5,"target")>0', criterion.replace(" ", "")
        )
        self.assertIn("not CellContainsSpecificEffectArea(913)", criterion)

    def test_steel_beak925926_are_created_by4877_before_the4880_consumer(self):
        for reference in (925, 926):
            paths = producer_paths(DATA["graph"], f"area:{reference}", {"spell:4877"})
            self.assertTrue(paths)
            self.assertEqual(paths[0][0], "spell:4877")
            self.assertFalse(
                producer_paths(DATA["graph"], f"area:{reference}", {"spell:4880"})
            )

    def test_rushu7288_owns_its1688_producer_instead_of_needing_a_fabricated_area(self):
        paths = producer_paths(DATA["graph"], "area:1688", {"spell:7288"})
        self.assertTrue(paths)
        self.assertIn("effect:323843", paths[0])

    def test_nox_phase_and_target_mark_come_from_the_original_constructor(self):
        for target in ("state:8981", "state:8976"):
            paths = producer_paths(DATA["graph"], target, {"monster:5664"})
            self.assertTrue(paths)
            self.assertIn("state:8969", paths[0])
            self.assertIn("state:8977", paths[0])

    def test_nox_phase_recipe_retains_genuine_turn_and_grade_prerequisites(self):
        path = producer_paths(DATA["graph"], "state:8981", {"monster:5664"})[0]
        guards = dict(path_guards(DATA["graph"], path))
        self.assertEqual(guards["effect:401768"], "GetFightCurrentTableTurn() == 1")
        self.assertEqual(guards["effect:401540"], "GetFightCurrentTableTurn() == 3")
        self.assertEqual(guards["effect:401760"], "HasState(8990, 1)")
        self.assertIn(
            "GetFightCurrentTableTurn() <> (8 + extraTurn)", guards["effect:401610"]
        )
        grade_producer = producer_paths(DATA["graph"], "state:8990", {"monster:5664"})
        self.assertTrue(grade_producer)
        self.assertIn("effect:401605", grade_producer[0])
        self.assertIn("effect:401606", grade_producer[0])

    def test_criteria_references_are_not_positive_producers_and_cycles_are_bounded(
        self,
    ):
        graph = {
            "edges": [
                {"source": "effect:1:criterion", "kind": "area", "reference": 913},
                {"source": "effect:2", "kind": "effect", "reference": 1},
                {"source": "effect:1", "kind": "effect", "reference": 2},
            ]
        }
        self.assertEqual(producer_paths(graph, "area:913", {"effect:1:criterion"}), ())
        self.assertEqual(producer_paths(graph, "effect:1", {"spell:1"}), ())
        with self.assertRaisesRegex(ValueError, "node bound"):
            producer_paths(graph, "effect:1", {"spell:1"}, maximum_nodes=1)

    def test_projected_columns_use_native_heights_without_inventing_missing_cells(self):
        scene = self.scene(1988)
        effect = DATA["point_effects"]["332546"]
        result = projected_native_columns(scene, effect, scene["anchor"], direction=3)
        self.assertEqual(len(result["projected"]), 5)
        self.assertTrue(set(result["existing"]) <= scene["cells"])
        self.assertEqual(
            len(result["projected"]),
            sum(len(result[k]) for k in ("existing", "absent", "ambiguous")),
        )
        with self.assertRaisesRegex(ValueError, "outside"):
            projected_native_columns(scene, effect, (-8, -7, -1), direction=3)

    def test_absent_and_ambiguous_columns_are_distinct_without_query_side_effects(self):
        effect = DATA["point_effects"]["332546"]
        scene = {"cells": frozenset({(0, 0, 0), (0, 4, 0), (0, 4, 1)})}
        result = projected_native_columns(scene, effect, (0, 0, 0), direction=3)
        self.assertEqual(result["existing"], ())
        self.assertEqual(result["ambiguous"], ((0, 4),))
        self.assertEqual(len(result["absent"]), 4)
        self.assertEqual(len(scene["cells"]), 3)


class UltimateEncounterConstructionTests(unittest.TestCase):
    """Real constructor probes; these do not claim complete boss mechanics."""

    def _construct(self, reference, *, native_lifecycle=False, player_cell=None):
        import traceback
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication

        scene = UltimateEncounterSceneRecipeTests().scene(reference)
        receipt = {"reference": reference, "status": "pending"}
        output = (
            Path(__file__).resolve().parents[2] / ".runtime/ultimate-scenes-20261021"
        )
        output.mkdir(parents=True, exist_ok=True)
        try:
            fixture, preparation = encounter_fixture_factory(validator, scene)
            receipt["preparation"] = preparation
            player_cell = scene["anchor"] if player_cell is None else tuple(player_cell)
            self.assertIn(player_cell, scene["cells"])
            with original_bootstrap_publication() as publication:
                fight, character, monsters, deck = fixture(
                    reference,
                    scene["level"],
                    player_cell,
                    native_lifecycle=native_lifecycle,
                )
            self.assertEqual(character["map_id"], scene["map_id"])
            self.assertEqual(monsters[-200]["map_id"], scene["map_id"])
            self.assertEqual(fight.actors[-200].position, preparation["source"])
            self.assertTrue(fight.walkable <= scene["cells"])
            self.assertTrue(
                all(a.position in fight.walkable for a in fight.actors.values())
            )
            self.assertIn(-200, fight.native_npc_initialization_receipts)
            receipt.update(
                status="native_constructor_on_configured_terrain",
                publication=publication,
                walkable_cells=len(fight.walkable),
                source=list(fight.actors[-200].position),
                player=list(fight.actors[7].position),
                direction=fight.actors[-200].direction,
                turn_id=fight.turn_id,
                states=[e.reference for e in fight.actors[-200].state_ledger.entries],
            )
            return fight, character, monsters, deck, scene, receipt
        except Exception as error:
            receipt.update(
                status="failed",
                error_type=type(error).__name__,
                error=str(error),
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            (output / f"construction-{reference}.json").write_text(
                json.dumps(receipt, indent=2, default=str) + "\n"
            )

    def test_black_crow_real_configured_map_construction(self):
        self._construct(1988)

    def test_steel_beak_real_configured_map_construction(self):
        self._construct(3582)

    def test_rushu_real_configured_map_construction(self):
        self._construct(5306)

    def test_nox_real_configured_map_construction(self):
        self._construct(5664)


class UltimateNativePaidProducerTests(unittest.TestCase):
    """Actual paid source producers on configured native encounter terrain."""

    def _fresh(self, reference, *, player_cell=None):
        return UltimateEncounterConstructionTests._construct(
            self, reference, native_lifecycle=True, player_cell=player_cell
        )

    @staticmethod
    def _serializer(character, monsters):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats

        def serialize(actor, fight):
            if getattr(actor, "native_summon_source", None) is not None:
                return registered_summon_stats(actor, fight, character["map_id"])
            values = dict(
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=fight,
            )
            if actor.controlled:
                return actual_actor_stats(character, actor, fight.id, **values)
            return actual_monster_actor_stats(
                monsters[actor.id], actor, fight.id, **values
            )

        return serialize

    def _paid(self, runtime, character, monsters, deck, spell, receipt):
        from random import Random
        from wakfu_server.combat_npc_spell import owned_spells, prepare_npc_spell
        from wakfu_server.combat_tactical_ai import NativeProvider
        from wakfu_server.fight_checkpoint_store import snapshot
        from monster_actual_ai_gameplay import (
            snapshot_gameplay,
            committed_gameplay_delta,
        )

        fight = runtime.fight
        actor = fight.current
        self.assertEqual(actor.id, -200)
        action = dict(
            type="cast",
            spellId=spell,
            level=owned_spells(fight, monsters)[spell],
            target=list(actor.position),
            targetId=actor.id,
        )
        before = snapshot(fight, runtime=runtime)
        gameplay = snapshot_gameplay(fight)
        try:
            transaction = prepare_npc_spell(
                fight,
                action,
                character,
                monsters,
                deck,
                action_id=runtime.action_id + 1,
                rng=Random(0),
            )
        except ValueError as error:
            diagnostic = getattr(error, "native_target_diagnostic", None)
            if diagnostic is None:
                raise
            self.assertEqual(snapshot(fight, runtime=runtime), before)
            receipt.setdefault("native_target_identity_resolution", []).append(
                diagnostic
            )
            action["targetId"] = diagnostic["native_target_id"]
            transaction = prepare_npc_spell(
                fight,
                action,
                character,
                monsters,
                deck,
                action_id=runtime.action_id + 1,
                rng=Random(0),
            )
        self.assertEqual(snapshot(fight, runtime=runtime), before)
        packets = NativeProvider(character, monsters, deck).commit(
            runtime, action, self._serializer(character, monsters)
        )
        self.assertTrue(packets)
        delta = committed_gameplay_delta(
            gameplay,
            snapshot_gameplay(runtime.fight),
            caster_id=actor.id,
            action=action,
        )
        receipt.setdefault("casts", []).append(
            dict(
                action=action,
                packet_count=len(packets),
                gameplay=delta,
                preview_action_id=transaction.action_id,
            )
        )
        return delta

    def _observe(self, reference, action, *, player_cell=None):
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        output = (
            Path(__file__).resolve().parents[2] / ".runtime/ultimate-scenes-20261021"
        )
        receipt = dict(
            reference=reference, status="pending", phase_or_resource_grants=False
        )
        try:
            fight, character, monsters, deck, scene, construction = self._fresh(
                reference, player_cell=player_cell
            )
            receipt["construction"] = construction
            runtime = RuntimeMessages(fight)
            action(runtime, character, monsters, deck, receipt)
            receipt["status"] = receipt.get(
                "observation_status", "native_paid_producer_observed"
            )
        except Exception as error:
            import traceback

            receipt.update(
                status="failed",
                error=str(error),
                error_type=type(error).__name__,
                traceback=traceback.format_exc(),
            )
            raise
        finally:
            output.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(receipt, indent=2, default=str) + "\n"
            from datetime import datetime, timezone

            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            (output / f"{reference}-{self._testMethodName}-{stamp}.json").write_text(
                encoded
            )
            (output / f"{reference}-{self._testMethodName}.json").write_text(encoded)
            (output / f"paid-producer-{reference}.json").write_text(encoded)

    def test_black_crow7501_creates_removable552_through_owned_paid_cast(self):
        def run(runtime, character, monsters, deck, receipt):
            self._paid(runtime, character, monsters, deck, 7501, receipt)
            holders = [
                a.id
                for a in runtime.fight.actors.values()
                if any(e.reference == 552 for e in a.state_ledger.entries)
            ]
            receipt["state552_holders"] = holders
            self.assertTrue(holders, "Actual owned7501 produced no native552 holder")

        self._observe(1988, run)

    def test_black_crow7501_then7502_consumes_the_real552_carrier(self):
        def run(runtime, character, monsters, deck, receipt):
            self._paid(runtime, character, monsters, deck, 7501, receipt)
            self.assertTrue(
                any(
                    e.reference == 552
                    for e in runtime.fight.actors[-200].state_ledger.entries
                )
            )
            delta = self._paid(runtime, character, monsters, deck, 7502, receipt)
            self.assertFalse(
                any(
                    e.reference == 552
                    for e in runtime.fight.actors[-200].state_ledger.entries
                )
            )
            self.assertTrue(delta["effectful_committed_cast"])

        self._observe(1988, run)

    def test_black_crow7502_damages_enemy_on_its_real_native_point_column(self):
        import validate_monster_spell_activation as validator

        scene = UltimateEncounterSceneRecipeTests().scene(1988)
        _fixture, preparation = encounter_fixture_factory(validator, scene)
        columns = projected_native_columns(
            scene, DATA["point_effects"]["332546"], preparation["source"], direction=3
        )
        self.assertTrue(columns["existing"])
        player_cell = columns["existing"][0]

        def run(runtime, character, monsters, deck, receipt):
            receipt["native_damage_point_recipient"] = player_cell
            before_hp = runtime.fight.actors[7].hp
            self._paid(runtime, character, monsters, deck, 7501, receipt)
            self._paid(runtime, character, monsters, deck, 7502, receipt)
            after_hp = runtime.fight.actors[7].hp
            receipt["native_recipient_hp"] = dict(before=before_hp, after=after_hp)
            self.assertLess(after_hp, before_hp)

        self._observe(1988, run, player_cell=player_cell)

    def test_steel_beak4877_creates_native925926_on_actual_room_columns(self):
        def run(runtime, character, monsters, deck, receipt):
            self._paid(runtime, character, monsters, deck, 4877, receipt)
            areas = [
                a
                for a in runtime.fight.native_effect_areas.values()
                if a["reference"] in (925, 926)
            ]
            receipt["born_areas"] = areas
            self.assertTrue(areas, "Actual owned4877 produced no native925/926 area")

        self._observe(3582, run)

    def test_steel_beak4854_creates_native913_near_the_real_human_enemy(self):
        def run(runtime, character, monsters, deck, receipt):
            self._paid(runtime, character, monsters, deck, 4854, receipt)
            areas = [
                a
                for a in runtime.fight.native_effect_areas.values()
                if a["reference"] == 913
            ]
            receipt["born_areas"] = areas
            self.assertTrue(
                areas,
                "Actual owned4854 produced no native913 despite the configured human opponent",
            )
            enemy = runtime.fight.actors[7]
            self.assertTrue(
                all(
                    1
                    <= abs(a["cell"][0] - enemy.position[0])
                    + abs(a["cell"][1] - enemy.position[1])
                    <= 5
                    for a in areas
                )
            )

        self._observe(3582, run)

    def test_steel_beak4877_then4880_hits_enemy_at_a_real_born_area(self):
        import validate_monster_spell_activation as validator

        scene = UltimateEncounterSceneRecipeTests().scene(3582)
        _fixture, preparation = encounter_fixture_factory(validator, scene)
        columns = projected_native_columns(
            scene, DATA["point_effects"]["153020"], preparation["source"], direction=3
        )
        self.assertTrue(columns["existing"])
        player_cell = columns["existing"][0]

        def run(runtime, character, monsters, deck, receipt):
            receipt["native_area_recipient"] = player_cell
            before_hp = runtime.fight.actors[7].hp
            self._paid(runtime, character, monsters, deck, 4877, receipt)
            areas = [
                a
                for a in runtime.fight.native_effect_areas.values()
                if a["reference"] in (925, 926)
            ]
            self.assertTrue(any(tuple(a["cell"]) == player_cell for a in areas))
            receipt["born_areas"] = areas
            self._paid(runtime, character, monsters, deck, 4880, receipt)
            after_hp = runtime.fight.actors[7].hp
            receipt["native_recipient_hp"] = dict(before=before_hp, after=after_hp)
            self.assertLess(after_hp, before_hp)

        self._observe(3582, run, player_cell=player_cell)

    def test_rushu7288_without_native7025_phase_preserves_zero_repeat_semantics(self):
        def run(runtime, character, monsters, deck, receipt):
            self.assertFalse(
                any(
                    e.reference == 7025
                    for e in runtime.fight.actors[-200].state_ledger.entries
                )
            )
            delta = self._paid(runtime, character, monsters, deck, 7288, receipt)
            areas = [
                a
                for a in runtime.fight.native_effect_areas.values()
                if a["reference"] == 1688
            ]
            receipt["born_areas"] = areas
            receipt[
                "observation_status"
            ] = "native_zero_repeat_without_phase7025_observed"
            self.assertEqual(areas, [])
            self.assertFalse(delta["effectful_committed_cast"])
            payments = delta["excluded_possible_caster_resource_payments"]
            self.assertTrue(
                any(p["stat"] == 2 and p["before"] - p["after"] == 3 for p in payments)
            )

        self._observe(5306, run)

    def _phase_scene(
        self, reference, target_state, maximum_table_turn, *, terminal_collection=False
    ):
        import struct
        from random import Random
        from unittest.mock import patch
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_effective_control import effective_server_controlled
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        events = []
        original_replay = NativeEventReplay.__call__
        executions = []
        original_execute = EffectDispatcher.execute

        def capture_execution(dispatcher, invocation, **kwargs):
            result = original_execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (
                401544,
                401546,
                401563,
                402278,
                402279,
                402280,
                402283,
                407626,
                407643,
            ):
                fight = dispatcher.native_retention.fight
                executions.append(
                    dict(
                        reference=invocation.reference,
                        result=bool(result),
                        turn_id=fight.turn_id,
                        table_turn=getattr(fight, "native_table_turn", None),
                        running_uid=invocation.native_running_uid,
                        retained_activation=(
                            dispatcher._active_activation is not None
                            and dispatcher._active_activation[0] is invocation
                        ),
                        base_uid=invocation.base_uid,
                        caster_id=invocation.caster_id,
                        target_id=invocation.target_id,
                    )
                )
            return result

        def capture(dispatcher, event, **kwargs):
            result = original_replay(dispatcher, event, **kwargs)
            events.append(
                dict(
                    manager=event.manager_actor_id,
                    event_ids=event.event_ids,
                    outcomes=list(result),
                )
            )
            return result

        def run(initial_runtime, character, monsters, deck, receipt):
            rng = Random(0)
            runtime = RuntimeMessages(
                initial_runtime.fight,
                runtime_stats_serializer=self._serializer(character, monsters),
                turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                    character,
                    monsters,
                    phase,
                    deck,
                    rng=rng,
                    native_events=True,
                    area_callbacks=True,
                    **kw,
                ),
                turn_end_provider=lambda phase, **kw: prepare_server_turn_end(
                    character, monsters, phase, deck, rng=rng, **kw
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
            receipt["native_events"] = events
            receipt["requested_phase_state"] = target_state
            receipt["boundaries"] = boundaries = []
            receipt["acknowledgements"] = acknowledgements = []
            receipt["selected_executions"] = executions
            receipt["paid_movements"] = movements = []
            phase_observed = False
            previous_table = None
            same_table_boundaries = 0
            runtime.turn_started()
            # Native summons enlarge the actual timeline; the table bound is
            # the semantic stop condition, with a separate finite safety cap.
            for _ in range(512):
                for _barrier in range(32):
                    if runtime.awaiting_ack is None:
                        break
                    actual_barrier = runtime.awaiting_ack
                    runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
                    acknowledgements.append(
                        dict(
                            ack=actual_barrier,
                            next_ack=runtime.awaiting_ack,
                            turn_id=runtime.fight.turn_id,
                        )
                    )
                else:
                    self.fail("Actual native skip-turn ACK chain exceeded its bound")
                fight = runtime.fight
                states = [
                    (e.reference, e.level)
                    for e in fight.actors[-200].state_ledger.entries
                ]
                table = getattr(fight, "native_table_turn", None)
                same_table_boundaries = (
                    same_table_boundaries + 1 if table == previous_table else 1
                )
                previous_table = table
                boundaries.append(
                    dict(
                        turn_id=fight.turn_id,
                        table_turn=table,
                        states=states,
                        phase=fight.phase,
                        current_id=None if fight.current is None else fight.current.id,
                        timeline_round=getattr(fight, "native_timeline_round", None),
                        runtime_round=runtime.round,
                        order=list(fight.order),
                        turn_index=fight.turn_index,
                        base_order=list(getattr(fight, "base_order", ())),
                        member_counters=dict(
                            getattr(fight, "native_timeline_member_counters", {})
                        ),
                    )
                )
                self.assertLessEqual(
                    same_table_boundaries,
                    max(64, 8 * len(fight.order)),
                    "Real timeline did not advance table: " + repr(boundaries[-1]),
                )
                if any(state_id == target_state for state_id, _level in states):
                    phase_observed = True
                    if not terminal_collection:
                        receipt[
                            "observation_status"
                        ] = f"native_lifecycle_phase{target_state}_observed"
                        return
                if (
                    terminal_collection
                    and phase_observed
                    and any(
                        row["reference"] == 401563
                        and row["result"]
                        and row["retained_activation"]
                        and row["table_turn"] >= 11
                        and any(
                            child["reference"] in (402278, 402279)
                            and child["result"]
                            and child["turn_id"] == row["turn_id"]
                            for child in executions
                        )
                        for row in executions
                    )
                ):
                    receipt[
                        "observation_status"
                    ] = "native_final_phase_and_terminal_producer_observed"
                    return
                if (
                    fight.phase != "active"
                    or fight.current is None
                    or getattr(fight, "native_table_turn", 1) >= maximum_table_turn
                ):
                    break
                actor = fight.current
                if (
                    terminal_collection
                    and actor.id == -200
                    and getattr(fight, "native_table_turn", 1) >= 8
                    and not phase_observed
                ):
                    from wakfu_server.combat_ai import snapshot, validate
                    from wakfu_server.combat_area_transaction import (
                        prepare_area_movement,
                    )
                    from wakfu_server.combat_movement_runtime import (
                        apply_ai,
                        _with_areas,
                    )

                    origin = tuple(actor.position)
                    legal = []
                    for start, destination in sorted(fight.edges):
                        if start != origin or (destination, origin) not in fight.edges:
                            continue
                        try:
                            deepcopy(fight).server_move(actor.id, [destination])
                        except ValueError:
                            continue
                        legal.append(destination)
                    self.assertTrue(
                        legal,
                        "Final-phase witness requires a real reversible paid native movement edge",
                    )

                    def patrol(current_fight, actor_id):
                        request = snapshot(current_fight, actor_id)
                        return validate(
                            current_fight,
                            actor_id,
                            request,
                            dict(
                                protocol=1,
                                requestId=request["requestId"],
                                stateKey=request["stateKey"],
                                decision=dict(
                                    actor_id=actor_id,
                                    path=[legal[0]],
                                    attack=None,
                                    target_id=None,
                                ),
                            ),
                        )

                    before_mp = actor.mp
                    with patch("wakfu_server.combat_ai.plan", patrol):
                        _packets, movement = _with_areas(
                            runtime,
                            lambda candidate, **boundary: prepare_area_movement(
                                character,
                                monsters,
                                candidate,
                                deck,
                                rng=rng,
                                **boundary,
                            ),
                            lambda candidate, callback: apply_ai(
                                candidate,
                                lambda current: self._serializer(character, monsters)(
                                    current, candidate.fight
                                ),
                                direction=actor.direction,
                                _step_callback=callback,
                            ),
                        )
                    actor = runtime.fight.actors[-200]
                    movements.append(
                        dict(
                            origin=origin,
                            destination=actor.position,
                            before_mp=before_mp,
                            after_mp=actor.mp,
                            event=movement["event"],
                        )
                    )
                    self.assertLess(actor.mp, before_mp)
                    fight = runtime.fight
                if effective_server_controlled(fight, actor):
                    runtime.end_server_turn(actor.id, fight.turn_id)
                else:
                    runtime.end_turn(actor.owner_id, actor.id, current_wire_turn(fight))
            self.fail(
                f"Native {reference} lifecycle produced no{target_state} within bounded real turns: "
                + repr(boundaries[-1])
            )

        with patch.object(NativeEventReplay, "__call__", capture), patch.object(
            EffectDispatcher, "execute", capture_execution
        ):
            self._observe(reference, run)

    def test_nox8981_phase_arrives_through_real_runtime_turn_boundaries(self):
        self._phase_scene(5664, 8981, 9)

    def test_nox_final_phase_and_terminal_producer_follow_real_movement_and_owned_ends(
        self,
    ):
        self._phase_scene(5664, 8979, 12, terminal_collection=True)
