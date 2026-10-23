"""Whole-item Ready and inverse coverage for mixed 400/449 equipment roots."""
from copy import deepcopy
from types import SimpleNamespace

from postgres_case import PostgresCase
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_protocol_reconstruction import decode_packet, _effect
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_reproduction_actions import AUTHORITY_RECIPE, bind_runtime
from wakfu_server.combat_reproduction_state import decode_state, encode_state
from wakfu_server.combat_server_spell import server_runtime
from wakfu_server.combat_shared import Session
from wakfu_server.fight_checkpoint_store import snapshot


class EquipmentMixedMarkerPipelineTests(PostgresCase):
    def _fixture(self, reference):
        from test_equipment_null_carrier_pipeline import (
            EquipmentNullCarrierPipelineTests,
        )

        return EquipmentNullCarrierPipelineTests._fixture(
            self, reference=reference, slot=7
        )

    def test_mixed_direct_marker_world_property_checkpoint_and_forced_inverse(self):
        for reference, marker_roots, world_root in (
            (30000, {380974, 383922}, 388308),
            (33000, {413344, 413345}, 413346),
        ):
            with self.subTest(reference=reference):
                char, monster, deck, rng, runtime, _stats = self._fixture(reference)
                owner = char["id"]
                fight = runtime.fight
                markers = {
                    uid: row
                    for uid, row in fight.owned_stat_effects.items()
                    if row["effect_class"] == 400
                    and row["target_id"] == owner
                    and _effect(bytes.fromhex(row["payload"]), 400)["definition"]
                    in marker_roots
                }
                self.assertEqual(len(markers), 2)
                world_rows = {
                    uid: row
                    for uid, row in fight.owned_stat_effects.items()
                    if row["effect_class"] == 449
                    and row["target_id"] == owner
                    and row["property_id"] == 5
                }
                self.assertEqual(len(world_rows), 1)
                world_uid, world_row = next(iter(world_rows.items()))
                self.assertEqual(world_row["actual"], 5)
                actor = fight.actors[owner]
                applied_counts = dict(actor.native_world_property_counts)
                self.assertEqual(applied_counts.get(5), 1)
                baseline_counts = dict(applied_counts)
                baseline_counts[5] -= 1
                if baseline_counts[5] == 0:
                    del baseline_counts[5]

                before = snapshot(fight)
                recovered = decode_state(encode_state(fight))
                self.assertEqual(snapshot(recovered), before)
                runtime.fight = recovered
                inputs = dict(
                    authority_recipe=AUTHORITY_RECIPE,
                    character=char,
                    monsters={-200: monster},
                    deck_blob=deck,
                    player_characters={owner: char},
                    deck_blobs={owner: deck},
                    map_id=1134,
                    native_events=True,
                    area_callbacks=True,
                )
                bind_runtime(runtime, inputs, rng, runtime.clock)
                shared = SimpleNamespace(
                    runtime=runtime,
                    map_id=1134,
                    instance_id=0,
                    join_context=dict(
                        arena=runtime.null_test_arena,
                        terrain_effect_id=46,
                        terrain_instance_id=9001,
                        leaders={0: owner, 1: -200},
                    ),
                )

                def actor_payload(current_fight, current_actor, recipient):
                    if current_actor.controlled:
                        payload = actual_actor_stats(
                            char,
                            current_actor,
                            current_fight.id,
                            wp_current=current_actor.effect_stats[4],
                            wp_maximum=current_actor.effect_maxima[4],
                        )
                    else:
                        payload = actual_monster_actor_stats(
                            monster,
                            current_actor,
                            current_fight.id,
                            wp_current=monster["wp"],
                            wp_maximum=monster["wp"],
                        )
                    return payload, actor_effects()

                stream = owned_snapshot(
                    recovered,
                    shared,
                    Session(char["account_id"], owner, f"mixed-{reference}", 1134, 0),
                    actor_payload=actor_payload,
                )
                packets = [
                    decode_packet(op, body) for op, body in stream if op == 12613
                ]
                received = [row for row in packets if row["effect"]["uid"] in markers]
                self.assertEqual(len(received), 2)
                self.assertIn(world_uid, recovered.owned_stat_effects)
                self.assertEqual(snapshot(recovered), before)

                preview = deepcopy(recovered)
                factory, _ = server_runtime(
                    char,
                    {-200: monster},
                    deck,
                    action_id=99,
                    critical=False,
                    rng=rng,
                )
                dispatcher, outbox = factory(
                    preview, {"native_retained_container": {"present": False}}
                )
                dispatcher.native_retention.removal(
                    dispatcher.native_retention.view()
                ).remove((*markers.keys(), world_uid))
                dispatcher.native_retention.synchronize()
                self.assertNotIn(world_uid, preview.owned_stat_effects)
                self.assertEqual(
                    preview.actors[owner].native_world_property_counts, baseline_counts
                )
                self.assertFalse(set(markers) & set(preview.owned_stat_effects))
                removals = [
                    decode_packet(op, body) for op, body in outbox if op == 13560
                ]
                self.assertEqual(
                    {row["effect"]["uid"] for row in removals},
                    {*markers, world_uid},
                )
                self.assertEqual(snapshot(recovered), before)


if __name__ == "__main__":
    import unittest

    unittest.main()
