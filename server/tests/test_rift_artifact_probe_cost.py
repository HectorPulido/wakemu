"""The live artifact probe derives pickup tolls from the selected native tree."""
import unittest
from tools.probe_rift_artifact_journey import artifact_contact_cost


class ArtifactProbeCostTests(unittest.TestCase):
    def test_native_toll_presence_never_fabricates_execution_proof(self):
        # Exact ordered child references/classes from published native area trees.
        areas = {
            "1568": {"effect_ids": [314889, 314893]},
            "1596": {"effect_ids": [315871, 315877]},
        }
        specs = {
            314889: (330, [314890]),
            314890: (330, [314891, 314892]),
            314891: (304, []),
            314892: (400, []),
            314893: (843, []),
            315871: (330, [315872]),
            315872: (330, [315873, 315874, 315875, 315876]),
            315873: (304, []),
            315874: (400, []),
            315875: (447, []),
            315876: (48, []),
            315877: (843, []),
        }
        effects = {
            str(i): dict(effect_class=kind, children=children)
            for i, (kind, children) in specs.items()
        }
        effects["315876"].update(parameters=[100.0, 0.0], native_effect_flags=[19, 30])
        before = dict(mp=6, position=[-1, 7, 0])
        after = dict(mp=1, position=[0, 11, 0])
        result = artifact_contact_cost(
            1568, before, after, areas=areas, effects=effects
        )
        self.assertEqual(result["whole_mp_toll_effects"], [])
        self.assertEqual(
            result["native_effect_order"], [314889, 314890, 314891, 314892, 314893]
        )
        self.assertFalse(result["toll_present"])
        self.assertFalse(result["toll_execution_verified"])
        self.assertEqual(result["toll_verification"], "no_native_toll")
        unproven = artifact_contact_cost(
            1596, before, after, areas=areas, effects=effects
        )
        self.assertTrue(unproven["toll_present"])
        self.assertFalse(unproven["toll_execution_verified"])
        self.assertEqual(unproven["toll_verification"], "execution_unproven")
        result = artifact_contact_cost(
            1596, before, dict(after, mp=0), areas=areas, effects=effects
        )
        self.assertEqual(result["whole_mp_toll_effects"], [315876])
        self.assertEqual(
            result["native_effect_order"],
            [315871, 315872, 315873, 315874, 315875, 315876, 315877],
        )
        # Even zero final MP does not prove which native effects executed.
        self.assertFalse(result["toll_execution_verified"])
        self.assertEqual(result["toll_verification"], "execution_unproven")
