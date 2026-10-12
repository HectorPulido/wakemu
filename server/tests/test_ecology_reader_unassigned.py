"""Known unassigned terrain must not poison unrelated affinity reads."""
import unittest
from unittest.mock import patch

from wakfu_server import flora_ecology, monster_harvest_ecology
from wakfu_server.planting import RESOURCES


class EcologyReaderUnassignedTests(unittest.TestCase):
    class DB:
        def execute(self, sql, parameters):
            if "pg_advisory_xact_lock" in sql:
                return []
            if "planted_resources" in sql:
                return [
                    dict(resource_uid=x + 1, resource_reference=60, x=x, y=0, z=0)
                    for x in (0, 1)
                ]
            return [
                {
                    "members": [
                        dict(id=-1, ref=6, x=0, y=0, z=0),
                        dict(id=-2, ref=6, x=1, y=0, z=0),
                    ]
                }
            ]

    @staticmethod
    def locate(map_id, x, y, z):
        return {"region_id": -1 if x == 1 else 79001}

    def test_flora_counts_known_region_and_ignores_unassigned_resource(self):
        resource = dict(
            resource_uid=1,
            resource_reference=60,
            map_id=1134,
            instance_id=0,
            x=0,
            y=0,
            z=0,
        )
        with patch.object(
            flora_ecology, "surface", side_effect=self.locate
        ), patch.object(
            flora_ecology, "decision", return_value={"evidence": {}}
        ) as decision, patch.object(
            flora_ecology,
            "apply",
            return_value={"packet": (1, b""), "duplicate": True, "receipt": {}},
        ):
            result = flora_ecology.change(
                self.DB(), 1, resource, operation="test", action="remove"
            )
        self.assertEqual(result["reason"], "applied")
        self.assertEqual(decision.call_args.kwargs["before"], 1)
        self.assertEqual(
            decision.call_args.kwargs["family_id"], RESOURCES[60]["family_id"]
        )

    def test_flora_target_unassigned_or_unknown_never_creates_affinity(self):
        resource = dict(
            resource_uid=1,
            resource_reference=60,
            map_id=1134,
            instance_id=0,
            x=1,
            y=0,
            z=0,
        )
        with patch.object(
            flora_ecology, "surface", side_effect=self.locate
        ), patch.object(flora_ecology, "decision") as decision, patch.object(
            flora_ecology, "apply"
        ) as apply:
            result = flora_ecology.change(
                self.DB(), 1, resource, operation="test", action="remove"
            )
        self.assertEqual(result["reason"], "native_unassigned_terrain")
        decision.assert_not_called()
        apply.assert_not_called()
        with patch.object(
            flora_ecology, "surface", side_effect=ValueError("unknown height")
        ), patch.object(flora_ecology, "decision") as decision:
            result = flora_ecology.change(
                self.DB(), 1, resource, operation="test", action="remove"
            )
        self.assertEqual(result["reason"], "native_region_unavailable")
        decision.assert_not_called()

    def test_harvest_counts_known_region_and_unassigned_target_has_no_receipt(self):
        monster = dict(id=-1, ref=6, map_id=1134, instance_id=0, x=0, y=0, z=0)
        with patch.object(
            monster_harvest_ecology, "decision", return_value={"evidence": {}}
        ) as decision, patch.object(
            monster_harvest_ecology, "apply", return_value={"duplicate": True}
        ) as apply:
            result = monster_harvest_ecology.change(
                self.DB(), 1, monster, operation="test", locate=self.locate
            )
            self.assertEqual(result, [])
            self.assertEqual(decision.call_args.kwargs["before"], 1)
            decision.reset_mock()
            apply.reset_mock()
            monster["x"] = 1
            monster_harvest_ecology.change(
                self.DB(), 1, monster, operation="test", locate=self.locate
            )
            decision.assert_not_called()
            apply.assert_not_called()

    def test_unrelated_unknown_height_still_blocks_flora_and_monster_harvest(self):
        def locate(map_id, x, y, z):
            if x == 1:
                raise ValueError("unknown native height")
            return {"region_id": 79001}

        resource = dict(
            resource_uid=1,
            resource_reference=60,
            map_id=1134,
            instance_id=0,
            x=0,
            y=0,
            z=0,
        )
        with patch.object(flora_ecology, "surface", side_effect=locate), patch.object(
            flora_ecology, "decision"
        ) as decision:
            result = flora_ecology.change(
                self.DB(), 1, resource, operation="test", action="remove"
            )
        self.assertEqual(result["reason"], "incomplete_native_population")
        decision.assert_not_called()
        monster = dict(id=-1, ref=6, map_id=1134, instance_id=0, x=0, y=0, z=0)
        with patch.object(monster_harvest_ecology, "decision") as decision:
            monster_harvest_ecology.change(
                self.DB(), 1, monster, operation="test", locate=locate
            )
        decision.assert_not_called()
