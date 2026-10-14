"""Timer waits stay deferred; occupied execution is reported per resource."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from wakfu_server import ecology_plants, planting
from wakfu_server.ecology.protocol import proposal
import test_ecology_priority


class EcologyGrowthDeferralTests(unittest.TestCase):
    def test_only_known_plant_growth_wait_reasons_are_admitted(self):
        fixture = test_ecology_priority.EcologyPriorityTests()
        for domain, kind, reason, expected in (
            ("plants", "resource_growth", "occupied", "deferred"),
            ("plants", "resource_growth", "not_due", "deferred"),
            ("plants", "resource_growth", "capacity", "deferred"),
            ("plants", "resource_growth_bulk", "occupied", "deferred"),
            ("plants", "resource_growth_bulk", "not_due", "deferred"),
            ("plants", "resource_growth_bulk", "capacity", "deferred"),
            ("plants", "resource_growth_bulk", "unknown", "retry"),
            ("mobs", "resource_growth", "occupied", "retry"),
            ("plants", "planting_begin", "occupied", "retry"),
            ("plants", "resource_growth", "unknown", "retry"),
        ):
            with self.subTest(domain=domain, kind=kind, reason=reason):
                bridge = fixture.bridge()
                bridge.handlers[domain] = lambda _: dict(
                    status="deferred", reason=reason
                )
                row = proposal(
                    domain, {"kind": kind, "world_epoch": bridge.epoch}, bridge.epoch
                )
                self.assertEqual(fixture.apply(bridge, [row])[0]["status"], expected)

    def test_seed_occupied_seed_not_due_and_flora_not_due_do_not_mutate(self):
        resource = dict(
            resource_uid=1,
            map_id=1134,
            instance_id=0,
            x=1,
            y=2,
            z=0,
            resource_reference=999,
            stage=1,
            creation_time=0,
        )
        runtime = Mock()
        runtime.ecology_world_epoch = "boot"
        runtime.store.clock.return_value = 1000
        runtime.growth_seconds = 60
        for monster, allowed, reason in (
            (True, False, "occupied"),
            (True, True, "not_due"),
            (False, True, "not_due"),
        ):
            with self.subTest(monster=monster, allowed=allowed):
                resource["creation_time"] = 0 if reason == "occupied" else 1000000
                definition = dict(monster_resource=monster, stages={1: {}, 2: {}})
                plan = dict(
                    kind="resource_growth",
                    world_epoch="boot",
                    expected=resource,
                    transition=None if monster else [2, 60000, 1.0],
                )
                with patch.dict(planting.RESOURCES, {999: definition}):
                    result = ecology_plants.apply(
                        runtime,
                        object(),
                        plan,
                        authorize_spawn=lambda _: allowed,
                        publish=lambda _: None,
                    )
                self.assertEqual(result["status"], "deferred")
                self.assertEqual(result["reason"], reason)
                self.assertEqual(
                    result.get("resource_failures", []),
                    [1] if reason == "occupied" else [],
                )
        runtime.apply_growth_candidates.assert_not_called()
        runtime.publish_growth.assert_not_called()
