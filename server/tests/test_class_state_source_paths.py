import json
from pathlib import Path
import tempfile
import unittest

from class_state_source_paths import reverse_edges, shortest_source_path, graph_nodes


class ScopedStateSourcePathTests(unittest.TestCase):
    def test_parent_guards_and_source_state_level_remain_candidate_evidence(self):
        graph = dict(
            nodes={
                "effect:1": dict(
                    kind="effect",
                    reference=1,
                    family=330,
                    criterion_raw="GetStateLevel(4)>=100",
                ),
                "effect:2": dict(
                    kind="effect", reference=2, family=304, raw_parameters=[5, 0, 2, 0]
                ),
            },
            edges=[
                dict(source="spell:10", target="effect:1", kind="native_spell_root"),
                dict(source="effect:1", target="effect:2", kind="ordered_group_child"),
            ],
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            with open(path, "wt") as stream:
                json.dump(graph, stream)
            parents = reverse_edges(path)
            result = shortest_source_path(parents, "spell:10", "effect:2")
            self.assertEqual(result["nodes"], ["spell:10", "effect:1", "effect:2"])
            self.assertFalse(result["executable_verified"])
            self.assertFalse(result["alternative_paths_complete"])
            nodes = graph_nodes(path, result["nodes"])
            self.assertEqual(
                nodes["effect:1"]["criterion_raw"], "GetStateLevel(4)>=100"
            )
            self.assertEqual(nodes["effect:2"]["raw_parameters"][2], 2)
            self.assertEqual(
                shortest_source_path(parents, "spell:99", "effect:2")["status"],
                "no_path_in_current_scoped_graph",
            )
