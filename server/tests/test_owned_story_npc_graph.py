"""Real native sessions must finish a guarded owned graph before progress."""
from contextlib import contextmanager
from copy import deepcopy
import gzip
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from wakfu_server import owned_story_npcs


class Store:
    def character(self, account_id, character_id, _db):
        return dict(
            id=character_id,
            account_id=account_id,
            level=65,
            map_id=945,
            instance_id=(1 << 57) + 77,
            x=155,
            y=3,
            z=0,
        )

    @contextmanager
    def connection(self):
        yield self


class OwnedStoryNpcGraphTests(unittest.TestCase):
    def fixture(self):
        root = Path(__file__).resolve().parents[2]
        native = json.loads(
            gzip.decompress(
                (root / "database/protocol/npc-dialogues.json.gz").read_bytes()
            )
        )
        native["node_index"] = {n["id"]: n for n in native["nodes"]}
        profile = json.loads(
            (
                root
                / "server/wakfu_server/maps/owned_story_npc_profiles/kelba-shop-945-late.json"
            ).read_text()
        )
        row = dict(
            profile["npcs"][0],
            actor_id=owned_story_npcs.actor_id((1 << 57) + 77, 1),
            map_id=945,
            instance_id=(1 << 57) + 77,
        )
        character = dict(
            id=8,
            account_id=7,
            level=65,
            map_id=945,
            instance_id=row["instance_id"],
            x=155,
            y=3,
            z=0,
        )
        state = dict(
            running=[2538], completed=[2537], objectives=[], active=[2537, 2538]
        )
        return native, profile, row, character, state

    def test_full_native_path_emits_only_at_real_terminal_and_replay_is_rejected(self):
        native, profile, row, character, state = self.fixture()
        with patch.object(
            owned_story_npcs, "_locked", return_value=(character, profile, row, state)
        ), patch.object(
            owned_story_npcs.npc_dialogue, "catalog", return_value=native
        ), patch.object(
            owned_story_npcs.mission_toolkit, "settle", return_value=[]
        ) as settle:
            session, _ = owned_story_npcs.begin(
                Store(), 7, 1, character, row["actor_id"], 673
            )
            self.assertEqual(session.node_id, 3106)
            for i, (node, choice, target) in enumerate(row["native_guard_path"]):
                owned_story_npcs.choose(
                    Store(), 7, 1, character, session, struct.pack(">ii", node, choice)
                )
                self.assertEqual(settle.call_count, int(i == 5))
                self.assertEqual(session.node_id, target or None)
            self.assertEqual(settle.call_args.args[-2:], ("npc_spoken", 5037))
            with self.assertRaises(ValueError):
                owned_story_npcs.choose(
                    Store(), 7, 1, character, session, struct.pack(">ii", 3111, 7734)
                )
            self.assertEqual(settle.call_count, 1)

    def test_terminal_rechecks_running_guard_after_earlier_native_dialogue(self):
        native, profile, row, character, state = self.fixture()
        with patch.object(
            owned_story_npcs, "_locked", return_value=(character, profile, row, state)
        ), patch.object(
            owned_story_npcs.npc_dialogue, "catalog", return_value=native
        ), patch.object(
            owned_story_npcs.mission_toolkit, "settle", return_value=[]
        ) as settle:
            session, _ = owned_story_npcs.begin(
                Store(), 7, 1, character, row["actor_id"], 673
            )
            for node, choice, _ in row["native_guard_path"][:-1]:
                owned_story_npcs.choose(
                    Store(), 7, 1, character, session, struct.pack(">ii", node, choice)
                )
            state["running"] = []
            state["completed"].append(2538)
            with self.assertRaises(ValueError):
                owned_story_npcs.choose(
                    Store(), 7, 1, character, session, struct.pack(">ii", 3111, 7734)
                )
            settle.assert_not_called()

    def test_native_default_greeting_remains_after_story_and_active_flags_survive(self):
        native, profile, row, character, state = self.fixture()
        state.update(
            running=[], completed=[2537, 2538, 2543], active=[2537, 2538, 2543]
        )
        self.assertTrue(
            owned_story_npcs._criterion(
                Store(), character, state, "IsAchievementActive(2538)"
            )
        )
        with patch.object(
            owned_story_npcs, "_locked", return_value=(character, profile, row, state)
        ), patch.object(owned_story_npcs.npc_dialogue, "catalog", return_value=native):
            session, _ = owned_story_npcs.begin(
                Store(), 7, 1, character, row["actor_id"], 673
            )
            self.assertEqual(session.node_id, 3080)

    def test_alternate_native_predecessor_cannot_bypass_bound_path(self):
        native, profile, row, _, _ = self.fixture()
        row = deepcopy(row)
        next(e for e in row["graph"] if e[:2] == [3106, 7736])[2] = 3111
        with self.assertRaises(ValueError):
            owned_story_npcs._dialogue_contract(profile, row, native)

    def test_initial_bootstrap_can_render_before_world_ready_without_unlocking_talk(
        self,
    ):
        native, profile, row, character, state = self.fixture()
        opcode, body = owned_story_npcs.npc_world.spawn(
            row, native, enabled_actions=row["action_ids"]
        )
        self.assertEqual(opcode, 12608)
        self.assertIn(struct.pack(">q", row["actor_id"]), body)

        class Database:
            def execute(self, *args):
                return self

            def fetchone(self):
                return {"context_policy_version": 1}

        with patch.object(
            owned_story_npcs, "profiles", return_value=(profile,)
        ), patch.object(
            owned_story_npcs.owned_story_controller,
            "recognizes_instance",
            return_value=True,
        ), patch.object(
            owned_story_npcs.owned_story_controller,
            "_scope",
            return_value=({"id": profile["controller_id"]}, set()),
        ), patch.object(
            owned_story_npcs.owned_story_refresh, "pending", return_value=None
        ), patch.object(
            owned_story_npcs.storage, "load_locked", return_value=state
        ):
            self.assertEqual(
                len(
                    owned_story_npcs._rows(
                        Database(), Store(), character, rendering=True
                    )
                ),
                1,
            )
            self.assertEqual(owned_story_npcs._rows(Database(), Store(), character), [])
