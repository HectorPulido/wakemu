"""Only immutable sealed group flags may bypass repeated definition decoding."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import wakfu_server.combat_event_replay as replay_module
from wakfu_server.combat_event_replay import (
    NativeCloneAuthority,
    NativeEventReplay,
    NativeExternalEvent,
)
from test_combat_replay_source_batch import Reader, sealed


class GroupProjectionTests(unittest.TestCase):
    def setUp(self):
        with replay_module._SUBSCRIPTION_LOCK:
            replay_module._SUBSCRIPTION_CACHE.clear()
            replay_module._SUBSCRIPTION_BYTES = 0

    def fixture(self, metadata, count=1):
        entries = [
            SimpleNamespace(uid=i, generic_effect=i, manager_id=7)
            for i in range(1, count + 1)
        ]
        groups = {
            entry.uid: dict(
                invocation=dict(reference=entry.generic_effect),
                native_subscription_masks=[[] for _ in range(7)],
                native_effect_flags=[],
            )
            for entry in entries
        }
        retention = SimpleNamespace(
            view=lambda: SimpleNamespace(entries=entries),
            metadata={"effects": metadata},
            fight=SimpleNamespace(native_owned_group_effects=groups),
        )
        authority = NativeCloneAuthority(
            lambda *args: self.fail("no activation"),
            lambda *args: self.fail("no condition"),
        )
        return NativeEventReplay(SimpleNamespace(effects={}), retention), authority

    def test_warm_group_selection_has_no_decode_and_keeps_source_reads_private(self):
        reader = Reader(
            {
                str(i): dict(
                    event_global_subscription=False, event_reverse_subscription=False
                )
                for i in range(1, 5)
            }
        )
        metadata = sealed(reader, collection="test.group_flags")
        replay, authority = self.fixture(metadata, 4)
        event = NativeExternalEvent(7, (1003,), 6)
        self.assertEqual(replay(event, authority=authority), ())
        self.assertEqual(reader.reads, ["1", "2", "3", "4"])
        self.assertEqual(replay(event, authority=authority), ())
        self.assertEqual(reader.reads, ["1", "2", "3", "4"])
        private = metadata["1"]
        private["event_global_subscription"] = True
        self.assertFalse(metadata["1"]["event_global_subscription"])

    def test_activating_warm_listener_reads_full_definition_at_consumption(self):
        reader = Reader(
            {
                "1": dict(
                    event_global_subscription=False,
                    event_reverse_subscription=False,
                    event_priority=0,
                )
            }
        )
        replay, authority = self.fixture(
            sealed(reader, collection="test.activate_flags")
        )
        event = NativeExternalEvent(7, (1003,), 6)
        replay(event, authority=authority)
        with patch.object(
            replay_module, "subscription_selection", return_value="activate"
        ):
            with self.assertRaisesRegex(ValueError, "execution count"):
                replay(event, authority=authority)
        self.assertEqual(reader.reads, ["1", "1"])

    def test_unsealed_definitions_remain_current_and_do_not_enter_cache(self):
        metadata = {
            "1": dict(event_global_subscription=False, event_reverse_subscription=False)
        }
        replay, authority = self.fixture(metadata)
        event = NativeExternalEvent(7, (1003,), 6)
        with patch.object(
            replay_module, "subscription_selection", return_value=None
        ) as select:
            replay(event, authority=authority)
            metadata["1"]["event_global_subscription"] = True
            replay(event, authority=authority)
        self.assertEqual(
            [call.kwargs["global_subscription"] for call in select.call_args_list],
            [False, True],
        )
        self.assertFalse(replay_module._SUBSCRIPTION_CACHE)

    def test_malformed_first_row_preserves_mask_error_before_definition_field(self):
        reader = Reader(
            {
                "1": dict(event_reverse_subscription=False),
                "2": dict(
                    event_global_subscription=False, event_reverse_subscription=False
                ),
            }
        )
        replay, authority = self.fixture(
            sealed(reader, collection="test.invalid_flags"), 2
        )
        del replay.retention.fight.native_owned_group_effects[1][
            "native_subscription_masks"
        ]
        with self.assertRaisesRegex(KeyError, "native_subscription_masks"):
            replay(NativeExternalEvent(7, (1003,), 6), authority=authority)
        self.assertEqual(reader.reads, ["1"])
        self.assertFalse(replay_module._SUBSCRIPTION_CACHE)

    def test_projection_is_generation_scoped_and_shares_existing_lru_bounds(self):
        rows = {
            str(i): dict(
                event_global_subscription=False, event_reverse_subscription=False
            )
            for i in range(1, 4)
        }
        reader = Reader(rows)
        replay, authority = self.fixture(
            sealed(reader, collection="test.bounded_flags"), 3
        )
        with patch.object(replay_module, "_SUBSCRIPTION_MAX_ENTRIES", 2):
            replay(NativeExternalEvent(7, (1003,), 6), authority=authority)
            self.assertLessEqual(len(replay_module._SUBSCRIPTION_CACHE), 2)
            self.assertLessEqual(
                replay_module._SUBSCRIPTION_BYTES, replay_module._SUBSCRIPTION_MAX_BYTES
            )
        newer = Reader(
            {
                "1": dict(
                    event_global_subscription=True, event_reverse_subscription=False
                )
            }
        )
        replay.retention.metadata["effects"] = sealed(
            newer, collection="test.other_generation"
        )
        with patch.object(
            replay_module, "subscription_selection", return_value=None
        ) as select:
            replay(
                NativeExternalEvent(7, (1003,), 6),
                authority=authority,
                eligible_uids=frozenset({1}),
            )
        self.assertTrue(select.call_args.kwargs["global_subscription"])
        self.assertEqual(newer.reads, ["1"])
