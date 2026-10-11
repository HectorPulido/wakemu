"""Actual seed-area outcomes controlled by Sadida passives 8153 and 8154."""
import json
import os
import struct
import unittest
from pathlib import Path

import test_sadida_semantic_qualification as semantic
import test_aniripsa_grant_summon_pipeline as turn_helpers
from wakfu_server.combat_diagnostics import combat_diagnostic_scope


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaPassiveSeedSemanticsTests(unittest.TestCase):
    def test_8153_seed_cast_comparison_records_stat_and_effect_changes(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book

        builder = semantic.SadidaSemanticQualificationTests()
        observations = {}
        for label, passives in (("baseline", ()), ("8153", (8153,))):
            data = builder.fixture_at_distance(2, passives=passives)
            seed, seed_trace = builder.cast_with_trace(data, 8137)
            data = (*data[:2], seed.fight, *data[3:])
            seed_area = next(
                row
                for row in data[2].native_effect_areas.values()
                if row.get("reference") == 1835 and row.get("owner_id") == 7
            )
            # The owner-end area callback applies state3624 to a live seed.
            # The following native921 transformation transfers its dynamic
            # rank into doll state8205, whose authored state effect supplies
            # state8209. Do this before testing8153's level-selected branch.
            turn_helpers.AniripsaGrantSummonPipelineTests().next_player_turn(
                data[2], data[:5]
            )
            doll_tx, doll_trace = builder.cast_with_trace(
                data,
                921,
                target=seed_area.get("cell", seed_area.get("position")),
                action_id=11,
            )
            data = (*data[:2], doll_tx.fight, *data[3:])
            dolls = [
                actor
                for actor in data[2].actors.values()
                if getattr(actor, "native_summon_source", None)
                and actor.hp > 0
                and actor_action_book(actor)["profile"] == 3748
            ]
            self.assertEqual(len(dolls), 1)
            doll = dolls[0]
            doll_state_levels = {
                entry.reference: entry.level for entry in doll.state_ledger.entries
            }
            self.assertGreaterEqual(
                doll_state_levels.get(8209, 0),
                1,
                {"label": label, "doll_states": doll_state_levels, "trace": doll_trace},
            )
            for _ in range(20):
                if data[2].current is not None and data[2].current.id == 7:
                    break
                turn_helpers.AniripsaGrantSummonPipelineTests().end_current_turn(
                    data[2], data[:5]
                )
            self.assertEqual(data[2].current.id, 7)
            before_wp = data[2].actors[7].effect_stats.get(4)
            transaction, trace = builder.cast_with_trace(
                data, 8137, target=doll.position, action_id=12
            )
            data = (*data[:2], transaction.fight, *data[3:])
            actor = data[2].actors[7]
            boundary_trace = []
            observations[label] = {
                "before_wp": before_wp,
                "after_wp": actor.effect_stats.get(4),
                "outcomes": list(transaction.outcomes),
                "doll_id": doll.id,
                "doll_cell": list(doll.position),
                "doll_state_levels_before_seed_cast": doll_state_levels,
                "areas": [
                    {
                        "reference": row.get("reference"),
                        "owner_id": row.get("owner_id"),
                        "cell": row.get("cell", row.get("position")),
                        "states": row.get("states"),
                    }
                    for row in data[2].native_effect_areas.values()
                ],
                "effects": [
                    dict(row)
                    for row in (*seed_trace, *doll_trace, *trace, *boundary_trace)
                    if row.get("effect_reference")
                    in (378140, 378141, 378143, 378811, 379609, 379610)
                ],
                "trace": [
                    dict(row)
                    for row in (*seed_trace, *doll_trace, *trace, *boundary_trace)
                ],
            }
            self.assertTrue(transaction.outcomes)
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-8153-observation.json"
        )
        output.write_text(json.dumps(observations, indent=2) + "\n")
        baseline_refs = {
            (row.get("effect_reference"), row.get("status"))
            for row in observations["baseline"]["trace"]
        }
        passive_refs = [
            row
            for row in observations["8153"]["trace"]
            if row.get("effect_reference") == 379610
        ]
        self.assertTrue(
            any(row["reference"] == 1835 for row in observations["baseline"]["areas"]),
            observations["baseline"],
        )
        self.assertFalse(
            any(row["reference"] == 1835 for row in observations["8153"]["areas"]),
            observations["8153"],
        )
        self.assertFalse(
            any(
                ref == 379610 and status == "completed" for ref, status in baseline_refs
            ),
            observations["baseline"],
        )
        self.assertTrue(
            any(
                row.get("status") == "completed" and row.get("level") == 2
                for row in passive_refs
            ),
            passive_refs,
        )

    def test_8154_seed_consumption_compares_native_area_callbacks(self):
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import server_runtime

        builder = semantic.SadidaSemanticQualificationTests()
        observations = {}
        for label, passives in (("baseline", ()), ("8154", (8154,))):
            data = builder.fixture_at_distance(2, passives=passives)
            seed, seed_trace = builder.cast_with_trace(data, 8137)
            data = (*data[:2], seed.fight, *data[3:])
            own_seed = next(
                row
                for row in data[2].native_effect_areas.values()
                if row.get("reference") == 1835 and row.get("owner_id") == 7
            )
            cell = own_seed.get("cell", own_seed.get("position"))
            character, monster, fight, deck, rng, _ = data
            runtime = RuntimeMessages(fight)

            def area_provider(preview, **boundary):
                return prepare_area_movement(
                    character, {-7: monster}, preview, deck, rng=rng, **boundary
                )

            origin = tuple(runtime.fight.actors[7].position)
            movement_trace = []
            with combat_diagnostic_scope(
                lambda **row: movement_trace.append(row), limit=8192
            ):
                apply_client(
                    runtime,
                    3,
                    struct.pack(">qiih", 7, *cell),
                    lambda actor: b"",
                    area_provider=area_provider,
                )
            moved_fight = runtime.fight
            observations[label] = {
                "seed_cell": list(cell),
                "movement_origin": list(origin),
                "movement_destination": list(moved_fight.actors[7].position),
                "remaining_areas": [
                    {
                        "reference": row.get("reference"),
                        "owner_id": row.get("owner_id"),
                        "cell": row.get("cell", row.get("position")),
                    }
                    for row in moved_fight.native_effect_areas.values()
                ],
                "effects": [
                    dict(row)
                    for row in (*seed_trace, *movement_trace)
                    if row.get("effect_reference")
                    in (379518, 379519, 379520, 379521, 379522)
                ],
                "trace": [dict(row) for row in (*seed_trace, *movement_trace)],
            }
            self.assertEqual(tuple(moved_fight.actors[7].position), tuple(cell))
            self.assertTrue(observations[label]["effects"] or movement_trace)
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-8154-observation.json"
        )
        output.write_text(json.dumps(observations, indent=2) + "\n")
        baseline_areas = {
            row["reference"] for row in observations["baseline"]["remaining_areas"]
        }
        passive_areas = {
            row["reference"] for row in observations["8154"]["remaining_areas"]
        }
        baseline_effects = observations["baseline"]["effects"]
        passive_effects = observations["8154"]["effects"]
        self.assertIn(1835, baseline_areas)
        self.assertNotIn(1835, passive_areas)
        self.assertFalse(
            any(
                row.get("effect_reference") == 379521
                and row.get("status") == "completed"
                for row in baseline_effects
            ),
            baseline_effects,
        )
        self.assertTrue(
            any(
                row.get("effect_reference") == 379521
                and row.get("status") == "completed"
                for row in passive_effects
            ),
            passive_effects,
        )
        self.assertTrue(
            any(
                row.get("effect_reference") == 379522
                and row.get("status") == "completed"
                for row in passive_effects
            ),
            passive_effects,
        )
