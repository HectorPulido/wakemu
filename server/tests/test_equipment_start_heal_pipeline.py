"""Owned start-heal equipment reaches only its native HP-gated start event."""
from copy import deepcopy
import importlib
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import health_store
from wakfu_server.combat_reproduction_state import decode_state, encode_state
from wakfu_server.fight_checkpoint_store import snapshot


class EquipmentStartHealPipelineTests(PostgresCase):
    def test_real_ready_damage_threshold_start_heal_full_hp_boundary_checkpoint_and_removal(
        self,
    ):
        null_pipeline = importlib.import_module("test_equipment_null_carrier_pipeline")
        cases = (
            (18090, (2513, 2572), 150, 4, None),
            # Victus applies 50%, then 75%, then 25% thresholds in native
            # order; the eighth-HP start exercises all three. Amounts are
            # checked from the actual handler results because native healing
            # resistance changes after each successful heal.
            (18458, (2573, 2411, 2574), None, 8, True),
        )
        raw_hp = importlib.import_module("wakfu_server.combat_hp_raw")
        healing_handler = importlib.import_module("wakfu_server.combat_healing_handler")
        from wakfu_server.combat_healing_handler import NativeHealingHandler

        for (
            reference,
            source_states,
            expected_heal,
            wound_divisor,
            next_start_heal,
        ) in cases:
            with self.subTest(reference=reference):
                owner_data = {}

                def damage_before_ready(
                    preview, action_id, character, monster, deck, rng
                ):
                    actor = preview.actors[character["id"]]
                    hp = max(1, actor.max_hp // wound_divisor)
                    with self.store.connection() as db:
                        session = db.execute(
                            "SELECT generation FROM sessions WHERE account_id=%s AND character_id=%s",
                            (character["account_id"], character["id"]),
                        ).fetchone()
                    self.assertIsNotNone(session)
                    generation = session["generation"]
                    health_store.sync(
                        self.store,
                        character["account_id"],
                        generation,
                        character["id"],
                        character["hp"],
                        hp,
                        coefficient=0,
                    )
                    # Keep the live actor's native raw/effective HP authority
                    # coherent with the persisted wound.
                    raw_hp.set_hp_raw_current(actor, hp)
                    owner_data.update(
                        character_id=character["id"],
                        generation=generation,
                        damaged_hp=hp,
                        maximum_hp=actor.max_hp,
                    )

                ready_hp = []
                healing_calls = []
                healing_effects = []
                original_prepare_ready = null_pipeline.prepare_ready
                original_plan_healing = healing_handler.plan_healing_consumption
                original_call = NativeHealingHandler.__call__

                def capture_healing(amount, target, target_stats, context):
                    result = original_plan_healing(
                        amount, target, target_stats, context
                    )
                    healing_calls.append(
                        {
                            "target_id": target.id,
                            "amount": amount,
                            "actual_hp_gain": result["hp_gain"],
                            "hp_before": target.hp,
                            "maximum_hp": target.max_hp,
                            "virtual_hp_before": target_stats.get(92, 0),
                            "maximum_virtual_hp": target.effect_maxima.get(92, 0),
                            "resistance_before": target_stats.get(32),
                            "resistance_after": result["target_heal_resistance"],
                        }
                    )
                    return result

                def capture_call(handler, effect, values, invocation):
                    calls_before = len(healing_calls)
                    result = original_call(handler, effect, values, invocation)
                    # _calculate prepares effects even when their live
                    # threshold is false. Count a leaf only if it reached
                    # actual healing consumption.
                    if len(healing_calls) > calls_before:
                        healing_effects.append(invocation.reference)
                    return result

                def hp_percent(hp, actor):
                    total = importlib.import_module(
                        "wakfu_server.combat_range_conditions"
                    ).total_hp_percent
                    return total(
                        {
                            "HP": hp,
                            "VIRTUAL_HP": actor.effect_stats.get(92, 0),
                        },
                        {
                            "HP": actor.max_hp,
                            "VIRTUAL_HP": actor.effect_maxima.get(92, 0),
                        },
                    )

                def capture_ready(*args, **kwargs):
                    prepared = original_prepare_ready(*args, **kwargs)
                    fight, _messages, _packets = prepared
                    ready_hp.append(fight.actors[owner_data["character_id"]].hp)
                    return prepared

                with (
                    patch.object(
                        null_pipeline, "prepare_ready", side_effect=capture_ready
                    ),
                    patch.object(
                        healing_handler,
                        "plan_healing_consumption",
                        side_effect=capture_healing,
                    ),
                    patch.object(NativeHealingHandler, "__call__", new=capture_call),
                ):
                    (
                        char,
                        monster,
                        deck,
                        rng,
                        runtime,
                        _stats,
                    ) = null_pipeline.EquipmentNullCarrierPipelineTests._fixture(
                        self,
                        reference=reference,
                        slot=5,
                        level=245,
                        select_elements=True,
                        before_initialization=damage_before_ready,
                    )

                owner = char["id"]
                actor = runtime.fight.actors[owner]
                # Ready installs the graph but leaves the wound intact. The
                # shared fixture then advances to the player's real 1001 turn.
                self.assertEqual(ready_hp, [owner_data["damaged_hp"]])
                if expected_heal is not None:
                    self.assertEqual(expected_heal, actor.hp - owner_data["damaged_hp"])
                self.assertEqual(len(source_states), len(healing_calls))
                self.assertTrue(all(row["target_id"] == owner for row in healing_calls))
                self.assertEqual(
                    actor.hp - owner_data["damaged_hp"],
                    sum(row["actual_hp_gain"] for row in healing_calls),
                )
                if reference == 18458:
                    self.assertEqual([107813, 109582, 109585], healing_effects)
                    for row, threshold in zip(healing_calls, (50.0, 75.0, 25.0)):
                        self.assertLessEqual(
                            hp_percent(row["hp_before"], actor), threshold
                        )
                self.assertEqual(actor.max_hp, owner_data["maximum_hp"])
                retained = {entry.reference for entry in actor.state_ledger.entries}
                self.assertTrue(set(source_states).issubset(retained))

                def advance_to_next_owner_start():
                    start_count = runtime.fight.actors[owner].turn_count
                    for _ in range(2 * len(runtime.fight.actors) + 2):
                        null_pipeline.advance_actual_turn(runtime)
                        current = runtime.fight.actors[owner]
                        if (
                            runtime.fight.current.id == owner
                            and current.turn_count > start_count
                        ):
                            return current
                    self.fail("Owner did not reach its next native start event")

                if next_start_heal:
                    # This is the same Victus fixture after its first ordered
                    # pass. At 25% HP the 50% and 75% branches remain true;
                    # their healing makes the final 25% predicate false.
                    current = self.store.character(char["account_id"], owner)
                    quarter_hp = max(1, actor.max_hp // 4)
                    health_store.sync(
                        self.store,
                        char["account_id"],
                        owner_data["generation"],
                        owner,
                        current["hp"],
                        quarter_hp,
                        coefficient=0,
                    )
                    raw_hp.set_hp_raw_current(actor, quarter_hp)
                    before = actor.hp
                    before_calls = len(healing_calls)
                    before_effects = len(healing_effects)
                    with (
                        patch.object(
                            healing_handler,
                            "plan_healing_consumption",
                            side_effect=capture_healing,
                        ),
                        patch.object(
                            NativeHealingHandler, "__call__", new=capture_call
                        ),
                    ):
                        after = advance_to_next_owner_start()
                    next_calls = healing_calls[before_calls:]
                    next_effects = healing_effects[before_effects:]
                    self.assertEqual(2, len(next_calls))
                    self.assertEqual([107813, 109582], next_effects)
                    self.assertEqual(
                        after.hp - before,
                        sum(row["actual_hp_gain"] for row in next_calls),
                    )
                    next_percentages = [
                        hp_percent(row["hp_before"], actor) for row in next_calls
                    ]
                    self.assertLessEqual(next_percentages[0], 50.0)
                    self.assertLessEqual(next_percentages[1], 75.0)
                    self.assertGreater(hp_percent(after.hp, actor), 25.0)

                # At full HP the native threshold is false. Use both canonical
                # storage and the normal raw HP mutator before the next turn.
                current = self.store.character(char["account_id"], owner)
                health_store.sync(
                    self.store,
                    char["account_id"],
                    owner_data["generation"],
                    owner,
                    current["hp"],
                    actor.max_hp,
                    coefficient=0,
                )
                raw_hp.set_hp_raw_current(actor, actor.max_hp)
                unchanged = advance_to_next_owner_start()
                self.assertEqual(unchanged.hp, unchanged.max_hp)

                before_checkpoint = snapshot(runtime.fight)
                restored = decode_state(encode_state(runtime.fight))
                self.assertEqual(snapshot(restored), before_checkpoint)

                # Remove the retained source through the production inverse;
                # the already-applied heal is an immediate event and remains.
                preview = deepcopy(restored)
                factory, _outbox = null_pipeline.server_runtime(
                    char,
                    {-200: monster},
                    deck,
                    action_id=runtime.action_id + 1,
                    critical=False,
                    rng=rng,
                )
                dispatcher, _packets = factory(
                    preview, {"native_retained_container": {"present": False}}
                )
                state_uids = tuple(
                    entry.uid
                    for entry in preview.actors[owner].state_ledger.entries
                    if entry.reference in source_states
                )
                self.assertEqual(len(source_states), len(state_uids))
                hp_before_remove = preview.actors[owner].hp
                dispatcher.native_retention.removal(
                    dispatcher.native_retention.view()
                ).remove(state_uids)
                dispatcher.native_retention.synchronize()
                self.assertFalse(
                    any(
                        entry.reference in source_states
                        for entry in preview.actors[owner].state_ledger.entries
                    )
                )
                self.assertEqual(preview.actors[owner].hp, hp_before_remove)
