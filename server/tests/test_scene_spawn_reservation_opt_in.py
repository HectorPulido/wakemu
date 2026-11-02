"""Scene slot reservation is opt-in; legacy policy output stays unchanged."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from wakfu_server import native_scene_start


class SceneSpawnReservationOptInTests(unittest.TestCase):
    def test_only_explicit_true_adds_initial_spawn_cells(self):
        # Existing immutable133 file is a test fixture, never a new rule source.
        original = json.loads(
            Path(
                "server/wakfu_server/maps/native_scene_start_contracts.json"
            ).read_text()
        )["policies"][0]
        for definition in (133, 134, 164):
            for flag in (None, False, True):
                with self.subTest(definition=definition, flag=flag):
                    rule = deepcopy(original)
                    rule["definition_id"] = definition
                    if flag is not None:
                        rule["environment"]["reserve_spawn_slots"] = flag
                    baseline = deepcopy(rule)
                    topology = dict(
                        _native_scene_started=True,
                        _native_scene_profile=dict(native_states=[]),
                    )
                    room = dict(
                        cells=rule["combat_cells"], anchor=rule["combat_anchor"]
                    )
                    with patch.object(native_scene_start, "binding", return_value=rule):
                        scene = native_scene_start.scene_room(topology, room)[
                            "encounter_scene"
                        ]
                    self.assertEqual(rule, baseline)
                    if flag is True:
                        self.assertEqual(
                            scene["native_initial_spawn_cells"],
                            [row["cell"] for row in rule["environment"]["placements"]],
                        )
                    else:
                        self.assertNotIn("native_initial_spawn_cells", scene)
