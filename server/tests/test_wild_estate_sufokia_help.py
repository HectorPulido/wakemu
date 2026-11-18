"""Confirmed native help starts real content; opening/preliminary talk does not."""
from contextlib import contextmanager
from copy import deepcopy
import gzip
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from wakfu_server import (
    owned_story_npcs as npcs,
    owned_story_controller,
    owned_story_mechanics,
)

ROOT = Path(__file__).parents[2]
PROFILES = ROOT / "server/wakfu_server/maps/owned_story_npc_profiles"


class Store:
    def __init__(self, character):
        self.current = character

    def character(self, *_):
        return dict(self.current)

    @contextmanager
    def connection(self):
        yield self


class WildSufokiaHelpTests(unittest.TestCase):
    def fixture(self, tag="start"):
        native = json.loads(
            gzip.decompress(
                (ROOT / "database/protocol/npc-dialogues.json.gz").read_bytes()
            )
        )
        native["node_index"] = {n["id"]: n for n in native["nodes"]}
        profile = json.loads(
            (PROFILES / ("wild-estate-sufokia-715-" + tag + ".json")).read_text()
        )
        instance = (1 << 57) + 77
        row = dict(
            profile["npcs"][0],
            actor_id=npcs.actor_id(instance, 1),
            map_id=715,
            instance_id=instance,
        )
        character = dict(
            id=8,
            account_id=7,
            level=50,
            map_id=715,
            instance_id=instance,
            x=0,
            y=-2,
            z=0,
        )
        state = dict(
            running=[1679],
            completed=[1677, 1678],
            objectives=[],
            active=[1677, 1678, 1679],
        )
        return native, profile, row, character, state

    def test_opening_preliminary_and_cancel_never_start_fight_or_award_help(self):
        native, profile, row, character, state = self.fixture()
        store = Store(character)
        with patch.object(
            npcs, "_locked", return_value=(character, profile, row, state)
        ), patch.object(
            npcs.npc_dialogue, "catalog", return_value=native
        ), patch.object(
            npcs.mission_toolkit, "settle"
        ) as quest, patch.object(
            owned_story_controller, "_settle"
        ) as story:
            session, _ = npcs.begin(store, 7, "lease", character, row["actor_id"], 440)
            result = npcs.choose(
                store, 7, "lease", character, session, struct.pack(">ii", 2331, 5639)
            )
            self.assertEqual(session.node_id, 2332)
            self.assertFalse(result["story_confirmed"])
            npcs.choose(
                store, 7, "lease", character, session, struct.pack(">ii", 2332, 5641)
            )
            story.assert_not_called()
            quest.assert_not_called()

    def test_confirmed_native_choice_starts_once_and_rechecks_guard_before_retry(self):
        native, profile, row, character, state = self.fixture()
        store = Store(character)
        with patch.object(
            npcs, "_locked", return_value=(character, profile, row, state)
        ), patch.object(
            npcs.npc_dialogue, "catalog", return_value=native
        ), patch.object(
            npcs.mission_toolkit, "settle"
        ) as quest, patch.object(
            owned_story_controller, "_scope", return_value=({}, set())
        ), patch.object(
            owned_story_mechanics, "executor", return_value=None
        ), patch.object(
            owned_story_controller,
            "_settle",
            return_value=dict(applied=True, packets=[]),
        ) as story:
            session, _ = npcs.begin(store, 7, "lease", character, row["actor_id"], 440)
            npcs.choose(
                store, 7, "lease", character, session, struct.pack(">ii", 2331, 5639)
            )
            result = npcs.choose(
                store, 7, "lease", character, session, struct.pack(">ii", 2332, 5640)
            )
            self.assertTrue(result["story_confirmed"])
            self.assertEqual(story.call_args.kwargs["reference"], 5640)
            self.assertEqual(story.call_args.kwargs["evidence"]["node_id"], 2332)
            quest.assert_not_called()  # 3115 belongs exclusively to the subsequent real victory.
            with self.assertRaises(ValueError):
                npcs.choose(
                    store,
                    7,
                    "lease",
                    character,
                    session,
                    struct.pack(">ii", 2332, 5640),
                )
            self.assertEqual(story.call_count, 1)
            # A fresh, guarded confirmation after a loss can retry the existing group.
            story.return_value = dict(applied=False, packets=[])
            session, _ = npcs.begin(store, 7, "lease", character, row["actor_id"], 440)
            npcs.choose(
                store, 7, "lease", character, session, struct.pack(">ii", 2331, 5639)
            )
            result = npcs.choose(
                store, 7, "lease", character, session, struct.pack(">ii", 2332, 5640)
            )
            self.assertTrue(result["story_confirmed"])
            session, _ = npcs.begin(store, 7, "lease", character, row["actor_id"], 440)
            npcs.choose(
                store, 7, "lease", character, session, struct.pack(">ii", 2331, 5639)
            )
            state["objectives"] = [3115]
            with self.assertRaises(ValueError):
                npcs.choose(
                    store,
                    7,
                    "lease",
                    character,
                    session,
                    struct.pack(">ii", 2332, 5640),
                )
            self.assertEqual(story.call_count, 2)

    def test_real_native_debrief_requires_victory_and_settles_separate_objective(self):
        native, profile, row, character, state = self.fixture("debrief")
        store = Store(character)
        with patch.object(
            npcs, "_locked", return_value=(character, profile, row, state)
        ), patch.object(
            npcs.npc_dialogue, "catalog", return_value=native
        ), patch.object(
            npcs.mission_toolkit, "settle", return_value=[]
        ) as quest:
            session, _ = npcs.begin(store, 7, "lease", character, row["actor_id"], 440)
            with self.assertRaises(ValueError):
                npcs.choose(
                    store,
                    7,
                    "lease",
                    character,
                    session,
                    struct.pack(">ii", 2331, 5645),
                )
            quest.assert_not_called()
            state["objectives"] = [3115]
            npcs.choose(
                store, 7, "lease", character, session, struct.pack(">ii", 2331, 5645)
            )
            npcs.choose(
                store, 7, "lease", character, session, struct.pack(">ii", 2333, 5642)
            )
            self.assertEqual(quest.call_args.args[-2:], ("npc_spoken", 3116))

    def test_original_enemy_roster_is_unavailable_before_confirmation(self):
        config = json.loads(
            (
                ROOT
                / "server/wakfu_server/maps/owned_story_profiles/wild-estate-sufokia-715.configuration.v2.json"
            ).read_text()
        )
        (room,) = config["topology"]["rooms"]
        self.assertEqual(room["requires"], ["frightened-bwork-help-confirmed"])
        self.assertEqual(
            {m["ref_id"] for m in config["compiled_plan"]["rooms"][0]["monsters"]},
            {2798, 2799},
        )
        profile = config["topology"]["owned_story_controller"]
        win = next(s for s in profile["steps"] if s["kind"] == "room_victory")
        self.assertEqual(
            win["effects"],
            [dict(kind="quest_objective", quest_id=1679, objective_id=3115)],
        )

    def test_bootstrap_renders_miner_before_ready_then_switches_to_same_debrief_actor(
        self,
    ):
        native, start, row, character, state = self.fixture()
        debrief = self.fixture("debrief")[1]
        store = Store(character)

        class DB:
            def execute(self, *_):
                return self

            def fetchone(self):
                return dict(context_policy_version=2)

        selected = {"id": start["controller_id"]}
        completed = set()
        with patch.object(
            npcs, "profiles", return_value=(start, debrief)
        ), patch.object(
            owned_story_controller, "recognizes_instance", return_value=True
        ), patch.object(
            owned_story_controller, "_scope", return_value=(selected, completed)
        ), patch.object(
            npcs.owned_story_refresh, "pending", return_value=None
        ), patch.object(
            npcs.storage, "load_locked", return_value=state
        ):
            before = npcs.rows(DB(), store, character, rendering=True)
            self.assertEqual(len(before), 1)
            self.assertEqual(npcs.rows(DB(), store, character), [])
            completed.update(
                [
                    "sufokian-storehouse-discovered",
                    "frightened-bwork-help-confirmed",
                    "sufokian-ghosts-admitted",
                    "sufokian-ghosts-defeated",
                ]
            )
            after = npcs.rows(DB(), store, character)
            self.assertEqual(len(after), 1)
            self.assertEqual(after[0]["actor_id"], before[0]["actor_id"])
            self.assertEqual(after[0]["objective_id"], 3116)


if __name__ == "__main__":
    unittest.main()
