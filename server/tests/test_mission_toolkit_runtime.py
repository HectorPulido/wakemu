"""Runtime deduplication and mixed-breed compatibility use producer identities."""

import copy
from datetime import datetime, timezone
from hashlib import sha256
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from wakfu_server.achievements import mission_toolkit as toolkit


class MissionToolkitRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.store = SimpleNamespace(
            now=lambda: datetime(2026, 11, 14, tzinfo=timezone.utc),
            character=lambda owner, identity, db: dict(self.character),
        )
        self.character = dict(id=7, account_id=2, map_id=1385, instance_id=0, level=20)
        self.before = dict(
            running=[1],
            completed=[],
            objectives=[],
            variables={},
            tracking=[1],
            recent=[],
            completion_dates={},
        )
        self.profile = dict(
            version=1,
            id="reviewed-test",
            evidence=["synthetic runtime test"],
            bindings=[
                dict(
                    id="seed",
                    quest_id=1,
                    objective_id=11,
                    variable_id=759,
                    event=dict(kind="resource_harvest", reference=31007),
                    count="operation",
                    maps=[1385],
                )
            ],
            links=[],
            activations=[],
        )
        self.native = {
            1: dict(
                d=1,
                native_class="aJM",
                aqb=False,
                cjI="",
                cjK=[],
                cjJ=[
                    dict(
                        d=11,
                        ckc="",
                        cke="",
                        ckf=[
                            dict(ckm='GetAchievementVariable("seed") >= 3', ckn=[759])
                        ],
                    )
                ],
            )
        }

    def execute(self, prior=(), profile=None):
        self.db.execute.return_value.fetchall.side_effect = [
            [{"profile_id": "test"}],
            list(prior),
        ]
        with patch.object(toolkit, "_load", return_value=None), patch.object(
            toolkit, "_project", return_value=(profile or self.profile, self.native)
        ), patch.object(
            toolkit.storage, "load_locked", return_value=copy.deepcopy(self.before)
        ), patch.object(
            toolkit.storage, "record_event", return_value=True
        ) as receipt, patch.object(
            toolkit.mission_dependencies,
            "settle",
            return_value={"packets": [(13371, b"journal")]},
        ) as settlement:
            result = toolkit.settle(
                self.db,
                self.store,
                self.character,
                "operation-42",
                "resource_harvest",
                31007,
                9,
            )
        return result, receipt, settlement

    def test_operation_count_is_once_and_uses_shared_settlement(self):
        packets, receipt, settlement = self.execute()
        self.assertEqual(packets, [(13371, b"journal")])
        self.assertEqual(settlement.call_args.args[4][0]["variables"], {"759": 1})
        receipt.assert_called_once()
        self.assertEqual(receipt.call_args.args[3]["quantity"], 9)

    def test_old_rii_receipt_skips_without_increment_or_new_reward(self):
        declaration = dict(self.profile, id="rii")
        key = "rii-ecosystem:resource_harvest:" + sha256(b"operation-42").hexdigest()
        packets, receipt, settlement = self.execute(
            [
                dict(
                    event_key=key,
                    payload=dict(kind="resource_harvest", item=31007, variable=759),
                )
            ],
            declaration,
        )
        self.assertEqual(packets, [])
        receipt.assert_not_called()
        settlement.assert_not_called()

    def test_conflicting_replay_is_rejected(self):
        key = (
            "mission-toolkit:resource_harvest:31007:"
            + sha256(b"operation-42").hexdigest()
        )
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.execute(
                [
                    dict(
                        event_key=key,
                        payload=dict(
                            kind="resource_harvest",
                            reference=31007,
                            quantity=2,
                            map_id=1385,
                        ),
                    )
                ]
            )

    def test_old_combat_aggregate_skips_rii_only_and_preserves_actual_breeds(self):
        self.db.execute.return_value.fetchone.return_value = dict(
            payload=dict(kind="rii_wodent_victory", fight_id=33, count=3)
        )
        with patch.object(toolkit, "_settle", return_value=[]) as event:
            toolkit.settle_combat(
                self.db,
                self.store,
                self.character,
                fight_id=33,
                breeds=[5455, 5455, 5456, 99],
            )
        self.assertEqual(
            [
                (call.args[4], call.args[5], call.args[6])
                for call in event.call_args_list
            ],
            [
                ("monster_defeat", 99, 1),
                ("monster_defeat", 5455, 2),
                ("monster_defeat", 5456, 1),
            ],
        )
        self.assertTrue(
            all(call.kwargs["excluded"] == ("rii",) for call in event.call_args_list)
        )

    def test_new_mixed_combat_records_one_complete_legacy_aggregate(self):
        self.db.execute.return_value.fetchone.return_value = None

        def apply(*args, **kwargs):
            kwargs["applied"].add("rii")
            return []

        with patch.object(toolkit, "_settle", side_effect=apply), patch.object(
            toolkit.storage, "record_event", return_value=True
        ) as receipt:
            toolkit.settle_combat(
                self.db,
                self.store,
                self.character,
                fight_id=33,
                breeds=[5455, 5455, 5456],
            )
        receipt.assert_called_once_with(
            self.db,
            7,
            "rii-wodent-victory:33",
            dict(kind="rii_wodent_victory", fight_id=33, count=3),
        )


class EffectiveToolkitCharacterTests(unittest.TestCase):
    def test_durable_level_and_inventory_preserve_private_producer_pose(self):
        durable = dict(
            id=7,
            account_id=2,
            level=20,
            map_id=1134,
            instance_id=0,
            x=1,
            y=2,
            z=3,
            inventory_items=[{"reference": 44}],
        )
        store = SimpleNamespace(character=lambda account, identity, db: durable)
        source = dict(
            id=7,
            account_id=2,
            level=1,
            map_id=1388,
            instance_id=991,
            x=0,
            y=-18,
            z=0,
            private_scene_token="owned-991",
        )
        result = toolkit.effective_character(None, store, source)
        self.assertEqual(result["level"], 20)
        self.assertEqual(
            (
                result["map_id"],
                result["instance_id"],
                result["x"],
                result["y"],
                result["z"],
            ),
            (1388, 991, 0, -18, 0),
        )
        self.assertEqual(result["inventory_items"], [{"reference": 44}])
        self.assertEqual(result["private_scene_token"], "owned-991")
        self.assertEqual(durable["map_id"], 1134)
