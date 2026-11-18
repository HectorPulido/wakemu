import unittest
import struct

from wakfu_server.maps.npc_objective_facts import definitions, evaluate
from wakfu_server.maps.npc_world import begin, spawn


class NativeObjectiveFactsTest(unittest.TestCase):
    def test_native_definitions_include_captured_tutorial_objectives(self):
        self.assertEqual(len(definitions()), 6029)
        self.assertTrue({10595, 10606, 10607} <= definitions())

    def test_known_initial_facts_and_explicit_completion(self):
        criterion = "not IsAchievementObjectiveComplete(10606)"
        self.assertTrue(evaluate(criterion, {}, {}))
        self.assertFalse(evaluate(criterion, {}, {10606: True}))
        self.assertTrue(
            evaluate("IsAchievementObjectiveComplete(10606)", {}, {10606: True})
        )

    def test_unknown_criteria_and_malformed_facts_fail_closed(self):
        for criterion in (
            "not IsAchievementObjectiveComplete(999999999)",
            "1 == 1",
            "GetRealLevel() >= 6",
            "",
        ):
            self.assertEqual(evaluate(criterion, {}, {}), criterion == "")
        self.assertFalse(
            evaluate("not IsAchievementObjectiveComplete(10606)", {}, {10606: 0})
        )

    def test_active_requires_owned_snapshot_and_rejects_foreign_load(self):
        from wakfu_server.maps import npc_objective_facts, dungeon_achievement_authority

        criterion = "IsAchievementActive(1109) && !IsAchievementComplete(1109)"
        authority = dungeon_achievement_authority.queries_from_snapshot(
            {"running": [1109], "completed": [], "objectives": []}
        )
        facts = npc_objective_facts.ObjectiveFacts(achievement_queries=authority)
        self.assertTrue(evaluate(criterion, {}, facts))
        self.assertFalse(evaluate("!IsAchievementActive(1109)", {}, {}))

        class ForeignConnection:
            def execute(self, sql, args):
                assert "account_id=%s AND id=%s" in sql
                assert args == (1, 2)
                return self

            def fetchone(self):
                return None

        with self.assertRaisesRegex(ValueError, "owned character"):
            npc_objective_facts.load(ForeignConnection(), 1, 2)

    def test_world_identity_is_not_private_instance(self):
        criterion = (
            "GetInstanceId() == 1385\r\nand not IsAchievementObjectiveComplete(10595)"
        )
        self.assertTrue(evaluate(criterion, {"map_id": 1385, "instance_id": 0}, {}))
        self.assertFalse(evaluate(criterion, {"map_id": 1388, "instance_id": 1385}, {}))

    def test_real_level_upper_bound_uses_owned_progression_level(self):
        criterion = "GetRealLevel() <= 30"
        self.assertTrue(evaluate(criterion, {"level": 30}, {}))
        self.assertFalse(evaluate(criterion, {"level": 31}, {}))
        self.assertFalse(evaluate(criterion, {"level": True}, {}))

    def test_three_native_initial_bindings_and_completion_revocation(self):
        bindings = (
            (-1706442046308322, 5461, 1385, -17, -4, 17, 3, 5765, 1243, 10595, 13275),
            (-1706442046308328, 5467, 1385, 12, 32, 1, 1, 5782, 1255, 10607, 13305),
            (-1706442046308339, 5460, 1388, 0, -19, 3, 3, 5755, 1390, 10606, 13258),
        )
        for (
            actor,
            ref,
            world,
            x,
            y,
            z,
            direction,
            root,
            action,
            objective,
            choice,
        ) in bindings:
            with self.subTest(reference=ref):
                row = dict(
                    actor_id=actor,
                    reference_id=ref,
                    map_id=world,
                    instance_id=0,
                    x=x,
                    y=y,
                    z=z,
                    direction=direction,
                    dialogue_root=root,
                    action_ids=[action],
                    interaction_range=4,
                    native_capture_id=actor,
                    native_publication_authorized=True,
                    enabled=True,
                )
                row["native_capture_contract"] = dict(
                    row, publication_authorized=True, source_sha256="e" * 64
                )
                character = dict(
                    id=100, account_id=200, map_id=world, instance_id=0, x=x, y=y, z=z
                )
                facts = {}
                self.assertEqual(spawn(row)[0], 12608)
                with self.assertRaises(ValueError):
                    begin(lambda: character, lambda: [row], actor, action)
                session, packet = begin(
                    lambda: character,
                    lambda: [row],
                    actor,
                    action,
                    facts_provider=lambda: facts,
                )
                self.assertEqual(packet, (12969, struct.pack(">ibq", root, 2, actor)))
                facts[objective] = True
                with self.assertRaises(ValueError):
                    session.choose(root, choice)
                with self.assertRaises(ValueError):
                    begin(
                        lambda: character,
                        lambda: [row],
                        actor,
                        action,
                        facts_provider=lambda: facts,
                    )


if __name__ == "__main__":
    unittest.main()
