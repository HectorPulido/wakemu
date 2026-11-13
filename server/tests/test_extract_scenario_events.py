import unittest

from tools.extract_scenario_events import extract_events


class ScenarioEventExtractionTests(unittest.TestCase):
    def test_event_comments_arguments_and_direct_and_delayed_callbacks(self):
        source = """-- ENTER_INSTANCE
-- Start
function event_2500_21800()
  Server.triggerEvent(21800)
end

-- 1 - TRIG(21800); Cinematic
function event_2500_22519(actorId, fightId)
  invoke_custom(6900, 1, "Server.triggerEvent", 22519)
end
"""
        events = extract_events(source)
        self.assertEqual(events[0]["comments"], ["ENTER_INSTANCE", "Start"])
        self.assertEqual(events[0]["callbacks"], [21800])
        self.assertEqual(events[1]["arguments"], ["actorId", "fightId"])
        self.assertEqual(events[1]["callbacks"], [22519])
        self.assertEqual(events[1]["event_id"], 22519)


if __name__ == "__main__":
    unittest.main()
