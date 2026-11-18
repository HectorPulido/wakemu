"""Independent farming earns loot only from its actual original-enemy victory."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import owned_quest_pools as pools


class OwnedQuestPoolAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.members = [dict(id=-10, ref=2779)]
        self.proof = dict(
            fight_id=40,
            player_team=0,
            profile_sha256="frozen-profile",
            group_id=30,
            map_id=723,
            instance_id=20,
            route_key="wild-past",
            policy_version=2,
            members=self.members,
        )
        self.declaration = dict(
            quest_id=1677,
            unfinished_objective_id=3106,
            monsters=[dict(reference=2779, count=1)],
            item_reference=17851,
            stop_quantity=3,
            loot_contract="wild-native-2779-item-17851-v1",
        )
        self.found = dict(
            proof=self.proof,
            owner=dict(account_id=99),
            selected=dict(declaration=self.declaration),
        )
        self.fight = SimpleNamespace(
            id=40,
            phase="finished",
            winner=0,
            events=[dict(kind="death", actor_id=-10)],
            actors={
                -10: SimpleNamespace(hp=0, team=1, controlled=False),
                10: SimpleNamespace(hp=50, team=0, controlled=True, owner_id=99),
            },
            native_summon_registrations={},
        )
        self.earned = {}

    def scope(self):
        from contextlib import ExitStack

        stack = ExitStack()
        stack.enter_context(patch.object(pools, "bound_fight", return_value=self.found))
        stack.enter_context(
            patch.object(
                pools,
                "_read",
                side_effect=lambda db, owner, key: deepcopy(self.earned.get(key)),
            )
        )
        stack.enter_context(
            patch.object(
                pools,
                "_write",
                side_effect=lambda db, owner, key, value: self.earned.setdefault(
                    key, deepcopy(value)
                ),
            )
        )
        return stack

    def test_actual_victory_freezes_eligibility_for_recovery_without_rerolling(self):
        with self.scope(), patch.object(
            pools, "_eligible", return_value=True
        ) as eligible:
            first = pools.loot_basis(
                None, 40, 10, fight=self.fight, original_monsters=self.members
            )
            self.assertTrue(first["eligible"])
            eligible.assert_called_once()
            eligible.reset_mock()
            eligible.return_value = False  # The delivered third part can stop the pool.
            replay = pools.loot_basis(None, 40, 10)
            self.assertEqual(replay, first)
            eligible.assert_not_called()
        self.assertEqual(len(self.earned), 1)

    def test_missing_or_forged_victory_cannot_create_an_earned_receipt(self):
        for change in ("live_enemy", "no_death", "loss", "summon", "foreign_roster"):
            fight, originals = deepcopy(self.fight), deepcopy(self.members)
            if change == "live_enemy":
                fight.actors[-10].hp = 1
            elif change == "no_death":
                fight.events = []
            elif change == "loss":
                fight.winner = 1
            elif change == "summon":
                fight.native_summon_registrations = {-10: {}}
            else:
                originals[0]["ref"] = 2793
            with self.subTest(change=change), self.scope(), patch.object(
                pools, "_eligible"
            ) as eligible:
                with self.assertRaises(ValueError):
                    pools.loot_basis(
                        None, 40, 10, fight=fight, original_monsters=originals
                    )
                self.assertEqual(self.earned, {})
                eligible.assert_not_called()
        with self.scope(), self.assertRaises(ValueError):
            pools.loot_basis(
                None, 40, 10
            )  # Recovery without an earned battle is invalid.

    def test_real_pool_authority_builds_exact_native_drop_permission(self):
        from wakfu_server import combat_drops, native_quest_complex_loot

        native_row = dict(
            complex_criteria=True,
            conditions=[],
            is_loot_table=False,
            native_csE=-1,
            native_csF=0,
            probability=0.2,
            quantity_max=1,
            quantity_min=1,
            reference_id=17851,
            roll_count=-1,
        )
        with self.scope(), patch.object(
            pools, "_eligible", return_value=True
        ), patch.object(
            combat_drops,
            "native_drop_catalog",
            return_value={"monsters": {2779: [native_row]}},
        ):
            permission = native_quest_complex_loot.pool_permission(
                None, 40, 10, fight=self.fight, original_monsters=self.members
            )
            native_quest_complex_loot.validate_context(permission)
            self.assertEqual(permission["rows"][0]["item_reference"], 17851)
            self.assertEqual(permission["policy_version"], 2)
            self.assertEqual(native_row["probability"], 0.2)

    def test_authenticated_operator_victory_needs_no_fabricated_death_events(self):
        fight = deepcopy(self.fight)
        fight.events = [
            dict(
                kind="administrative_outcome",
                command="!winfight",
                account_id=99,
                character_id=10,
                winner=0,
            )
        ]
        # The command can set the opposing actor's HP to zero, but it does not
        # create a native death event or claim the original combat effect ran.
        fight.actors[-10].hp = 0
        with self.scope(), patch.object(
            pools, "_eligible", return_value=True
        ) as eligible:
            receipt = pools.loot_basis(
                None, 40, 10, fight=fight, original_monsters=self.members
            )
        self.assertTrue(receipt["eligible"])
        self.assertEqual(
            self.earned["owned-quest-pool:earned:40"]["victory_source"],
            "administrative_original_enemy_victory",
        )
        self.assertFalse(any(event.get("kind") == "death" for event in fight.events))
        eligible.assert_called_once()

        for changed in (
            dict(account_id=98),
            dict(character_id=11),
            dict(winner=1),
            dict(command="!teleport"),
            dict(kind="finished"),
        ):
            bad = deepcopy(fight)
            bad.events[0].update(changed)
            self.earned.clear()
            with self.subTest(changed=changed), self.scope(), patch.object(
                pools, "_eligible"
            ) as rejected:
                with self.assertRaises(ValueError):
                    pools.loot_basis(
                        None, 40, 10, fight=bad, original_monsters=self.members
                    )
                rejected.assert_not_called()
                self.assertEqual(self.earned, {})


if __name__ == "__main__":
    unittest.main()
