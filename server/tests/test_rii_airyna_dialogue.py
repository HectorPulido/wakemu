import struct
import unittest

from wakfu_server import rii_airyna_dialogue as dialogue
from wakfu_server import npc_world, rii_dialogue_gate
from test_npc_observed_dialogue import captured_row


class AirynaReturnTests(unittest.TestCase):
    def setUp(self):
        self.row = captured_row(-1706442046308339, 5460, 1388, 0, -19, 3, 3, 5755, 1390)
        self.character = dict(
            id=1, account_id=2, map_id=1388, instance_id=0, x=0, y=-18, z=3, level=10
        )
        self.facts = {10606: True, 10574: True}

    def begin(self):
        return dialogue.begin(
            lambda: self.character,
            lambda: [self.row],
            lambda: self.facts,
            self.row["actor_id"],
            1389,
        )

    def test_return_opens_native_root_and_offers_eligible_element_lesson(self):
        session, packet = self.begin()
        self.assertEqual(packet[1][:4], struct.pack(">i", 5787))
        with self.assertRaises(ValueError):
            session.choose(5787, 13324)
        self.assertEqual(session.choose(5787, 13323), (12218, struct.pack(">i", 0)))

    def test_return_can_retry_unfinished_orientation(self):
        self.facts.pop(10574)
        session, _ = self.begin()
        self.assertEqual(session.choose(5787, 13322), (12218, struct.pack(">i", 0)))
        self.facts[10574] = True
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13322)

    def test_accepted_intro_survives_its_own_action_criterion_changing(self):
        self.facts.clear()
        session, _ = npc_world.begin(
            lambda: self.character,
            lambda: [self.row],
            self.row["actor_id"],
            1390,
            facts_provider=lambda: self.facts,
        )
        self.assertEqual(session.choose(5755, 13258), (12218, struct.pack(">i", 5756)))
        self.facts[10606] = True
        self.assertEqual(session.choose(5756, 13260), (12218, struct.pack(">i", 0)))

    def test_return_action_is_admitted_and_scene_opens_with_captured_placement(self):
        # Action 1389 is a native returning action; the captured initial row
        # advertises 1390, and must not have to be rewritten to reopen Airyna.
        request = struct.pack(">qq", self.row["actor_id"], 1389)
        self.assertTrue(rii_dialogue_gate.allow(13222, request, self.character, None))
        npc_world.validate_placements([self.row])
        session, packet = self.begin()
        self.assertEqual(packet[0], 12969)
        self.assertTrue(
            rii_dialogue_gate.allow(
                12058, struct.pack(">ii", 5787, 13329), self.character, session
            )
        )
        self.assertEqual(session.choose(5787, 13329), (12218, struct.pack(">i", 0)))

    def test_element_choice_disappears_after_completion(self):
        self.facts[10575] = True
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13323)
        self.assertEqual(session.choose(5787, 13329), (12218, struct.pack(">i", 0)))

    def test_distance_offered_after_element_and_hidden_after_completion(self):
        self.facts[10575] = True
        session, _ = self.begin()
        self.assertEqual(session.choose(5787, 13324), (12218, struct.pack(">i", 0)))
        self.facts[10576] = True
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13324)

    def test_line_of_sight_is_available_only_between_its_prerequisite_and_completion(
        self,
    ):
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13325)
        self.facts[10576] = True
        session, _ = self.begin()
        self.assertEqual(session.choose(5787, 13325), (12218, struct.pack(">i", 0)))
        self.facts[10608] = True
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13325)

    def test_area_requires_line_of_sight_and_disappears_after_completion(self):
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13326)
        self.facts[10608] = True
        session, _ = self.begin()
        self.assertEqual(session.choose(5787, 13326), (12218, struct.pack(">i", 0)))
        self.facts[10609] = True
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13326)

    def test_movement_is_available_only_between_its_prerequisite_and_completion(self):
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13327)
        self.facts[10609] = True
        session, _ = self.begin()
        self.assertEqual(session.choose(5787, 13327), (12218, struct.pack(">i", 0)))
        self.facts[10610] = True
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13327)

    def test_flag_and_range_are_required(self):
        self.facts[10606] = False
        with self.assertRaises(ValueError):
            self.begin()
        self.facts[10606] = True
        self.character["x"] = 100
        with self.assertRaises(ValueError):
            self.begin()

    def test_states_requires_movement_and_disappears_after_completion(self):
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13328)
        self.facts[10610] = True
        session, _ = self.begin()
        self.assertEqual(session.choose(5787, 13328), (12218, struct.pack(">i", 0)))
        self.facts[10611] = True
        session, _ = self.begin()
        with self.assertRaises(ValueError):
            session.choose(5787, 13328)


if __name__ == "__main__":
    unittest.main()
