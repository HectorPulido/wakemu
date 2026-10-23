"""Actual Ready equipment finish policy, food exclusion and durable replay."""
import struct
import unittest
from types import SimpleNamespace
from postgres_case import PostgresCase
import test_equipment_null_carrier_pipeline as _null_pipeline


class EquipmentTerminalBoundaryTests(unittest.TestCase):
    def test_only_finished_winner_context_can_deliver(self):
        from wakfu_server.combat_equipment_finish import prepare_equipment_finish

        for phase, winner in (("active", None), ("finished", None), ("finished", True)):
            with self.assertRaisesRegex(ValueError, "settled terminal fight"):
                prepare_equipment_finish(
                    SimpleNamespace(phase=phase, winner=winner), None, action_id=1
                )

    def test_no_listener_requires_no_factory_and_malformed_masks_reject(self):
        from wakfu_server.combat_equipment_finish import (
            prepare_equipment_finish,
            preflight_equipment_finish,
        )

        self.assertFalse(
            preflight_equipment_finish(None, {"present": True, "type": 12})
        )
        fight = SimpleNamespace(
            phase="finished",
            winner=0,
            native_owned_equipment_initializations={1: {"sources": []}},
            native_owned_group_effects={},
        )
        self.assertEqual(
            prepare_equipment_finish(fight, None, action_id=1), (fight, ())
        )
        fight.native_owned_group_effects[9] = {"native_subscription_masks": [None]}
        with self.assertRaisesRegex(
            ValueError, "Malformed equipment finish subscription"
        ):
            prepare_equipment_finish(fight, None, action_id=1)


class EquipmentTerminalFinishTests(PostgresCase):
    def test_ready_terminal_snapshot_replay_excludes_food_and_live_mutation(self):
        from wakfu_server.inventory_items import grant
        from wakfu_server.inventory_consumable_effects import use
        from wakfu_server.consumable_buffs import enter_combat
        from wakfu_server.combat_equipment_finish import prepare_equipment_finish
        from wakfu_server.combat_reproduction_state import decode_state, encode_state
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from test_equipment_null_carrier_pipeline import advance_actual_turn

        def food_before_ready(preview, action_id, character, monster, deck, rng):
            account, identity = character["account_id"], character["id"]
            with self.store.connection() as db:
                generation = db.execute(
                    "SELECT generation FROM sessions WHERE account_id=%s", (account,)
                ).fetchone()["generation"]
            bag = next(
                row["uid"]
                for row in character["inventory_containers"]
                if row["kind"] == 0
            )
            source = grant(
                self.store,
                account,
                generation,
                identity,
                reference=5010,
                quantity=1,
                container=bag,
                slot=1,
                allowed_references={5010},
            )
            used = use(
                self.store,
                account,
                generation,
                identity,
                struct.pack(">qB", source["uid"], 0),
                expected_hp=character["hp"],
                in_fight=False,
            )
            character.update(used["character"])
            with self.store.connection() as db:
                character["consumable_states"] = enter_combat(
                    self.store, db, identity, preview.id, generation=generation
                )

        (
            character,
            monster,
            deck,
            rng,
            runtime,
            stats,
        ) = _null_pipeline.EquipmentNullCarrierPipelineTests._fixture(
            self,
            reference=13946,
            slot=0,
            level=200,
            breed=5,
            active_spells=[775],
            before_initialization=food_before_ready,
            monster_reference=1,
            monster_level=8,
            monster_position=(-7, -7, -1),
        )
        owner, fight = character["id"], runtime.fight
        native = next(
            row
            for row in fight.actors[owner].state_ledger.entries
            if row.reference == 1354
        )
        food_binding = fight.native_consumable_initializations[owner][0]
        food = next(
            row
            for row in fight.actors[owner].state_ledger.entries
            if row.uid == food_binding["combat_uid"]
        )
        self.assertEqual(food.level, 5)
        for _ in range(2 * len(fight.actors) + 1):
            if runtime.fight.current.id == -200:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, -200)
        spells = owned_spells(runtime.fight, {-200: monster}, character=character)
        self.assertIn(5767, spells)
        from unittest.mock import patch
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_final_modifier import triggering_runner_source
        from wakfu_server.combat_trigger_value_modifier import mutate_triggering_runner

        mutations, heal_calls = [], []
        execute = EffectDispatcher.execute

        def observe_execute(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference == 66438 and result:
                heal_calls.append((invocation.caster_id, invocation.target_id))
            return result

        def observe_mutation(mode, value, replace):
            source = triggering_runner_source()
            before = (
                None
                if source is None or source.runner_modifier is None
                else source.runner_modifier.value
            )
            result = mutate_triggering_runner(mode, value, replace)
            after = (
                None
                if source is None or source.runner_modifier is None
                else source.runner_modifier.value
            )
            mutations.append((mode, value, replace, before, after, result))
            return result

        def attack(*, first=False):
            target = runtime.fight.actors[owner]
            transaction = prepare_npc_spell(
                runtime.fight,
                dict(
                    type="cast",
                    spellId=5767,
                    level=spells[5767],
                    targetId=owner,
                    target=list(target.position),
                ),
                character,
                {-200: monster},
                deck,
                action_id=runtime.action_id + 1,
                rng=rng,
            )
            self.assertGreater(transaction.plan["costs"]["ap"], 0)
            if first:
                self.assertLess(transaction.fight.actors[owner].hp, target.hp)
            commit_spell_transaction(runtime, transaction, stats_serializer=stats)

        # The original aura has1% proc chance. Supply legal minimum RNG draws
        # to witness that branch without changing the effect or its event.
        with patch.object(rng, "random", return_value=0.0), patch.object(
            rng, "randint", side_effect=lambda low, high: low
        ), patch.object(EffectDispatcher, "execute", observe_execute), patch(
            "wakfu_server.combat_trigger_value_handler.mutate_triggering_runner",
            side_effect=observe_mutation,
        ):
            attack(first=True)
            state = next(
                row
                for row in runtime.fight.actors[-200].state_ledger.entries
                if row.reference == 1311
            )
            # Use the real turn boundary, preserving the native two-turn1311
            # clock while resetting ordinary AP/launch limits for the next hit.
            advance_actual_turn(runtime)
            for _ in range(2 * len(runtime.fight.actors) + 1):
                if runtime.fight.current.id == -200:
                    break
                advance_actual_turn(runtime)
            self.assertEqual(runtime.fight.current.id, -200)
            self.assertTrue(
                any(
                    row.uid == state.uid
                    for row in runtime.fight.actors[-200].state_ledger.entries
                )
            )
            attack()
        self.assertIn((-200, owner), heal_calls)
        self.assertTrue(
            any(
                row[:3] == (0, -100, False)
                and row[3] is not None
                and row[3] > 0
                and row[4] == 0
                and row[5]
                for row in mutations
            ),
            mutations,
        )
        fight = runtime.fight
        # The terminal policy also covers scripted/turn-limit victories, which
        # do not require first delivering an unrelated actor-death1010.
        fight.phase, fight.winner = "finished", 0
        original = snapshot(fight)
        outcome, packets = prepare_equipment_finish(
            fight, runtime.expiration_runtime_factory, action_id=runtime.action_id + 1
        )
        self.assertTrue(packets)
        self.assertEqual(snapshot(fight), original)
        self.assertFalse(
            any(
                row.uid == native.uid
                for row in outcome.actors[owner].state_ledger.entries
            )
        )
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )

        # Nested1311 owns its original native lifetime; the boundary must not
        # invent a cascade just because the source's own aura was removed.
        for actor_id in outcome.actors:
            native_retained_condition_effects(outcome, actor_id)
        self.assertEqual(
            next(
                row.level
                for row in outcome.actors[owner].state_ledger.entries
                if row.uid == food.uid
            ),
            food.level,
        )
        self.assertEqual((outcome.phase, outcome.winner), ("finished", 0))
        self.assertTrue(outcome.native_equipment_finish_delivered)
        recovered = decode_state(encode_state(outcome))
        self.assertTrue(recovered.native_equipment_finish_delivered)
        previous = snapshot(recovered)
        repeated, repeated_packets = prepare_equipment_finish(
            recovered,
            runtime.expiration_runtime_factory,
            action_id=runtime.action_id + 2,
        )
        self.assertIs(repeated, recovered)
        self.assertEqual(repeated_packets, ())
        self.assertEqual(snapshot(recovered), previous)
