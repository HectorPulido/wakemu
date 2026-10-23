"""Earn the native Rykaon ultimate through one real continuous reflected ray."""
from collections import deque
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
from unittest.mock import patch

from postgres_case import PostgresCase

ROOT = Path(__file__).resolve().parents[2]

# One actual in-process continuation, including its live isolated Store/schema.
# This holds original objects; it never reconstructs state from a receipt.
TAL_ACTUAL_CHECKPOINT = None
TAL_HOLD_ACTUAL_CHECKPOINT = False
# Central qualification may retain the actual encounter beyond this component.
TAL_RETAIN_ENCOUNTER_CHECKPOINT = False


def release_actual_talkasha_checkpoint():
    global TAL_ACTUAL_CHECKPOINT
    checkpoint, TAL_ACTUAL_CHECKPOINT = TAL_ACTUAL_CHECKPOINT, None
    if checkpoint is not None:
        for function, args, kwargs in reversed(checkpoint["cleanups"]):
            function(*args, **kwargs)


def _runtime_source_pins():
    directory = ROOT / "server/wakfu_server"
    return {
        str(path.relative_to(directory)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.rglob("*.py"))
    }


def admit_actual_talkasha_continuation(*, verifier):
    """Attach one loaded-code verifier after temporary observer patches unwind."""
    checkpoint = TAL_ACTUAL_CHECKPOINT
    if checkpoint is None or not callable(verifier):
        raise AssertionError(
            "An authentic retained checkpoint and verifier are required"
        )
    if "loaded_implementation_verifier" in checkpoint:
        raise AssertionError(
            "The authentic continuation attestation is already admitted"
        )
    checkpoint["loaded_implementation_verifier"] = verifier


def _verify_actual_checkpoint(checkpoint):
    verifier = checkpoint.get("loaded_implementation_verifier")
    if verifier is not None:
        report = verifier()
        checkpoint["receipt"]["loaded_implementation_attestation"] = report
        return
    if TAL_RETAIN_ENCOUNTER_CHECKPOINT:
        raise AssertionError(
            "Admit loaded implementation attestation before encounter continuation"
        )
    if _runtime_source_pins() != checkpoint["runtime_source_pins"]:
        raise AssertionError(
            "Actual component runtime sources changed; no hot-swap continuation"
        )


def continue_actual_talkasha_checkpoint(*, maximum_paid_casts=None):
    checkpoint = TAL_ACTUAL_CHECKPOINT
    if checkpoint is None:
        raise AssertionError("No actual Tal Kasha component checkpoint is retained")
    _verify_actual_checkpoint(checkpoint)
    return checkpoint["continue"](maximum_paid_casts=maximum_paid_casts)


def continue_actual_talkasha_melee_tactic(
    *, maximum_paid_casts=8, maximum_boundaries=10
):
    """Use the retained objects; spend movement and AP in the same owned turn."""
    if not 1 <= maximum_paid_casts <= 8 or not 0 <= maximum_boundaries <= 10:
        raise AssertionError(
            "Tal melee continuation exceeds the explicit component budget"
        )
    checkpoint = TAL_ACTUAL_CHECKPOINT
    if checkpoint is None:
        raise AssertionError("Actual component checkpoint is unavailable")
    _verify_actual_checkpoint(checkpoint)
    current, receipt = checkpoint["current"], checkpoint["receipt"]
    paid, boundaries = 0, 0

    def levels(actor):
        result = {}
        for entry in actor.state_ledger.entries:
            result[entry.reference] = result.get(entry.reference, 0) + entry.level
        return result

    try:
        while paid < maximum_paid_casts:
            boss = current.fight.actors[-200]
            if any(reference in levels(boss) for reference in (8243, 8244, 8245, 8246)):
                # The original continuation now follows its actual phase guards
                # to pyramid death/5501/8148, with unchanged native oracles.
                return continue_actual_talkasha_checkpoint(maximum_paid_casts=1)
            if levels(boss).get(8891) != 4:
                raise AssertionError("The authentic four-pyramid damage window expired")
            actor = current.fight.current
            if actor.id in (3, 5, 6) and actor.ap >= 3:
                path = current.cast_path(actor.id, -200, 1, 2)
                if path:
                    current.player_move_prefix(actor.id, path)
                    path = current.cast_path(actor.id, -200, 1, 2)
                if path == ():
                    continue_actual_talkasha_checkpoint(maximum_paid_casts=1)
                    paid += 1
                    continue
            if boundaries >= maximum_boundaries:
                raise AssertionError(
                    "Actual melee continuation reached its paid-turn budget"
                )
            current.advance()
            boundaries += 1
        boss = current.fight.actors[-200]
        if any(reference in levels(boss) for reference in (8243, 8244, 8245, 8246)):
            return continue_actual_talkasha_checkpoint(maximum_paid_casts=1)
        raise AssertionError(
            "Eight actual melee payments did not reach the original phase guard"
        )
    finally:
        receipt["melee_driver_budget"] = dict(
            paid_casts=paid,
            actual_boundaries=boundaries,
            maximum_paid_casts=maximum_paid_casts,
            maximum_boundaries=maximum_boundaries,
        )
        receipt["payments"] = current.payments
        receipt["actors"] = {
            i: dict(position=a.position, hp=a.hp, states=levels(a))
            for i, a in current.fight.actors.items()
        }
        receipt["areas"] = [
            dict(reference=row["reference"], cell=row["cell"])
            for row in current.fight.native_effect_areas.values()
        ]
        output = (
            ROOT / ".runtime/ultimate-scenes-20261021/talkasha-paid-native-rykaon.json"
        )
        output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
        if not TAL_RETAIN_ENCOUNTER_CHECKPOINT:
            release_actual_talkasha_checkpoint()


class TalKashaPaidNativeRykaonTests(PostgresCase):
    def test_paid_cardinal_lights_and_native_phase_produce_eligible_rykaon_and_8148(
        self,
    ):
        self._run_paid_component(melee_preflight=False)

    def test_paid_melee_hit_preserves_actual_continuous_ray_checkpoint(self):
        self._run_paid_component(melee_preflight=True)

    def _run_paid_component(self, *, melee_preflight):
        global TAL_ACTUAL_CHECKPOINT
        self.assertIsNone(
            TAL_ACTUAL_CHECKPOINT,
            "Release or continue the existing actual checkpoint first",
        )
        from native_paid_party_fixture import (
            native_endgame_iop_build,
            native_paid_party_fixture,
        )
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_supreme_paid_component_runtime import PaidComponentRuntime
        from wakfu_server.combat_fulmoon_talkasha_scenes import (
            reconstructed_talkasha_scene,
        )
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_triggered_spell_handler import (
            NativeTriggeredSpellHandler,
        )
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_orientation import apply as apply_orientation
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_encounter_roles import bind_roles
        from wakfu_server.combat_encounter_event_population import (
            event_population_from_record,
        )
        from wakfu_server.combat_encounter_movement_binding import binding_from_record
        from wakfu_server.combat_event_replay import NativeEventReplay

        # Fail before native scene construction if the central warm heap kept
        # an older role binder or factory while adopting the new controller.
        self.assertIn("freeze_event_population_policy", bind_roles.__code__.co_names)
        self.assertIn("freeze_movement_binding", bind_roles.__code__.co_names)
        self.assertIn("movement_caster", NativeEventReplay.__call__.__code__.co_names)
        self.assertIn(
            "permits_event_group_population",
            NativeEffectRuntimeFactory.__call__.__code__.co_names,
        )

        geometry = json.loads(
            (
                ROOT / ".runtime/parallel-readiness-20261021/"
                "supreme-entry-staging/map-1400.json"
            ).read_text()
        )
        scene = reconstructed_talkasha_scene(geometry)
        scene.update(reference=5500, level=155)
        self.assertEqual(scene["policy"], "wakemu.talkasha.native_marker_fit.v4")
        self.assertEqual(len(scene["cells"]), 549)
        self.assertEqual(
            scene["edges"],
            frozenset(
                (tuple(a), tuple(b))
                for a, b in geometry["edges"]
                if tuple(a) in scene["cells"] and tuple(b) in scene["cells"]
            ),
        )
        self.assertEqual(
            set(scene["glyph_cells"]),
            {
                (-3, -38, -22),
                (3, -38, -22),
                (0, -41, -22),
                (0, -35, -22),
                (0, -38, -22),
            },
        )
        # These are declared component approach positions before construction,
        # not recovered official spawns or movement applied to a live actor.
        positions = (
            (-2, -37, -22),
            (2, -38, -22),
            (2, -35, -22),
            (-2, -38, -22),
            (5, -33, -22),
            (-1, -37, -22),
        )
        self.assertTrue(set(positions) <= set(scene["cells"]))
        self.assertFalse(
            set(positions) & (set(scene["glyph_cells"]) | set(scene["boss_footprint"]))
        )
        scene["party_placement_cells"] = positions
        scene["anchor"] = positions[0]
        build = replace(native_endgame_iop_build(), active_spells=(4775,))
        receipt = dict(
            scope="paid_original_8148_continuous_ray_component",
            full_victory=False,
            injected_states_or_resources=False,
            damage_isolations=[],
            approach_positions=positions,
            prepared=[],
            reflections=[],
            leaf_contexts=[],
            ultimates=[],
            geometry=dict(
                policy=scene["policy"],
                original_coordinates=False,
                surfaces=549,
                original_edges_preserved=True,
                maximum_required_ray_span=6,
            ),
        )
        output = (
            ROOT / ".runtime/ultimate-scenes-20261021/talkasha-paid-native-rykaon.json"
        )
        try:
            with original_bootstrap_publication():
                (
                    fight,
                    characters,
                    monsters,
                    decks,
                    _,
                    _,
                    premise,
                ) = native_paid_party_fixture(
                    self.store,
                    scene,
                    (build,) * 6,
                    positions,
                    name_prefix="talkasha-rykaon",
                    encounter_layout=scene,
                )
            frozen_event_policy = getattr(
                fight, "native_encounter_event_population", None
            )
            self.assertIsInstance(frozen_event_policy, dict)
            self.assertEqual(
                frozen_event_policy, event_population_from_record(frozen_event_policy)
            )
            self.assertEqual(
                frozen_event_policy["policy"],
                "wakemu-tal-pyramid-element-event-population-v1",
            )
            self.assertEqual(frozen_event_policy["map_id"], 1400)
            self.assertEqual(frozen_event_policy["monster_references"], [5500])
            self.assertEqual(frozen_event_policy["carrier_state"], 8231)
            self.assertEqual(
                {row["effect_reference"] for row in frozen_event_policy["effects"]},
                {379873, 379882, 379884, 379886},
            )
            receipt["admitted_event_population"] = frozen_event_policy
            frozen_movement = getattr(fight, "native_encounter_movement_binding", None)
            self.assertIsInstance(frozen_movement, dict)
            self.assertEqual(frozen_movement, binding_from_record(frozen_movement))
            self.assertEqual(
                frozen_movement["policy"], "wakemu-tal-committed-movement-caster-v1"
            )
            self.assertEqual(
                (frozen_movement["map_id"], frozen_movement["monster_references"]),
                (1400, [5500]),
            )
            self.assertEqual(
                (
                    frozen_movement["carrier_state"],
                    frozen_movement["listener_reference"],
                    frozen_movement["event_id"],
                    frozen_movement["channel"],
                ),
                (8231, 379830, 1005, 60),
            )
            receipt["admitted_movement_binding"] = frozen_movement
            current = PaidComponentRuntime(
                fight, characters, monsters, decks, map_id=1400
            )
            if TAL_RETAIN_ENCOUNTER_CHECKPOINT:
                # Keep startup failures after real gameplay inspectable too.
                TAL_ACTUAL_CHECKPOINT = dict(
                    current=current,
                    receipt=receipt,
                    runtime_source_pins=_runtime_source_pins(),
                    store=self.store,
                    rng=current.rng,
                    cleanups=self._cleanups,
                )
                self._cleanups = []
            receipt.update(premise=premise, native_order=list(fight.order))
            self.assertEqual(set(characters), {1, 2, 3, 4, 5, 6})
            self.assertTrue(all(fight.actors[i].team == 1 for i in characters))
            self.assertEqual(fight.actors[-200].team, 0)
            order = [i for i in fight.order if i in characters]
            self.assertLess(
                max(order.index(i) for i in (2, 4, 1)), order.index(6), order
            )
            props = {
                actor_id: row["authority"]["breed_id"]
                for actor_id, row in fight.native_summon_registrations.items()
                if actor_id in fight.actors
            }
            mirror = next(i for i, reference in props.items() if reference == 5579)
            pyramids = {
                tuple(fight.actors[i].position): i
                for i, reference in props.items()
                if reference == 5502
            }
            self.assertEqual(len(pyramids), 4)
            self.assertTrue(
                all(
                    current.fight.actors[i].effect_stats[7] == 0
                    for i in (*pyramids.values(), mirror)
                )
            )
            self.assertTrue(
                all(current.fight.actors[i].effect_stats[8] == 548 for i in characters)
            )
            receipt["native_contact_facts"] = dict(
                prop_lock=0, player_dodge=548, boss_contact_departures_excluded=True
            )
            glyphs = {
                tuple(row["cell"])
                for row in fight.native_effect_areas.values()
                if row["reference"] == 1845
            }
            self.assertTrue(
                glyphs, "Original initial luminous producer did not create1845"
            )
            original_dispatch = EffectDispatcher.execute
            original_trigger = NativeTriggeredSpellHandler.__call__

            def states(actor):
                levels = {}
                for entry in actor.state_ledger.entries:
                    levels[entry.reference] = (
                        levels.get(entry.reference, 0) + entry.level
                    )
                return levels

            def record_boundary(label):
                actual = current.fight
                receipt.setdefault("actual_boundaries", []).append(
                    dict(
                        label=label,
                        turn_id=actual.turn_id,
                        current=actual.current.id,
                        phase=actual.phase,
                        action_id=current.runtime.action_id,
                        awaiting_ack=current.runtime.awaiting_ack,
                        payments=len(current.payments),
                        actors={
                            identity: dict(
                                position=actor.position,
                                hp=actor.hp,
                                ap=actor.ap,
                                mp=actor.mp,
                                states=states(actor),
                            )
                            for identity, actor in actual.actors.items()
                        },
                        movement_caster_deliveries=deepcopy(
                            getattr(actual, "native_movement_caster_deliveries", {})
                        ),
                    )
                )

            def observe_dispatch(dispatcher, invocation, **kwargs):
                if invocation.reference not in (
                    379384,
                    379386,
                    394706,
                    394707,
                    378827,
                    378829,
                    378831,
                    378833,
                    379873,
                    379882,
                    379884,
                    379886,
                    379874,
                    379883,
                    379885,
                    379887,
                    379875,
                    380138,
                    379881,
                    379891,
                    379893,
                    379895,
                    379897,
                    379899,
                    379830,
                    380304,
                    380338,
                    380339,
                    380340,
                    380342,
                    380344,
                    380346,
                    379316,
                ):
                    return original_dispatch(dispatcher, invocation, **kwargs)
                row = dict(
                    reference=invocation.reference,
                    level=invocation.level,
                    caster=invocation.caster_id,
                    target=invocation.target_id,
                    base_uid=invocation.base_uid,
                    state_uid=invocation.state_uid,
                    native_trigger_context=invocation.native_trigger_context,
                    native_explicit_target=invocation.native_explicit_target,
                    native_preselected_target=invocation.native_preselected_target,
                    fresh=invocation.wakemu_fresh_child_selection,
                    rebound=invocation.wakemu_rebound_child_selection,
                )
                receipt["leaf_contexts"].append(row)
                result = original_dispatch(dispatcher, invocation, **kwargs)
                row["result"] = bool(result)
                return result

            def observe_trigger(handler, effect, values, invocation):
                if invocation.reference != 379836:
                    return original_trigger(handler, effect, values, invocation)
                row = dict(
                    reference=invocation.reference,
                    spell=int(effect["parameters"][0]),
                    caster=invocation.caster_id,
                    children=[
                        dict(
                            id=a.id,
                            reference=handler.fight.native_summon_registrations.get(
                                a.id, {}
                            )
                            .get("authority", {})
                            .get("breed_id"),
                            states=states(a),
                        )
                        for a in handler.fight.actors.values()
                        if getattr(a, "native_summon_source", None) is not None
                    ],
                )
                result = original_trigger(handler, effect, values, invocation)
                row["result"] = bool(result)
                receipt["ultimates"].append(row)
                return result

            def route(identity, destination, *, forbidden=()):
                blocked = set().union(
                    *(
                        footprint(a.position, a.physical_radius)
                        for a in current.fight.actors.values()
                        if a.hp > 0 and a.id != identity
                    )
                )
                blocked.update(tuple(cell[:2]) for cell in forbidden)
                # Keep the offline native contact budget: preparing a ranged
                # approach must not leave a cell adjacent to the actual boss.
                bx, by, _ = current.fight.actors[-200].position
                blocked.update(
                    (bx + dx, by + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                )
                adjacent = {}
                for start, end in current.fight.edges:
                    if end[:2] not in blocked:
                        adjacent.setdefault(start, []).append(end)
                origin = current.fight.actors[identity].position
                pending, seen = deque([(origin, ())]), {origin}
                while pending:
                    cell, path = pending.popleft()
                    if cell == destination:
                        return path
                    for end in sorted(adjacent.get(cell, ())):
                        if end not in seen:
                            seen.add(end)
                            pending.append((end, (*path, end)))
                return None

            def move_to(identity, destination, *, forbidden=()):
                path = route(identity, destination, forbidden=forbidden)
                self.assertIsNotNone(path, (identity, destination))
                if path:
                    self.assertTrue(current.player_move_prefix(identity, path))
                self.assertEqual(current.fight.actors[identity].position, destination)

            def face(identity, direction):
                actor = current.fight.actors[identity]
                before = actor.ap, actor.mp
                result = apply_orientation(
                    current.runtime,
                    actor.owner_id,
                    struct.pack(">qB", identity, direction),
                )
                self.assertEqual((actor.ap, actor.mp), before)
                self.assertEqual(result["direction"], direction)

            # Prepare original mode9 orientations with actual owned inline hits.
            # Every reflector's approach excursion costs six native MP.
            tasks = {
                2: ((3, -40, -22), (3, -38, -22), 7, positions[1]),
                4: ((-2, -41, -22), (0, -41, -22), 5, (-1, -39, -22)),
                1: ((-3, -36, -22), (-3, -38, -22), 3, (-2, -38, -22)),
                3: (positions[2], (0, -35, -22), 1, (4, -33, -22)),
            }
            prepared = set()
            reflectors = {
                2: ((1, -38, -22), (3, -41, -22), 5),
                4: ((-1, -38, -22), (-3, -41, -22), 3),
                1: ((-1, -38, -22), (-3, -35, -22), 1),
            }
            reflected, armed, mirror_paid = set(), False, False
            with patch.object(
                EffectDispatcher, "execute", observe_dispatch
            ), patch.object(NativeTriggeredSpellHandler, "__call__", observe_trigger):
                current.runtime.turn_started(arm_deadline=False)
                for boundary in range(32):
                    self.assertEqual(current.fight.phase, "active")
                    actor = current.fight.current
                    if actor.id == -200 and prepared == set(tasks):
                        armed = True
                    if not armed and actor.id in tasks and actor.id not in prepared:
                        approach, target_cell, expected, parking = tasks[actor.id]
                        move_to(actor.id, approach, forbidden=glyphs)
                        current.cast(actor.id, 4775, pyramids[target_cell])
                        self.assertEqual(
                            current.fight.actors[pyramids[target_cell]].direction,
                            expected,
                        )
                        move_to(actor.id, parking, forbidden=glyphs)
                        prepared.add(actor.id)
                        receipt["prepared"].append(
                            dict(
                                actor=actor.id,
                                target=target_cell,
                                direction=expected,
                                parking=parking,
                            )
                        )
                    elif armed and actor.id in reflectors and actor.id not in reflected:
                        luminous, destination, direction = reflectors[actor.id]
                        self.assertIn(luminous, glyphs)
                        move_to(actor.id, luminous)
                        self.assertIn(8242, states(current.fight.actors[actor.id]))
                        move_to(actor.id, destination)
                        face(actor.id, direction)
                        reflected.add(actor.id)
                        receipt["reflections"].append(
                            dict(
                                actor=actor.id,
                                position=destination,
                                direction=direction,
                                states=states(current.fight.actors[actor.id]),
                            )
                        )
                    elif armed and actor.id == 6 and reflected == set(reflectors):
                        self.assertTrue(
                            all(
                                8242 in states(current.fight.actors[i])
                                for i in reflectors
                            )
                        )
                        move_to(6, (-1, -38, -22))
                        current.cast(6, 4775, mirror)
                        mirror_paid = True
                        receipt["lit_pyramids"] = {
                            i: states(current.fight.actors[i])
                            for i in pyramids.values()
                        }
                        receipt["boss_after_continuous_ray"] = states(
                            current.fight.actors[-200]
                        )
                        self.assertTrue(
                            all(
                                8238 in states(current.fight.actors[i])
                                for i in pyramids.values()
                            ),
                            receipt,
                        )
                        self.assertEqual(
                            states(current.fight.actors[-200]).get(8891), 4, receipt
                        )
                        break
                    current.advance()
                    record_boundary("paid_end_and_native_ack_complete")
                self.assertTrue(mirror_paid, receipt)
                casts_per_turn = {current.fight.turn_id: 1}
                burst_budget = dict(
                    paid_casts=0,
                    boundaries=0,
                    maximum_paid_casts=8,
                    maximum_boundaries=3,
                )
                receipt["burst_budget"] = burst_budget

                def finish_component(*, maximum_paid_casts=None):
                    paid_casts = 0
                    # The same actual prepared fight now pays original fire hits to
                    # its native80% cap; no health or phase carrier is assigned.
                    for _ in range(16):
                        if any(
                            s in states(current.fight.actors[-200])
                            for s in (8243, 8244, 8245, 8246)
                        ):
                            break
                        actor = current.fight.current
                        if (
                            actor.id not in (6, 3, 5)
                            or states(current.fight.actors[-200]).get(8891) != 4
                            or burst_budget["paid_casts"] >= 8
                        ):
                            break
                        if actor.id in characters and actor.id not in reflectors:
                            path = current.cast_path(actor.id, -200, 1, 2)
                            if path is not None:
                                if path:
                                    moved = current.player_move_prefix(actor.id, path)
                                    if (
                                        moved
                                        and current.fight.current.id == actor.id
                                        and current.fight.current.ap >= 3
                                    ):
                                        continue
                                elif (
                                    actor.ap >= 3
                                    and casts_per_turn.get(current.fight.turn_id, 0) < 3
                                ):
                                    before = current.fight.actors[-200].hp
                                    before_ap = actor.ap
                                    origin = actor.position
                                    target_position = current.fight.actors[
                                        -200
                                    ].position
                                    distance = abs(
                                        origin[0] - target_position[0]
                                    ) + abs(origin[1] - target_position[1])
                                    self.assertLessEqual(distance, 2)
                                    current.cast(actor.id, 4775, -200)
                                    damage = before - current.fight.actors[-200].hp
                                    receipt.setdefault("melee_paid_hits", []).append(
                                        dict(
                                            actor=actor.id,
                                            origin=origin,
                                            distance=distance,
                                            damage=damage,
                                            costs=current.payments[-1]["costs"],
                                        )
                                    )
                                    self.assertEqual(
                                        before_ap - current.fight.actors[actor.id].ap, 3
                                    )
                                    casts_per_turn[current.fight.turn_id] = (
                                        casts_per_turn.get(current.fight.turn_id, 0) + 1
                                    )
                                    paid_casts += 1
                                    burst_budget["paid_casts"] += 1
                                    if (
                                        maximum_paid_casts is not None
                                        and paid_casts >= maximum_paid_casts
                                    ):
                                        self.assertGreater(damage, 0)
                                        receipt[
                                            "status"
                                        ] = "actual_paid_melee_preflight_checkpoint_held"
                                        return dict(
                                            damage=damage,
                                            distance=distance,
                                            boss_hp=current.fight.actors[-200].hp,
                                        )
                                    continue
                        current.advance()
                        record_boundary("paid_end_and_native_ack_complete")
                        burst_budget["boundaries"] += 1
                        self.assertLessEqual(burst_budget["boundaries"], 3)
                    self.assertTrue(
                        any(
                            s in states(current.fight.actors[-200])
                            for s in (8243, 8244, 8245, 8246)
                        ),
                        receipt,
                    )
                    for _ in range(8):
                        if receipt["ultimates"]:
                            break
                        if current.fight.current.id == -200:
                            path = current.path_to(
                                -200,
                                lambda cell: cell
                                != current.fight.actors[-200].position,
                            )
                            self.assertTrue(path)
                            current.npc_move(path[:1])
                            record_boundary("paid_phase_npc_step_committed")
                            break
                        else:
                            current.advance()
                            record_boundary("paid_end_and_native_ack_complete")
                    self.assertTrue(
                        any(
                            row["result"]
                            and row["spell"] == 8148
                            and any(
                                child["reference"] == 5501
                                and 8240 in child["states"]
                                and 8247 not in child["states"]
                                for child in row["children"]
                            )
                            for row in receipt["ultimates"]
                        ),
                        receipt,
                    )
                    receipt["status"] = "actual_continuous_ray_eligible_rykaon_and_8148"

                def continue_component(*, maximum_paid_casts=None):
                    receipt["status"] = "actual_paid_melee_continuation_pending"
                    try:
                        with patch.object(
                            EffectDispatcher, "execute", observe_dispatch
                        ), patch.object(
                            NativeTriggeredSpellHandler, "__call__", observe_trigger
                        ):
                            result = finish_component(
                                maximum_paid_casts=maximum_paid_casts
                            )
                        if (
                            receipt.get("status")
                            == "actual_continuous_ray_eligible_rykaon_and_8148"
                            and not TAL_RETAIN_ENCOUNTER_CHECKPOINT
                        ):
                            release_actual_talkasha_checkpoint()
                        return result
                    except BaseException as error:
                        receipt["endpoint_error"] = dict(
                            type=type(error).__name__, message=str(error)
                        )
                        raise
                    finally:
                        record_boundary("component_endpoint")
                        write_receipt()

                def write_receipt():
                    receipt["payments"] = current.payments
                    receipt["movement_caster_deliveries"] = getattr(
                        current.fight, "native_movement_caster_deliveries", {}
                    )
                    receipt["actors"] = {
                        i: dict(position=a.position, hp=a.hp, states=states(a))
                        for i, a in current.fight.actors.items()
                    }
                    receipt["areas"] = [
                        dict(reference=row["reference"], cell=row["cell"])
                        for row in current.fight.native_effect_areas.values()
                    ]
                    output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")

                # Preserve the live runtime, RNG, pending transport, ownership and
                # transaction state, together with the real isolated DB lifecycle.
                # No clone, reset, policy reload or receipt-based restoration occurs.
                TAL_ACTUAL_CHECKPOINT = dict(
                    current=current,
                    receipt=receipt,
                    runtime_source_pins=_runtime_source_pins(),
                    store=self.store,
                    rng=current.rng,
                    cleanups=(TAL_ACTUAL_CHECKPOINT or {}).get(
                        "cleanups", self._cleanups
                    ),
                )
                TAL_ACTUAL_CHECKPOINT["continue"] = continue_component
                self._cleanups = []
                if not (TAL_HOLD_ACTUAL_CHECKPOINT or TAL_RETAIN_ENCOUNTER_CHECKPOINT):
                    self.addCleanup(release_actual_talkasha_checkpoint)
                continue_component(maximum_paid_casts=1 if melee_preflight else None)
        finally:
            if "current" in locals():
                receipt["payments"] = current.payments
                receipt["movement_caster_deliveries"] = getattr(
                    current.fight, "native_movement_caster_deliveries", {}
                )
                receipt["actors"] = {
                    i: dict(position=a.position, hp=a.hp, states=states(a))
                    for i, a in current.fight.actors.items()
                }
                receipt["areas"] = [
                    dict(reference=row["reference"], cell=row["cell"])
                    for row in current.fight.native_effect_areas.values()
                ]
            output.write_text(json.dumps(receipt, indent=2, default=str) + "\n")
