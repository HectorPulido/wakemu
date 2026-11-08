"""Native immutable birth history must not disable unrelated terminal GC."""
from copy import deepcopy
import unittest
from test_gc_owned_collections import OwnedCollectionGCTests
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_retained_gc import plan_retired_effects


class BirthDeliveriesGCTests(unittest.TestCase):
    def test_native_birth_history_admission_matches_plain_and_rejects_active_bytes(
        self,
    ):
        packet_a, packet_b = b"creation-packet", b"placement-packet"
        plans = []
        for immutable in (False, True):
            previous, fight, runtime, dead, uid = OwnedCollectionGCTests().fixture()
            history = (
                {dead: ((12608, packet_a), (13091, packet_b))}
                if immutable
                else {dead: [[12608, packet_a.hex()], [13091, packet_b.hex()]]}
            )
            fight.native_rift_creation_deliveries = history
            saved = deepcopy(history)
            schemas, readers = [], set()
            self.assertTrue(
                boundary._canonical_graph(
                    fight, reference_schemas=schemas, projection_opaque=readers
                )
            )
            self.assertEqual(schemas, [True])
            self.assertNotIn(None, readers)
            projected, roots = boundary._project_snapshot(fight, ())
            plans.append(
                plan_retired_effects(
                    projected,
                    {dead},
                    pending_roots=roots,
                    _reference_schemas_valid=True,
                )
            )
            self.assertIn(uid, plans[-1].effect_uids)
            boundary.prepare_retired_gc(previous, fight, runtime, ())
            self.assertNotIn(uid, fight.native_retained_records)
            self.assertNotIn(uid, fight.native_owned_group_effects)
            self.assertIn(uid, previous.native_retained_records)
            self.assertIs(fight.native_rift_creation_deliveries, history)
            self.assertEqual(history, saved)
            self.assertIn(dead, fight.actors)
        self.assertEqual(plans[0], plans[1])

        class CustomHistory(dict):
            def items(self):
                raise AssertionError("custom history reader invoked")

        class CustomPackets(tuple):
            pass

        class CustomBytes(bytes):
            pass

        cases = (
            {"bad-key": ((12608, packet_a), (13091, packet_b))},
            {7: ((12608, packet_a), (99999, packet_b))},
            {7: ((12608, packet_a),)},
            {7: ((12608, bytearray(packet_a)), (13091, packet_b))},
            {7: ((12608, CustomBytes(packet_a)), (13091, packet_b))},
            {7: CustomPackets(((12608, packet_a), (13091, packet_b)))},
            CustomHistory({7: ((12608, packet_a), (13091, packet_b))}),
        )
        for history in cases:
            with self.subTest(
                kind=type(history).__name__,
                value_types=tuple(type(v).__name__ for v in dict.values(history)),
            ):
                _, fight, _, _, _ = OwnedCollectionGCTests().fixture()
                fight.native_rift_creation_deliveries = history
                self.assertFalse(boundary._canonical_graph(fight))

        # The same immutable bytes are not a general whitelist. Both direct
        # active aliases and aliases of the entire history remain unaudited.
        for alias in (
            packet_a,
            ((12608, packet_a), (13091, packet_b)),
            "whole-history",
        ):
            previous, fight, runtime, dead, uid = OwnedCollectionGCTests().fixture()
            fight.native_rift_creation_deliveries = {
                dead: ((12608, packet_a), (13091, packet_b))
            }
            fight.actors[dead].active_opaque_payload = (
                fight.native_rift_creation_deliveries
                if alias == "whole-history"
                else alias
            )
            self.assertFalse(boundary._canonical_graph(fight))
            boundary.prepare_retired_gc(previous, fight, runtime, ())
            self.assertIn(uid, fight.native_retained_records)
