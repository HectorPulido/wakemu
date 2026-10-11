import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from wakfu_server import dungeon_instances, dungeon_difficulty
from wakfu_server.maps import dungeon_context


class _ContextStore:
    @contextmanager
    def connection(self):
        class Cursor:
            def fetchone(self):
                return {
                    "context_route_key": "dynamic_dungeon_route",
                    "context_policy_version": 7,
                    "definition_id": 90,
                }

        class Connection:
            def execute(self, _query, _parameters):
                return Cursor()

        yield Connection()


class DungeonContextPolicyTests(unittest.TestCase):
    def setUp(self):
        self.route = dungeon_instances.route("jalato_normal")
        self.row = {
            "route_key": self.route.key,
            "policy_version": 1,
            "template_id": self.route.template_id,
            "definition_id": self.route.definition_id,
            "max_level": 0,
            "min_level": 0,
            "difficulty_level": 2,
            "is_difficulty_available": False,
            "can_increase_difficulty": True,
            "is_competitive_cancelled": False,
            "allowed_ids": [987654321],
            "provenance": "synthetic unit-test context; not native Jalató policy",
        }

    def test_explicit_policy_does_not_derive_allow_ids_from_party(self):
        policy = dungeon_context._policy(self.row, self.route)
        context = policy.proto_context(fight_in_progress=True)
        self.assertEqual(context["allowed_ids"], (987654321,))
        self.assertTrue(context["is_fight_in_progress"])
        self.assertEqual(
            set(context),
            {
                "max_level",
                "min_level",
                "difficulty_level",
                "is_difficulty_available",
                "can_increase_difficulty",
                "is_fight_in_progress",
                "is_competitive_cancelled",
                "allowed_ids",
            },
        )

    def test_missing_policy_and_runtime_fight_state_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "not configured"):
            dungeon_context._policy(None, self.route)
        policy = dungeon_context._policy(self.row, self.route)
        with self.assertRaisesRegex(ValueError, "fight state is required"):
            policy.proto_context(fight_in_progress=None)

    def test_policy_must_match_native_route_and_bounds(self):
        wrong_route = dict(self.row, template_id=199)
        with self.assertRaisesRegex(ValueError, "does not match"):
            dungeon_context._policy(wrong_route, self.route)
        for key, value in (
            ("difficulty_level", 0),
            ("max_level", -1),
            ("allowed_ids", [1, True]),
            ("provenance", "  "),
        ):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    dungeon_context._policy(dict(self.row, **{key: value}), self.route)

    def test_instance_context_resolves_route_from_canonical_dynamic_registry(self):
        route = object()
        policy = Mock()
        policy.proto_context.return_value = {"is_fight_in_progress": True}
        with (
            patch.object(dungeon_instances, "route", return_value=route) as resolve,
            patch.object(
                dungeon_difficulty,
                "selection",
                return_value={"stasis_level": 5, "competitive_max_level": 20},
            ),
            patch.object(
                dungeon_difficulty,
                "definition",
                return_value={"difficulty_available": True},
            ),
            patch.object(
                dungeon_context, "policy_version", return_value=policy
            ) as version,
        ):
            result = dungeon_context.for_instance(
                _ContextStore(), 1234, fight_in_progress=True
            )
        self.assertIs(dungeon_context.dungeon_instances, dungeon_instances)
        resolve.assert_called_once_with("dynamic_dungeon_route")
        version.assert_called_once_with(unittest.mock.ANY, route, 7)
        self.assertEqual(
            result,
            {
                "is_fight_in_progress": True,
                "difficulty_level": 5,
                "max_level": 20,
                "is_difficulty_available": True,
                "can_increase_difficulty": False,
            },
        )


if __name__ == "__main__":
    unittest.main()
