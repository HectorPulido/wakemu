import unittest
from unittest.mock import Mock

from wakfu_server.achievements import rii_lesson_layout as layout
from wakfu_server.achievements.rii_lesson_auto_start import KEYS
from wakfu_server.combat_encounter_scene_layout import scene_player_position


class RiiLessonLayoutTests(unittest.TestCase):
    def test_captured_formations_preserve_world_origin_and_match_dojo(self):
        character = {
            "id": 7,
            "map_id": 1388,
            "instance_id": 0,
            "x": -1,
            "y": -16,
            "z": 0,
        }
        for objective in layout.SUPPORTED:
            with self.subTest(objective=objective):
                count = 4 if objective == 10609 else 1
                monsters = [
                    {"id": -10 - i, "ref": 5466, "x": -2 - i, "y": -16, "z": 0}
                    for i in range(count)
                ]
                db = Mock()
                prefix, kind = KEYS[objective]

                def execute(_sql, args):
                    key = args[1]
                    if not key.startswith(prefix):
                        return Mock(fetchone=Mock(return_value=None))
                    actor = -int(key.removeprefix(prefix))
                    return Mock(
                        fetchone=Mock(
                            return_value={
                                "payload": {
                                    "kind": kind,
                                    "owner": 7,
                                    "actor_id": actor,
                                    "ref": 5466,
                                }
                            }
                        )
                    )

                db.execute.side_effect = execute
                self.assertEqual(layout.identify(db, character, monsters), objective)
                arena = layout.arena(
                    character, monsters, objective, cell_budget=2500, size_range=(7, 20)
                )
                self.assertEqual(
                    (arena["x"], arena["y"], arena["width"], arena["height"]),
                    (-5, -18, 11, 11),
                )
                self.assertEqual(scene_player_position(character, arena), layout.PLAYER)
                actual = tuple(pair[1] for pair in arena["participant_positions"])
                self.assertEqual(actual, layout.AREA if count == 4 else (layout.SACK,))
                self.assertEqual(
                    (character["x"], character["y"], character["z"]), (-1, -16, 0)
                )
                with self.assertRaises(ValueError):
                    scene_player_position(dict(character, id=8), arena)
