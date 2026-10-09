"""Actual Iop combo and stationary-state lifecycle, without state injection."""
import os
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class IopPreparationMovementRuntimeTests(unittest.TestCase):
    def test_borrasca_uppercut_preparation_modifies_and_consumes_next_attack(self):
        from test_combat_iop_cast_boundary_runtime import IopCastBoundaryRuntimeTests

        helper = IopCastBoundaryRuntimeTests()
        fixture = helper.fixture([4785], distance=1)
        character, monster, fight, deck, rng = fixture
        for action_id, reference in enumerate((8402, 8402, 8403), 2):
            transaction, _ = helper.cast(
                (character, monster, fight, deck, rng), reference, action_id
            )
            fight = transaction.fight
        prepared = next(
            state
            for state in fight.actors[7].state_ledger.entries
            if state.reference == 3462
        )
        self.assertGreater(prepared.level, 0)
        from wakfu_server.combat_final_modifier import NativeFinalModifier

        additions = []
        original_add = NativeFinalModifier.add

        def observe_add(accumulator, value):
            result = original_add(accumulator, value)
            additions.append((accumulator.family, value, result))
            return result

        with patch.object(NativeFinalModifier, "add", observe_add):
            transaction, trace = helper.cast(
                (character, monster, fight, deck, rng), 4785, 5
            )
        completed = {
            row.get("effect_reference")
            for row in trace
            if row.get("status") == "completed"
        }
        self.assertIn(151183, completed)
        self.assertIn(151185, completed)
        self.assertIn(
            (5, prepared.level), [(family, value) for family, value, _ in additions]
        )
        self.assertNotIn(
            3462,
            {
                state.reference
                for state in transaction.fight.actors[7].state_ledger.entries
            },
        )
        self.assertLess(transaction.fight.actors[-7].hp, fight.actors[-7].hp)

    def test_banner_actual_cast_then_legal_step_removes_stationary_state(self):
        from test_combat_iop_cast_boundary_runtime import IopCastBoundaryRuntimeTests
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_actor import actual_actor_stats

        helper = IopCastBoundaryRuntimeTests()
        character, monster, fight, deck, rng = helper.fixture(
            [4785], passive=[8422], distance=2
        )
        caster = fight.actors[7]
        from wakfu_server.combat_spell_grant import granted_spells

        grant = granted_spells(fight, 7)[8405]
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=4096):
            transaction = prepare_server_spell(
                struct.pack(">qqiih", 7, grant["uid"], *caster.position),
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=2,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        self.assertIn(
            8965,
            {
                state.reference
                for state in transaction.fight.actors[7].state_ledger.entries
            },
            dict(
                actors={
                    identity: [state.reference for state in actor.state_ledger.entries]
                    for identity, actor in transaction.fight.actors.items()
                },
                effects=[
                    row
                    for row in trace
                    if row.get("effect_reference") in (397431, 398799, 398800)
                ],
            ),
        )
        runtime = RuntimeMessages(transaction.fight)
        runtime.action_id = transaction.action_id
        caster = runtime.fight.actors[7]
        destinations = [
            end
            for start, end in sorted(runtime.fight.edges)
            if start == caster.position and end != runtime.fight.actors[-7].position
        ]
        self.assertTrue(destinations)
        before_mp = caster.mp

        def provider(candidate, **boundary):
            return prepare_area_movement(
                character, {-7: monster}, candidate, deck, rng=rng, **boundary
            )

        apply_client(
            runtime,
            3,
            struct.pack(">qiih", 7, *destinations[0]),
            lambda actor: actual_actor_stats(
                character,
                actor,
                runtime.fight.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
            ),
            area_provider=provider,
        )
        self.assertNotIn(
            8965,
            {state.reference for state in runtime.fight.actors[7].state_ledger.entries},
        )
        self.assertEqual(runtime.fight.actors[7].position, destinations[0])
        self.assertLess(runtime.fight.actors[7].mp, before_mp)
