"""Regression coverage for explicitly mapped native running-stage roots."""

import unittest
from contextlib import contextmanager
from unittest.mock import patch

from wakfu_server import quest_npc


class _DB:
    def execute(self, *_args, **_kwargs):
        return self

    def fetchone(self):
        return {"id": 1}


class _Store:
    @contextmanager
    def connection(self):
        yield _DB()

    def lock_character(self, *_args, **_kwargs):
        pass

    def character(self, account_id, character_id, _db):
        return {
            "id": character_id,
            "account_id": account_id,
            "map_id": 507,
            "instance_id": 0,
            "x": 1,
            "y": 1,
            "z": 0,
        }


class _Session:
    opened = []

    def __init__(self, *_args, **_kwargs):
        pass

    def open(self, root, actor_id, _authorize):
        self.opened.append((root, actor_id))
        return b"open"


class RunningRootsBeginTests(unittest.TestCase):
    def test_parallel_running_stages_must_resolve_to_one_shared_root(self):
        state = {
            "running": [2784, 2786],
            "completed": [],
            "active": [2784, 2786],
            "active_periods": {},
            "active_unknown": [],
            "objectives": [],
        }
        item = {
            "quest_id": 2784,
            "row": {"dialogue_root": 3300},
            "running_roots": {"2784": 3339, "2786": 3339},
        }
        self.assertEqual(quest_npc._running_root(None, {}, item, state), 3339)

        conflicting = dict(item, running_roots={"2784": 3339, "2786": 3340})
        with self.assertRaisesRegex(ValueError, "Conflicting active quest chain"):
            quest_npc._running_root(None, {}, conflicting, state)

    def test_opening_activation_selects_explicit_conditional_running_root(self):
        actor_id = -2251799934992048
        row = {
            "actor_id": actor_id,
            "reference_id": 1,
            "action_ids": [436],
            "dialogue_root": 2791,
            "map_id": 507,
            "instance_id": 0,
            "x": 1,
            "y": 1,
            "z": 0,
            "interaction_range": 2,
            "provenance": "wakemu.qualified-quest-conversation.v1:test",
        }
        item = {
            "row": row,
            "quest_id": 2691,
            "activation_policy": "already_running",
            "available_quests_on_open": [2691],
            "graph": [],
            "running_roots": {"2691": 2791},
            "running_root_branches": {
                "2691": [{"root": 2792, "criterion": "IsAchievementRunning(2691)"}]
            },
            # Deliberately no legacy `running_root`: deployments with an
            # explicit per-quest map must not evaluate a fallback eagerly.
        }
        document = {"placements": [item]}
        definition = {"d": 2691}
        bindings = {}
        state = {
            "running": [],
            "completed": [],
            "active": [],
            "active_periods": {},
            "objectives": [],
            "variables": {},
            "completion_dates": {},
        }

        def activate(*_args, **_kwargs):
            state["running"] = [2691]
            state["active"] = [2691]
            return [b"activation"]

        _Session.opened = []
        with (
            patch.object(
                quest_npc,
                "publication",
                return_value=(document, {2691: definition}, bindings),
            ),
            patch.object(quest_npc, "_owner"),
            patch.object(quest_npc, "_row", return_value=(row, item)),
            patch.object(quest_npc, "_nearby_placement", return_value=True),
            patch.object(quest_npc, "_activate", side_effect=activate) as activation,
            patch(
                "wakfu_server.achievements.storage.load_locked",
                side_effect=lambda *_args: state,
            ),
            patch.object(quest_npc, "_criterion", return_value=True) as criterion,
            patch.object(
                quest_npc.npc_dialogue, "catalog", return_value={"node_index": {}}
            ),
            patch.object(quest_npc.npc_dialogue, "DialogueSession", _Session),
        ):
            _session, packets = quest_npc.begin(
                _Store(),
                8,
                "lease",
                {"id": 7, "account_id": 8},
                actor_id,
                436,
                character_provider=lambda: {"id": 7, "account_id": 8},
                rows_provider=lambda: [row],
            )

        activation.assert_called_once()
        criterion.assert_called_once()
        self.assertEqual(_Session.opened, [(2792, actor_id)])
        self.assertEqual(packets, [b"activation", b"open"])


if __name__ == "__main__":
    unittest.main()
