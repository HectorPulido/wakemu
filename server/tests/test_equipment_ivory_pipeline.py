"""Actual saved Ivory equipment admission using a live owner/factory contract."""
from random import Random
from test_equipment_dynamic_owner_postgres import EquipmentDynamicOwnerPostgresTests


class EquipmentIvoryPipelineTests(EquipmentDynamicOwnerPostgresTests):
    def test_actual_saved_ivory_ready_admits_complete_native_source(self):
        from wakfu_server.combat_equipment_initialization import plan
        from wakfu_server.combat_equipment_dynamic_levels import OwnerLevelFacts
        from wakfu_server.combat_equipment_operation_capability import validate_graph
        from wakfu_server.combat_owned_equipment import compiled_with_sources
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_server_spell import (
            compiled_runtime_catalog,
            server_runtime,
        )
        from wakfu_server.spells import encode_deck

        account, generation, owner = self._owner()
        item = self._grant(account, generation, owner, 31361, 0)
        owner = self._save(account, generation, owner, item)
        sources = plan(owner, ordinary_only=True)
        source = next(row for row in sources if row["source_reference"] == 31361)
        fight, runtime, packets, arena, payload, stats = self._ready(owner, account)
        factory, _ = server_runtime(
            owner,
            {-200: self._monster_for_runtime()},
            encode_deck([6972]),
            action_id=901,
            critical=False,
            rng=Random(9),
        )
        routes, provider = factory.equipment_operation_capability()
        result = validate_graph(
            source,
            compiled_with_sources(compiled_runtime_catalog(), sources),
            characteristic_registry(),
            runtime_bindings=routes,
            criteria_capability=provider,
            owner_level_facts=OwnerLevelFacts.capture(fight, owner["id"], account),
        )
        print("Ivory actual source admission:", result.status, result.reasons)
        self.assertEqual(result.status, "supported", result.reasons)
        pin = fight.native_owned_equipment_sources[str(owner["id"])]
        self.assertTrue(any(row["source_reference"] == 31361 for row in pin["sources"]))
        self.assertFalse(
            any(row["source_reference"] == 31361 for row in pin["deferred"])
        )
        reopened = self.store.character(account, owner["id"])
        self.assertTrue(
            any(
                row["uid"] == item["uid"] and row["quantity"] == 1
                for row in reopened["inventory_items"]
            )
        )

    def test_actual_movement_installs_levelled_paid_hit_modifiers_and_cleanup(self):
        from copy import deepcopy
        import struct
        from unittest.mock import patch
        import test_equipment_null_carrier_pipeline as helpers
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_npc_spell import owned_spells, prepare_npc_spell
        from wakfu_server.combat_reproduction_state import encode_state, decode_state
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
        from wakfu_server.fight_checkpoint_store import snapshot

        (
            char,
            monster,
            deck,
            rng,
            runtime,
            stats,
        ) = helpers.EquipmentNullCarrierPipelineTests._fixture(
            self,
            reference=31361,
            slot=17,
            level=245,
            breed=8,
            active_spells=[4780],
            monster_reference=1,
            monster_level=8,
            monster_position=(-6, -7, -1),
        )
        owner = char["id"]
        source = next(
            row
            for row in runtime.fight.native_owned_equipment_sources[str(owner)][
                "sources"
            ]
            if row["source_reference"] == 31361
        )
        self.assertIs(source["_generic_operation_admission"], True)
        self.assertEqual(
            source["_generic_owner_level_facts"]["effective_level"],
            runtime.fight.actors[owner].effective_level,
        )
        before = snapshot(runtime.fight)
        expected = 2 * runtime.fight.actors[owner].effective_level
        destination = (-7, -7, -1)
        messages, moved = apply_client(
            runtime,
            char["account_id"],
            struct.pack(">qiih", owner, *destination),
            stats,
            runtime_stats_serializer=lambda actor, preview: stats(actor, preview),
            area_provider=lambda preview, **boundary: prepare_area_movement(
                char, {-200: monster}, preview, deck, rng=rng, **boundary
            ),
        )
        self.assertTrue(messages)
        self.assertTrue(moved)
        self.assertEqual(runtime.fight.actors[owner].position, destination)
        groups = runtime.fight.native_owned_group_effects
        negatives = [
            row
            for row in groups.values()
            if row.get("invocation", {}).get("reference")
            in (380198, 380201, 380204, 380207)
        ]
        self.assertEqual(len(negatives), 4)
        self.assertTrue(
            all(row["invocation"]["level"] == expected for row in negatives)
        )
        stable = snapshot(runtime.fight)
        restored = decode_state(encode_state(runtime.fight))
        self.assertEqual(snapshot(restored), stable)
        runtime.fight = restored

        mutate = NativeRunnerAmount.mutate
        mutations = []

        def observe(runner, mode, value, replace):
            old = runner.value
            result = mutate(runner, mode, value, replace)
            mutations.append(
                (runner.uid, runner.family, mode, value, replace, old, runner.value)
            )
            return result

        # Branch A: the owner really pays for a native Earth cast. Observe
        # the live source Qe gain, not an injected430 or fabricated damage.
        with patch.object(NativeRunnerAmount, "mutate", observe):
            attack = prepare_server_spell(
                struct.pack(
                    ">qqiih",
                    owner,
                    (owner << 32) | 4780,
                    *runtime.fight.actors[-200].position
                ),
                char,
                {-200: monster},
                runtime.fight,
                char["account_id"],
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=lambda *_args: True,
                critical=False,
                rng=rng,
            )
        self.assertGreater(attack.plan["costs"]["ap"], 0)
        self.assertTrue(
            any(
                family == 3
                and mode == 1
                and amount == expected
                and after - prior == expected
                for _uid, family, mode, amount, _replace, prior, after in mutations
            ),
            mutations,
        )
        self.assertFalse(
            any(
                row.get("invocation", {}).get("reference") in (380196, 380204)
                for row in attack.fight.native_owned_group_effects.values()
            )
        )
        self.assertEqual(snapshot(runtime.fight), stable)
        attacking = deepcopy(runtime)
        commit_spell_transaction(
            attacking,
            attack,
            stats_serializer=lambda actor, preview: stats(actor, preview),
        )
        self.assertLess(attacking.fight.actors[-200].hp, runtime.fight.actors[-200].hp)
        self.assertEqual(
            snapshot(decode_state(encode_state(attacking.fight))),
            snapshot(attacking.fight),
        )

        # Branch B starts from the same actual moved/checkpointed fight, then
        # advances the real owner end/ACK to a real Jalato native5767 action.
        # This keeps the negative elemental charge available independently of
        # branch A's successful cast cleanup; no level/event/state is injected.
        incoming = deepcopy(runtime)
        helpers.advance_actual_turn(incoming)
        self.assertEqual(incoming.fight.current.id, -200)
        book = owned_spells(incoming.fight, {-200: monster}, character=char)
        self.assertIn(5767, book)
        mutations.clear()
        with patch.object(NativeRunnerAmount, "mutate", observe):
            defense = prepare_npc_spell(
                incoming.fight,
                dict(
                    type="cast",
                    spellId=5767,
                    level=book[5767],
                    targetId=owner,
                    target=list(incoming.fight.actors[owner].position),
                ),
                char,
                {-200: monster},
                deck,
                action_id=incoming.action_id + 1,
                rng=rng,
            )
        self.assertGreater(defense.plan["costs"]["ap"], 0)
        actual = [row for row in mutations if row[2] == 1 and row[3] == -expected]
        self.assertTrue(actual, mutations)
        # Native eXt amount mutation clamps damage to zero. A weak real Jalato
        # therefore cannot lose490 points from a source smaller than490.
        self.assertTrue(
            all(
                after == max(0, prior - expected)
                for _uid, _family, _mode, _amount, _replace, prior, after in actual
            ),
            actual,
        )
        commit_spell_transaction(
            incoming,
            defense,
            stats_serializer=lambda actor, preview: stats(actor, preview),
        )
        committed = snapshot(incoming.fight)
        self.assertEqual(
            snapshot(decode_state(encode_state(incoming.fight))), committed
        )
        self.assertEqual(snapshot(runtime.fight), stable)

        # Native permanent carrier retirement preserves the independent live
        # source and physical inventory; it does not recreate dynamic groups.
        preview = deepcopy(incoming.fight)
        root = next(
            state
            for state in preview.actors[owner].state_ledger.entries
            if state.reference == 8251
        )
        factory, _ = server_runtime(
            char,
            {-200: monster},
            deck,
            action_id=incoming.action_id + 1,
            critical=False,
            rng=rng,
        )
        dispatcher, _outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        retained = dispatcher.native_retention
        retained.removal(retained.view()).remove((root.uid,))
        retained.synchronize()
        self.assertFalse(
            any(
                row.get("invocation", {}).get("reference") == 380193
                for row in preview.native_owned_group_effects.values()
            )
        )
        self.assertEqual(snapshot(incoming.fight), committed)
        self.assertTrue(
            any(
                item["reference"] == 31361 and item["quantity"] == 1
                for item in self.store.character(char["account_id"], owner)[
                    "inventory_items"
                ]
            )
        )
