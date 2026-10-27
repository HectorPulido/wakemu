"""Lifecycle bulk coalescing refreshes CAS state and retains its first draw."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import wakfu_server
from wakfu_server import monster_life_plans

spec = importlib.util.spec_from_file_location(
    "ecology_service_bulk_merge",
    Path(__file__).resolve().parents[1] / "ecology-service/service.py",
)
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def lifecycle_entry(*, x, y, draw):
    parent = dict(
        id=-8818,
        ref=88,
        team=1,
        x=x,
        y=y,
        z=60,
        ap=7,
        hp=153,
        max_hp=153,
        mp=3,
        wp=0,
        breed=88,
        level=22,
        map_id=527,
        instance_id=0,
        sprite_id=101500088,
        initiative=16,
        effective_level=22,
    )
    return dict(
        kind="maturation",
        scope=[527, 0],
        configuration={
            "interval_ms": 300000,
            "stage_decay": 0.5,
            "base_probability": 0.1,
            "boss_probability": 1e-05,
        },
        expected_members=[parent],
        draw=draw,
        plan={"draw": draw, "cycle": 18},
        grown={"id": -8818, "x": -1, "y": -168, "z": 60, "ref": 87},
        ticket=dict(
            map_id=527,
            instance_id=0,
            monster_id=-8818,
            group_id=881,
            reference=88,
            cycle=18,
            plan_incarnation="fixture-native-incarnation",
            decision={
                "draw": 0.1337787157356456,
                "cycle": 18,
                "attempts": 1,
                "group_draw": 0.9225139524098953,
                "variant_seed": "1152527292a2b3f5cba5b55f50e82597b6ca949460e152ab91e6137e2ad4f3c7",
                "destination_draw": 0.025525398700429247,
            },
        ),
    )


class EcologyServiceBulkMergeTests(unittest.TestCase):
    def test_stale_maturation_rebuilds_grown_from_fresh_parent_and_first_decision(self):
        original = lifecycle_entry(x=-1, y=-168, draw=0.1337787157356456)
        fresh = lifecycle_entry(x=-2, y=-170, draw=0.1337787157356456)
        candidates = [
            {"reference": 87, "min_level": 22},
            {"reference": 89, "min_level": 22},
        ]
        chosen = monster_life_plans.choose(candidates, original["ticket"]["decision"])
        factory_calls = []

        def choose_next(
            reference, configuration, *, draw, members, choose, source_level
        ):
            self.assertEqual(reference, 88)
            self.assertEqual(configuration, fresh["configuration"])
            self.assertEqual(draw, original["draw"])
            self.assertEqual(source_level, fresh["expected_members"][0]["level"])
            self.assertIn(
                members,
                (fresh["expected_members"], original["expected_members"]),
            )
            return choose(candidates)

        def owned_instance(reference, level, actor_id, **position):
            result = dict(
                id=actor_id,
                ref=reference,
                level=level,
                owner=actor_id,
                **position,
            )
            factory_calls.append(result)
            return result

        fake_maturation = SimpleNamespace(choose_next=choose_next)
        fake_monsters = ModuleType("wakfu_server.monsters")
        fake_monsters.owned_instance = owned_instance
        with patch.object(
            wakfu_server, "monster_maturation", fake_maturation, create=True
        ), patch.dict(sys.modules, {"wakfu_server.monsters": fake_monsters}):
            merged = service.merge_bulk_payload(
                dict(kind="lifecycle_bulk", scope=[527, 0], operations=[original]),
                dict(kind="lifecycle_bulk", scope=[527, 0], operations=[fresh]),
            )
            unchanged = service.refresh_stale_decision(original, original)

        entry = merged["operations"][0]
        self.assertEqual(entry["expected_members"], fresh["expected_members"])
        self.assertEqual(entry["draw"], original["draw"])
        self.assertEqual(entry["plan"], original["plan"])
        self.assertEqual(entry["ticket"]["cycle"], 18)
        self.assertEqual(entry["ticket"]["decision"], original["ticket"]["decision"])
        self.assertEqual(chosen["reference"], entry["grown"]["ref"])
        self.assertEqual(entry["grown"]["ref"], 87)
        self.assertEqual(entry["grown"]["id"], original["ticket"]["monster_id"])
        self.assertEqual(
            (entry["grown"]["x"], entry["grown"]["y"], entry["grown"]["z"]),
            (-2, -170, 60),
        )
        self.assertEqual(len(factory_calls), 2)
        self.assertEqual(unchanged["grown"]["x"], -1)


if __name__ == "__main__":
    unittest.main()
