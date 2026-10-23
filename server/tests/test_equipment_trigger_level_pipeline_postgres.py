"""Actual 1020 and resource-characteristic listeners on ordinary equipment."""
from copy import deepcopy
import struct
from random import Random
from unittest.mock import patch

from postgres_case import PostgresCase
import test_equipment_null_carrier_pipeline as _null_pipeline


class EquipmentTriggerLevelPipelinePostgresTests(PostgresCase):
    def _fight(
        self, reference, *, slot, level=200, breed=5, spells=(775,), admin=False
    ):
        return _null_pipeline.EquipmentNullCarrierPipelineTests._fixture(
            self,
            reference=reference,
            slot=slot,
            level=level,
            breed=breed,
            active_spells=list(spells),
            administrator=admin,
        )

    def test_13946_real_npc_hits_checkpoint_and_source_removal(self):
        import json
        from pathlib import Path
        from unittest.mock import patch

        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_reproduction_state import decode_state, encode_state
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_final_modifier import triggering_runner_source
        from wakfu_server.combat_trigger_value_modifier import mutate_triggering_runner

        import wakfu_server.combat_owned_equipment_pin as equipment_pin

        preparations = []
        original_prepare = equipment_pin.prepare

        def observe_prepare(*args, **kwargs):
            result = original_prepare(*args, **kwargs)
            preparations.append(
                {
                    "sources": [
                        {
                            "source_reference": row.get("source_reference"),
                            "generic_admission": row.get(
                                "_generic_operation_admission"
                            ),
                            "roots": list(row.get("roots", ())),
                        }
                        for row in result.get("sources", ())
                    ],
                    "deferred": [repr(row) for row in result.get("deferred", ())],
                }
            )
            return result

        with patch.object(equipment_pin, "prepare", side_effect=observe_prepare):
            char, monster, deck, rng, runtime, stats = self._fight(13946, slot=0)
        owner, fight = char["id"], runtime.fight
        diagnostic = {
            "reference": 13946,
            "preparations": preparations,
            "pinned_sources": getattr(fight, "native_owned_equipment_sources", {}).get(
                str(owner)
            ),
            "states_on_owner": [
                {"uid": row.uid, "reference": row.reference, "level": row.level}
                for row in fight.actors[owner].state_ledger.entries
            ],
        }
        evidence = Path(
            ".runtime/equipment-trigger-level-route-20261021/13946-ready-diagnostic.json"
        )
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(
            json.dumps(diagnostic, indent=2, sort_keys=True, default=str) + "\n"
        )
        root_state = next(
            row
            for row in fight.actors[owner].state_ledger.entries
            if row.reference == 1354
        )
        self.assertEqual(
            sum(
                row.reference == 1354
                for row in fight.actors[owner].state_ledger.entries
            ),
            1,
        )
        source = next(
            row
            for row in fight.native_owned_equipment_sources[str(owner)]["sources"]
            if row["source_reference"] == 13946
        )
        self.assertIs(source.get("_generic_operation_admission"), True)

        calls = []
        mutations = []
        execute = EffectDispatcher.execute
        mutate = mutate_triggering_runner

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (68995, 66437, 66438, 66439):
                calls.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        bool(result),
                        invocation.native_trigger_context,
                    )
                )
            return result

        def observe_mutation(mode, value, replace):
            actual = triggering_runner_source()
            before = (
                None
                if actual is None or actual.runner_modifier is None
                else actual.runner_modifier.value
            )
            result = mutate(mode, value, replace)
            after = (
                None
                if actual is None or actual.runner_modifier is None
                else actual.runner_modifier.value
            )
            mutations.append(
                (
                    None if actual is None else actual.effect_action_id,
                    None if actual is None else actual.uid,
                    mode,
                    value,
                    replace,
                    before,
                    after,
                    result,
                )
            )
            return result

        def npc_attack():
            target = runtime.fight.actors[owner]
            tx = prepare_npc_spell(
                runtime.fight,
                dict(
                    type="cast",
                    spellId=5767,
                    level=8,
                    targetId=owner,
                    target=list(target.position),
                ),
                char,
                {-200: monster},
                deck,
                action_id=runtime.action_id + 1,
                rng=rng,
            )
            self.assertGreater(tx.plan["costs"]["ap"], 0)
            self.assertLess(tx.fight.actors[owner].hp, target.hp)
            commit_spell_transaction(runtime, tx, stats_serializer=stats)

        def wait_for_npc(*, next_round=False):
            if next_round:
                _null_pipeline.advance_actual_turn(runtime)
            for _ in range(2 * len(runtime.fight.actors) + 1):
                if runtime.fight.current.id == -200:
                    return
                _null_pipeline.advance_actual_turn(runtime)
            self.fail("Actual native turn order did not select the NPC")

        with patch.object(EffectDispatcher, "execute", observe), patch(
            "wakfu_server.combat_trigger_value_handler.mutate_triggering_runner",
            side_effect=observe_mutation,
        ):
            wait_for_npc()
            npc_attack()
            attacker_state = next(
                row
                for row in runtime.fight.actors[-200].state_ledger.entries
                if row.reference == 1311
            )
            self.assertTrue(
                any(
                    row[0] == 68995 and row[1] == -200 and row[2] == owner and row[3]
                    for row in calls
                ),
                calls,
            )
            wait_for_npc(next_round=True)
            npc_attack()

        # The native second hit owns the reverse subscription: its real Qe
        # recipient is the player, and eZL mutates that triggering value.
        self.assertTrue(any(row[0] == 66437 for row in calls), calls)
        heal_calls = [row for row in calls if row[0] == 66438 and row[3]]
        self.assertTrue(heal_calls, calls)
        self.assertTrue(
            any(row[1] == -200 and row[2] == owner for row in heal_calls), heal_calls
        )
        self.assertLessEqual(
            runtime.fight.actors[owner].hp, runtime.fight.actors[owner].max_hp
        )
        self.assertTrue(any(row[0] == 66439 for row in calls), calls)
        self.assertTrue(
            any(
                row[0] is not None
                and row[1] is not None
                and row[2:5] == (0, -100, False)
                and row[5] is not None
                and row[6] == 0
                and row[7]
                for row in mutations
            ),
            mutations,
        )
        self.assertEqual(
            attacker_state.uid,
            next(
                row.uid
                for row in runtime.fight.actors[-200].state_ledger.entries
                if row.reference == 1311
            ),
        )

        before_checkpoint = snapshot(runtime.fight)
        recovered = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(recovered), before_checkpoint)
        self.assertEqual(
            next(
                row.uid
                for row in recovered.actors[-200].state_ledger.entries
                if row.reference == 1311
            ),
            attacker_state.uid,
        )

        preview = deepcopy(recovered)
        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        dispatcher, _ = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        retained = dispatcher.native_retention
        retained.removal(retained.view()).remove((root_state.uid,))
        retained.synchronize()
        self.assertFalse(
            any(
                row.reference in (1354, 1311)
                for actor in preview.actors.values()
                for row in actor.state_ledger.entries
            )
        )
        self.assertEqual(snapshot(runtime.fight), before_checkpoint)

    def test_18097_paid_spell_and_real_1037_gain_are_mutated_and_reversible(self):
        from wakfu_server.combat_final_modifier import triggering_runner_source
        from wakfu_server.combat_reproduction_state import decode_state, encode_state
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_trigger_value_modifier import mutate_triggering_runner
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_server_spell import prepare_server_spell

        char, monster, deck, rng, runtime, stats = self._fight(
            18097, slot=7, level=200, breed=5, spells=(775,), admin=True
        )
        owner, fight = char["id"], runtime.fight
        source = next(
            row
            for row in fight.native_owned_equipment_sources[str(owner)]["sources"]
            if row["source_reference"] == 18097
        )
        self.assertIs(source.get("_generic_operation_admission"), True)
        state = next(
            row
            for row in fight.actors[owner].state_ledger.entries
            if row.reference == 731
        )
        paid_before = fight.actors[owner].effect_stats[4]
        target = fight.actors[-200]
        tx = prepare_server_spell(
            struct.pack(">qqiih", owner, (owner << 32) | 775, *target.position),
            char,
            {-200: monster},
            fight,
            char["account_id"],
            deck,
            action_id=runtime.action_id + 1,
            line_of_sight=lambda *_: True,
            critical=False,
            rng=rng,
        )
        self.assertGreater(tx.plan["costs"]["wp"], 0)
        self.assertEqual(
            tx.fight.actors[owner].effect_stats[4], paid_before - tx.plan["costs"]["wp"]
        )
        commit_spell_transaction(runtime, tx, stats_serializer=stats)
        paid_value = runtime.fight.actors[owner].effect_stats[4]
        checkpoint = snapshot(runtime.fight)
        checkpoint_fight = decode_state(encode_state(runtime.fight))
        retained_430_before = {
            uid: row
            for uid, row in runtime.fight.owned_stat_effects.items()
            if row.get("effect_class") == 430 and row.get("target_id") == owner
        }

        mutations = []
        original_mutate = mutate_triggering_runner

        def observe_mutation(mode, value, replace):
            actual = triggering_runner_source()
            before = (
                None
                if actual is None or actual.runner_modifier is None
                else actual.runner_modifier.value
            )
            result = original_mutate(mode, value, replace)
            after = (
                None
                if actual is None or actual.runner_modifier is None
                else actual.runner_modifier.value
            )
            mutations.append(
                (
                    None if actual is None else actual.effect_action_id,
                    None if actual is None else actual.uid,
                    mode,
                    value,
                    replace,
                    before,
                    after,
                    result,
                )
            )
            return result

        with patch(
            "wakfu_server.combat_trigger_value_handler.mutate_triggering_runner",
            side_effect=observe_mutation,
        ):
            _null_pipeline.advance_actual_turn(runtime)
        retained_430_after = {
            uid: row
            for uid, row in runtime.fight.owned_stat_effects.items()
            if row.get("effect_class") == 430 and row.get("target_id") == owner
        }
        self.assertEqual(retained_430_after, retained_430_before)
        actual_wp = runtime.fight.actors[owner].effect_stats[4]
        self.assertEqual(actual_wp, paid_value)
        self.assertTrue(
            any(
                row[0] == 193
                and row[2:5] == (0, -100, False)
                and row[5] > 0
                and row[6] == 0
                and row[7]
                for row in mutations
            ),
            mutations,
        )
        restored = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(restored), snapshot(runtime.fight))

        # On a detached copy, remove the real source state through the native
        # retained inverse, then replay the same ordinary 1037 boundary. The
        # paid point regenerates again only after its listener is gone.
        preview = deepcopy(checkpoint_fight)
        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        dispatcher, _ = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        retained = dispatcher.native_retention
        retained.removal(retained.view()).remove((state.uid,))
        retained.synchronize()
        before_preview = snapshot(preview)
        ended, _ = prepare_server_turn_end(
            char,
            {-200: monster},
            preview,
            deck,
            actor_id=owner,
            action_id=runtime.action_id + 2,
            rng=rng,
        )
        self.assertEqual(snapshot(preview), before_preview)
        self.assertEqual(ended.actors[owner].effect_stats[4], paid_value + 1)
        self.assertEqual(snapshot(runtime.fight), snapshot(restored))
