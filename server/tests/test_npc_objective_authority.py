import unittest

from wakfu_server.npc_objective_facts import evaluate, load


class _Result:
    def __init__(self, value):
        self.value = value

    def fetchone(self):
        return self.value

    def fetchall(self):
        return self.value


class _Database:
    def __init__(self, *, owner=True, facts=(), snapshot=None):
        self.owner = owner
        self.facts = facts
        self.snapshot = snapshot

    def execute(self, sql, parameters):
        if "FROM characters " in sql:
            return _Result({"id": 1} if self.owner else None)
        if "FROM npc_objective_facts " in sql:
            return _Result(self.facts)
        if "FROM character_achievement_authority " in sql:
            return _Result(
                None if self.snapshot is None else {"snapshot": self.snapshot}
            )
        raise AssertionError(sql)


class NpcObjectiveAuthorityTest(unittest.TestCase):
    def test_owned_progress_controls_native_npc_criteria(self):
        # Both captured Rii actors and any other NPC using the same native
        # criterion observe the quest engine's authoritative completion.
        snapshot = {"running": [5154], "completed": [], "objectives": [10595, 10606]}
        db = _Database(
            facts=[{"objective_id": 10595, "completed": False}], snapshot=snapshot
        )
        facts = load(db, 2, 1)
        known = {10595, 10606, 10607}
        self.assertFalse(
            evaluate("not IsAchievementObjectiveComplete(10595)", {}, facts, known)
        )
        self.assertTrue(
            evaluate("IsAchievementObjectiveComplete(10606)", {}, facts, known)
        )
        self.assertTrue(
            evaluate("not IsAchievementObjectiveComplete(10607)", {}, facts, known)
        )

    def test_legacy_facts_and_uninitialized_authority_remain_supported(self):
        db = _Database(facts=[{"objective_id": 10607, "completed": True}])
        self.assertEqual(load(db, 2, 1), {10607: True})

    def test_rejects_foreign_owner_and_malformed_authority(self):
        with self.assertRaises(ValueError):
            load(_Database(owner=False), 2, 1)
        with self.assertRaises(ValueError):
            load(
                _Database(
                    snapshot={"running": [], "completed": [], "objectives": [True]}
                ),
                2,
                1,
            )


if __name__ == "__main__":
    unittest.main()
