"""Finite, source-bound physical entrance offers use native NPC presentation."""

from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server import dungeon_instances, generic_transports, npc_world
from wakfu_server import owned_physical_offers as offers, owned_object_trials


_PROFILE = Path(__file__).parents[1] / "wakfu_server" / "maps" / "owned_story_profiles"
_TRIAL_PROFILE = (
    Path(__file__).parents[1] / "wakfu_server" / "maps" / "owned_object_trial_profiles"
)


class OwnedPhysicalOffersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.configuration = json.loads(
            (_PROFILE / "astrub-crypt-889.configuration.json").read_text()
        )
        cls.source = generic_transports.source(527, 19411)

    def test_published_actor_uses_native_speaker_action_and_explicit_label(self):
        row = offers._row(self.configuration)
        self.assertEqual(row["reference_id"], 3275)
        self.assertEqual(row["action_ids"], [596])
        self.assertEqual(row["map_id"], 527)
        self.assertEqual(row["interaction_anchor"], {"x": 54, "y": 85, "z": 0})
        self.assertEqual(row["_physical_offer_label"], "Enter dungeon")
        from wakfu_server import npc_dialogue

        prototype = next(
            s for s in npc_dialogue.catalog()["speakers"] if s["ref"] == 3275
        )
        self.assertEqual((prototype["min_level"], prototype["max_level"]), (3, 3))
        self.assertTrue(offers.placement(row))

        opcode, packet = npc_world.spawn(row, enabled_actions=[596])
        self.assertEqual(opcode, 12608)
        self.assertEqual(packet[:2], b"\x00\x01")
        _kind, actor, payload_size = struct.unpack_from(">BqH", packet, 2)
        payload = packet[2 + struct.calcsize(">BqH") :]
        self.assertEqual(payload[0], 11)
        self.assertEqual(payload_size, len(payload))
        actor_in_payload, _kind, _owner, name_size = struct.unpack_from(
            ">qBqH", payload, 1
        )
        self.assertEqual(actor_in_payload, actor)
        offset = 1 + struct.calcsize(">qBqH")
        self.assertEqual(actor, row["actor_id"])
        self.assertEqual(payload[offset : offset + name_size].decode(), "Enter dungeon")
        self.assertEqual(struct.unpack_from(">h", payload, offset + name_size)[0], 3275)

    def test_archaeology_trial_offer_uses_original_native_source_and_keeps_prior_offers(
        self,
    ):
        configuration = json.loads(
            (_TRIAL_PROFILE / "archaeology-2698.configuration.json").read_text()
        )
        self.assertIsNotNone(owned_object_trials.policy(configuration))
        source = generic_transports.source(1134, 25474)
        row = offers._row(configuration)
        declaration = offers._declaration(configuration, source)
        self.assertIsNotNone(declaration)
        self.assertEqual(declaration["route_key"], configuration["route"]["key"])
        self.assertEqual(
            (source["id"], source["x"], source["y"], source["z"]),
            (25474, -21.0, 65.0, -16.0),
        )
        destination = next(
            item for item in source["destinations"] if item["destination_id"] == 2290
        )
        self.assertEqual(
            (
                destination["criterion"],
                destination["cvd"],
                destination["cyW"],
                destination["cyX"],
            ),
            ("IsAchievementActive(2698)", True, 0, 0),
        )
        self.assertEqual(
            (
                row["map_id"],
                row["reference_id"],
                row["action_ids"],
                row["interaction_anchor"],
                row["_physical_offer_label"],
            ),
            (1134, 3275, [596], {"x": -21, "y": 66, "z": -16}, "Enter dungeon"),
        )
        self.assertEqual(
            row["actor_id"],
            offers.actor_id(
                configuration["route"]["key"],
                row["_physical_offer"]["configuration_sha256"],
                row["_physical_offer"]["source_sha256"],
            ),
        )
        self.assertEqual(
            row["_physical_offer"]["source_sha256"], offers._digest(source)
        )

        opcode, packet = npc_world.spawn(row, enabled_actions=[596])
        self.assertEqual(opcode, 12608)
        self.assertEqual(packet[:2], b"\x00\x01")
        self.assertIn(b"Enter dungeon", packet)
        self.assertIn(struct.pack(">h", 3275), packet)

        declarations = offers.policy()["offers"]
        self.assertEqual(
            {item["route_key"] for item in declarations},
            {
                "quest-map-889-19411-1249",
                "quest-map-728-20653-1441",
                "quest-map-1001-25474-2290",
                "quest-map-951-25127-2210",
            },
        )
        old_configurations = (
            self.configuration,
            json.loads((_PROFILE / "astrub-nest-728.configuration.json").read_text()),
        )
        for old_configuration in old_configurations:
            self.assertTrue(offers.placement(offers._row(old_configuration)))

        kelba = json.loads((_PROFILE / "kelba-lair-951.configuration.json").read_text())
        kelba_source = generic_transports.source(949, 25127)
        kelba_row = offers._row(kelba)
        self.assertEqual((kelba_source["id"], kelba_source["map_id"]), (25127, 949))
        self.assertEqual(
            (
                kelba_row["map_id"],
                kelba_row["reference_id"],
                kelba_row["action_ids"],
                kelba_row["interaction_anchor"],
                kelba_row["_physical_offer_label"],
            ),
            (949, 3275, [596], {"x": -3, "y": -4, "z": 0}, "Enter dungeon"),
        )
        self.assertEqual(
            kelba_row["_physical_offer"]["source_sha256"], offers._digest(kelba_source)
        )
        self.assertTrue(offers.placement(kelba_row))

        wrong_configuration = deepcopy(configuration)
        wrong_configuration["route"]["destination_id"] = 2291
        with self.assertRaises(ValueError):
            offers._row(wrong_configuration)
        with patch.object(
            generic_transports, "source", return_value=dict(source, x=-20.0)
        ):
            with self.assertRaises(ValueError):
                offers._row(configuration)
        multiple_policies = deepcopy(configuration)
        multiple_policies["topology"]["owned_story_controller"] = {"fixture": True}
        with self.assertRaisesRegex(ValueError, "one typed owned policy"):
            offers._row(multiple_policies)

    def test_tampering_with_presentation_or_location_is_rejected_even_if_rehashed(self):
        row = offers._row(self.configuration)
        for changes in (
            {"actor_id": row["actor_id"] + 1},
            {"reference_id": 12608},
            {"action_ids": [62]},
            {"map_id": 528},
            {"x": row["x"] + 1},
            {"interaction_anchor": {"x": 53, "y": 85, "z": 0}},
            {"_physical_offer_label": "Open secret portal"},
        ):
            candidate = dict(row, **changes)
            candidate["_physical_offer_sha256"] = offers._digest(
                {
                    key: value
                    for key, value in candidate.items()
                    if key != "_physical_offer_sha256"
                }
            )
            with self.subTest(changes=changes):
                self.assertFalse(offers.placement(candidate))

    def test_private_and_replayed_actor_identities_are_not_accepted(self):
        row = offers._row(self.configuration)
        self.assertTrue(
            offers.recognizes(13222, struct.pack(">qq", row["actor_id"], 61))
        )
        self.assertFalse(offers.recognizes(13222, struct.pack(">qq", 12000, 61)))
        self.assertFalse(
            offers.recognizes(13221, struct.pack(">qq", row["actor_id"], 61))
        )
        self.assertFalse(offers.recognizes(13222, b"short"))
        self.assertNotEqual(
            row["actor_id"],
            offers.actor_id(
                self.configuration["route"]["key"],
                "0" * 64,
                row["_physical_offer"]["source_sha256"],
            ),
        )

    def test_stale_configuration_and_changed_native_source_are_denied(self):
        stale = deepcopy(self.configuration)
        stale["version"] += 1
        with self.assertRaises(ValueError):
            offers._row(stale)
        with patch.object(
            generic_transports, "source", return_value=dict(self.source, x=99)
        ):
            with self.assertRaises(ValueError):
                offers._row(self.configuration)

    def test_missing_native_approach_or_unregistered_route_is_skipped(self):
        character = {"map_id": 527, "instance_id": 0}
        record = {"configuration": self.configuration}
        db = Mock()
        db.execute.return_value.fetchall.return_value = [record]
        store = Mock()
        route = Mock()
        with patch.object(
            generic_transports,
            "source",
            return_value=dict(self.source, approach_positions=[]),
        ):
            with patch.object(dungeon_instances, "route", return_value=route):
                with patch(
                    "wakfu_server.owned_physical_entry.qualifies", return_value=True
                ):
                    self.assertEqual(offers.rows(db, store, character), ())

        with patch.object(
            dungeon_instances, "route", side_effect=ValueError("not loaded")
        ):
            with patch(
                "wakfu_server.owned_physical_entry.qualifies", return_value=True
            ):
                self.assertEqual(offers.rows(db, store, character), ())

    def test_duplicate_policy_entrance_is_rejected(self):
        profile = (
            Path(offers.__file__).with_name("owned_physical_offer_profiles")
            / "astrub-cemetery-nest.json"
        )
        document = json.loads(profile.read_text())
        document["offers"].append(dict(document["offers"][0]))
        raw = json.dumps(document).encode()
        import hashlib

        source_files = tuple(
            (name, hashlib.sha256(raw).hexdigest() if name == profile.name else digest)
            for name, digest in offers.SOURCE_FILES
        )
        with patch.object(offers, "SOURCE_FILES", source_files):
            original_read_bytes = Path.read_bytes

            def read_profile(path):
                if path.name == profile.name:
                    return raw
                return original_read_bytes(path)

            with patch.object(
                Path, "read_bytes", autospec=True, side_effect=read_profile
            ):
                offers.policy.cache_clear()
                try:
                    with self.assertRaisesRegex(ValueError, "overlap"):
                        offers.policy()
                finally:
                    offers.policy.cache_clear()


if __name__ == "__main__":
    unittest.main()
