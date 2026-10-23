"""Actual owned MP carrier: native paid movement, end trigger and expiry."""
import struct

from postgres_case import PostgresCase
import test_equipment_null_carrier_pipeline as _pipeline
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_server_spell import prepare_server_turn_end
from wakfu_server.combat_protocol_reconstruction import _effect
from wakfu_server.combat_qi_movement import movement_blocked_cells
from wakfu_server.fight_checkpoint_store import snapshot


class EquipmentEndResourceMpTests(PostgresCase):
    _fixture = _pipeline.EquipmentNullCarrierPipelineTests._fixture

    def test_actual_paid_movement_then_1037_maximum_mp_gain_and_native_timer_expiry(
        self,
    ):
        char, monster, deck, rng, runtime, stats = self._fixture(
            reference=32618,
            slot=17,
            level=245,
            select_elements=True,
        )
        from collections import ChainMap
        from types import SimpleNamespace
        from wakfu_server.combat_equipment_initialization import plan
        from wakfu_server.combat_owned_equipment import compiled_with_sources
        from wakfu_server.combat_server_spell import compiled_runtime_catalog
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_equipment_end_resource_contract import (
            end_resource_state_contract,
        )

        sources = plan(char, ordinary_only=True)
        self.assertEqual(len(sources), 1)
        source = sources[0]
        compiled = compiled_with_sources(compiled_runtime_catalog(), sources)
        registry = characteristic_registry()
        self.assertIsNone(end_resource_state_contract(source, compiled, registry))
        for label, identity, changes in (
            (
                "wrong-boundary",
                408298,
                {"target_masks": (None, None, None, None, None, (1001,), None)},
            ),
            ("grant-current", 408299, {"parameters": (1, 0, 1, 0, 0, 0)}),
            (
                "wrong-timer",
                408299,
                {
                    "native_timing_definition": dict(
                        compiled.effects["408299"]["native_timing_definition"],
                        esr=False,
                    )
                },
            ),
            (
                "foreign-target",
                408299,
                {"native_target_selector": {"class": "fcE", "mask": 2}},
            ),
        ):
            with self.subTest(malformed=label):
                altered = dict(compiled.effects[str(identity)], **changes)
                view = SimpleNamespace(
                    effects=ChainMap({str(identity): altered}, compiled.effects),
                    source_states=compiled.source_states,
                )
                self.assertIsNotNone(
                    end_resource_state_contract(source, view, registry)
                )
        self.assertIsNotNone(
            end_resource_state_contract(
                dict(source, unplanned_passive_effect_ids=(999999,)),
                compiled,
                registry,
            )
        )
        owner = char["id"]
        actor = runtime.fight.actors[owner]
        self.assertIn(9078, {entry.reference for entry in actor.state_ledger.entries})
        initial_maximum = actor.max_mp
        initial_mp = actor.mp
        occupied = {
            other.position
            for other in runtime.fight.actors.values()
            if other.id != owner and other.hp > 0
        }
        candidates = [
            cell
            for cell in runtime.fight.walkable
            if abs(cell[0] - actor.position[0]) + abs(cell[1] - actor.position[1]) == 1
            and cell[2] == actor.position[2]
            and cell not in occupied
            and (
                runtime.fight.edges is None
                or (actor.position, cell) in runtime.fight.edges
            )
            and cell
            not in (movement_blocked_cells(runtime.fight, actor, (cell,)) or ())
        ]
        self.assertTrue(candidates)
        destination = max(
            candidates,
            key=lambda cell: (
                abs(cell[0] - monster["x"]) + abs(cell[1] - monster["y"]),
                cell,
            ),
        )

        def areas(preview, **boundary):
            return prepare_area_movement(
                char,
                {-200: monster},
                preview,
                deck,
                rng=rng,
                **boundary,
            )

        packets, result = apply_client(
            runtime,
            char["account_id"],
            struct.pack(">qiih", owner, *destination),
            stats,
            runtime_stats_serializer=stats,
            area_provider=areas,
        )
        self.assertTrue(result)
        self.assertTrue(packets)
        before = runtime.fight.actors[owner].mp
        self.assertLess(before, initial_mp)
        self.assertGreaterEqual(before, 1)
        self.assertEqual(runtime.fight.actors[owner].max_mp, initial_maximum)
        original = snapshot(runtime.fight)
        ended, end_packets = prepare_server_turn_end(
            char,
            {-200: monster},
            runtime.fight,
            deck,
            actor_id=owner,
            action_id=runtime.action_id + 1,
            rng=rng,
        )
        self.assertEqual(snapshot(runtime.fight), original)
        self.assertTrue(end_packets)
        self.assertEqual(ended.actors[owner].mp, before)
        self.assertEqual(ended.actors[owner].max_mp, initial_maximum + 1)
        rows = [
            (uid, row)
            for uid, row in ended.owned_stat_effects.items()
            if row["target_id"] == owner
            and row["effect_class"] == 41
            and _effect(bytes.fromhex(row["payload"]), 41)["definition"] == 408299
        ]
        self.assertEqual(len(rows), 1)
        uid, row = rows[0]
        self.assertEqual(
            (
                row["stat_id"],
                row["actual"],
                row["effective_delta"],
                row["remove_current"],
            ),
            (3, 1, 1, False),
        )
        timer = row["timer"]
        self.assertEqual((timer["actor_id"], timer["phase"]), (owner, "end"))
        self.assertGreaterEqual(timer["expiration_round"], ended.native_table_turn)
        # A completed owned boundary is fenced, not silently replayed.
        preview_snapshot = snapshot(ended)
        with self.assertRaisesRegex(ValueError, "already delivered"):
            prepare_server_turn_end(
                char,
                {-200: monster},
                ended,
                deck,
                actor_id=owner,
                action_id=runtime.action_id + 1,
                rng=rng,
            )
        self.assertEqual(snapshot(ended), preview_snapshot)
        # Commit the ordinary runtime boundary from the untouched live source.
        # The isolated preview is a witness, not a second source of callbacks.
        _pipeline.advance_actual_turn(runtime)
        rows = [
            (key, value)
            for key, value in runtime.fight.owned_stat_effects.items()
            if value["target_id"] == owner
            and value["effect_class"] == 41
            and _effect(bytes.fromhex(value["payload"]), 41)["definition"] == 408299
        ]
        self.assertEqual(len(rows), 1)
        uid, row = rows[0]
        timer = row["timer"]
        for _ in range(30):
            previous_actor = runtime.fight.current.id
            previous_round = runtime.fight.native_table_turn
            _pipeline.advance_actual_turn(runtime)
            if uid not in runtime.fight.owned_stat_effects:
                self.assertEqual(
                    (previous_actor, previous_round), (owner, timer["expiration_round"])
                )
                break
        else:
            self.fail("Native timed MP carrier did not retire at its end bucket")
        self.assertIn(
            9078,
            {
                entry.reference
                for entry in runtime.fight.actors[owner].state_ledger.entries
            },
        )
        remaining = [
            value
            for value in runtime.fight.owned_stat_effects.values()
            if value["target_id"] == owner
            and value["effect_class"] == 41
            and _effect(bytes.fromhex(value["payload"]), 41)["definition"] == 408299
        ]
        self.assertEqual(
            runtime.fight.actors[owner].max_mp,
            initial_maximum + sum(value["effective_delta"] for value in remaining),
        )
