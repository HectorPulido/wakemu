"""Native cast gate for the account-quest common spell scroll."""

import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server import native_catalog
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.spells import encode_deck


class CommonSpellNativeCastTests(unittest.TestCase):
    def setUp(self):
        original_load = native_catalog.load
        common_files = {
            "native-common-spell-effect-trees.json",
            "native-common-spell-casting-roots.json",
        }

        def load_qualified(path):
            path = Path(path)
            if path.name in common_files:
                return json.loads(path.read_text())
            return original_load(path)

        patcher = patch.object(native_catalog, "load", side_effect=load_qualified)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _cast(self):
        import random
        from test_combat_spell_transaction import SpellTransactionTests

        fixture = SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(
            3, 130, native_qi=True, target_distance=2
        )
        # Native GetItemQuantity reads the account quest inventory, not a bag
        # stack. This is the real ownership shape hydrated by Store.character.
        character["account_quest_items"] = [
            {"account_id": character["account_id"], "reference": 26347, "quantity": 1}
        ]
        spell_uid = (character["id"] << 32) | 5623
        deck = encode_deck([5623])
        result = prepare_server_spell(
            struct.pack(
                ">qqiih", character["id"], spell_uid, *fight.actors[-7].position
            ),
            character,
            {-7: monster},
            fight,
            character["account_id"],
            deck,
            action_id=1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        return fight, result

    def test_owned_common_spell_casts_with_native_base_cost(self):
        baseline_fight, baseline = self._cast()
        self.assertEqual(7, baseline.plan["actor_id"])
        self.assertEqual(4, baseline.fight.actors[7].ap)
        self.assertEqual(3, baseline.fight.actors[7].mp)
        self.assertTrue(baseline.outcomes)
        self.assertEqual(6, baseline_fight.actors[7].ap)

    def test_real_enutrof_state_702_selects_native_common_spell_mp_cost(self):
        import random
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_start,
        )
        from wakfu_server.combat_spell_grant import granted_spells

        fixture = SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(
            3,
            200,
            native_qi=True,
            full_health=True,
            target_hp=20000,
            target_distance=3,
            variation_seed=17,
        )
        character["account_quest_items"] = [
            {
                "account_id": character["account_id"],
                "reference": 26347,
                "quantity": 1,
            }
        ]
        # 2038 is a native granted action, not a deck spell. Keep the three
        # Enutrof actives and add the owned common spell plus native passive.
        deck = encode_deck((2008, 2014, 2018, 5623), (8274,))
        rng = random.Random(7)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            character["account_id"],
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        fight, _ = prepare_server_turn_start(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=fight.current.id,
            action_id=2,
            rng=rng,
            area_callbacks=True,
        )
        self.assertEqual(7, fight.current.id)
        native_uid = granted_spells(fight, 7).get(2038, {}).get("uid", (7 << 32) | 2038)
        installed = prepare_server_spell(
            struct.pack(">qqiih", 7, native_uid, *fight.actors[7].position),
            character,
            {-7: monster},
            fight,
            character["account_id"],
            deck,
            action_id=3,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertTrue(
            any(
                entry.reference == 702
                for entry in installed.fight.actors[7].state_ledger.entries
            )
        )
        before = (installed.fight.actors[7].ap, installed.fight.actors[7].mp)
        spell_uid = (7 << 32) | 5623
        cast = prepare_server_spell(
            struct.pack(">qqiih", 7, spell_uid, *installed.fight.actors[-7].position),
            character,
            {-7: monster},
            installed.fight,
            character["account_id"],
            deck,
            action_id=4,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertEqual(before[0], cast.fight.actors[7].ap)
        self.assertEqual(before[1] - 2, cast.fight.actors[7].mp)
        self.assertTrue(cast.outcomes)

    def test_native_702_cost_branches_use_owned_quantity_and_deck_conditions(self):
        from wakfu_server.combat_conditional_costs import resolve_costs
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext

        for present, passive in ((False, False), (True, False), (True, True)):
            with self.subTest(state702=present, passive8274=passive):
                context = ConditionContext(
                    {
                        "caster": ConditionActor(
                            state_ids=frozenset({702} if present else ()),
                            deck_spell_ids=frozenset(
                                {5623, 8274} if passive else {5623}
                            ),
                            excluded_deck_spell_ids=frozenset(),
                            is_player=True,
                            effective_level=130,
                            real_level=130,
                        )
                    },
                    item_quantity_query=lambda refs: int(26347 in refs),
                )
                costs = resolve_costs(
                    5623, 130, dict(ap=2, mp=0, wp=0, conditional_rules=2), context
                )
                self.assertEqual(
                    (costs["ap"], costs["mp"], costs["wp"]),
                    (0, 2, 0) if present else (2, 0, 0),
                )
                self.assertEqual(costs["matched_rules"], int(present))


if __name__ == "__main__":
    unittest.main()
