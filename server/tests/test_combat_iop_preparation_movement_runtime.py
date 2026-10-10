"""Actual Iop combo and stationary-state lifecycle, without state injection."""
import os
import struct
import unittest
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class IopPreparationMovementRuntimeTests(unittest.TestCase):
    def _checkpoint_proven_environmental_combo(self, attack_reference):
        import random

        from test_combat_iop_cast_boundary_runtime import IopCastBoundaryRuntimeTests
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_environment_glyphs import prepare_environment_glyphs
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.spells import encode_deck

        # This Qq/faY UID is from read-only checkpoint 98; it seeds a detached
        # local arena through the normal faP/faY producers, never a fake manager.
        terrain_uid = 645778764256831384
        character, monster, fight = SpellTransactionTests().native_server_fixture(
            8,
            200,
            target_hp=2000,
            native_qi=True,
            target_distance=1,
            variation_seed=17,
        )
        arena = local_arena(
            character["map_id"],
            character["id"],
            fight.actors[7].position,
            fight.actors[-7].position,
            variation_seed=17,
        )
        fight.native_border_constructor = dict(
            reference=46,
            identity=terrain_uid,
            arena={
                key: arena[key]
                for key in ("native_border_policy", "native_border_cells", "min_z")
            },
        )
        prepare_environment_glyphs(fight, arena, terrain_uid)
        deck = encode_deck([attack_reference])
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

        helper = IopCastBoundaryRuntimeTests()
        for action_id, reference in enumerate((8402, 8402, 8403, attack_reference), 2):
            if action_id == 5:
                self.assertIn(
                    3462,
                    {state.reference for state in fight.actors[7].state_ledger.entries},
                )
            try:
                transaction, trace = helper.cast(
                    (character, monster, fight, deck, rng), reference, action_id
                )
            except Exception as error:
                raise AssertionError(
                    f"Native Iop spell {reference} at action {action_id} failed; "
                    "checkpoint-backed faY/faP registrations were installed"
                ) from error
            if action_id == 5:
                self.assertTrue(
                    any(
                        row.get("effect_reference") == 151184
                        and row.get("status") in ("completed", "no_effect")
                        for row in trace
                    ),
                    trace,
                )
            fight = transaction.fight

        area_rows = tuple(fight.native_effect_areas.values())
        self.assertTrue(any(row["reference"] == 910 for row in area_rows))
        self.assertTrue(any(row["reference"] == 46 for row in area_rows))
        self.assertTrue(
            all(row["native_running_effect_manager"] is False for row in area_rows)
        )
        area_ids = {row["uid"] for row in area_rows}
        self.assertTrue(
            area_ids.isdisjoint(
                {
                    record.get("manager_id")
                    for record in fight.native_retained_records.values()
                }
            )
        )

    def test_borrasca_combo_dispatches_checkpoint_proven_null_qf_areas_with_jabs_4785(
        self,
    ):
        self._checkpoint_proven_environmental_combo(4785)

    def test_borrasca_combo_dispatches_checkpoint_proven_null_qf_areas_with_bofetada_4787(
        self,
    ):
        self._checkpoint_proven_environmental_combo(4787)

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

        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        executions = []
        original_execute = EffectDispatcher.execute

        def observe_execute(dispatcher, invocation, **kwargs):
            result = original_execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (409890, 151186, 151188):
                executions.append(
                    {
                        "reference": invocation.reference,
                        "caster_id": invocation.caster_id,
                        "target_id": invocation.target_id,
                        "state_uid": invocation.state_uid,
                        "native_context": invocation.native_trigger_context,
                        "native_explicit_target": invocation.native_explicit_target,
                        "result": result,
                    }
                )
            return result

        with (
            patch.object(NativeFinalModifier, "add", observe_add),
            patch.object(EffectDispatcher, "execute", observe_execute),
        ):
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
            msg={
                "preparation_trace": [
                    {
                        key: row.get(key)
                        for key in (
                            "effect_reference",
                            "status",
                            "caster_id",
                            "target_id",
                            "state_uid",
                            "reason",
                        )
                    }
                    for row in trace
                    if row.get("effect_reference") in range(151183, 151191)
                    or row.get("effect_reference") in (409890, 151186)
                ],
                "selected_executions": executions,
                "retained_rows": [
                    {
                        key: row.get(key)
                        for key in (
                            "uid",
                            "target_id",
                            "generic_effect",
                            "owner_uid",
                            "manager_id",
                            "container_type",
                            "container_id",
                            "container_kind",
                            "container_is_spell",
                        )
                    }
                    for row in transaction.fight.native_retained_records.values()
                    if row.get("generic_effect") in (409890, 151186, 151183, 151185)
                ],
                "remaining_preparation": [
                    (state.reference, state.uid, state.level)
                    for state in transaction.fight.actors[7].state_ledger.entries
                    if state.reference == 3462
                ],
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
