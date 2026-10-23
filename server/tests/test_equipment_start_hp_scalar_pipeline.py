"""Real start-bound HP scalar equipment sources and their native inverse."""
from copy import deepcopy
import importlib
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import health_store
from wakfu_server.combat_reproduction_state import decode_state, encode_state
from wakfu_server.fight_checkpoint_store import snapshot


class EquipmentStartHpScalarPipelineTests(PostgresCase):
    def test_two_native_sources_are_ready_neutral_start_gated_timed_and_reversible(
        self,
    ):
        null_pipeline = importlib.import_module("test_equipment_null_carrier_pipeline")
        raw_hp = importlib.import_module("wakfu_server.combat_hp_raw")
        cases = (
            # Ref, native damage/resistance masks, state, leaves, scalar deltas.
            (29447, (14, 0), 7072, (323158, 323159), {27: -40, 11: 1}),
            (
                29446,
                (6, 0),
                7071,
                (323145, 323149, 323154),
                {27: -50, 120: 15, 114: 15},
            ),
        )

        for reference, masks, state_reference, leaves, deltas in cases:
            with self.subTest(reference=reference):
                owner_data = {}
                ready_snapshots = []
                original_prepare_ready = null_pipeline.prepare_ready

                def wound_before_initialization(
                    preview, action_id, character, monster, deck, rng
                ):
                    actor = preview.actors[character["id"]]
                    hp = max(1, actor.max_hp * 70 // 100)
                    with self.store.connection() as db:
                        session = db.execute(
                            "SELECT generation FROM sessions WHERE account_id=%s AND character_id=%s",
                            (character["account_id"], character["id"]),
                        ).fetchone()
                    self.assertIsNotNone(session)
                    health_store.sync(
                        self.store,
                        character["account_id"],
                        session["generation"],
                        character["id"],
                        character["hp"],
                        hp,
                        coefficient=0,
                    )
                    raw_hp.set_hp_raw_current(actor, hp)
                    owner_data.update(
                        account=character["account_id"],
                        character_id=character["id"],
                        generation=session["generation"],
                        low_hp=hp,
                    )

                def capture_ready(*args, **kwargs):
                    prepared = original_prepare_ready(*args, **kwargs)
                    fight = prepared[0]
                    actor = fight.actors[owner_data["character_id"]]
                    ready_snapshots.append(
                        (
                            dict(actor.effect_stats),
                            dict(actor.effect_maxima),
                            actor.hp,
                            actor.max_hp,
                        )
                    )
                    return prepared

                with patch.object(
                    null_pipeline, "prepare_ready", side_effect=capture_ready
                ):
                    (
                        char,
                        monster,
                        deck,
                        rng,
                        runtime,
                        stats,
                    ) = null_pipeline.EquipmentNullCarrierPipelineTests._fixture(
                        self,
                        reference=reference,
                        slot=17,
                        level=245,
                        select_elements=masks,
                        before_initialization=wound_before_initialization,
                    )

                owner = char["id"]
                actor = runtime.fight.actors[owner]
                self.assertEqual(len(ready_snapshots), 1)
                ready_stats, ready_maxima, ready_hp, ready_max_hp = ready_snapshots[0]
                self.assertLess(actor.hp * 100, actor.max_hp * 80)
                # The initial state/subscriber is present, but Ready and the
                # first below-threshold start must not install timed leaves.
                self.assertIn(
                    state_reference,
                    {row.reference for row in actor.state_ledger.entries},
                )
                self.assertEqual(dict(actor.effect_stats), ready_stats)
                self.assertEqual(dict(actor.effect_maxima), ready_maxima)
                self.assertEqual(actor.max_hp, ready_max_hp)
                self.assertFalse(
                    any(
                        row.get("target_id") == owner
                        and row.get("effect_class") in {39, 100, 1095, 160, 126}
                        for row in runtime.fight.owned_stat_effects.values()
                    )
                )

                # Change HP only at the real turn-start boundary. This keeps
                # intervening NPC actions from changing the tested threshold.
                original_turn_start = runtime.turn_start_provider
                pending_hp = [max(1, actor.max_hp * 90 // 100), owner_data["low_hp"]]
                applied_hp = []

                def turn_start_with_native_hp(fight, *, actor_id, action_id):
                    if actor_id == owner and pending_hp:
                        current_actor = fight.actors[owner]
                        new_hp = pending_hp.pop(0)
                        current = self.store.character(char["account_id"], owner)
                        health_store.sync(
                            self.store,
                            char["account_id"],
                            owner_data["generation"],
                            owner,
                            current["hp"],
                            new_hp,
                            coefficient=0,
                        )
                        raw_hp.set_hp_raw_current(current_actor, new_hp)
                        applied_hp.append(new_hp)
                    return original_turn_start(
                        fight, actor_id=actor_id, action_id=action_id
                    )

                runtime.turn_start_provider = turn_start_with_native_hp

                def next_owner_start():
                    old_turn = runtime.fight.actors[owner].turn_count
                    for _ in range(2 * len(runtime.fight.actors) + 2):
                        null_pipeline.advance_actual_turn(runtime)
                        current_actor = runtime.fight.actors[owner]
                        if (
                            runtime.fight.current.id == owner
                            and current_actor.turn_count > old_turn
                        ):
                            return current_actor
                    self.fail("Owner did not reach the next native start event")

                # Above 80%, each original leaf runs once from the one native
                # subscription root. Current stats change; their maxima do not.
                actor = next_owner_start()
                self.assertEqual(applied_hp[0], actor.hp)
                for stat_id, amount in deltas.items():
                    self.assertEqual(
                        actor.effect_stats.get(stat_id, 0)
                        - ready_stats.get(stat_id, 0),
                        amount,
                    )
                self.assertEqual(dict(actor.effect_maxima), ready_maxima)
                self.assertEqual(actor.max_hp, ready_max_hp)
                from wakfu_server.combat_protocol_reconstruction import _effect

                leaf_rows = []
                for uid, row in runtime.fight.owned_stat_effects.items():
                    if row.get("target_id") != owner or row.get("effect_class") not in {
                        39,
                        100,
                        1095,
                        160,
                        126,
                    }:
                        continue
                    decoded = _effect(
                        bytes.fromhex(row["payload"]), row["effect_class"]
                    )
                    if decoded["definition"] in leaves:
                        leaf_rows.append((decoded["definition"], row))
                self.assertEqual(len(leaf_rows), len(leaves))
                self.assertEqual(
                    sorted(definition for definition, _row in leaf_rows), sorted(leaves)
                )
                self.assertTrue(
                    all(
                        isinstance(row.get("timer"), dict)
                        for _definition, row in leaf_rows
                    )
                )
                self.assertTrue(
                    all(
                        row["timer"].get("actor_id") == owner
                        for _definition, row in leaf_rows
                    )
                )

                stable = snapshot(runtime.fight)
                restored = decode_state(encode_state(runtime.fight))
                self.assertEqual(snapshot(restored), stable)

                # At the next real owner start, the previous one-turn leaves
                # expire before the below-threshold subscription is evaluated.
                actor = next_owner_start()
                self.assertEqual(applied_hp[-1], actor.hp)
                self.assertLess(actor.hp * 100, actor.max_hp * 80)
                self.assertFalse(
                    any(
                        row.get("target_id") == owner
                        and row.get("effect_class") in {39, 100, 1095, 160, 126}
                        and _effect(bytes.fromhex(row["payload"]), row["effect_class"])[
                            "definition"
                        ]
                        in leaves
                        for row in runtime.fight.owned_stat_effects.values()
                    )
                )
                for stat_id, amount in deltas.items():
                    self.assertEqual(
                        actor.effect_stats.get(stat_id, 0)
                        - ready_stats.get(stat_id, 0),
                        0,
                    )
                self.assertEqual(dict(actor.effect_maxima), ready_maxima)

                # Remove the permanent source through the production retained
                # inverse, leaving the live combat untouched.
                preview = deepcopy(runtime.fight)
                state = next(
                    row
                    for row in preview.actors[owner].state_ledger.entries
                    if row.reference == state_reference
                )
                factory, _ = null_pipeline.server_runtime(
                    char,
                    {-200: monster},
                    deck,
                    action_id=runtime.action_id + 1,
                    critical=False,
                    rng=rng,
                )
                dispatcher, outbox = factory(
                    preview, {"native_retained_container": {"present": False}}
                )
                retention = dispatcher.native_retention
                retention.removal(retention.view()).remove((state.uid,))
                retention.synchronize()
                self.assertNotIn(
                    state_reference,
                    {
                        row.reference
                        for row in preview.actors[owner].state_ledger.entries
                    },
                )
                self.assertEqual(
                    dict(preview.actors[owner].effect_stats), dict(actor.effect_stats)
                )
                self.assertTrue(any(op == 13560 for op, _body in outbox))


if __name__ == "__main__":
    import unittest

    unittest.main()
