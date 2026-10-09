"""fOs controls collision reactions independently from AP-loss parameter rDX."""
from types import SimpleNamespace
import unittest
from wakfu_server.combat_displacement import displacement_geometry


class DisplacementCollisionCapabilityTests(unittest.TestCase):
    def test_native_fOs_contract_for_all_four_path_runners(self):
        source = SimpleNamespace(position=(0, 0, 0))
        target = SimpleNamespace(position=(2, 0, 0))
        for family, expected in ((300, True), (301, True), (331, False), (305, False)):
            geometry = displacement_geometry(
                dict(effect_class=family, parameters=[2, 0]),
                1,
                source=source,
                target=target,
                cell=(4, 0, 0),
            )
            self.assertIs(geometry["collision_reactions"], expected)
        # eXp inherits rDX=true, but fOs=false prevents all fPa reactions.
        geometry = displacement_geometry(
            dict(effect_class=331, parameters=[2, 0]),
            1,
            source=source,
            target=target,
            cell=(4, 0, 0),
        )
        self.assertTrue(geometry["loss_ap"])
        self.assertFalse(geometry["collision_reactions"])
