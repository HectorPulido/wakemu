"""Lifecycle envelopes validate before committing and yield at the deadline."""
import unittest
from unittest.mock import patch
from wakfu_server import ecology_mobs


def envelope():
    operations = []
    for actor in (-1, -2):
        operations.append(
            dict(
                kind="maturation",
                scope=[1134, 0],
                world_epoch="boot",
                configuration={},
                expected_members=[dict(id=actor)],
                draw=0.1,
                grown=None,
                ticket=dict(
                    map_id=1134,
                    instance_id=0,
                    monster_id=actor,
                    group_id=1,
                    reference=60,
                    cycle=1,
                    plan_incarnation="native",
                    decision={},
                ),
            )
        )
    return dict(
        kind="lifecycle_bulk",
        scope=[1134, 0],
        world_epoch="boot",
        operations=operations,
    )


class LifecycleBulkTests(unittest.TestCase):
    def test_malformed_last_or_duplicate_cannot_commit_first(self):
        malformed = envelope()
        malformed["operations"][-1]["draw"] = 2
        duplicate = envelope()
        duplicate["operations"][-1] = duplicate["operations"][0]
        for proposal in (malformed, duplicate):
            with self.subTest(proposal=proposal), patch.object(
                ecology_mobs, "apply"
            ) as commit, patch("wakfu_server.monster_maturation.validate_policy"):
                with self.assertRaises(ValueError):
                    ecology_mobs._apply_lifecycle_bulk(
                        None, None, None, None, proposal, world_epoch="boot"
                    )
                commit.assert_not_called()

    def test_deadline_preserves_first_atomic_result_and_skips_remaining(self):
        with patch.object(
            ecology_mobs, "apply", return_value=dict(status="applied")
        ) as commit, patch(
            "wakfu_server.monster_maturation.validate_policy"
        ), patch.object(
            ecology_mobs.time, "monotonic", side_effect=[0, 0, 0.026]
        ):
            result = ecology_mobs._apply_lifecycle_bulk(
                None, None, None, None, envelope(), world_epoch="boot"
            )
        self.assertEqual(commit.call_count, 1)
        self.assertEqual(result["operations"], [dict(status="applied")])
        self.assertEqual(result["skipped_operations"], 1)
        self.assertEqual(result["skip_reason"], "budget")
