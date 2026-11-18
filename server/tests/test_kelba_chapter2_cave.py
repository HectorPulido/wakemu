"""Representative contracts for the native Kelba chapter-two cave slice."""
from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_admission, owned_story_controller
from wakfu_server import owned_story_mechanics, owned_story_traps
from wakfu_server.achievements import tutorial_presentation_once
from wakfu_server.application import owned_object_trial_dispatch, owned_story_dispatch

ROOT = Path(__file__).resolve().parents[1]
STORY = ROOT / "wakfu_server/maps/owned_story_profiles"


def load(path):
    return json.loads(path.read_text())


class KelbaChapterTwoCaveTests(unittest.TestCase):
    def test_discovery_requires_original_cinematic_before_separate_native_talk(self):
        policy = owned_story_controller.policy(
            {
                "topology": {
                    "owned_story_controller": load(STORY / "kelba-cave-952.json")
                }
            }
        )
        native = owned_story_mechanics.sources(policy)
        self.assertEqual(native["scenario_id"], 1967)
        finished = set()
        start = owned_story_controller.plan(
            policy, finished, kind="world_ready", reference=952
        )
        self.assertEqual(start["effects"][0]["event"], 15832)
        self.assertFalse(any(e["kind"] == "quest_objective" for e in start["effects"]))
        finished.add(start["id"])
        for callback, following in [(15832, 15833), (15833, 15834), (19799, 19799)]:
            if callback != 19799:
                self.assertIsNone(
                    owned_story_controller.plan(
                        policy, finished, kind="scenario_complete", reference=19799
                    )
                )
            step = owned_story_controller.plan(
                policy, finished, kind="scenario_complete", reference=callback
            )
            self.assertEqual(step["effects"][0]["event"], following)
            finished.add(step["id"])
        self.assertEqual(
            [
                (e["quest_id"], e["objective_id"])
                for e in step["effects"]
                if e["kind"] == "quest_objective"
            ],
            [(2547, 5046), (2548, 5047)],
        )
        for quest, objective in [(2547, 5065), (2548, 5064)]:
            npc = load(
                ROOT
                / f"wakfu_server/maps/owned_story_npc_profiles/kelba-cave-952-{quest}.json"
            )
            self.assertEqual(npc["requires"], ["chapter2-discovered"])
            row = npc["npcs"][0]
            self.assertEqual(
                (
                    row["reference_id"],
                    row["action_ids"],
                    row["dialogue_root"],
                    row["choice_id"],
                    row["objective_id"],
                ),
                (3580, [673], 3149, 7804, objective),
            )
        geometry = load(STORY / "kelba-cave-952.exploration.json")
        self.assertEqual((len(geometry["cells"]), len(geometry["edges"])), (65, 208))
        self.assertIn([-2, 0, 0], geometry["cells"])
        self.assertEqual(native["scene_actors"][0]["until"], ["chapter2-discovered"])

    def test_hydrate_projects_kabrok_while_accepted_move_waits_for_position_flush(self):
        configuration = load(STORY / "kelba-cave-952.configuration.json")
        selected = owned_story_controller.policy(configuration)
        character = {
            "id": 91,
            "account_id": 22,
            "map_id": 952,
            "instance_id": (1 << 57) + 31,
            "x": -1,
            "y": 0,
            "z": 0,
        }
        persisted = dict(character, x=0)
        db = object()
        store = SimpleNamespace(
            connection=lambda: nullcontext(db), character=Mock(return_value=persisted)
        )
        connection = SimpleNamespace()
        runtime = SimpleNamespace(STORE=store, send_batch=Mock())
        session = SimpleNamespace(
            runtime=runtime,
            state=SimpleNamespace(
                account_id=character["account_id"],
                character=character,
                connection=connection,
                service=3,
            ),
        )

        def scope(_db, _store, owner, *, check_position=True, lock=True):
            if check_position and owner["x"] != persisted["x"]:
                raise ValueError("Owned story position changed during its action")
            self.assertFalse(lock)
            return selected, set()

        with (
            patch.object(owned_object_trial_dispatch, "hydrate"),
            patch.object(owned_story_dispatch, "stage_ready", return_value=False),
            patch.object(
                owned_story_dispatch, "_configuration", return_value=configuration
            ),
            patch.object(owned_story_controller, "_scope", side_effect=scope) as scoped,
            patch.object(tutorial_presentation_once, "register_context"),
            patch.object(
                owned_story_traps, "projection", return_value={"active": False}
            ),
        ):
            self.assertTrue(owned_story_dispatch.hydrate(session, chunks={(0, 0)}))
            scoped.assert_called_once_with(
                db, store, character, check_position=False, lock=False
            )
            sent_connection, service, packets = runtime.send_batch.call_args.args
            self.assertIs(sent_connection, connection)
            self.assertEqual(service, 3)
            self.assertEqual([opcode for opcode, _ in packets], [12608])
            self.assertTrue(connection.owned_story_active)
            with self.assertRaisesRegex(ValueError, "position changed"):
                owned_story_admission.scene_actor_rows(db, store, character)


if __name__ == "__main__":
    unittest.main()
