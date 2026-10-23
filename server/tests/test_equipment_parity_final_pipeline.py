"""Real paid casts exercise permanent gear's table-parity faq branches."""
from copy import deepcopy
import importlib
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
import test_equipment_null_carrier_pipeline as _null_pipeline

advance_actual_turn = _null_pipeline.advance_actual_turn
from wakfu_server.combat_final_modifier import triggering_runner_source
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.fight_checkpoint_store import snapshot


class EquipmentParityFinalPipelineTests(PostgresCase):
    def _fixture(self, reference):
        # Reuse the established native Ready fixture; this still grants and
        # equips the real item through its persisted inventory/build path.
        return _null_pipeline.EquipmentNullCarrierPipelineTests._fixture(
            self,
            reference=reference,
            slot=17,
            level=245,
            breed=8,
            active_spells=[4780, 4782],
            select_elements=True,
        )

    def _wait_for_owner_table_turn(self, values, expected_parity):
        char, _monster, _deck, _rng, runtime, _stats = values
        owner = char["id"]
        for _ in range(20):
            if (
                runtime.fight.current.id == owner
                and runtime.fight.native_table_turn % 2 == expected_parity
            ):
                return
            advance_actual_turn(runtime)
        self.fail("Native table-turn driver did not reach requested owner parity")

    def _cast_and_observe(self, values, spell_id, *, expected_delta):
        char, monster, deck, rng, runtime, stats = values
        owner = char["id"]
        actor = runtime.fight.actors[owner]
        target = runtime.fight.actors[-200]
        before_ap = actor.ap
        before_target_hp = target.hp
        observed = []

        final_module = importlib.import_module("wakfu_server.combat_final_modifier")

        original = final_module.update_triggering_final

        def observe(invocation, value):
            source = triggering_runner_source()
            before = None if source is None else source.final_modifier.value
            result = original(invocation, value)
            after = None if source is None else source.final_modifier.value
            observed.append(
                {
                    "reference": invocation.reference,
                    "caster_id": invocation.caster_id,
                    "target_id": invocation.target_id,
                    "source_uid": None if source is None else source.uid,
                    "source_family": None
                    if source is None
                    else source.effect_action_id,
                    "trigger_uid": (
                        None
                        if invocation.native_trigger_context is None
                        else invocation.native_trigger_context.get("uid")
                    ),
                    "before": before,
                    "after": after,
                    "value": value,
                    "accepted": result,
                }
            )
            return result

        with patch.object(final_module, "update_triggering_final", side_effect=observe):
            tx = prepare_server_spell(
                struct.pack(
                    ">qqiih", owner, (owner << 32) | spell_id, *target.position
                ),
                char,
                {-200: monster},
                runtime.fight,
                char["account_id"],
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
            self.assertGreater(tx.plan["costs"]["ap"], 0)
            self.assertLess(tx.fight.actors[owner].ap, before_ap)
            self.assertLess(tx.fight.actors[-200].hp, before_target_hp)
            packets = commit_spell_transaction(
                runtime,
                tx,
                stats_serializer=lambda current, preview: stats(current, preview),
            )
        self.assertTrue(packets)
        self.assertIs(runtime.fight, tx.fight)
        actual = [row for row in observed if row["accepted"]]
        if expected_delta is None:
            self.assertFalse(actual, observed)
            return actual, before_target_hp - runtime.fight.actors[-200].hp
        self.assertTrue(actual, observed)
        self.assertEqual({row["value"] for row in actual}, {expected_delta}, actual)
        self.assertTrue(all(row["caster_id"] == owner for row in actual), actual)
        self.assertTrue(all(row["target_id"] == -200 for row in actual), actual)
        self.assertTrue(all(row["source_family"] == 3 for row in actual), actual)
        self.assertTrue(
            all(isinstance(row["source_uid"], int) for row in actual), actual
        )
        self.assertTrue(
            all(row["source_uid"] == row["trigger_uid"] for row in actual), actual
        )
        self.assertTrue(
            all(row["after"] - row["before"] == expected_delta for row in actual),
            actual,
        )
        self.assertEqual(
            len({row["source_uid"] for row in actual}), len(actual), actual
        )
        self.assertFalse(
            any(
                effect.get("effect_class") == 1093
                for effect in runtime.fight.owned_stat_effects.values()
            )
        )
        return actual, before_target_hp - runtime.fight.actors[-200].hp

    def test_paid_damage_updates_only_the_matching_native_parity_modifier(self):
        # 29420: even-table melee branch adds five; the next odd-table melee
        # branch is the native complement and must not mutate the faq source.
        values = self._fixture(29420)
        char, monster, deck, rng, runtime, stats = values
        owner = char["id"]
        self._wait_for_owner_table_turn(values, 0)
        actor = runtime.fight.actors[owner]
        self.assertEqual(runtime.fight.native_table_turn % 2, 0)
        destination = (-7, -7, -1)
        movement_provider = lambda preview, **boundary: prepare_area_movement(
            char, {-200: monster}, preview, deck, rng=rng, **boundary
        )
        packets, movement_event = apply_client(
            runtime,
            char["account_id"],
            struct.pack(">qiih", owner, *destination),
            stats,
            runtime_stats_serializer=lambda current, preview: stats(current, preview),
            area_provider=movement_provider,
        )
        self.assertTrue(packets)
        self.assertTrue(movement_event)
        self.assertEqual(runtime.fight.actors[owner].position, destination)
        # Compare the real carrier against the same actor/turn/RNG with its
        # native permanent state retired through the production inverse path.
        from copy import deepcopy
        from random import Random
        from wakfu_server.combat_server_spell import server_runtime

        source_turn = deepcopy(runtime.fight)
        control_rng = Random()
        control_rng.setstate(rng.getstate())
        control_runtime = deepcopy(runtime)
        control_fight = control_runtime.fight
        state_uids = [
            state.uid
            for state in control_fight.actors[owner].state_ledger.entries
            if state.reference == 7069
        ]
        self.assertEqual(len(state_uids), 1)
        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=control_runtime.action_id + 1,
            critical=False,
            rng=control_rng,
        )
        dispatcher, _ = factory(
            control_fight, {"native_retained_container": {"present": False}}
        )
        retained = dispatcher.native_retention
        retained.removal(retained.view()).remove(tuple(state_uids))
        retained.synchronize()
        self.assertFalse(
            any(
                state.reference == 7069
                for state in control_fight.actors[owner].state_ledger.entries
            )
        )
        self.assertEqual(snapshot(runtime.fight), snapshot(source_turn))
        _rows, control_loss = self._cast_and_observe(
            (char, monster, deck, control_rng, control_runtime, stats),
            4780,
            expected_delta=None,
        )
        _rows, equipped_loss = self._cast_and_observe(values, 4780, expected_delta=5)
        self.assertGreater(equipped_loss, control_loss)
        stable = snapshot(runtime.fight)
        from wakfu_server.combat_reproduction_state import decode_state, encode_state

        restored = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(restored), stable)
        runtime.fight = restored
        self._wait_for_owner_table_turn(values, 1)
        # The actor remains in melee range. On the odd turn the same real cast
        # is paid and damages, while the opposite-parity modifier stays inert.
        before_hp = runtime.fight.actors[-200].hp
        actor = runtime.fight.actors[owner]
        before_ap = actor.ap
        final_module = importlib.import_module("wakfu_server.combat_final_modifier")

        observed_values = []
        original = final_module.update_triggering_final

        def observe_unmatched(invocation, value):
            source = triggering_runner_source()
            before = None if source is None else source.final_modifier.value
            result = original(invocation, value)
            after = None if source is None else source.final_modifier.value
            observed_values.append((result, before, after, invocation.reference))
            return result

        target = runtime.fight.actors[-200]
        with patch.object(
            final_module, "update_triggering_final", side_effect=observe_unmatched
        ):
            tx = prepare_server_spell(
                struct.pack(">qqiih", owner, (owner << 32) | 4780, *target.position),
                char,
                {-200: monster},
                runtime.fight,
                char["account_id"],
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
            self.assertLess(tx.fight.actors[owner].ap, before_ap)
            self.assertLess(tx.fight.actors[-200].hp, before_hp)
            commit_spell_transaction(
                runtime,
                tx,
                stats_serializer=lambda current, preview: stats(current, preview),
            )
        self.assertFalse(
            any(
                result and after != before
                for result, before, after, _ in observed_values
            ),
            observed_values,
        )

        # 29445: odd-table zone branch is positive. Its real spell4782 has an
        # explicitly native zone trigger even though the geometry is a point.
        values = self._fixture(29445)
        char, _monster, _deck, _rng, runtime, _stats = values
        self._wait_for_owner_table_turn(values, 1)
        self._cast_and_observe(values, 4782, expected_delta=5)
