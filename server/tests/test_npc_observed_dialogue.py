"""Capture-qualified view transitions retain scene and objective authority."""
import copy
import struct
import unittest

from wakfu_server.maps import npc_dialogue, npc_observed_dialogue, npc_world
from test_npc_protectors import otomai

SOURCE = "eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69"


def captured_row(actor, reference, world, x, y, z, direction, root, action):
    row = dict(
        actor_id=actor,
        reference_id=reference,
        map_id=world,
        instance_id=0,
        x=x,
        y=y,
        z=z,
        direction=direction,
        dialogue_root=root,
        action_ids=[action],
        interaction_range=4,
        enabled=True,
        native_capture_id=actor,
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
        source_sha256=SOURCE
    )
    return row


class ObservedDialogueTests(unittest.TestCase):
    def setUp(self):
        self.nodes = {row["id"]: row for row in npc_dialogue.catalog()["nodes"]}

    def test_ledger_inventory_and_selected_initial_root_scope(self):
        evidence = npc_observed_dialogue.ledger()
        self.assertEqual(len(evidence["edges"]), 29)
        row = otomai()
        row["native_capture_contract"]["source_sha256"] = SOURCE
        self.assertEqual(
            npc_observed_dialogue.graph(row, self.nodes),
            {(5772, 13288): 5773, (5773, 13289): 5774, (5774, 13290): 0},
        )
        row = captured_row(-1706442046308328, 5467, 1385, 12, 32, 1, 1, 5782, 1255)
        graph = npc_observed_dialogue.graph(row, self.nodes)
        self.assertEqual(graph, {(5782, 13305): 5786, (5786, 13318): 0})
        self.assertNotIn((5762, 13337), graph)

    def test_wrong_native_speaker_or_initial_root_cannot_select_another_tree(self):
        row = otomai()
        row["native_capture_contract"]["source_sha256"] = SOURCE
        row["native_capture_contract"]["speaker_id"] = 425
        row["native_protector_contract"]["protector_id"] = 425
        self.assertEqual(npc_observed_dialogue.graph(row, self.nodes), {})
        row = otomai()
        row["native_capture_contract"]["source_sha256"] = SOURCE
        row["dialogue_root"] = 6274
        row["native_capture_contract"]["dialogue_root"] = 6274
        self.assertEqual(npc_observed_dialogue.graph(row, self.nodes), {})

    def test_all_five_captured_initial_paths_return_original_packets(self):
        specs = [
            (
                captured_row(-1706442046308322, 5461, 1385, -17, -4, 17, 3, 5765, 1243),
                [
                    (5765, 13275, 5766),
                    (5766, 13278, 5767),
                    (5767, 13280, 5768),
                    (5768, 13281, 5769),
                    (5769, 13282, 5783),
                    (5783, 13306, 5770),
                    (5770, 13283, 0),
                ],
            ),
            (
                captured_row(-1706442046308328, 5467, 1385, 12, 32, 1, 1, 5782, 1255),
                [(5782, 13305, 5786), (5786, 13318, 0)],
            ),
            (
                captured_row(-1706442046308339, 5460, 1388, 0, -19, 3, 3, 5755, 1390),
                [(5755, 13258, 5756), (5756, 13260, 0)],
            ),
        ]
        specs.append(
            (
                captured_row(-1706442035962340, 5458, 1387, -12, 0, 2, 1, 5764, 1238),
                [(5764, 13343, 5790), (5790, 13345, 5791), (5791, 13347, 0)],
            )
        )
        row = otomai()
        row["native_capture_contract"]["source_sha256"] = SOURCE
        specs.append(
            (row, [(5772, 13288, 5773), (5773, 13289, 5774), (5774, 13290, 0)])
        )
        for row, edges in specs:
            with self.subTest(root=row["dialogue_root"]):
                character = {
                    key: row[key] for key in ("map_id", "instance_id", "x", "y", "z")
                }
                character["level"] = 6
                original = copy.deepcopy(character)
                facts = {}
                session, _ = npc_world.begin(
                    lambda: character,
                    lambda: [row],
                    row["actor_id"],
                    row["action_ids"][0],
                    facts_provider=lambda: facts,
                )
                for node, choice, target in edges:
                    self.assertEqual(
                        session.choose(node, choice), (12218, struct.pack(">i", target))
                    )
                self.assertIsNone(session.node_id)
                self.assertEqual(facts, {})
                self.assertEqual(character, original)
                with self.assertRaises(ValueError):
                    session.choose(edges[-1][0], edges[-1][1])

    def test_mid_tree_original_action_facts_and_actor_distance_revoke(self):
        for mutation in ("facts", "distance"):
            row = otomai()
            row["native_capture_contract"]["source_sha256"] = SOURCE
            character = dict(map_id=1385, instance_id=0, x=20, y=17, z=1)
            facts = {}
            session, _ = npc_world.begin(
                lambda: character,
                lambda: [row],
                row["actor_id"],
                1244,
                facts_provider=lambda: facts,
            )
            self.assertEqual(
                session.choose(5772, 13288), (12218, struct.pack(">i", 5773))
            )
            if mutation == "facts":
                facts[10596] = True
            else:
                character["x"] += 100
            with self.assertRaises(ValueError):
                session.choose(5773, 13289)
            self.assertIsNone(session.node_id)

    def test_foreign_capture_source_and_conflicting_observation_fail_closed(self):
        row = otomai()
        self.assertEqual(npc_observed_dialogue.graph(row, self.nodes), {})
        row["native_capture_contract"]["source_sha256"] = SOURCE
        evidence = copy.deepcopy(npc_observed_dialogue.ledger())
        conflicting = copy.deepcopy(
            next(e for e in evidence["edges"] if e["node_id"] == 5772)
        )
        conflicting["target_node_id"] = 5774
        evidence["edges"].append(conflicting)
        with self.assertRaises(ValueError):
            npc_observed_dialogue.graph(row, self.nodes, evidence)

    def test_real_level_requires_progression_authority_and_unproven_quests_fail_closed(
        self,
    ):
        row = captured_row(-1706442035962340, 5458, 1387, -12, 0, 2, 1, 5764, 1238)
        character = dict(
            map_id=1387, instance_id=0, x=-12, y=0, z=2, level=5, effective_level=200
        )
        session, _ = npc_world.begin(
            lambda: character,
            lambda: [row],
            row["actor_id"],
            1238,
            facts_provider=lambda: {},
        )
        with self.assertRaises(ValueError):
            session.choose(5764, 13343)
        self.assertEqual(session.node_id, 5764)
        self.assertIsNone(session.choose(5764, 13344))
        self.assertNotIn((5764, 13344), npc_observed_dialogue.graph(row, self.nodes))
        from wakfu_server.maps import npc_objective_facts

        self.assertTrue(
            npc_objective_facts.evaluate(
                'GetRealLevel("caster") >= 6', dict(level=6, effective_level=1), {}
            )
        )
        for level in (None, True, 0, 201, "6", 5):
            self.assertFalse(
                npc_objective_facts.evaluate(
                    'GetRealLevel("caster") >= 6',
                    dict(level=level, effective_level=200),
                    {},
                )
            )
        self.assertFalse(
            npc_objective_facts.evaluate(
                "IsAchievementRunning(5145)", dict(level=200), {}
            )
        )
        self.assertFalse(
            npc_objective_facts.evaluate(
                'GetRealLevel("target") >= 6', dict(level=200), {}
            )
        )

    def test_missing_target_and_disconnected_nodes_do_not_authorize(self):
        row = otomai()
        row["native_capture_contract"]["source_sha256"] = SOURCE
        evidence = copy.deepcopy(npc_observed_dialogue.ledger())
        selected = next(e for e in evidence["edges"] if e["node_id"] == 5772)
        selected["target_node_id"] = 9999999
        with self.assertRaises(ValueError):
            npc_observed_dialogue.graph(row, self.nodes, evidence)
        evidence["edges"] = [
            e for e in npc_observed_dialogue.ledger()["edges"] if e["node_id"] != 5772
        ]
        self.assertEqual(npc_observed_dialogue.graph(row, self.nodes, evidence), {})
