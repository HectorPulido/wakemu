import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import rii_lesson_presentation as presentation


class RiiLessonPresentationTests(unittest.TestCase):
    def test_each_official_lesson_starts_and_completes_its_own_scenario(self):
        for index, (contract, objective, start, end) in enumerate(presentation.LESSONS):
            with self.subTest(objective=objective):
                fight = SimpleNamespace(**{contract: {"owner": 1}})
                choice = (5756, 13260) if index == 0 else (5787, 13322 + index)
                self.assertEqual(
                    presentation.begin(*choice),
                    (13411, struct.pack(">BiiB", 0, start, 2543, 0)),
                )
                self.assertEqual(
                    presentation.admission(fight, 1, *choice),
                    presentation.begin(*choice),
                )
                with self.assertRaisesRegex(ValueError, "admitted owner"):
                    presentation.admission(fight, 2, *choice)
                wrong_choice = (5787, 13322 + (index + 1) % 7)
                with self.assertRaisesRegex(ValueError, "admitted owner"):
                    presentation.admission(fight, 1, *wrong_choice)
                self.assertIsNone(presentation.finish(fight, []))
                self.assertIsNone(
                    presentation.finish(
                        fight, [(13832, struct.pack(">qi", 1, objective + 1))]
                    )
                )
                self.assertEqual(
                    presentation.finish(
                        fight, [(13832, struct.pack(">qi", 1, objective))]
                    ),
                    (13411, struct.pack(">BiiB", 0, end, 2543, 0)),
                )

    def test_normal_fight_has_no_tutorial(self):
        self.assertIsNone(presentation.begin(1, 2))
        self.assertIsNone(presentation.finish(SimpleNamespace(), []))

    def test_delivery_revision_never_reopens_any_guide_already_seen_by_character(self):
        from wakfu_server.achievements import tutorial_presentation_once as once

        seen = set()
        history = {}
        for _contract, _objective, event, _end in presentation.LESSONS:
            for variant in (0, 1):
                key = f"tutorial-presentation:2543:{event}:{variant}"
                history.setdefault(1, {})[key] = dict(
                    kind="tutorial_presentation",
                    scenario_id=2543,
                    event_id=event,
                    variant=variant,
                )

        class LegacyDB:
            def execute(self, sql, params):
                character_id, _length, prefix, expected = params
                expected = getattr(expected, "obj", expected)
                found = any(
                    key.startswith(prefix)
                    and all(
                        payload.get(key) == value for key, value in expected.items()
                    )
                    for key, payload in history.get(character_id, {}).items()
                )
                return SimpleNamespace(
                    fetchone=lambda: ({"present": 1} if found else None)
                )

        def record(_db, character_id, key, _payload):
            identity = (character_id, key)
            fresh = identity not in seen
            seen.add(identity)
            return fresh

        with patch.object(once.storage, "record_event", side_effect=record):
            db = LegacyDB()
            for index, (contract, _, start, _) in enumerate(presentation.LESSONS):
                fight = SimpleNamespace(**{contract: {"owner": 1}})
                choice = (5787, 13322 + index)
                packet = presentation.begin(*choice)
                self.assertEqual(
                    presentation.claim_admission(db, fight, 1, *choice), []
                )
                self.assertEqual(
                    presentation.claim_admission(db, fight, 1, *choice), []
                )
                guide_key = (1, f"tutorial-guide:{presentation.GUIDES[start]}")
                self.assertIn(guide_key, seen)

                other = SimpleNamespace(**{contract: {"owner": 2}})
                self.assertEqual(
                    presentation.claim_admission(db, other, 2, *choice), [packet]
                )


if __name__ == "__main__":
    unittest.main()
