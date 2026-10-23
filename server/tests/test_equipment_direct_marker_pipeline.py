"""Public Ready/reconnect/removal coverage for owned direct marker roots."""
from copy import deepcopy
from types import SimpleNamespace

from postgres_case import PostgresCase
from wakfu_server.combat_protocol_reconstruction import decode_packet, _effect
from wakfu_server.combat_reconnect_snapshot import owned_snapshot
from wakfu_server.combat_shared import Session
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server.combat_reproduction_actions import bind_runtime, AUTHORITY_RECIPE
from wakfu_server.combat_server_spell import server_runtime
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from unittest.mock import patch


class EquipmentDirectMarkerPipelineTests(PostgresCase):
    """Reuse the established real-owner Ready fixture without inheriting its suite."""

    def _fixture(self, *args, **kwargs):
        from test_equipment_null_carrier_pipeline import (
            EquipmentNullCarrierPipelineTests,
        )

        return EquipmentNullCarrierPipelineTests._fixture(self, *args, **kwargs)

    @staticmethod
    def _nulls(*args, **kwargs):
        from test_equipment_null_carrier_pipeline import (
            EquipmentNullCarrierPipelineTests,
        )

        return EquipmentNullCarrierPipelineTests._nulls(*args, **kwargs)

    def test_light_marker_ready_turn_checkpoint_reconnect_and_exact_removal(self):
        # Item8089's original condition allows its direct light marker at
        # night. Map1134 is not in its location exceptions; clock zero makes
        # the real `not IsDay()` branch determine admission.
        with patch("wakfu_server.world_clock.current_time_ms", return_value=0):
            char, monster, deck, rng, runtime, _stats = self._fixture(
                reference=8089, slot=17
            )
        owner = char["id"]
        # The pinned original 8089 plan contains one direct marker root. The
        # live plan is clock-dependent, so inspect the actual retained fight
        # state by its exported root rather than recomputing eligibility after
        # the fixture's night-clock scope has ended.
        marker_refs = {32422}
        marker_rows = self._nulls(runtime.fight, owner, marker_refs)
        self.assertEqual(len(marker_rows), 1)
        marker_uid, (retained, decoded) = next(iter(marker_rows.items()))
        self.assertEqual(decoded["definition"], next(iter(marker_refs)))
        self.assertIs(retained["actual"], 0)

        ready_packets = [
            decode_packet(opcode, body)
            for opcode, body in runtime.null_test_ready_packets
            if opcode == 12613
        ]
        ready_markers = [
            row
            for row in ready_packets
            if row["effect"]["family"] == 400 and row["effect"]["uid"] == marker_uid
        ]
        self.assertEqual(len(ready_markers), 1)
        self.assertIs(ready_markers[0]["immediate"], False)

        # A normal owned turn does not consume or replace the marker identity.
        stable_payload = retained["payload"]
        from test_equipment_null_carrier_pipeline import advance_actual_turn

        for _ in range(len(runtime.fight.actors)):
            advance_actual_turn(runtime)
        self.assertEqual(
            runtime.fight.owned_stat_effects[marker_uid]["payload"], stable_payload
        )

        before = snapshot(runtime.fight)
        recovered = decode_state(encode_state(runtime.fight))
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

        def actor_payload(fight, actor, recipient):
            if actor.controlled:
                payload = actual_actor_stats(
                    char,
                    actor,
                    fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                )
            else:
                payload = actual_monster_actor_stats(
                    monster,
                    actor,
                    fight.id,
                    wp_current=monster["wp"],
                    wp_maximum=monster["wp"],
                )
            return payload, actor_effects()

        stream = owned_snapshot(
            recovered,
            shared,
            Session(char["account_id"], owner, "direct-marker-reconnect", 1134, 0),
            actor_payload=actor_payload,
        )
        reconnect_markers = [
            decode_packet(opcode, body) for opcode, body in stream if opcode == 12613
        ]
        reconnect_markers = [
            row for row in reconnect_markers if row["effect"]["uid"] == marker_uid
        ]
        self.assertEqual(len(reconnect_markers), 1)
        self.assertEqual(
            reconnect_markers[0]["effect"]["definition"], decoded["definition"]
        )
        self.assertEqual(snapshot(recovered), before)

        preview = deepcopy(recovered)
        factory, _ = server_runtime(
            char, {-200: monster}, deck, action_id=99, critical=False, rng=rng
        )
        dispatcher, outbox = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        retention = dispatcher.native_retention
        removal = retention.removal(retention.view())
        removal.remove((marker_uid,))
        retention.synchronize()
        self.assertNotIn(marker_uid, preview.owned_stat_effects)
        removal_packets = [
            decode_packet(opcode, body) for opcode, body in outbox if opcode == 13560
        ]
        self.assertEqual(
            [row["effect"]["uid"] for row in removal_packets],
            [marker_uid],
        )
        self.assertEqual(removal_packets[0]["effect"]["family"], 400)
        self.assertEqual(snapshot(recovered), before)


if __name__ == "__main__":
    import unittest

    unittest.main()
