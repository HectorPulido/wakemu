"""Microbot geometry uses actual selected-terrain provenance, not Fight.map_id."""
import unittest
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_microbot_path import microbot_path_projection


class MicrobotMapIdentityTests(unittest.TestCase):
    def fight(self):
        actor = Actor(7, 0, (0, 0, 0), 100, 6, 3, 1, 1, 3, True)
        enemy = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 1, 1)
        return Fight(
            9,
            [actor, enemy],
            {actor.position, enemy.position},
            {0: {actor.position}, 1: {enemy.position}},
        )

    def test_real_fight_without_map_attribute_uses_exact_selected_provenance(self):
        from wakfu_server.combat_qi_surface_catalog import native_qi_surface_provenance

        fight = self.fight()
        self.assertFalse(hasattr(fight, "map_id"))
        fight.native_qi_surface_provenance = native_qi_surface_provenance(1134)
        # Real native Fight and publication validate before projection assembly;
        # assembly is observed independently of unrelated obstacle fixtures.
        with patch(
            "wakfu_server.combat_microbot_path.NativeMicrobotPathProjection",
            return_value="projection",
        ) as build, patch("wakfu_server.combat_qi_fight.current_registry") as registry:
            self.assertEqual(microbot_path_projection(fight), "projection")
        self.assertEqual(build.call_args.args[1].map_id, 1134)
        self.assertEqual(build.call_args.args[2].map_id, 1134)
        registry.assert_called_once_with(fight)

    def test_conflicting_publication_and_missing_map_are_rejected(self):
        from wakfu_server.combat_qi_surface_catalog import native_qi_surface_provenance

        fight = self.fight()
        fight.native_qi_surface_provenance = native_qi_surface_provenance(1134)
        fight.native_qi_surface_provenance["source_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "provenance mismatch"):
            microbot_path_projection(fight)
        fight.native_qi_surface_provenance = {"map_id": None}
        with self.assertRaisesRegex(ValueError, "Missing native microbot map identity"):
            microbot_path_projection(fight)
