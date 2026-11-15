"""Reviewed Goultard dialogue phases share the generic authenticated NPC path."""

import json
from pathlib import Path
import struct
import unittest

from wakfu_server import npc_world
from wakfu_server.achievements import npc_dialogue_actions

ACTOR = -1776810790485981


def row():
    value = dict(
        actor_id=ACTOR,
        reference_id=4688,
        map_id=527,
        instance_id=0,
        x=11,
        y=155,
        z=0,
        direction=3,
        dialogue_root=7119,
        action_ids=[969],
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
    contract = npc_dialogue_actions.resolve(row(), 969)
    graphs = [contract["edges"]] + [phase["edges"] for phase in contract["phases"]]
    choices = {}
    for graph in graphs:
        for (node, choice), target in graph.items():
            choices.setdefault(node, set()).add(choice)
            if target:
                choices.setdefault(target, set())
    nodes = [
        dict(
            id=node,
            criteria="",
            native_cmT="",
            choices=[dict(id=choice, criteria="") for choice in sorted(values)],
        )
        for node, values in choices.items()
    ]
    return dict(
        nodes=nodes,
        speakers=[dict(ref=4688, min_level=0, actions=[dict(id=969, criteria="")])],
        translations={"es": {"content.7.4688": "Gúltar"}},
    )


class AstrubGoultardDialogueTests(unittest.TestCase):
    def begin(self, facts):
        placement = row()
        character = dict(
            id=1, account_id=2, map_id=527, instance_id=0, x=11, y=154, z=0
        )
        return npc_world.begin(
            lambda: character,
            lambda: [placement],
            ACTOR,
            969,
            native=native(),
            facts_provider=lambda: facts,
        )

    def test_owned_progress_selects_briefing_reminder_return_and_completed_text(self):
        for facts, root in (
            ({11509: True}, 7119),
            ({11509: True, 11510: True}, 7128),
            ({11515: True}, 7129),
            ({11515: True, 11544: True}, 7137),
        ):
            with self.subTest(facts=facts):
                session, packet = self.begin(facts)
                self.assertEqual(packet, (12969, struct.pack(">ibq", root, 2, ACTOR)))
                if 11544 in facts:
                    self.assertEqual(session.nodes[root]["choices"], [])
                    self.assertIsNone(session.choose(root, -1))
        session, _ = self.begin({11510: True})
        with self.assertRaisesRegex(ValueError, "Stale"):
            session.choose(7137, 15236)

    def test_initial_narrative_finishes_only_through_offered_terminal_choice(self):
        session, _ = self.begin({11509: True})
        for node, choice, target in (
            (7119, 15212, 7120),
            (7120, 15214, 7121),
            (7121, 15223, 7122),
            (7122, 15216, 7123),
            (7123, 15217, 7124),
            (7124, 15218, 7125),
            (7125, 15222, 7126),
            (7126, 15220, 0),
        ):
            self.assertEqual(
                session.choose(node, choice), (12218, struct.pack(">i", target))
            )
        self.assertIsNone(session.node_id)

    def test_return_narrative_has_its_own_terminal_choice(self):
        session, _ = self.begin({11515: True})
        for node, choice, target in (
            (7129, 15226, 7130),
            (7130, 15228, 7131),
            (7131, 15229, 7132),
            (7132, 15230, 7133),
            (7133, 15231, 7134),
            (7134, 15232, 7135),
            (7135, 15234, 7136),
            (7136, 15235, 7137),
            (7137, 15236, 0),
        ):
            self.assertEqual(
                session.choose(node, choice), (12218, struct.pack(">i", target))
            )
        self.assertIsNone(session.node_id)

    def test_profile_binds_only_authored_dialogue_events_and_not_combat_steps(self):
        profile = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "wakfu_server"
                / "achievements"
                / "mission_profiles"
                / "astrub-arrival.json"
            ).read_text()
        )
        bindings = {
            row["objective_id"]: row
            for row in profile["bindings"]
            if row["event"]["kind"] == "dialogue"
        }
        self.assertEqual(bindings[11510]["event"]["reference"], 15220)
        self.assertEqual(bindings[11544]["event"]["reference"], 15236)
        self.assertEqual(bindings[11510]["maps"], [527])
        self.assertEqual(bindings[11544]["maps"], [527])
        self.assertFalse(set(bindings).intersection(range(11511, 11516)))


if __name__ == "__main__":
    unittest.main()
