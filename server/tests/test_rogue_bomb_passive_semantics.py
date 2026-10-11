"""Actual owned Rogue bomb casts for the bomb-wall/delay/elemental passives."""
import os
import random
import unittest

import test_combat_spell_transaction as native_fixture
import test_rogue_runtime_pipeline as pipeline
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_start,
)
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.spells import encode_deck, validate_deck


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RogueBombPassiveSemanticsTests(unittest.TestCase):
    """Use real spell grants, target validation, and summon/state transitions."""

    cast = pipeline.RogueRuntimePipelineTests.cast
    los = staticmethod(pipeline.RogueRuntimePipelineTests.los)
    summons = staticmethod(pipeline.RogueRuntimePipelineTests.summons)

    def fixture(self, active, passives=(), *, target_distance=3):
        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            13,
            200,
            native_qi=True,
            full_health=True,
            target_hp=20000,
            target_distance=target_distance,
            variation_seed=17,
        )
        deck, rng = encode_deck(active, passives), random.Random(17)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        fight, _ = prepare_server_turn_start(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=fight.current.id,
            action_id=2,
            rng=rng,
            area_callbacks=True,
        )
        return character, monster, fight, deck, rng

    @staticmethod
    def states(actor):
        return sorted(
            (entry.reference, entry.level) for entry in actor.state_ledger.entries
        )

    def cast_with_trace(self, data, reference, target=None, *, action_id=10):
        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=8192):
            data, tx = self.cast(data, reference, target, action_id=action_id)
        return data, tx, trace

    @staticmethod
    def areas(fight):
        return sorted(
            (str(row.get("reference")), tuple(row.get("cell", ())))
            for row in getattr(fight, "native_effect_areas", {}).values()
        )

    def bomb_scenario(self, passives=(), *, earth=False):
        # Keep the authentic owned deck used by the Rogue pipeline. 6468 is
        # owned there; 7906 and 6495 are granted spell-book actions, not deck
        # entries, and are cast only through their actual grants.
        active = (6463, 6468, 6473)
        data = self.fixture(active, passives, target_distance=2 if earth else 3)
        if earth:
            data, _ = self.cast(data, 6468, data[2].actors[-7].position, action_id=10)
            stance = {
                ref
                for actor in data[2].actors.values()
                for ref, _ in self.states(actor)
            }
            self.assertTrue(
                stance & {7916, 7917},
                {
                    "states": {
                        actor.id: self.states(actor)
                        for actor in data[2].actors.values()
                    }
                },
            )
        data, _ = self.cast(data, 7906, action_id=11 if earth else 10)
        bombs = self.summons(data[2], (3795, 3796, 3797))
        self.assertEqual(
            len(bombs), 1, "actual native seed cast should create one owned bomb"
        )
        bomb = bombs[0]
        self.assertEqual(bomb.native_summon_source["caster_id"], 7)
        self.assertEqual(bomb.native_summon_source["controller_id"], 7)
        return data, bomb

    def test_powder_wall_passive_creates_native_wall_from_real_bomb_cast(self):
        control, control_bomb = self.bomb_scenario()
        enabled, enabled_bomb = self.bomb_scenario((6487,))
        control, _ = self.cast(control, 6495, control_bomb.position, action_id=11)
        enabled, _ = self.cast(enabled, 6495, enabled_bomb.position, action_id=11)
        control_walls = [area for area in self.areas(control[2]) if area[0] == "1818"]
        enabled_walls = [area for area in self.areas(enabled[2]) if area[0] == "1818"]
        self.assertFalse(control_walls)
        self.assertTrue(enabled_walls, self.areas(enabled[2]))

    def test_delayed_bomb_passive_uses_real_earth_stance_and_delayed_area_route(self):
        active = (6463, 6468, 6473)
        control = self.fixture(active, target_distance=2)
        enabled = self.fixture(active, (7984,), target_distance=2)
        for case, data in (("control", control), ("enabled", enabled)):
            data, _ = self.cast(data, 6468, data[2].actors[-7].position, action_id=10)
            self.assertIn(
                7917,
                {ref for ref, _ in self.states(data[2].actors[7])},
                {actor.id: self.states(actor) for actor in data[2].actors.values()},
            )
            # 6468 lawfully establishes the caster's native 7917 stance. Cast
            # the granted seed through the actual free-cell selector; the paired
            # passive branch changes that real placement into a delayed area.
            data, _ = self.cast(data, 7906, action_id=11)
            if case == "control":
                control = data
            else:
                enabled = data
        control_delayed = [
            area
            for area in self.areas(control[2])
            if area[0] in {"1809", "1810", "1811"}
        ]
        enabled_delayed = [
            area
            for area in self.areas(enabled[2])
            if area[0] in {"1809", "1810", "1811"}
        ]
        self.assertFalse(control_delayed)
        self.assertTrue(enabled_delayed, self.areas(enabled[2]))

    @staticmethod
    def trace_rows(trace, references):
        return [row for row in trace if row.get("effect_reference") in references]

    def test_elemental_bombs_passive_uses_authentic_detonation_event(self):
        control, control_bomb = self.bomb_scenario()
        enabled, enabled_bomb = self.bomb_scenario((7090,))
        enabled_passives = set(validate_deck(enabled[3], 13, 200)["passive"])
        self.assertIn(7090, enabled_passives)
        self.assertIn(7923, {ref for ref, _ in self.states(enabled_bomb)})
        # The real granted 6495 cast kills the actual owned bomb. Observe the
        # native state-listener children during that transaction, before the
        # death cleanup removes the bomb's retained manager and ledger.
        control, _, control_trace = self.cast_with_trace(
            control, 6495, control_bomb.position, action_id=11
        )
        enabled, _, enabled_trace = self.cast_with_trace(
            enabled, 6495, enabled_bomb.position, action_id=11
        )
        self.assertEqual(control[2].actors[control_bomb.id].hp, 0)
        self.assertEqual(enabled[2].actors[enabled_bomb.id].hp, 0)
        elemental_refs = {376891, 376895, 376899, 376917, 376922, 376927}
        control_rows = self.trace_rows(control_trace, elemental_refs)
        enabled_rows = self.trace_rows(enabled_trace, elemental_refs)
        self.assertFalse(control_rows)
        # Own-bomb detonation does not establish the enemy marker route.
        self.assertFalse(enabled_rows, enabled_trace)

    def test_elemental_bombs_enemy_marker_route_uses_actual_element_and_detonation(
        self,
    ):
        control, control_bomb = self.bomb_scenario()
        enabled, enabled_bomb = self.bomb_scenario((7090,))
        enabled_passives = set(validate_deck(enabled[3], 13, 200)["passive"])
        self.assertIn(7090, enabled_passives)
        self.assertIn(7923, {ref for ref, _ in self.states(enabled_bomb)})
        # Match the source-qualified probe: elemental hit on the live owned
        # bomb, followed by granted detonation at an actual enemy cell.
        control, _, control_element_trace = self.cast_with_trace(
            control, 6463, control_bomb.position, action_id=30
        )
        enabled, _, enabled_element_trace = self.cast_with_trace(
            enabled, 6463, enabled_bomb.position, action_id=30
        )
        self.assertIn(
            8041, {ref for ref, _ in self.states(enabled[2].actors[enabled_bomb.id])}
        )
        control, control_tx, control_trace = self.cast_with_trace(
            control, 6495, control[2].actors[-7].position, action_id=31
        )
        enabled, enabled_tx, enabled_trace = self.cast_with_trace(
            enabled, 6495, enabled[2].actors[-7].position, action_id=31
        )
        self.assertEqual(control[2].actors[control_bomb.id].hp, 0)
        self.assertEqual(enabled[2].actors[enabled_bomb.id].hp, 0)
        self.assertIn(
            8041, {ref for ref, _ in self.states(control[2].actors[control_bomb.id])}
        )
        self.assertIn(
            8041, {ref for ref, _ in self.states(enabled[2].actors[enabled_bomb.id])}
        )

        def state_events(tx, kind, state_id, actor_id):
            return [
                row
                for row in tx.events
                if row.get("kind") == kind
                and row.get("state_id", row.get("reference")) == state_id
                and row.get("actor_id") == actor_id
            ]

        # The passive's enemy branch comes from the native 376868->376870
        # retained-effect route. 8037 is applied, then decursed in the same
        # transaction; 756 remains on the enemy. The matched control has
        # neither receipt.
        self.assertFalse(state_events(control_tx, "state_applied", 756, -7))
        self.assertFalse(state_events(control_tx, "state_applied", 8037, -7))
        self.assertTrue(
            state_events(enabled_tx, "state_applied", 756, -7), enabled_tx.events
        )
        self.assertTrue(
            state_events(enabled_tx, "state_applied", 8037, -7), enabled_tx.events
        )
        self.assertTrue(
            state_events(enabled_tx, "state_removed", 8037, -7), enabled_tx.events
        )
        enabled_route = self.trace_rows(enabled_trace, {376868, 376870})
        self.assertIn(
            (376868, "completed"),
            {(row.get("effect_reference"), row.get("status")) for row in enabled_route},
        )
        self.assertIn(
            (376870, "completed"),
            {(row.get("effect_reference"), row.get("status")) for row in enabled_route},
        )

    def test_explobomba_native_children_run_in_authentic_detonation(self):
        control, control_bomb = self.bomb_scenario()
        enabled, enabled_bomb = self.bomb_scenario((7065,))
        enabled_passives = set(validate_deck(enabled[3], 13, 200)["passive"])
        self.assertIn(7065, enabled_passives)
        self.assertIn(7923, {ref for ref, _ in self.states(enabled_bomb)})
        control, _, control_trace = self.cast_with_trace(
            control, 6495, control_bomb.position, action_id=11
        )
        enabled, _, enabled_trace = self.cast_with_trace(
            enabled, 6495, enabled_bomb.position, action_id=11
        )
        self.assertEqual(control[2].actors[control_bomb.id].hp, 0)
        self.assertEqual(enabled[2].actors[enabled_bomb.id].hp, 0)
        passive_refs = {372320, 372321, 372324, 372325}
        control_rows = self.trace_rows(control_trace, passive_refs)
        enabled_rows = self.trace_rows(enabled_trace, passive_refs)
        enabled_status = {
            (row.get("effect_reference"), row.get("status")) for row in enabled_rows
        }
        # Native own-6495/current-fighter guard: the two guarded children
        # reject this exact branch; the passive-only children complete.
        self.assertTrue(
            {(372320, "skipped_condition"), (372324, "skipped_condition")}
            <= enabled_status,
            enabled_rows,
        )
        self.assertTrue(
            {(372321, "completed"), (372325, "completed")} <= enabled_status,
            enabled_rows,
        )
        control_status = {
            (row.get("effect_reference"), row.get("status")) for row in control_rows
        }
        self.assertTrue(
            {(reference, "skipped_condition") for reference in passive_refs}
            <= control_status,
            control_rows,
        )
        self.assertFalse(
            any(status == "completed" for _, status in control_status), control_rows
        )
        self.assertTrue(
            all(
                "GetActiveSpellId() <> 6495" in row.get("criteria", "")
                for row in enabled_rows
                if row.get("effect_reference") in {372320, 372324}
                and row.get("status") == "skipped_condition"
            ),
            enabled_rows,
        )
