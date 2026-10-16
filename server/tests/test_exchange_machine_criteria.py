"""Owned exchange predicates preserve native membership, timing and unknowns."""
from types import SimpleNamespace
import unittest
from wakfu_server.characters.cosmetics import OwnedCosmetics
from wakfu_server.exchange_machine_criteria import evaluate


class Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Database:
    def __init__(self):
        self.cosmetics = OwnedCosmetics(
            9, ((3, 20820, 0, 0), (16, 20834, 0, 0))
        ).to_record()
        self.guild_id = 12
        self.bonuses = {}
        self.achievement = None

    def execute(self, query, parameters=None):
        if "to_regclass('account_cosmetics')" in query:
            return Cursor(dict(relation="account_cosmetics"))
        if "FROM account_cosmetics" in query:
            return Cursor(dict(record=self.cosmetics))
        if "FROM guild_members" in query:
            return Cursor(None if self.guild_id is None else dict(id=self.guild_id))
        if "FROM guild_service_state" in query:
            return Cursor(dict(record=dict(bonuses=self.bonuses)))
        if "FROM character_achievement_authority" in query:
            return Cursor(
                None if self.achievement is None else dict(snapshot=self.achievement)
            )
        raise AssertionError(query)


class ExchangeMachineCriteriaTests(unittest.TestCase):
    def setUp(self):
        self.db = Database()
        self.store = SimpleNamespace(clock=lambda: 1000)
        self.character = dict(id=7, account_id=9, level=100, nation_id=30)

    def check(self, expression):
        return evaluate(self.db, self.store, self.character, expression)

    def test_cosmetic_ownership_not_equipped_and_accessory_excluded(self):
        self.assertTrue(self.check("HasCosmeticId(20820) and GetRealLevel() >= 100"))
        self.assertFalse(self.check("HasCosmeticId(20834)"))
        self.assertFalse(self.check("HasCosmeticId(99999)"))

    def test_guild_bonus_requires_defined_completed_activation(self):
        self.db.bonuses["10"] = dict(active=False, purchased_at_ms=1, learned_at_ms=2)
        self.assertFalse(self.check("HasGuildBonus(10)"))
        self.db.bonuses["10"] = dict(active=True, activated_at_ms=1000001)
        self.assertFalse(self.check("HasGuildBonus(10)"))
        self.db.bonuses["10"]["activated_at_ms"] = 1000000
        self.assertTrue(self.check("HasGuildBonus(10)"))
        self.db.guild_id = None
        self.assertFalse(self.check("HasGuildBonus(10)"))

    def test_missing_ordinary_systems_remain_unknown_despite_client_fields(self):
        self.character.update(crime_score=10000, company_rank=10, pvp_rank=10)
        for expression in (
            "GetCrimeScore(30) >= 10000",
            "GetCompanyRank() >= 2",
            "HasPvpRank(1)",
        ):
            with self.subTest(expression=expression), self.assertRaisesRegex(
                ValueError, "Missing native exchange predicate authority"
            ):
                self.check(expression)
        with self.assertRaises(ValueError):
            self.check("IsAdmin()")

    def test_nation_and_annotations_reuse_authoritative_values(self):
        self.assertTrue(
            self.check('@("owned") HasCosmeticId(20820)@ and GetNationId() == 30')
        )
        self.assertFalse(self.check("GetNationId() == 31"))
        del self.character["nation_id"]
        with self.assertRaisesRegex(ValueError, "nation authority"):
            self.check("GetNationId() == 0")

    def test_malformed_predicate_and_activation_are_not_false_defaults(self):
        for expression in (
            "HasCosmeticId()",
            "HasGuildBonus(True)",
            "HasCosmeticId(-1)",
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                self.check(expression)
        self.db.bonuses["10"] = dict(active=True)
        with self.assertRaisesRegex(ValueError, "activation date"):
            self.check("HasGuildBonus(10)")

    def test_existing_achievement_snapshot_is_preserved_with_new_predicates(self):
        self.db.achievement = dict(running=[], completed=[1], objectives=[])
        self.assertTrue(self.check("HasCosmeticId(20820) and IsAchievementComplete(1)"))
        self.assertFalse(
            self.check("HasCosmeticId(20820) and IsAchievementComplete(2)")
        )
        self.db.achievement = None
        with self.assertRaisesRegex(ValueError, "achievement authority"):
            self.check("IsAchievementComplete(1)")
