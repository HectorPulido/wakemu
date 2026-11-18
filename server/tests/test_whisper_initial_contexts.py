"""Initial Whisper chapters use actual terrain, native sources and terminal facts."""

from copy import deepcopy
from collections import defaultdict, deque
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_emotes as emotes
from wakfu_server import owned_story_mechanics as mechanics
import test_owned_story_terminal_returns as terminal_fixtures

ROOT = Path(__file__).resolve().parents[1] / "wakfu_server/maps/owned_story_profiles"


def read(slug, suffix=".json"):
    return json.loads((ROOT / (slug + suffix)).read_text())


class WhisperInitialContextTests(unittest.TestCase):
    def test_original_player_walking_reaches_every_required_story_frontier(self):
        for slug, frontiers in (
            ("whisper-crisper-1302", [(-11, -6, 0), (-8, 0, 0)]),
            ("whisper-fort-453", [(4, -25, 0), (4, -26, 0), (-1, -8, 0)]),
        ):
            native = read(slug, ".exploration.json")
            outgoing = defaultdict(list)
            for start, end in native["edges"]:
                outgoing[tuple(start)].append(tuple(end))
            reached = {(0, 0, 0)}
            pending = deque(reached)
            while pending:
                for end in outgoing[pending.popleft()]:
                    if end not in reached:
                        reached.add(end)
                        pending.append(end)
            with self.subTest(map_id=native["map_id"]):
                self.assertTrue(set(frontiers) <= reached)
                self.assertEqual(
                    native["profile"],
                    dict(height=6, movement_type=0, jump_capacity=4, native_class="Sm"),
                )

    def test_crisper_original_transport_intro_sergeant_and_orders_frontier(self):
        slug = "whisper-crisper-1302"
        selected = read(slug)
        configuration = read(slug, ".configuration.json")
        native = read(slug, ".native.v1.json")
        self.assertEqual(configuration["route"]["entry_object_id"], 32825)
        self.assertEqual(configuration["route"]["destination_id"], 4433)
        self.assertEqual(native["scenario_id"], 2447)
        self.assertEqual(native["scenes"]["21224"]["duration_ms"], 20000)
        self.assertEqual(native["interaction_approaches"]["32856"], [[-11, -6, 0]])
        self.assertEqual(native["programs"]["32856"]["descriptor_id"], 35)
        self.assertIsNone(
            controller.plan(selected, set(), kind="interactive", reference=32856)
        )
        intro_done = {"crisper-intro", "crisper-intro-done"}
        self.assertIsNone(
            controller.plan(selected, intro_done, kind="interactive", reference=32856)
        )
        winner = intro_done | {"crisper-sergeant-victory"}
        orders = controller.plan(selected, winner, kind="interactive", reference=32856)
        self.assertEqual(
            orders["effects"][-1],
            dict(kind="quest_objective", quest_id=4871, objective_id=10044),
        )
        self.assertIsNone(
            controller.plan(
                selected,
                winner | {"crisper-read-orders"},
                kind="interactive",
                reference=32856,
            )
        )
        roster = configuration["compiled_plan"]["rooms"][0]["monsters"]
        self.assertEqual(
            [
                (r["ref_id"], r["count"], r["native_min_level"], r["native_max_level"])
                for r in roster
            ],
            [(2142, 1, 113, 118)],
        )
        self.assertTrue(
            all(
                r["guide_min_level"] is None and r["guide_max_level"] is None
                for r in roster
            )
        )

    def test_fort_loss_is_distinct_from_win_and_emote_uses_real_actor_facing(self):
        selected = read("whisper-fort-453")
        native = read("whisper-fort-453", ".native.v1.json")
        completed = {"fort-arrival"}
        self.assertEqual(
            controller.plan(selected, completed, kind="room_victory", reference=1)[
                "effects"
            ],
            [],
        )
        loss = controller.plan(selected, completed, kind="room_defeat", reference=1)
        self.assertEqual(loss["effects"][-1]["objective_id"], 10047)
        actor = dict(role="crossbowman", actor_id=9001, x=4, y=-27, z=0)
        cells = {tuple(p) for p in selected["emote_triggers"][0]["positions"]} | {
            (4, -27, 0),
            (-3, -8, 0),
        }
        geometry = SimpleNamespace(cells=cells)
        emotes.validate_sources(selected, native, geometry)
        active = dict(running=[4872], completed=[], objectives=[10046])
        for position, direction, reference, story_state, expected in (
            ((4, -26, 0), 7, 20106, active, True),
            ((4, -26, 0), 3, 20106, active, False),
            ((4, -25, 0), 7, 20106, active, False),
            ((4, -26, 0), 7, 20107, active, False),
            (
                (4, -26, 0),
                7,
                20106,
                dict(running=[], completed=[], objectives=[]),
                False,
            ),
            (
                (4, -26, 0),
                7,
                20106,
                dict(running=[4872], completed=[], objectives=[10046, 10048]),
                False,
            ),
        ):
            character = dict(
                id=7,
                account_id=2,
                instance_id=123,
                map_id=453,
                x=position[0],
                y=position[1],
                z=position[2],
                direction=direction,
            )
            with self.subTest(
                position=position, direction=direction, emote=reference
            ), patch.object(
                controller, "recognizes_instance", return_value=True
            ), patch.object(
                controller, "_scope", return_value=(selected, completed)
            ), patch(
                "wakfu_server.combat_geometry.published_geometry", return_value=geometry
            ), patch(
                "wakfu_server.owned_story_admission.scene_actor_rows",
                return_value=[actor],
            ), patch(
                "wakfu_server.achievements.storage.load_locked",
                return_value=story_state,
            ), patch.object(
                mechanics, "executor", return_value=object()
            ), patch.object(
                controller, "_settle", return_value=dict(packets=[(13411, b"native")])
            ) as settle:
                packets = emotes.performed(object(), object(), character, reference)
                self.assertEqual(bool(packets), expected)
                self.assertEqual(bool(settle.call_count), expected)
                if expected:
                    self.assertEqual(
                        settle.call_args.kwargs["evidence"]["actor_id"], 9001
                    )

    def test_fort_emote_invalid_area_or_missing_scoped_actor_fails_closed(self):
        selected = read("whisper-fort-453")
        native = read("whisper-fort-453", ".native.v1.json")
        cells = set(map(tuple, read("whisper-fort-453", ".exploration.json")["cells"]))
        bad = deepcopy(selected)
        bad["emote_triggers"][0]["positions"] = [[500, 500, 0]]
        with self.assertRaisesRegex(ValueError, "native floor"):
            emotes.validate_sources(bad, native, SimpleNamespace(cells=cells))
        bad = deepcopy(native)
        bad["scene_actors"] = []
        with self.assertRaisesRegex(ValueError, "unique native actor"):
            emotes.validate_sources(selected, bad, SimpleNamespace(cells=cells))

    def test_genuine_loss_invokes_owned_native_feedback_after_roster_proof(self):
        fixture = terminal_fixtures.OwnedStoryTerminalReturnTests()
        values = fixture.fixture(victory=False)
        db, store, fight, participants, original, selected, configuration = values
        selected["steps"] = [
            dict(
                id="native-loss",
                kind="room_defeat",
                reference=1,
                requires=[],
                effects=[],
                evidence="fixture",
            )
        ]
        fight.actors[7].hp = 0
        fight.events.append(dict(kind="death", actor_id=7))
        with patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ), patch(
            "wakfu_server.achievements.mission_toolkit.settle", return_value=[]
        ), patch.object(
            controller, "_settle", return_value=dict(packets=[(13411, b"feedback")])
        ) as settle:
            self.assertEqual(fixture.stage(*values), {2: [(13411, b"feedback")]})
            self.assertEqual(settle.call_args.kwargs["kind"], "room_defeat")
            self.assertEqual(
                settle.call_args.kwargs["evidence"]["original_actor_ids"], [-11]
            )


if __name__ == "__main__":
    unittest.main()
