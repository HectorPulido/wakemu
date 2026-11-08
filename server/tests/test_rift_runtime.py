"""Local rift selection is deterministic and never claims official balancing."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from wakfu_server.rift_policy import select_wave, validate


def policy():
    return dict(
        enabled=True,
        policy_kind="local_dev_not_official",
        turn_budget=40,
        max_members=4,
        classic_wave_size=4,
        ultimate_wave_size=2,
        starting_wave=1,
        selection="uniform_with_replacement",
        scaling="native_base_grade",
        quest_requirements=False,
        key_requirements=False,
        rewards="callback_only",
    )


class RiftCommittedProgressTests(unittest.TestCase):
    def test_committed_history_skips_database_replay_without_removing_births(self):
        from wakfu_server.rift_runtime import persist_progress, mark_progress_committed

        history = [dict(completed_wave=wave) for wave in range(1, 201)]
        fight = SimpleNamespace(
            id=7,
            phase="active",
            rift_wave_state=dict(instance_id=9, staged_receipts=history),
        )
        mark_progress_committed(fight, [dict(wave=200)])
        db = Mock()
        with patch(
            "wakfu_server.rift_runtime._run", return_value=dict(fight_id=7, wave=201)
        ), patch("wakfu_server.rift_runtime.record_wave") as record:
            self.assertEqual(persist_progress(db, fight), ())
        record.assert_not_called()
        db.execute.assert_not_called()
        self.assertIs(fight.rift_wave_state["staged_receipts"], history)

    def test_commit_marker_never_advances_without_successful_receipts(self):
        from wakfu_server.rift_runtime import mark_progress_committed, persist_progress

        fight = SimpleNamespace(id=7, rift_wave_state=dict(instance_id=9))
        mark_progress_committed(fight, ())
        self.assertNotIn("persisted_wave", fight.rift_wave_state)
        fight.rift_wave_state["persisted_wave"] = 4
        with patch(
            "wakfu_server.rift_runtime._run", return_value=dict(fight_id=7, wave=4)
        ), self.assertRaisesRegex(ValueError, "watermark"):
            persist_progress(Mock(), fight)


class RiftPolicyTests(unittest.TestCase):
    def setUp(self):
        self.catalog = dict(wave_id=3, type="INFINITE_WAVE", species_refs=[1, 4, 41])

    def test_retries_select_identical_native_pool(self):
        result = select_wave(self.catalog, policy(), "seed", 5)
        self.assertEqual(result, select_wave(self.catalog, policy(), "seed", 5))
        self.assertEqual(len(result), 4)
        self.assertTrue(set(result) <= {1, 4, 41})

    def test_ultimate_uses_separate_explicit_size(self):
        self.catalog["type"] = "ULTIMATE_INFINITE_WAVE"
        self.assertEqual(len(select_wave(self.catalog, policy(), "s", 1)), 2)

    def test_invalid_policy_or_empty_native_pool_fails_closed(self):
        for change in [
            dict(turn_budget=0),
            dict(turn_budget=True),
            dict(max_members=7),
            dict(policy_kind="official"),
            dict(selection="guess"),
            dict(key_requirements=True),
        ]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate(dict(policy(), **change))
        self.catalog["species_refs"] = []
        with self.assertRaises(ValueError):
            select_wave(self.catalog, policy(), "seed", 1)

    def test_six_member_dev_override_does_not_change_native_wave_selection(self):
        six = dict(policy(), max_members=6)
        self.assertEqual(validate(six)["max_members"], 6)
        self.assertEqual(
            select_wave(self.catalog, six, "six", 1),
            select_wave(self.catalog, policy(), "six", 1),
        )
