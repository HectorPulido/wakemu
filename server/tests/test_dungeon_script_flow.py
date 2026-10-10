"""Ensure evidence extraction cannot invent door control from numeric coincidence."""
import unittest
from server.tools.extract_dungeon_script_flow import script_references


class DungeonScriptFlowTests(unittest.TestCase):
    def test_numeric_map_or_function_name_does_not_bind_object(self):
        script = "function event_26873_1()\n local map = 26873\nend\n"
        self.assertEqual(script_references(script, {26873}), [])

    def test_typed_reference_retains_presentation_authority(self):
        script = 'function openDoor()\n InteractiveElement.setAnimation(26873, "AnimTrans_1_0")\nend\n'
        refs = script_references(script, {26873})
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["object_id"], 26873)
        self.assertEqual(refs[0]["function"], "openDoor")
        self.assertEqual(refs[0]["line"], 2)
        self.assertEqual(
            refs[0]["authority"], "client_presentation_call_not_server_unlock_condition"
        )

    def test_unknown_object_and_dynamic_variable_are_not_claimed(self):
        script = 'InteractiveElement.setAnimation(999, "Open")\nInteractiveElement.setAnimation(doorId, "Open")\n'
        self.assertEqual(script_references(script, {26873}), [])


if __name__ == "__main__":
    unittest.main()
