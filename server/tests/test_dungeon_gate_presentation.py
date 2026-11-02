import copy
import struct
import unittest
from unittest.mock import patch
from wakfu_server import dungeon_gate_presentation as presentation
from wakfu_server import dungeon_object_states as states
from wakfu_server import dungeon_physical_doors as doors


def topology():
    return dict(
        asset_map_id=712,
        policy=doors.POLICY,
        rooms=[
            dict(order=1, cells=[[23, -58, -16]], anchor=[23, -58, -16]),
            dict(order=2, cells=[[23, -59, -16]], anchor=[23, -59, -16]),
        ],
        physical_doors=[
            dict(
                source_id=20418,
                position=[23, -59, -16],
                source_room=1,
                destination_room=2,
                presentation_rule="native-antre-oublie-gate20418-scene1648",
            )
        ],
    )


class NativeDoorProjectionTests(unittest.TestCase):
    def test_closed_payload_keeps_both_native_collision_flags(self):
        self.assertEqual(
            struct.unpack(">h6Bi", states.physical_door_payload(opened=False)[7:]),
            (1, 1, 0, 0, 1, 1, 0, 0),
        )

    def test_open_payload_hides_native_view_and_clears_collision(self):
        self.assertEqual(
            struct.unpack(">h6Bi", states.physical_door_payload(opened=True)[7:]),
            (0, 0, 0, 0, 0, 0, 0, 0),
        )

    def test_untyped_state_wire_remains_unchanged(self):
        self.assertEqual(
            states.state_payload(visible=True, usable=False, state_id=1).hex(),
            "01020000000602000101000000000000000000",
        )

    def test_rejects_non_boolean_state(self):
        for value in (0, 1, None, "open"):
            with self.assertRaises(ValueError):
                states.physical_door_payload(opened=value)

    def test_closed_gate_does_not_trigger_graphics(self):
        self.assertEqual(presentation.packets(topology(), opened_source_ids=()), ())

    def test_original_entry_event_and_long_parameter_replayed(self):
        packet = presentation.packets(topology(), opened_source_ids=(20418,))
        self.assertEqual(
            packet, ((13411, struct.pack(">BiiBq", 0, 13117, 1648, 1, 2)),)
        )
        self.assertEqual(
            presentation.packets(topology(), opened_source_ids=(20418,)), packet
        )

    def test_foreign_door_map_position_and_stage_are_rejected(self):
        for location, key, value in (
            ("top", "asset_map_id", 716),
            ("door", "source_id", 20414),
            ("door", "position", [23, -58, -16]),
            ("door", "destination_room", 1),
            ("door", "presentation_rule", "unknown"),
        ):
            t = topology()
            target = t if location == "top" else t["physical_doors"][0]
            target[key] = value
            with self.assertRaises(ValueError):
                presentation.packets(t, opened_source_ids=(20418,))

    def test_unqualified_old_pin_has_no_new_scenario(self):
        t = topology()
        t["physical_doors"][0].pop("presentation_rule")
        self.assertEqual(presentation.packets(t, opened_source_ids=(20418,)), ())

    def test_public_door_projection_orders_native_script_after_state(self):
        with patch(
            "wakfu_server.dungeon_optional_vote_geometry.gate_packets", return_value=()
        ):
            closed = doors.packets(
                topology(), map_id=712, instance_id=943, unlocked_room=1
            )
            opened = doors.packets(
                topology(), map_id=712, instance_id=943, unlocked_room=2
            )
            bootstrap = doors.packets(
                topology(), map_id=712, instance_id=943, unlocked_room=2
            )
            blocked = doors.packets(
                topology(),
                map_id=712,
                instance_id=943,
                unlocked_room=2,
                blocked_source_ids=(20418,),
            )
        self.assertEqual([p[0] for p in closed], [12344])
        self.assertEqual([p[0] for p in opened], [12344, 13411])
        self.assertEqual(opened, bootstrap)
        self.assertEqual([p[0] for p in blocked], [12344])

    def test_older_pin_bridge_requires_entire_configuration_hash(self):
        from wakfu_server.dungeon_runtime_config import canonical_hash

        config = dict(
            route=dict(key="native_dungeon_81"),
            version=6,
            topology=topology(),
            compiled_plan=dict(rooms=["unchanged"]),
            level_policy=dict(mode="fixed"),
        )
        config["topology"]["physical_doors"][0].pop("presentation_rule")
        rule = copy.deepcopy(presentation._rules()[0])
        rule["compatible_configuration"]["canonical_sha256"] = canonical_hash(config)
        untouched = copy.deepcopy(config)
        with patch.object(presentation, "_rules", return_value=[rule]):
            projected = presentation.project_configuration(config)
            self.assertEqual(config, untouched)
            self.assertIsNot(projected, config)
            self.assertEqual(projected["compiled_plan"], config["compiled_plan"])
            self.assertEqual(
                presentation.packets(projected["topology"], opened_source_ids=(20418,))[
                    0
                ][0],
                13411,
            )
            for key, value in (
                ("version", 7),
                ("compiled_plan", dict(rooms=["changed"])),
                ("level_policy", dict(mode="changed")),
            ):
                changed = copy.deepcopy(config)
                changed[key] = value
                self.assertIs(presentation.project_configuration(changed), changed)

    def test_foreign_pin_does_not_receive_compatibility_projection(self):
        config = dict(
            route=dict(key="native_dungeon_80"), version=6, topology=topology()
        )
        self.assertIs(presentation.project_configuration(config), config)

    def test_prevalidated_pin_compares_all_remaining_fields(self):
        from wakfu_server.dungeon_runtime_config import canonical_hash

        config = dict(
            route=dict(key="native_dungeon_81"),
            version=6,
            topology=topology(),
            evidence_hashes=dict(plan="p", topology="t", route="r"),
            compiled_plan=dict(rooms=["unchanged"]),
            level_policy=dict(mode="fixed"),
        )
        config["topology"]["physical_doors"][0].pop("presentation_rule")
        rule = copy.deepcopy(presentation._rules()[0])
        pin = rule["compatible_configuration"]
        pin.update(
            canonical_sha256=canonical_hash(config),
            validated_route=config["route"],
            validated_evidence_hashes=config["evidence_hashes"],
            remaining_configuration={
                k: v
                for k, v in config.items()
                if k not in ("compiled_plan", "topology", "route")
            },
        )
        with patch.object(presentation, "_rules", return_value=[rule]):
            self.assertEqual(
                presentation.project_configuration(config),
                presentation.project_configuration(config, validated_pin=True),
            )
            for key, value in (
                ("level_policy", dict(mode="changed")),
                ("extra", "unreviewed"),
                ("evidence_hashes", dict(plan="p", topology="other", route="r")),
            ):
                changed = copy.deepcopy(config)
                changed[key] = value
                self.assertIs(
                    presentation.project_configuration(changed, validated_pin=True),
                    changed,
                )

    def test_prevalidated_pin_requires_actual_boolean(self):
        with self.assertRaises(ValueError):
            presentation.project_configuration({}, validated_pin=1)


if __name__ == "__main__":
    unittest.main()
