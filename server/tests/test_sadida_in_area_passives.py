"""Actual in-area doll/passive effects for Sadida."""
import json
import os
import random
import struct
import unittest
from pathlib import Path

from wakfu_server.combat_diagnostics import combat_diagnostic_scope

import test_sadida_grant_pipeline as grants
import test_sadida_semantic_qualification as semantic


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaInAreaPassiveTests(unittest.TestCase):
    cast = grants.SadidaGrantPipelineTests.cast

    def make_tree_with_loca_in_area(self, passives):
        fixture_builder = semantic.SadidaSemanticQualificationTests()
        data = fixture_builder.fixture_at_distance(2, passives=passives)
        character, monster, fight, deck, rng, _ = data
        casts_trace = []
        # Source379581 requires an owned live1835 area at the same time as
        # the 1836/1850 tree field. Plant that seed first and cross a complete
        # real player-turn boundary before using the remaining8137 casts.
        # The actual owned1836 footprint is the square ring around its later
        # tree center(-7,-7), excluding the center. Keep this seed on a ring
        # cell so the passive's IsOnSpecificEffectArea leaf has a true case.
        spare_seed, trace = fixture_builder.cast_with_trace(
            data, 8137, target=(-7, -8, -1), action_id=9
        )
        casts_trace.extend(trace)
        data = (*data[:2], spare_seed.fight, *data[3:])
        live_seed_areas = [
            row
            for row in data[2].native_effect_areas.values()
            if row.get("reference") == 1835 and row.get("owner_id") == 7
        ]
        self.assertTrue(live_seed_areas, list(data[2].native_effect_areas.values()))
        spare_seed_cell = tuple(live_seed_areas[0]["cell"])
        from test_aniripsa_grant_summon_pipeline import (
            AniripsaGrantSummonPipelineTests,
        )

        AniripsaGrantSummonPipelineTests().next_player_turn(data[2], data[:5])
        # Create the Ghulotona before the tree area exists. The seed spell is
        # only converted when it is a live 1835 seed; casting seed on an
        # already occupied tree footprint is a legal no-op, not a new doll.
        # Exclude the spare live seed's cell so this conversion leaves1835
        # available for the separate passive prerequisite.
        doll_cell = next(
            cell for cell in ((-6, -8, -1), (-6, -6, -1)) if cell != spare_seed_cell
        )
        seed, trace = fixture_builder.cast_with_trace(
            data, 8137, target=doll_cell, action_id=10
        )
        casts_trace.extend(trace)
        data = (*data[:2], seed.fight, *data[3:])
        doll_cast, trace = fixture_builder.cast_with_trace(
            data, 921, target=doll_cell, action_id=11
        )
        casts_trace.extend(trace)
        data = (*data[:2], doll_cast.fight, *data[3:])
        tree_seed, trace = fixture_builder.cast_with_trace(
            data, 8137, target=(-7, -7, -1), action_id=12
        )
        casts_trace.extend(trace)
        data = (*data[:2], tree_seed.fight, *data[3:])
        tree_cast, trace = fixture_builder.cast_with_trace(
            data, 8137, target=(-7, -7, -1), action_id=13
        )
        casts_trace.extend(trace)
        data = (*data[:2], tree_cast.fight, *data[3:])
        trees = [
            actor
            for actor in data[2].actors.values()
            if getattr(actor, "native_summon_source", None)
            and actor.hp > 0
            and __import__(
                "wakfu_server.combat_summon_spellbook", fromlist=["actor_action_book"]
            ).actor_action_book(actor)["profile"]
            == 5577
        ]
        self.assertEqual(len(trees), 1)
        tree_areas = [
            row
            for row in data[2].native_effect_areas.values()
            if row.get("reference") == 1836
        ]
        self.assertTrue(tree_areas, list(data[2].native_effect_areas.values()))
        area_cells = {
            tuple(cell) for row in tree_areas for cell in row.get("native_cells_xy", ())
        }

        live_seed_areas = [
            row
            for row in data[2].native_effect_areas.values()
            if row.get("reference") == 1835 and row.get("owner_id") == 7
        ]
        self.assertTrue(live_seed_areas, list(data[2].native_effect_areas.values()))
        self.assertTrue(
            any(
                tuple(row.get("cell", row.get("position", ()))) == spare_seed_cell
                for row in live_seed_areas
            ),
            {"retained_seed_cell": spare_seed_cell, "live_seed_areas": live_seed_areas},
        )
        self.assertIn(spare_seed_cell[:2], area_cells)

        from wakfu_server.combat_server_spell import server_runtime

        live_seed_areas = [
            row
            for row in data[2].native_effect_areas.values()
            if row.get("reference") == 1835 and row.get("owner_id") == 7
        ]
        self.assertTrue(live_seed_areas, list(data[2].native_effect_areas.values()))

        dolls = [
            actor
            for actor in data[2].actors.values()
            if getattr(actor, "native_summon_source", None)
            and actor.hp > 0
            and __import__(
                "wakfu_server.combat_summon_spellbook", fromlist=["actor_action_book"]
            ).actor_action_book(actor)["profile"]
            == 3748
        ]
        self.assertEqual(len(dolls), 1)
        doll = dolls[0]
        return (
            data,
            doll.id,
            doll_cell,
            spare_seed_cell,
            doll_cast.outcomes,
            sorted(area_cells),
            casts_trace,
        )

    def test_8151_upgrades_actual_ghulotona_inside_owned_tree_area(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_state_managers import state_manager
        from wakfu_server.fight_checkpoint_store import snapshot

        observations = {}
        for name, passives in (("baseline", ()), ("8151", (8151,))):
            (
                data,
                doll_id,
                doll_cell,
                spare_seed_cell,
                doll_cast_outcomes,
                area_cells,
                cast_trace,
            ) = self.make_tree_with_loca_in_area(passives)
            character, monster, fight, deck, rng, _ = data
            doll = fight.actors[doll_id]
            before_states = sorted(
                entry.reference for entry in doll.state_ledger.entries
            )
            caster_states_before = {
                entry.reference: entry.level
                for entry in fight.actors[7].state_ledger.entries
            }
            self.assertIn(3599, before_states)
            trace = []
            runtime = RuntimeMessages(
                fight,
                turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                    character, {-7: monster}, preview, deck, rng=rng, **boundary
                ),
                turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                    character,
                    {-7: monster},
                    preview,
                    deck,
                    rng=rng,
                    area_callbacks=True,
                    **boundary
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    character,
                    {-7: monster},
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            turn_order = []
            caster_state_transitions = []
            with combat_diagnostic_scope(lambda **row: trace.append(row), limit=8192):
                for _ in range(20):
                    if fight.current is not None and fight.current.id == doll_id:
                        break
                    caster_before = {
                        entry.reference: entry.level
                        for entry in fight.actors[7].state_ledger.entries
                    }
                    turn_order.append(
                        None if fight.current is None else fight.current.id
                    )
                    advance_actual_turn(runtime)
                    caster_after = {
                        entry.reference: entry.level
                        for entry in fight.actors[7].state_ledger.entries
                    }
                    caster_state_transitions.append(
                        {"before": caster_before, "after": caster_after}
                    )
                else:
                    self.fail(
                        "Owned Ghulotona did not become current during native turn cycle"
                    )
            doll = fight.actors[doll_id]
            area_state_ledgers = []
            for area_uid, area in sorted(fight.native_effect_areas.items()):
                if area.get("owner_id") != 7:
                    continue
                manager = state_manager(fight, area_uid)
                area_state_ledgers.append(
                    {
                        "uid": area_uid,
                        "reference": area.get("reference"),
                        "cell": list(area.get("cell", ())),
                        "states": None
                        if manager is None
                        else [
                            {
                                "uid": entry.uid,
                                "reference": entry.reference,
                                "level": entry.level,
                                "caster_id": entry.caster_id,
                                "target_id": entry.target_id,
                                "duration": entry.duration,
                                "retained": entry.retained,
                            }
                            for entry in manager.state_ledger.entries
                        ],
                    }
                )
            seed_area = next(
                row
                for row in area_state_ledgers
                if row["reference"] == 1835 and tuple(row["cell"]) == spare_seed_cell
            )
            seed_state = next(
                row for row in seed_area["states"] if row["reference"] == 3624
            )
            expected_state_level = 3 if name == "8151" else 4
            self.assertEqual(seed_state["level"], expected_state_level, seed_area)
            expected_stage = 1853 if name == "8151" else 1854
            self.assertTrue(
                any(
                    row["reference"] == expected_stage
                    and tuple(row["cell"]) == spare_seed_cell
                    for row in area_state_ledgers
                ),
                {"expected_stage": expected_stage, "areas": area_state_ledgers},
            )
            action = next(
                row
                for row in actor_action_book(doll)["actions"]
                if row["reference"] == 5023
            )
            _, adapter = server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=40,
                critical=False,
                rng=rng,
            )

            def los(origin, destination, current):
                return authoritative_visible(
                    character["map_id"],
                    origin,
                    destination,
                    current,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in current.actors.values()
                        if actor.hp > 0
                    },
                )

            selection = eligible_cast_targets(
                fight,
                character,
                deck,
                action["uid"],
                adapter=adapter,
                line_of_sight=los,
                actor_id=doll_id,
                limit=128,
                maximum_eligible=16,
            )
            enemy_target = next(
                (
                    row
                    for row in selection["eligible"]
                    if tuple(row["target"]) == fight.actors[-7].position
                ),
                None,
            )
            self.assertIsNotNone(
                enemy_target, {"selection": selection, "doll": doll.position}
            )
            before_action = snapshot(fight)
            action_trace = []
            with combat_diagnostic_scope(
                lambda **row: action_trace.append(row), limit=8192
            ):
                action_tx = prepare_server_spell(
                    struct.pack(
                        ">qqiih", doll_id, action["uid"], *enemy_target["target"]
                    ),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=40,
                    line_of_sight=los,
                    critical=False,
                    rng=rng,
                    player_characters={7: character},
                    deck_blobs={7: deck},
                )
            self.assertEqual(snapshot(fight), before_action)
            self.assertTrue(any(action_tx.outcomes), {"outcomes": action_tx.outcomes})
            final_fight = action_tx.fight
            after_states = sorted(
                entry.reference
                for entry in final_fight.actors[doll_id].state_ledger.entries
            )
            caster_state_levels = {
                entry.reference: entry.level
                for entry in final_fight.actors[7].state_ledger.entries
            }
            observations[name] = {
                "doll_id": doll_id,
                "doll_cell": list(doll_cell),
                "tree_area_cells": [list(cell) for cell in sorted(area_cells)],
                "spare_seed_cell": list(spare_seed_cell),
                "cast_outcomes": list(doll_cast_outcomes),
                "turn_order": turn_order,
                "states_before_doll_turn": before_states,
                "states_after_doll_turn_start": after_states,
                "caster_states_before_turn": caster_states_before,
                "caster_state_transitions": caster_state_transitions,
                "caster_state_levels_after_doll_turn": caster_state_levels,
                "owned_area_state_ledgers_after_doll_turn": area_state_ledgers,
                "native_action_outcomes": list(action_tx.outcomes),
                "retained_8151_listener": [
                    {
                        "uid": uid,
                        "effect_class": row.get("effect_class"),
                        "invocation": row.get("invocation"),
                        "native_subscription_masks": row.get(
                            "native_subscription_masks"
                        ),
                        "native_retained_container": row.get(
                            "native_retained_container"
                        ),
                    }
                    for uid, row in final_fight.native_owned_group_effects.items()
                    if row.get("invocation", {}).get("reference") == 379566
                ],
                "8151_source_event_trace": [
                    dict(row)
                    for row in (*cast_trace, *trace, *action_trace)
                    if row.get("effect_reference") in range(379566, 379582)
                ],
                "area_effect_trace": [
                    dict(row)
                    for row in (*cast_trace, *trace, *action_trace)
                    if row.get("effect_reference")
                    in (
                        378645,
                        380036,
                        379712,
                        380035,
                        379567,
                        379568,
                        379569,
                        379570,
                        379571,
                        379572,
                        379574,
                        379575,
                        379576,
                        379577,
                        379578,
                        379579,
                    )
                ],
            }
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-8151-in-area-observation.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(observations, indent=2) + "\n")
        self.assertTrue(observations["baseline"]["cast_outcomes"])
        self.assertTrue(observations["8151"]["cast_outcomes"])
        baseline_callbacks = [
            row
            for row in observations["baseline"]["8151_source_event_trace"]
            if row.get("effect_reference") == 379581
        ]
        passive_callbacks = [
            row
            for row in observations["8151"]["8151_source_event_trace"]
            if row.get("effect_reference") == 379581
        ]
        self.assertTrue(baseline_callbacks)
        self.assertFalse(
            any(row.get("status") == "completed" for row in baseline_callbacks),
            baseline_callbacks,
        )
        completed_passive_callbacks = [
            row for row in passive_callbacks if row.get("status") == "completed"
        ]
        self.assertTrue(completed_passive_callbacks, passive_callbacks)
        self.assertTrue(
            all(row.get("effect_class") == 304 for row in completed_passive_callbacks),
            completed_passive_callbacks,
        )
