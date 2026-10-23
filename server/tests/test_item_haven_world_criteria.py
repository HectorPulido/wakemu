"""Signed item world predicates require the owned SQL world projection."""
import unittest

from wakfu_server import simple_item_actions as actions
from wakfu_server.guild_haven_world import project_character
from wakfu_server.random_item_criteria import evaluate as random_criterion
from wakfu_server.consumable_criteria import evaluate as consumable_criterion


class _BindingDB:
    def execute(self, _query, _params):
        row = dict(guild_id=8, native_world_id=-8, name="Owned World", blazon=0)
        return type("Result", (), {"fetchone": staticmethod(lambda: row)})()


class ItemWorldCriterionTests(unittest.TestCase):
    def owned(self):
        return project_character(
            _BindingDB(),
            dict(id=7, account_id=3, map_id=2000000008, instance_id=700008),
        )

    def test_ordinary_map_and_live_positive_override_keep_their_contract(self):
        self.assertEqual(actions.criterion_world_identity(dict(map_id=527)), 527)
        self.assertEqual(actions.criterion_world_identity(dict(map_id=527), 723), 723)
        self.assertEqual(actions.criterion_world_identity({}, 723), 723)
        self.assertTrue(
            actions._criterion(
                None, None, 3, dict(map_id=527), "GetInstanceId() == 723", 723
            )
        )
        from wakfu_server.native_world_context import battleground_worlds

        battle_map = next(iter(battleground_worlds()))
        self.assertTrue(
            consumable_criterion("IsBattleground()", {}, native_map_id=battle_map)
        )

    def test_signed_world_uses_proved_identity_not_terrain_or_private_instance(self):
        actor = self.owned()
        for value in (None, actor["map_id"], -8):
            self.assertEqual(actions.criterion_world_identity(actor, value), -8)
            self.assertTrue(
                actions._criterion(None, None, 3, actor, "GetInstanceId() < 0", value)
            )
        # Positive server-scene overrides also cover virtual Haven Bag views.
        self.assertEqual(actions.criterion_world_identity(actor, 527), 527)
        self.assertTrue(
            random_criterion(
                "GetInstanceId() < 0", actor, native_map_id=-8, is_neo_server=False
            )
        )
        self.assertTrue(
            consumable_criterion("not IsBattleground()", actor, native_map_id=-8)
        )

    def test_negative_overrides_and_forged_or_stale_private_contexts_reject(self):
        forged = dict(map_id=2000000008, instance_id=700008, native_world_id=-8)
        actual = self.owned()
        for actor, value in (
            (dict(map_id=527), -8),
            (forged, -8),
            (forged, 527),
            (dict(actual, instance_id=700009), -8),
            (dict(actual, map_id=527), -8),
            (actual, -9),
            (actual, True),
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                actions.criterion_world_identity(actor, value)
        with self.assertRaises(ValueError):
            random_criterion(
                "GetInstanceId() < 0",
                dict(map_id=527),
                native_map_id=-8,
                is_neo_server=False,
            )
        with self.assertRaises(ValueError):
            consumable_criterion(
                "not IsBattleground()", dict(map_id=527), native_map_id=-8
            )


class ItemWorldCriterionPostgresTests(unittest.TestCase):
    def test_owned_actual_sql_world_hydrates_signed_item_context_across_reconnect(self):
        import test_haven_world_bombs_postgres as world_fixture

        # Use the complete real guild/world authority fixture without inheriting
        # or importing its TestCase into module discovery.
        helper = world_fixture.HavenWorldBombsPostgresTests("runTest")
        self.addCleanup(helper.doCleanups)
        helper.setUp()
        actor = helper.store.character(
            helper.owner["account"], helper.owner["character"]
        )
        self.assertEqual(
            actions.criterion_world_identity(actor, actor["map_id"]), -helper.guild_id
        )
        self.assertTrue(
            actions._criterion(
                None,
                None,
                helper.owner["account"],
                actor,
                "GetInstanceId() < 0",
                -helper.guild_id,
            )
        )
        self.assertFalse(
            actions._criterion(
                None,
                None,
                helper.owner["account"],
                actor,
                "GetInstanceId() > 0",
                actor["map_id"],
            )
        )
        reopened = helper.reopen().character(
            helper.owner["account"], helper.owner["character"]
        )
        self.assertEqual(actions.criterion_world_identity(reopened), -helper.guild_id)
        forged = dict(reopened)
        forged.pop("_native_haven_world_position")
        with self.assertRaises(ValueError):
            actions.criterion_world_identity(forged, -helper.guild_id)
