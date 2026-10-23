"""Owned normal gear, real Ogrest artifact pickup and earned phase boundaries."""
import json
from pathlib import Path
from random import Random
import struct
from unittest.mock import patch
from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]


def original_final_projection():
    """Resolve the original state effect before advancing any combat turns."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.combat_native_area_metadata import merge_native_point_areas

    effect = native_catalog.record(
        DATA_ROOT / "combat-state-definitions.json", "effects", "238860"
    )
    if (
        not isinstance(effect, dict)
        or effect.get("effect_class") != 330
        or effect.get("area_class") != "anE"
        or effect.get("children") != [238861]
    ):
        raise AssertionError("Missing actual Ogrest final-state projection238860")
    effect = merge_native_point_areas({"238860": effect})["238860"]
    if effect.get("native_area_points") != [[-3, -2]]:
        raise AssertionError("Original Ogrest exit point metadata changed")
    from wakfu_server.combat_area_contracts import AREA_CONTRACTS

    for reference in (1254, 1255):
        area = native_catalog.record(
            DATA_ROOT / "native-effect-areas.json", "areas", str(reference)
        )
        if (
            not isinstance(area, dict)
            or area.get("type") != "GLYPH"
            or area.get("native_class") != "bcT"
            or AREA_CONTRACTS[area["type"]] != "faY"
        ):
            raise AssertionError("Original Ogrest final area constructor changed")
    return effect


class OgrestReconstructedNativePhaseTests(PostgresCase):
    def test_original_artifact_pickup_and_three_table_phase_transition(self):
        self.exercise_native_phases(terminal=False)

    def test_original_artifact_six_phases_and_owned_final_exit(self):
        self.exercise_native_phases(terminal=True)

    def test_original_protective_artifact_pickup(self):
        self.exercise_native_phases(terminal=True, pickup_only=True)

    def test_original_ivory_role_cast_preflight(self):
        self.exercise_native_phases(terminal=True, ivory_paid=True, preflight_only=True)

    def test_original_earned_ivory_paid_attack_increases_native_resistance(self):
        self.exercise_native_phases(terminal=True, ivory_paid=True)

    def exercise_native_phases(
        self, *, terminal, pickup_only=False, ivory_paid=False, preflight_only=False
    ):
        final_projection = original_final_projection() if terminal else None
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from wakfu_server.combat_supreme_scene_policies import resolve_supreme_scene
        from wakfu_server.combat_ogrest_phase_controller import (
            POLICY,
            PURPLE,
            PHASE_STATES,
            ogrest_terminal_authority,
            ogrest_exit_areas,
        )
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_summon_stats import registered_summon_stats
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_damage_handler import NativeDamageHandler
        from wakfu_server.combat_obstacle_condition import footprint
        from tools.combat_audit_turns import advance_actual_turn

        geometry = json.loads(
            (ROOT / ".runtime/ultimate-scenes-20261021/map-1156.json").read_text()
        )
        layout = resolve_supreme_scene(4378, geometry)
        scene = dict(layout, level=230)
        initial_cell = (2, -22, 40) if terminal else tuple(layout["anchor"])
        self.assertIn(initial_cell, layout["party_placement_cells"])
        pickup_reference, pickup_state = (1217, 4992) if terminal else (1220, 4997)
        with original_bootstrap_publication():
            (
                fight,
                characters,
                monsters,
                decks,
                resources,
                generations,
                preparation,
            ) = native_paid_party_fixture(
                self.store,
                scene,
                [native_endgame_iop_build()],
                [initial_cell],
                name_prefix="ogrest-normal",
                encounter_layout=layout,
                production_scene=True,
                initialization_seed=2,
            )
        character = next(iter(characters.values()))
        identity, deck = character["id"], decks[character["id"]]
        receipt = dict(
            scope="Normal native gear, actual artifact movement pickup and first earned phase transition; no complete encounter claim",
            preparation=preparation,
            pickup=None,
            boundaries=[],
            hp_effects=[],
            damage_calculations=[],
            exit_movements=[],
        )
        output = ROOT / (
            ".runtime/parallel-readiness-20261021/ogrest-real-six-phases-terminal-receipt.json"
            if terminal
            else ".runtime/parallel-readiness-20261021/ogrest-real-scene-first-phase-receipt.json"
        )
        if terminal:
            receipt[
                "scope"
            ] = "Actual six-phase director, original artifact and owned final-cell policy; no complete paid NPC book or durable loot claim"
        if pickup_only:
            output = (
                ROOT
                / ".runtime/parallel-readiness-20261021/ogrest-original-4992-pickup-receipt.json"
            )
            receipt[
                "scope"
            ] = "Actual original1217 protective pickup and paid return only; no six-phase or terminal claim"
        if ivory_paid:
            output = ROOT / (
                ".runtime/parallel-readiness-20261021/ogrest-ivory-player1-cast-preflight.json"
                if preflight_only
                else ".runtime/parallel-readiness-20261021/ogrest-ivory-player1-paid-resistance.json"
            )
            receipt[
                "scope"
            ] = "Actual player1 role, earned Ivory and one paid elemental attack; no exit, loot or full spellbook claim"
            receipt["resistance_effects"] = []
        self.addCleanup(
            lambda: output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        )
        context = fight.native_ogrest_phase_context
        self.assertEqual(
            (context["policy"], context["current_phase"]), (POLICY, PURPLE)
        )
        self.assertFalse(context["final_entered"])
        self.assertEqual(
            sum(
                row["reference"] in range(1213, 1223)
                for row in fight.native_effect_areas.values()
            ),
            10,
        )
        boss = fight.actors[-200]
        self.assertEqual((boss.hp, boss.max_hp), (50000000, 50000000))
        rng = Random(2)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)

        def stats(actor, current):
            if getattr(actor, "native_summon_source", None) is not None:
                return registered_summon_stats(actor, current, 1156)
            values = dict(
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=current,
            )
            return (
                actual_actor_stats(characters[actor.id], actor, current.id, **values)
                if actor.id in characters
                else actual_monster_actor_stats(
                    monsters[actor.id], actor, current.id, **values
                )
            )

        runtime = RuntimeMessages(
            fight,
            runtime_stats_serializer=stats,
            turn_start_provider=lambda phase, **kw: prepare_server_turn_start(
                character,
                monsters,
                phase,
                deck,
                native_events=True,
                area_callbacks=True,
                **common,
                **kw
            ),
            turn_end_provider=lambda phase, **kw: prepare_server_turn_end(
                character, monsters, phase, deck, **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character, monsters, deck, action_id=action_id, critical=False, **common
            )[0],
        )
        ivory_ops = None
        if ivory_paid:
            from native_supreme_paid_component_runtime import PaidComponentRuntime
            from wakfu_server import native_catalog
            from wakfu_server.paths import DATA_ROOT

            ivory_ops = PaidComponentRuntime(
                fight, characters, monsters, decks, map_id=1156, seed=2
            )
            runtime, rng, common = ivory_ops.runtime, ivory_ops.rng, ivory_ops.common
            casting = native_catalog.record(
                DATA_ROOT / "native-spell-casting.json", "spells", "4780"
            )
            self.assertIsInstance(casting, dict)
            self.assertEqual(casting["maximum_level"], 245)
            self.assertEqual(casting["costs"][244], [2, 0, 0])
            self.assertEqual(casting["levels"][244][:2], [1, 3])
            damage = native_catalog.record(
                DATA_ROOT / "spell-effect-trees.json", "effects", "151640"
            )
            reaction = native_catalog.record(
                DATA_ROOT / "combat-state-definitions.json", "effects", "238002"
            )
            gain = native_catalog.record(
                DATA_ROOT / "combat-state-definitions.json", "effects", "240713"
            )
            self.assertEqual(damage["effect_class"], 3)
            self.assertEqual(reaction["target_masks"][1], [8])
            self.assertEqual(
                (gain["effect_class"], gain["parameters"]), (84, [0.0, 5.0])
            )
            registry = native_catalog.record(
                DATA_ROOT / "effect-characteristic-registry.json", "effects", "84"
            )
            self.assertEqual(
                (registry["fixed_stat_id"], registry["fixed_stat_name"]),
                (30, "RES_EARTH_PERCENT"),
            )
            actor = fight.actors[identity]
            self.assertEqual((actor.team, boss.team), (1, 0))
            binding = fight.native_encounter_recipient_binding
            self.assertIsInstance(
                binding,
                dict,
                "Reviewed DB258 policy must be admitted before phase traversal",
            )
            self.assertEqual(
                (
                    binding["map_id"],
                    binding["boss_reference"],
                    binding["carrier_state"],
                ),
                (1156, 4378, 4984),
            )
            self.assertIn(
                240713, {row["effect_reference"] for row in binding["effects"]}
            )
            self.assertGreaterEqual(actor.ap, 2)
            self.assertGreaterEqual(actor.mp, 6)
            self.assertIn(30, boss.effect_stats)
            ivory_ops.casting_flags = {
                key: casting[key]
                for key in ("linear", "diagonal", "linear_path", "path_option")
            }
            route = ivory_ops.cast_path(
                identity,
                boss.id,
                1,
                3,
                visible_footprint=True,
                casting_flags=ivory_ops.casting_flags,
            )
            self.assertIsNotNone(
                route, "No original range/LOS-valid paid attack approach"
            )
            self.assertLessEqual(len(route), 3 * actor.mp)
            receipt["preflight"] = dict(
                actor_id=identity,
                actor_team=actor.team,
                boss_team=boss.team,
                hp=actor.hp,
                ap=actor.ap,
                mp=actor.mp,
                spell=4780,
                source_cost=[2, 0, 0],
                source_range=[1, 3],
                native_los_height=actor.native_los_height,
                native_damage_family=3,
                native_event=8,
                resistance_family=84,
                resistance_stat=30,
                counter_state=5066,
                casting_flags=ivory_ops.casting_flags,
                approach=list(route),
                admitted_roles=fight.native_encounter_roles,
                recipient_binding=fight.native_encounter_recipient_binding,
            )
            if preflight_only:
                return
        original_execute = EffectDispatcher.execute
        original_calculate = NativeDamageHandler._calculate

        def execute(dispatcher, invocation, *args, **kwargs):
            retention = getattr(dispatcher, "native_retention", None)
            if retention is None:
                return original_execute(dispatcher, invocation, *args, **kwargs)
            current = retention.fight
            before_resistance = (
                current.actors[-200].effect_stats[30] if ivory_paid else None
            )
            before = (
                current.phase,
                {key: actor.hp for key, actor in current.actors.items()},
            )
            result = original_execute(dispatcher, invocation, *args, **kwargs)
            after = (
                current.phase,
                {key: actor.hp for key, actor in current.actors.items()},
            )
            if before != after:
                receipt["hp_effects"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        before=before,
                        after=after,
                    )
                )
            if (
                ivory_paid
                and current.actors[-200].effect_stats[30] != before_resistance
            ):
                receipt["resistance_effects"].append(
                    dict(
                        reference=invocation.reference,
                        caster=invocation.caster_id,
                        target=invocation.target_id,
                        level=invocation.level,
                        trigger_context=invocation.native_trigger_context,
                        before=before_resistance,
                        after=current.actors[-200].effect_stats[30],
                    )
                )
            return result

        def calculate(handler, effect, invocation, **kwargs):
            result = original_calculate(handler, effect, invocation, **kwargs)
            context, flags, amount = result
            receipt["damage_calculations"].append(
                dict(
                    reference=invocation.reference,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    amount=amount,
                    flags=flags,
                    context=dict(vars(context)),
                )
            )
            return result

        observer = patch.object(EffectDispatcher, "execute", execute)
        damage_observer = patch.object(NativeDamageHandler, "_calculate", calculate)
        observer.start()
        damage_observer.start()
        self.addCleanup(observer.stop)
        self.addCleanup(damage_observer.stop)
        receipt["before_turn_start"] = dict(
            phase=runtime.fight.phase,
            actors={
                key: dict(
                    hp=actor.hp,
                    maximum=actor.max_hp,
                    position=actor.position,
                    states=[
                        (state.reference, state.level)
                        for state in actor.state_ledger.entries
                    ],
                )
                for key, actor in runtime.fight.actors.items()
            },
        )
        runtime.turn_started()
        if runtime.awaiting_ack is not None:
            runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
        for _ in range(80 if terminal else 12):
            current = runtime.fight
            context = current.native_ogrest_phase_context
            receipt["boundaries"].append(
                dict(
                    table=current.native_timeline_round,
                    actor=None if current.current is None else current.current.id,
                    phase=current.phase,
                    context=json.loads(json.dumps(context)),
                    player_hp=current.actors[identity].hp,
                )
            )
            if terminal and current.phase == "finished":
                self.assertFalse(ivory_paid, receipt)
                receipt["terminal_authority"] = ogrest_terminal_authority(current)
                self.assertIsNotNone(receipt["terminal_authority"], receipt)
                self.assertEqual(current.winner, current.actors[identity].team)
                break
            self.assertEqual(current.phase, "active", receipt)
            self.assertIsNotNone(current.current, receipt)
            if context["transitions"] and not terminal:
                break
            if current.current.id == identity and receipt["pickup"] is None:
                actor = current.actors[identity]
                self.assertNotIn(
                    pickup_state,
                    {state.reference for state in actor.state_ledger.entries},
                )
                path = (
                    [(1, -22, 40), (0, -22, 40), (0, -21, 40)]
                    if terminal
                    else [(3, -23, 40), (3, -22, 40), (3, -21, 40)]
                )
                before = dict(mp=actor.mp, hp=actor.hp, position=actor.position)
                self.assertGreaterEqual(actor.mp, len(path))
                apply_client(
                    runtime,
                    actor.owner_id,
                    struct.pack(">q", identity)
                    + b"".join(struct.pack(">iih", *cell) for cell in path),
                    lambda selected: stats(selected, runtime.fight),
                    runtime_stats_serializer=stats,
                    area_provider=lambda candidate, **boundary: prepare_area_movement(
                        character, monsters, candidate, deck, **common, **boundary
                    ),
                )
                actor = runtime.fight.actors[identity]
                receipt["pickup"] = dict(
                    before=before,
                    after=dict(mp=actor.mp, hp=actor.hp, position=actor.position),
                    states=[
                        (state.reference, state.level)
                        for state in actor.state_ledger.entries
                    ],
                )
                self.assertEqual(actor.position, path[-1])
                self.assertLess(actor.mp, before["mp"])
                self.assertIn(
                    pickup_state,
                    {state.reference for state in actor.state_ledger.entries},
                )
                self.assertFalse(
                    any(
                        area["reference"] == pickup_reference
                        for area in runtime.fight.native_effect_areas.values()
                    )
                )
                if terminal:
                    # Return by paid walking to the safe native formation.
                    # This also leaves both final turns available for the
                    # actual exit, whose location is discovered at table19.
                    retreat = [(0, -22, 40), (1, -22, 40), initial_cell]
                    self.assertGreaterEqual(actor.mp, len(retreat))
                    remaining_mp = actor.mp
                    apply_client(
                        runtime,
                        actor.owner_id,
                        struct.pack(">q", identity)
                        + b"".join(struct.pack(">iih", *cell) for cell in retreat),
                        lambda selected: stats(selected, runtime.fight),
                        runtime_stats_serializer=stats,
                        area_provider=lambda candidate, **boundary: prepare_area_movement(
                            character, monsters, candidate, deck, **common, **boundary
                        ),
                    )
                    returned = runtime.fight.actors[identity]
                    receipt["pickup_return"] = dict(
                        position=returned.position, mp=returned.mp
                    )
                    self.assertEqual(returned.position, initial_cell)
                    self.assertLess(returned.mp, remaining_mp)
                    if pickup_only:
                        self.assertIn(
                            4992,
                            {
                                state.reference
                                for state in returned.state_ledger.entries
                            },
                        )
                        self.assertGreater(returned.hp, 0)
                        self.assertEqual(runtime.fight.phase, "active")
                        self.assertIsNone(ogrest_terminal_authority(runtime.fight))
                        receipt["final_hp"] = returned.hp
                        receipt["final_maximum"] = returned.max_hp
                        return
            if (
                ivory_paid
                and current.current.id == identity
                and any(
                    state.reference == 4984
                    for state in current.actors[boss.id].state_ledger.entries
                )
            ):
                receipt["ivory_phase"] = dict(
                    table=current.native_timeline_round,
                    phase_order=list(context["phase_order"]),
                    transitions=list(context["transitions"]),
                )
                route = ivory_ops.cast_path(
                    identity,
                    boss.id,
                    1,
                    3,
                    visible_footprint=True,
                    casting_flags=ivory_ops.casting_flags,
                )
                self.assertIsNotNone(route)
                if route:
                    self.assertTrue(
                        ivory_ops.player_move_prefix(identity, route), receipt
                    )
                    route = ivory_ops.cast_path(
                        identity,
                        boss.id,
                        1,
                        3,
                        visible_footprint=True,
                        casting_flags=ivory_ops.casting_flags,
                    )
                    self.assertIsNotNone(route)
                if not route:
                    actor, target = (
                        runtime.fight.actors[identity],
                        runtime.fight.actors[boss.id],
                    )
                    grade = lambda selected: sum(
                        state.level
                        for state in selected.state_ledger.entries
                        if state.reference == 5066
                    )
                    before = dict(
                        actor_id=actor.id,
                        team=actor.team,
                        ap=actor.ap,
                        hp=target.hp,
                        resistance=target.effect_stats[30],
                        player_resistance=actor.effect_stats[30],
                        grade=grade(target),
                    )
                    from native_visible_target_fixture import visible_target_cells

                    _, adapter = server_runtime(
                        character,
                        monsters,
                        deck,
                        action_id=runtime.action_id + 1,
                        critical=False,
                        **common
                    )
                    aims = visible_target_cells(
                        runtime.fight,
                        adapter.actor_authority,
                        1156,
                        actor,
                        target,
                        minimum=1,
                        maximum=3,
                        casting_flags=ivory_ops.casting_flags,
                    )
                    self.assertTrue(aims)
                    payment = ivory_ops.cast(identity, 4780, boss.id, aim_cell=aims[0])
                    target, actor = (
                        runtime.fight.actors[boss.id],
                        runtime.fight.actors[identity],
                    )
                    after = dict(
                        ap=actor.ap,
                        hp=target.hp,
                        resistance=target.effect_stats[30],
                        player_resistance=actor.effect_stats[30],
                        grade=grade(target),
                    )
                    receipt["paid_ivory"] = dict(
                        before=before,
                        after=after,
                        payment=payment,
                        operations=ivory_ops.payments,
                    )
                    self.assertEqual(payment["costs"]["ap"], 2)
                    self.assertEqual(before["ap"] - after["ap"], 2)
                    self.assertGreater(after["grade"], before["grade"])
                    gains = [
                        row
                        for row in receipt["resistance_effects"]
                        if row["reference"] == 240713
                    ]
                    self.assertTrue(gains)
                    self.assertEqual(
                        after["player_resistance"], before["player_resistance"]
                    )
                    for row in gains:
                        self.assertEqual(row["target"], boss.id)
                        self.assertEqual(row["after"] - row["before"], 5 * row["level"])
                    self.assertEqual(
                        after["resistance"] - before["resistance"],
                        sum(row["after"] - row["before"] for row in gains),
                    )
                    self.assertGreater(target.hp, 0)
                    self.assertTrue(receipt["resistance_effects"])
                    self.assertIsNone(ogrest_terminal_authority(runtime.fight))
                    return
            preposition = (
                terminal and not ivory_paid and current.native_timeline_round == 18
            )
            if (
                terminal
                and not ivory_paid
                and current.current.id == identity
                and (
                    preposition
                    or (
                        context["final_entered"]
                        and current.native_timeline_round in (19, 20)
                    )
                )
            ):
                # Discover the actual original final glyphs; do not supply a
                # target coordinate, synthetic area or direct actor movement.
                from collections import deque

                actor = current.actors[identity]
                if preposition:
                    # Read the same original directional238860 from the actual
                    # 1254 PV. Anticipation changes only this player's paid walk.
                    from wakfu_server.combat_group_cells import group_cells

                    sources = [
                        area
                        for area in current.native_effect_areas.values()
                        if area["reference"] == 1254 and area.get("owner_id") == boss.id
                    ]
                    self.assertTrue(sources)
                    goals = {
                        cell
                        for area in sources
                        for cell in group_cells(
                            current,
                            final_projection,
                            tuple(area["cell"]),
                            caster_id=area["uid"],
                        )
                    }
                else:
                    goals = {tuple(area["cell"]) for area in ogrest_exit_areas(current)}
                self.assertTrue(goals, receipt)
                occupied = set()
                for other in current.actors.values():
                    if other.id != identity and current._in_play(other):
                        self.assertIsNotNone(other.physical_radius)
                        occupied.update(
                            footprint(other.position, other.physical_radius)
                        )
                edges = {}
                for start, end in current.edges:
                    if end[:2] not in occupied:
                        edges.setdefault(start, []).append(end)
                queue, paths = deque([actor.position]), {actor.position: []}
                route = None
                while queue:
                    cell = queue.popleft()
                    if cell in goals:
                        route = paths[cell]
                        break
                    for adjacent in sorted(edges.get(cell, ())):
                        if adjacent not in paths:
                            paths[adjacent] = paths[cell] + [adjacent]
                            queue.append(adjacent)
                self.assertIsNotNone(
                    route,
                    dict(goals=list(goals), position=actor.position, receipt=receipt),
                )
                path = route[: actor.mp]
                if path:
                    before = dict(position=actor.position, mp=actor.mp, hp=actor.hp)
                    apply_client(
                        runtime,
                        actor.owner_id,
                        struct.pack(">q", identity)
                        + b"".join(struct.pack(">iih", *cell) for cell in path),
                        lambda selected: stats(selected, runtime.fight),
                        runtime_stats_serializer=stats,
                        area_provider=lambda candidate, **boundary: prepare_area_movement(
                            character, monsters, candidate, deck, **common, **boundary
                        ),
                    )
                    after = runtime.fight.actors[identity]
                    receipt.setdefault(
                        "preposition_movements" if preposition else "exit_movements", []
                    ).append(
                        dict(
                            table=current.native_timeline_round,
                            before=before,
                            after=dict(
                                position=after.position, mp=after.mp, hp=after.hp
                            ),
                            goals=list(goals),
                        )
                    )
                    self.assertEqual(after.position, path[-1])
                    self.assertLess(after.mp, before["mp"])
            advance_actual_turn(runtime)
        else:
            self.fail(
                "Ogrest native phase did not advance through the bounded real turn sequence"
            )
        context = runtime.fight.native_ogrest_phase_context
        receipt["final_context"] = context
        receipt["final_hp"] = runtime.fight.actors[identity].hp
        self.assertIsNotNone(receipt["pickup"])
        self.assertEqual(context["transitions"][0]["table"], 4)
        self.assertEqual(context["transitions"][0]["completed"], PURPLE)
        if terminal:
            self.assertEqual(context["phase_order"][0], PURPLE)
            self.assertEqual(len(context["phase_order"]), 6)
            self.assertEqual(set(context["phase_order"]), set(PHASE_STATES))
            self.assertTrue(context["final_entered"])
            self.assertEqual(
                [row["table"] for row in context["transitions"]], [4, 7, 10, 13, 16, 19]
            )
            self.assertIn(receipt["terminal_authority"]["table"], (19, 20))
            self.assertEqual(receipt["terminal_authority"]["area_reference"], 1255)
        else:
            self.assertEqual(len(context["phase_order"]), 2)
            self.assertEqual(len(set(context["phase_order"])), 2)
            self.assertFalse(context["final_entered"])
        self.assertFalse(
            any(
                area["reference"] in range(1213, 1223)
                for area in runtime.fight.native_effect_areas.values()
            )
        )
