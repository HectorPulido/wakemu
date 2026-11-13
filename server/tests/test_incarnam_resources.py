import unittest
from unittest.mock import patch

from wakfu_server.achievements import incarnam_resources as ir
from wakfu_server.intro_cinematic import private_instance_id


class IncarnamResourceTests(unittest.TestCase):
    def setUp(self):
        self.actor = {"id": 42, "map_id": 1361, "instance_id": private_instance_id(42)}

    def test_private_scope_and_tutorial_resource_identity(self):
        self.assertTrue(ir.owned_scene(self.actor))
        self.assertFalse(
            ir.owned_scene({**self.actor, "instance_id": private_instance_id(43)})
        )
        resource = {
            "map_id": 1361,
            "instance_id": self.actor["instance_id"],
            "resource_reference": 824,
        }
        with patch.object(ir, "active", return_value=True), patch.object(
            ir.incarnam_tutorial, "settle", return_value=[("ok", b"")]
        ) as settle:
            self.assertEqual(
                ir.harvested(
                    None,
                    None,
                    self.actor,
                    resource,
                    {"action_id": 2266},
                    token="t",
                    product_reference=30939,
                ),
                [("ok", b"")],
            )
            self.assertEqual(
                ir.harvested(
                    None,
                    None,
                    self.actor,
                    resource,
                    {"action_id": 99},
                    token="u",
                    product_reference=30939,
                ),
                [],
            )
            self.assertEqual(settle.call_count, 1)

    def test_craft_requires_exact_recipe_station_and_product(self):
        row = {
            "table_uid": 34582,
            "recipe_id": 9323,
            "map_id": 1361,
            "instance_id": self.actor["instance_id"],
        }
        with patch.object(ir, "active", return_value=True), patch.object(
            ir.incarnam_tutorial, "settle", return_value=[("ok", b"")]
        ) as settle:
            self.assertEqual(
                ir.crafted(
                    None, None, self.actor, row, [{"reference": 30940}], token="t"
                ),
                [("ok", b"")],
            )
            self.assertEqual(
                ir.crafted(
                    None,
                    None,
                    self.actor,
                    {**row, "table_uid": 7},
                    [{"reference": 30940}],
                    token="t",
                ),
                [],
            )
            self.assertEqual(
                ir.crafted(None, None, self.actor, row, [{"reference": 7}], token="t"),
                [],
            )
            self.assertEqual(settle.call_count, 1)

    def test_gate_request_is_scene_scoped(self):
        import struct

        request = struct.pack(">qHH", 34612, 0, 0)
        self.assertTrue(ir.is_gate_request(self.actor, request))
        self.assertFalse(ir.is_gate_request({**self.actor, "instance_id": 0}, request))
        self.assertFalse(
            ir.is_gate_request(self.actor, struct.pack(">qHH", 34612, 1, 0))
        )

    def test_gate_state_recovers_only_after_completion_for_owner(self):
        self.assertEqual(ir.gate_state_packets(self.actor, {"completed": []}), [])
        packets = ir.gate_state_packets(self.actor, {"completed": [5138]})
        self.assertEqual(len(packets), 3)
        self.assertTrue(all(opcode == 12344 for opcode, _ in packets))
        self.assertEqual(
            ir.gate_state_packets(
                {**self.actor, "instance_id": 0}, {"completed": [5138]}
            ),
            [],
        )

    def test_first_barriers_match_official_and_recover_after_fight(self):
        self.assertEqual(ir.first_barrier_packets(self.actor, {"completed": []}), [])
        packets = ir.first_barrier_packets(self.actor, {"completed": [5135]})
        self.assertEqual(len(packets), 5)
        self.assertEqual(
            packets[0],
            (
                12344,
                bytes.fromhex(
                    "0000000000008711001301020000000602000001010000000000000000"
                ),
            ),
        )
        self.assertEqual(packets[-1][1][:8], (34581).to_bytes(8, "big"))
        self.assertEqual(
            ir.first_barrier_packets(
                {**self.actor, "instance_id": 0}, {"completed": [5135]}
            ),
            [],
        )

    def test_seed_grant_once_and_both_ingredients(self):
        with patch.object(ir, "active", return_value=True), patch.object(
            ir.storage, "record_event", side_effect=[True, False]
        ), patch.object(
            ir.rewards,
            "_item",
            side_effect=lambda db, store, character, ref, qty: [(ref, qty)],
        ):
            self.assertEqual(
                ir.give_seed(None, None, self.actor), [(30938, 10), (30941, 1)]
            )
            self.assertEqual(ir.give_seed(None, None, self.actor), [])


if __name__ == "__main__":
    unittest.main()
