"""Exact protector actor join, speaker contract and original native record."""
import copy
import struct
import unittest

from wakfu_server.maps import npc_protectors, npc_world


def otomai():
    row = dict(
        actor_id=-1706442046308330,
        reference_id=5459,
        map_id=1385,
        instance_id=0,
        x=20,
        y=17,
        z=1,
        direction=3,
        dialogue_root=5772,
        action_ids=[1244],
        interaction_range=4,
        enabled=True,
        native_capture_id=-1706442046308330,
        native_publication_authorized=True,
    )
    row["native_capture_contract"] = dict(
        **{
            key: row[key]
            for key in (
                "actor_id",
                "reference_id",
                "map_id",
                "x",
                "y",
                "z",
                "direction",
                "dialogue_root",
                "action_ids",
            )
        },
        publication_authorized=True,
        source_sha256="e" * 64,
        speaker_type=1,
        speaker_id=424
    )
    row["native_protector_contract"] = dict(
        actor_id=row["actor_id"],
        protector_id=424,
        map_id=1385,
        territory_id=93601,
        appearance_id=22193,
        original_nation=0,
        current_nation=0,
    )
    return row


class NpcProtectorTests(unittest.TestCase):
    def test_minimal_record_equals_original_native_consumer_oracle(self):
        self.assertEqual(
            npc_protectors.record(otomai()).hex(),
            "000001a801000000000000000000016da101000056b1fff9f000000000160000000000000000000000",
        )
        self.assertEqual(len(npc_protectors.record(otomai())), 41)

    def test_missing_contradictory_or_forged_join_fails_closed(self):
        changes = [
            ("actor_id", -7),
            ("protector_id", 425),
            ("map_id", 1388),
            ("territory_id", 0),
            ("appearance_id", True),
            ("current_nation", -1),
        ]
        for key, value in changes:
            row = otomai()
            row["native_protector_contract"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                npc_protectors.record(row)
        row = otomai()
        row["native_protector_contract"] = None
        with self.assertRaises(ValueError):
            npc_protectors.record(row)
        row = otomai()
        row["native_publication_authorized"] = False
        with self.assertRaises(ValueError):
            npc_protectors.record(row)

    def test_no_duplicate_protector_registration_or_npc_identity_substitution(self):
        row = otomai()
        with self.assertRaises(ValueError):
            npc_protectors.records([row, copy.deepcopy(row)])
        request = dict(node_id=5772, speaker_type=1, speaker_id=424)
        self.assertTrue(npc_world.matches_open_request(row, request))
        self.assertFalse(
            npc_world.matches_open_request(
                row, dict(request, speaker_type=2, speaker_id=row["actor_id"])
            )
        )
        self.assertFalse(
            npc_world.matches_open_request(row, dict(request, speaker_id=425))
        )

    def test_real_catalog_action_opens_original_protector_and_rechecks_facts(self):
        row = otomai()
        character = dict(
            id=100, account_id=200, map_id=1385, instance_id=0, x=20, y=17, z=1
        )
        facts = {}
        session, packet = npc_world.begin(
            lambda: character,
            lambda: [row],
            row["actor_id"],
            1244,
            facts_provider=lambda: facts,
        )
        self.assertEqual(packet, (12969, struct.pack(">ibq", 5772, 1, 424)))
        facts[10596] = True
        with self.assertRaises(ValueError):
            session.choose(5772, 13288)
        self.assertIsNone(session.node_id)

    def test_original_close_choice_does_not_grant_quest_or_transition(self):
        row = otomai()
        character = dict(
            id=100, account_id=200, map_id=1385, instance_id=0, x=20, y=17, z=1
        )
        session, _ = npc_world.begin(
            lambda: character,
            lambda: [row],
            row["actor_id"],
            1244,
            facts_provider=lambda: {},
        )
        self.assertIsNone(session.choose(5772, 13288))
        self.assertIsNone(session.node_id)
        character["map_id"] = 1388
        with self.assertRaises(ValueError):
            npc_world.begin(
                lambda: character,
                lambda: [row],
                row["actor_id"],
                1244,
                facts_provider=lambda: {},
            )

    def test_npc_default_contract_remains_original_kind(self):
        row = dict(actor_id=-10)
        self.assertEqual(npc_protectors.speaker(row), (2, -10))
        self.assertEqual(npc_protectors.records([row]), ())
        row["native_capture_contract"] = dict(speaker_type=2, speaker_id=424)
        with self.assertRaises(ValueError):
            npc_protectors.speaker(row)
