"""Public API regressions for source-pinned paid scene activation."""
import copy
import unittest
from wakfu_server import native_scene_start, quest_npc


class NativeSceneContractTests(unittest.TestCase):
    def topology(self):
        rule = next(
            rule for rule in native_scene_start._rules() if rule["definition_id"] == 133
        )
        return (
            dict(
                asset_map_id=rule["map_id"],
                native_scene_start=dict(
                    policy_id=rule["policy_id"], source_id=rule["source_id"]
                ),
            ),
            rule,
        )

    def test_unrelated_dungeons_keep_ordinary_spawn_and_room(self):
        self.assertTrue(native_scene_start.can_spawn({}))
        room = dict(cells=[[0, 0, 0]])
        self.assertIs(native_scene_start.scene_room({}, room), room)
        self.assertEqual(native_scene_start.packets({}), ())

    def test_start_requires_receipt_and_profile_preserves_native_programs(self):
        topology, rule = self.topology()
        self.assertFalse(native_scene_start.can_spawn(topology))
        topology.update(
            _native_scene_started=True,
            _native_scene_profile=dict(
                native_states=[
                    dict(id=value, level=1)
                    for value in rule["profile"]["native_binary_state_ids"]
                ]
            ),
        )
        self.assertTrue(native_scene_start.can_spawn(topology))
        room = dict(cells=rule["combat_cells"], anchor=rule["combat_anchor"])
        before = copy.deepcopy(room)
        result = native_scene_start.scene_room(topology, room)
        self.assertEqual(room, before)
        self.assertEqual(len(result["encounter_scene"]["state_programs"]), 3)
        self.assertEqual(len(result["encounter_scene"]["native_initial_glyphs"]), 4)
        self.assertEqual(
            {
                row["reference"]
                for row in result["encounter_scene"]["native_initial_glyphs"]
            },
            {1282},
        )

    def test_locked_native_gate_denies_walk_before_payment(self):
        topology, rule = self.topology()
        gate = rule["gates"][0]["position"]
        request = dict(start_position=dict(zip(("x", "y", "z"), gate)), steps=[])
        with self.assertRaises(ValueError):
            native_scene_start.validate_movement(topology, request)
        native_scene_start.validate_movement(
            dict(topology, _native_scene_started=True), request
        )
        self.assertEqual(len(native_scene_start.packets(topology)), 3)

    def test_quest_arrival_never_bypasses_native_cost_or_criterion(self):
        arrival = dict(
            destination_id=3115,
            map_id=1201,
            cyZ=-1,
            native_altitude_walkable=True,
            criterion="",
            cyW=0,
            cyX=0,
            item_reference=0,
            cof=False,
        )
        source = dict(destinations=[arrival])
        self.assertEqual(quest_npc._free_quest_arrival(source, 3115), arrival)
        for key, value in (
            ("criterion", "GetRealLevel() >= 50"),
            ("cyW", 1),
            ("cyX", 1),
            ("item_reference", 28028),
            ("cof", True),
            ("cyZ", 136),
            ("native_altitude_walkable", False),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                quest_npc._free_quest_arrival(
                    dict(destinations=[dict(arrival, **{key: value})]), 3115
                )
        for source in (
            None,
            dict(destinations=[]),
            dict(destinations=[arrival, arrival]),
        ):
            with self.assertRaises(ValueError):
                quest_npc._free_quest_arrival(source, 3115)
