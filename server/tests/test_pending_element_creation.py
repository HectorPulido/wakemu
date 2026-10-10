"""Fresh equipment must reach the native element picker without random bonuses."""
import unittest
from unittest.mock import patch

from wakfu_server.inventory_elements import (
    create,
    masks,
    bonuses,
    proto,
    binary_options,
)
from wakfu_server.element_selection import encode_result
from wakfu_server.wire import proto_fields


class PendingElementCreationTests(unittest.TestCase):
    def test_fresh_selectable_equipment_has_pending_wire_state_and_no_bonus(self):
        pending = create(2869)
        self.assertEqual(masks(pending), (0, 0))
        fields = dict(proto_fields(proto(pending)))
        self.assertEqual(dict(proto_fields(fields[450])), {8: 0, 16: 0})
        self.assertEqual(binary_options(pending), bytes((0, 0, 0, 0, 0, 1, 0, 0, 0, 0)))
        effect = dict(
            generic=1068,
            parameter_count=2,
            effect_criteria=False,
            has_triggers=False,
            target_mask=0,
            values=[21],
        )
        self.assertEqual(bonuses(pending, effect), {})
        self.assertEqual(
            bonuses(dict(damage_elements=26, resistance_elements=0), effect),
            {21: 21, 23: 21, 24: 21},
        )

    def test_nonselectable_templates_do_not_gain_element_metadata(self):
        with patch("wakfu_server.equipment_stats.CATALOG", {1: {"effects": []}}):
            self.assertIsNone(create(1))

    def test_element_choice_response_repairs_legacy_slots_without_losing_them(self):
        legacy = bytes.fromhex("0a04500060010a0450016003")
        _, body = encode_result(31, 26, 0, sockets=legacy)
        self.assertEqual(body[17:19], bytes((26, 0)))
        self.assertEqual(body[23:], bytes.fromhex("0a065000600158000a06500160035800"))
