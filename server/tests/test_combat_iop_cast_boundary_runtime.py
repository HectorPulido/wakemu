"""Real native Iop states and cast targets through the shared runtime."""
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class IopCastBoundaryRuntimeTests(unittest.TestCase):
    def fixture(self, active, passive=(), *, distance=2):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_server_spell import prepare_server_initialization

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            8,
            200,
            target_hp=2000,
            native_qi=True,
            target_distance=distance,
        )
        deck = encode_deck(active, passive)
        rng = random.Random(0)
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
        return character, monster, fight, deck, rng

    def cast(self, fixture, reference, action_id):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        character, monster, fight, deck, rng = fixture
        from wakfu_server.combat_spell_grant import granted_spells

        grants = granted_spells(fight, 7)
        uid = grants[reference]["uid"] if reference in grants else (7 << 32) | reference
        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=4096):
            transaction = prepare_server_spell(
                struct.pack(">qqiih", 7, uid, *fight.actors[-7].position),
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=action_id,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        self.assertTrue(transaction.fight.native_owned_group_effects)
        for row in transaction.fight.native_owned_group_effects.values():
            self.assertIsNone(row["invocation"].get("native_cast_boundary_context"))
        return transaction, trace

    def test_charge_selects_only_real_distance_branch_one_two_three(self):
        selected = {1: 397665, 2: 397666, 3: 397667}
        for distance, branch in selected.items():
            with self.subTest(distance=distance):
                fixture = self.fixture([4783], distance=distance)
                self.assertIn(
                    7553,
                    {
                        state.reference
                        for state in fixture[2].actors[7].state_ledger.entries
                    },
                )
                transaction, trace = self.cast(fixture, 4783, 2)
                executed = {
                    row.get("effect_reference")
                    for row in trace
                    if row.get("status") in ("completed", "no_effect")
                }
                # Distance3's original removal branch is admitted but is a
                # native no-op when none of its removable states is present.
                self.assertIn(branch, executed)
                self.assertTrue(
                    (set(selected.values()) - {branch}).isdisjoint(executed)
                )
                self.assertEqual(transaction.plan["target_id"], -7)

    def test_judgment_then_fire_spell_activates_actual_8912_tree(self):
        fixture = self.fixture([4776, 4775])
        first, _ = self.cast(fixture, 4776, 2)
        self.assertIn(
            8912,
            {state.reference for state in first.fight.actors[-7].state_ledger.entries},
        )
        character, monster, _, deck, rng = fixture
        second, trace = self.cast((character, monster, first.fight, deck, rng), 4775, 3)
        completed = {
            row.get("effect_reference")
            for row in trace
            if row.get("status") == "completed"
        }
        self.assertIn(397245, completed)
        self.assertIn(397246, completed)
        self.assertIn(397247, completed)
        self.assertTrue(second.outcomes)

    def test_uppercut_then_owned_movement_and_charge_three_raise_ap_combo(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_actor import actual_actor_stats
        from wakfu_server.combat_condition_distance import (
            DistanceActor,
            native_caster_target_distance,
        )

        fixture = self.fixture([4783], distance=1)
        uppercut, _ = self.cast(fixture, 8403, 2)
        caster = uppercut.fight.actors[7]
        self.assertEqual(
            next(
                state.level
                for state in caster.state_ledger.entries
                if state.reference == 3448
            ),
            1,
        )
        target = uppercut.fight.actors[-7]
        target_shape = DistanceActor(*target.position[:2], target.physical_radius)
        paths = []
        for start, middle in sorted(uppercut.fight.edges):
            if start != caster.position:
                continue
            for origin, end in sorted(uppercut.fight.edges):
                if (
                    origin != middle
                    or end == caster.position
                    or target.position in (middle, end)
                ):
                    continue
                if (
                    native_caster_target_distance(
                        DistanceActor(*end[:2], caster.physical_radius), target_shape
                    )
                    == 3
                ):
                    paths.append((middle, end))
        self.assertTrue(paths, "Actual native map requires a legal two-MP retreat")
        runtime = RuntimeMessages(uppercut.fight)
        runtime.action_id = uppercut.action_id
        character, monster, _, deck, rng = fixture
        before_mp = caster.mp
        _, moved = apply_client(
            runtime,
            3,
            struct.pack(">q", 7)
            + b"".join(struct.pack(">iih", *cell) for cell in paths[0]),
            lambda actor: actual_actor_stats(
                character,
                actor,
                runtime.fight.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
            ),
        )
        self.assertEqual(moved["cost"], 2)
        self.assertEqual(caster.mp, before_mp - 2)
        charged, trace = self.cast(
            (character, monster, runtime.fight, deck, rng), 4783, runtime.action_id + 1
        )
        self.assertEqual(
            next(
                state.level
                for state in charged.fight.actors[7].state_ledger.entries
                if state.reference == 3448
            ),
            2,
        )
        self.assertIn(
            397587,
            {
                row.get("effect_reference")
                for row in trace
                if row.get("status") == "completed"
            },
        )

    def test_judgment_does_not_activate_fire_clause_for_earth_spell(self):
        from wakfu_server.combat_activation_conditions import current_activation
        from wakfu_server.combat_active_spell import active_spell_scope

        fixture = self.fixture([4776, 4780])
        first, _ = self.cast(fixture, 4776, 2)
        with active_spell_scope(first.fight, 4780, level=200):
            self.assertFalse(current_activation(first.fight, "IsActivatedByElement", 1))
        character, monster, _, deck, rng = fixture
        second, trace = self.cast((character, monster, first.fight, deck, rng), 4780, 3)
        skipped = {
            row.get("effect_reference")
            for row in trace
            if row.get("status") == "skipped_condition"
        }
        self.assertIn(397245, skipped)
        self.assertNotIn(397247, {row.get("effect_reference") for row in trace})
        self.assertTrue(second.outcomes)
