import copy
import struct
import unittest

from wakfu_server.maps.npc_world import begin, spawn, validate_placements


class CapturedNpcWorldTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(
            actor_id=-1706442035962340,
            reference_id=5458,
            map_id=1387,
            instance_id=0,
            x=-12,
            y=0,
            z=2,
            direction=1,
            dialogue_root=5764,
            action_ids=[1238],
            interaction_range=4,
            native_capture_id=-1706442035962340,
            native_publication_authorized=True,
            enabled=True,
        )
        self.row["native_capture_contract"] = dict(
            self.row,
            publication_authorized=True,
            source_sha256="eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69",
        )
        self.character = dict(
            id=100, account_id=200, map_id=1387, instance_id=0, x=-11, y=0, z=2
        )

    def test_original_actor_actual_catalog_action_root_and_spawn(self):
        self.assertEqual(validate_placements([self.row]), (self.row,))
        packet = spawn(self.row)
        self.assertEqual(packet[0], 12608)
        self.assertIn("Grugaloragrán".encode(), packet[1])
        session, packet = begin(
            lambda: self.character, lambda: [self.row], self.row["actor_id"], 1238
        )
        self.assertEqual(
            packet, (12969, struct.pack(">ibq", 5764, 2, self.row["actor_id"]))
        )
        # No inferred level-dependent quest transition is executed.
        with self.assertRaises(ValueError):
            session.choose(5764, 13343)
        self.assertIsNone(session.choose(5764, 13344))
        with self.assertRaises(ValueError):
            session.choose(5764, 13344)

    def test_foreign_unaccredited_ids_and_altered_contract_fields_rejected(self):
        for changes in (
            dict(actor_id=-7),
            dict(x=-16),
            dict(dialogue_root=6274),
            dict(action_ids=[515]),
            dict(instance_id=1),
            dict(native_capture_contract=None),
            dict(native_capture_contract={"source_sha256": None}),
            dict(native_publication_authorized=False),
        ):
            with self.subTest(changes=changes):
                row = dict(self.row, **changes)
                with self.assertRaises(ValueError):
                    validate_placements([row])
        row = copy.deepcopy(self.row)
        row["native_capture_contract"]["source_sha256"] = "invalid"
        with self.assertRaises(ValueError):
            validate_placements([row])

    def test_scene_distance_and_foreign_action_are_authoritative(self):
        for changes, action in (
            (dict(instance_id=1), 1238),
            (dict(map_id=1134), 1238),
            (dict(x=0), 1238),
            ({}, 999),
        ):
            character = dict(self.character, **changes)
            with self.assertRaises(ValueError):
                begin(
                    lambda: character, lambda: [self.row], self.row["actor_id"], action
                )
        session, _ = begin(
            lambda: self.character, lambda: [self.row], self.row["actor_id"], 1238
        )
        self.row["native_publication_authorized"] = False
        with self.assertRaises(ValueError):
            # Fresh authoritative placement validation also revokes publication.
            validate_placements([self.row])

    def test_unsafe_lua_identity_and_duplicate_binding_rejected(self):
        row = copy.deepcopy(self.row)
        row["actor_id"] = row["native_capture_id"] = -(2**53 + 1)
        row["native_capture_contract"]["actor_id"] = row["actor_id"]
        with self.assertRaises(ValueError):
            validate_placements([row])
        with self.assertRaises(ValueError):
            validate_placements([self.row, self.row])
