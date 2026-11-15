"""World validates prepared seed births; native selection contracts live in Rust."""

import copy
import unittest
from unittest.mock import Mock

from wakfu_server import ecology_plants, planting
from wakfu_server.monsters import owned_instance


def prepared_birth():
    """Explicit native Wodent fixture, without a Python selection algorithm."""
    resource = dict(
        resource_uid=101,
        map_id=1,
        instance_id=0,
        x=0,
        y=0,
        z=0,
        resource_reference=823,
        stage=1,
        creation_time=0,
    )
    return dict(
        kind="resource_growth",
        world_epoch="seed-admission",
        expected=resource,
        transition=None,
        member=owned_instance(5525, 1, -1234, map_id=1, x=0, y=0, z=0),
    )


def runtime():
    result = Mock(ecology_world_epoch="seed-admission", growth_seconds=30)
    result.store.clock.return_value = 1000
    result.apply_growth_candidates.return_value = dict(
        applied=[101], capacity_skipped=[]
    )
    result.publish_growth.return_value = [dict(resource_uid=101)]
    return result


class WorldSeedAdmissionTests(unittest.TestCase):
    def test_world_admits_exact_prepared_native_child_without_selecting_again(self):
        proposal = prepared_birth()
        self.assertIn(1113, planting.RESOURCES[823]["monster_family_ids"])
        actor = runtime()
        outcome = ecology_plants.apply(
            actor, object(), proposal, authorize_spawn=lambda _: True, publish=Mock()
        )
        self.assertTrue(outcome["applied"])
        self.assertEqual(
            actor.apply_growth_candidates.call_args.kwargs["prepared_members"],
            {101: proposal["member"]},
        )

    def test_foreign_family_child_is_rejected_before_durable_mutation(self):
        proposal = prepared_birth()
        proposal["member"]["ref"] = proposal["member"]["breed"] = 6
        actor = runtime()
        with self.assertRaisesRegex(ValueError, "family differs"):
            ecology_plants.apply(
                actor,
                object(),
                proposal,
                authorize_spawn=lambda _: True,
                publish=Mock(),
            )
        actor.apply_growth_candidates.assert_not_called()
        actor.publish_growth.assert_not_called()

    def test_malformed_native_child_is_not_downgraded_to_unavailable_or_stale(self):
        original = prepared_birth()
        proposal = copy.deepcopy(original)
        proposal["member"]["level"] = 0
        actor = runtime()
        with self.assertRaises(ValueError):
            ecology_plants.apply(
                actor,
                object(),
                proposal,
                authorize_spawn=lambda _: True,
                publish=Mock(),
            )
        actor.apply_growth_candidates.assert_not_called()
        actor.publish_growth.assert_not_called()
        self.assertEqual(original["member"]["level"], 1)
