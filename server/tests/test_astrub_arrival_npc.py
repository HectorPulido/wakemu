"""Captured grandma dialogue admission, native presentation and repeat entry."""

import struct
import unittest

from wakfu_server.achievements import npc_dialogue_actions
from wakfu_server import npc_world, rii_dialogue_gate

ACTOR = -1776810787923716


def row():
    value = dict(
        actor_id=ACTOR,
        reference_id=3257,
        map_id=895,
        instance_id=0,
        x=0,
        y=-2,
        z=0,
        direction=3,
        dialogue_root=7115,
        action_ids=[587],
        interaction_range=3,
        enabled=True,
        native_capture_id=ACTOR,
        native_publication_authorized=True,
    )
    value["native_capture_contract"] = dict(
        **{
            key: value[key]
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
        source_sha256="a" * 64,
    )
    return value


def native():
    nodes = [
        dict(
            id=7115, choices=[dict(id=15205, criteria="")], criteria="", native_cmT=""
        ),
        dict(
            id=7116, choices=[dict(id=15208, criteria="")], criteria="", native_cmT=""
        ),
        dict(
            id=7117, choices=[dict(id=15209, criteria="")], criteria="", native_cmT=""
        ),
        dict(
            id=7118, choices=[dict(id=15210, criteria="")], criteria="", native_cmT=""
        ),
    ]
    return dict(
        nodes=nodes,
        speakers=[dict(ref=3257, min_level=3, actions=[dict(id=587, criteria="")])],
        translations={"es": {"content.7.3257": "Abuelita Ditocas"}},
    )


class AstrubArrivalNpcTests(unittest.TestCase):
    def test_only_exact_reviewed_scene_and_action_are_admitted(self):
        character = dict(map_id=895, instance_id=0)
        request = struct.pack(">qq", ACTOR, 587)
        self.assertTrue(rii_dialogue_gate.allow(13222, request, character, None))
        for changed, body in (
            (dict(character, map_id=527), request),
            (dict(character, instance_id=1), request),
            (character, struct.pack(">qq", ACTOR, 588)),
            (character, struct.pack(">qq", ACTOR + 1, 587)),
            (character, request[:-1]),
        ):
            self.assertFalse(npc_dialogue_actions.allow(13222, body, changed, None))
        self.assertFalse(
            npc_dialogue_actions.allow(
                12058, struct.pack(">ii", 7118, 15210), character, None
            )
        )

    def test_captured_graph_advances_and_terminal_response_closes(self):
        placement = row()
        character = dict(id=1, account_id=2, map_id=895, instance_id=0, x=0, y=-1, z=0)
        session, packet = npc_world.begin(
            lambda: character,
            lambda: [placement],
            ACTOR,
            587,
            native=native(),
            facts_provider=lambda: {},
        )
        self.assertEqual(packet, (12969, struct.pack(">ibq", 7115, 2, ACTOR)))
        for node, choice, target in (
            (7115, 15205, 7116),
            (7116, 15208, 7117),
            (7117, 15209, 7118),
            (7118, 15210, 0),
        ):
            self.assertEqual(
                session.choose(node, choice), (12218, struct.pack(">i", target))
            )
        self.assertIsNone(session.node_id)

    def test_completed_introduction_reopens_native_reminder_and_can_close(self):
        placement = row()
        character = dict(id=1, account_id=2, map_id=895, instance_id=0, x=0, y=-1, z=0)
        source = native()
        session, packet = npc_world.begin(
            lambda: character,
            lambda: [placement],
            ACTOR,
            587,
            native=source,
            facts_provider=lambda: {11508: True},
        )
        self.assertEqual(packet, (12969, struct.pack(">ibq", 7118, 2, ACTOR)))
        self.assertEqual(session.nodes[7118]["choices"], [])
        self.assertEqual(len(source["nodes"][3]["choices"]), 1)
        self.assertIsNone(session.choose(7118, -1))
        self.assertIsNone(session.node_id)


if __name__ == "__main__":
    unittest.main()
