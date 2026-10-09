import struct
import unittest
from unittest.mock import patch
from test_combat_spell_transaction import SpellTransactionTests
from wakfu_server.combat_cast import prepare_spell_cast
from wakfu_server.combat_spell_grant import NativeSpellGrantHandler, remove_spell_grant
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_spells import spell_wire
from wakfu_server.spells import encode_deck
from wakfu_server.combat_native_spell_casting import catalog


@patch.dict("os.environ", {"WAKFU_NATIVE_GRANTED_CAST": "1"})
class GrantedCastTests(unittest.TestCase):
    def test_grant_cast_and_removal_use_real_registry_and_native_uid(self):
        fixture = SpellTransactionTests()
        fixture.setUp()
        fight = fixture.fight
        handler = NativeSpellGrantHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: 901,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
        )
        handler(
            {
                "effect_class": 649,
                "parameters": [2.0, 0.0, 0.0, 0.0, 6266.0, 0.0, 1.0, 0.0],
            },
            [],
            EffectInvocation(313107, 1, 7, 7, (0, 0, 0)),
        )
        body = struct.pack(">qqiih", 7, 6266, 1, 0, 0)
        kwargs = dict(
            wp=6,
            line_of_sight=lambda *args: True,
            conditional_context=fixture.cast_authority(deck=()),
        )
        plan = prepare_spell_cast(
            body, fixture.character, fight, 3, encode_deck([], []), **kwargs
        )
        self.assertEqual(plan["spell_uid"], 6266)
        self.assertEqual(plan["evaluation_level"], 1)
        self.assertEqual(plan["effect_ids"], tuple(catalog()["6266"]["levels"][0][2]))
        self.assertEqual(
            struct.unpack(
                ">qih",
                spell_wire(
                    fixture.character,
                    6266,
                    native_uid=plan["spell_uid"],
                    native_level=plan["evaluation_level"],
                ),
            ),
            (6266, 6266, 1),
        )
        remove_spell_grant(handler, 901)
        with self.assertRaisesRegex(ValueError, "expired grant"):
            prepare_spell_cast(
                body, fixture.character, fight, 3, encode_deck([], []), **kwargs
            )

    def test_native_level_not_clamped_to_actor_level(self):
        from wakfu_server.combat_native_spell_casting import definition

        self.assertEqual(len(catalog()["5624"]["levels"]), 1)
        with self.assertRaises(ValueError):
            definition(5624, 2, None, {})

    def test_native_grant_full_dispatch_cast_wire_and_retirement(self):
        import random
        from wakfu_server.combat_server_spell import (
            server_runtime,
            prepare_server_spell,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_retained_runtime import remove_owned_stat
        from wakfu_server.fight_checkpoint_store import snapshot

        fixture = SpellTransactionTests()
        fixture.setUp()
        character, monster, fight = fixture.native_server_fixture(5, 20)
        factory, _ = server_runtime(
            character,
            {-7: monster},
            encode_deck([], []),
            action_id=1,
            critical=False,
            rng=random.Random(1),
        )
        # Native child313108 of state6755: the packed fyW container and level1
        # are explicit; this verifies dispatch/casting, not delivery of event1028.
        dispatcher, packets = factory(
            fight,
            dict(
                native_retained_container=dict(
                    present=True,
                    type=3,
                    id=(6755 << 16) + 1,
                    is_spell=False,
                    protected=None,
                )
            ),
        )
        dispatcher.execute(EffectInvocation(313108, 1, 7, 7, (0, 0, 0)))
        self.assertEqual(fight.native_spell_grants[7][3909]["level"], 20)
        grant_uid = next(
            uid
            for uid, row in fight.owned_stat_effects.items()
            if row["effect_class"] == 649
        )
        before = snapshot(fight)
        body = struct.pack(">qqiih", 7, 3909, 0, 0, 0)
        tx = prepare_server_spell(
            body,
            character,
            {-7: monster},
            fight,
            3,
            encode_deck([], []),
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.assertTrue(tx.outcomes)
        self.assertTrue(
            any(row["family"] == "eWN" for row in tx.fight.owned_stat_effects.values())
        )
        self.assertEqual(snapshot(fight), before)
        wire = next(payload for opcode, payload in tx.packets if opcode == 12588)
        self.assertEqual(struct.unpack_from(">qih", wire, 20), (3909, 3909, 20))
        remove_owned_stat(dispatcher.native_retention.stat_handler, grant_uid)
        with self.assertRaisesRegex(ValueError, "expired grant"):
            prepare_server_spell(
                body,
                character,
                {-7: monster},
                fight,
                3,
                encode_deck([], []),
                action_id=3,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=random.Random(1),
            )

    def test_native_constructor_clamps_granted_level_before_cast(self):
        fixture = SpellTransactionTests()
        fixture.setUp()
        fight = fixture.fight
        fight.actors[7].effective_level = 200
        handler = NativeSpellGrantHandler(
            fight,
            [],
            action_id=1,
            allocate_uid=lambda: 901,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
        )
        handler(
            {
                "effect_class": 649,
                "parameters": [2.0, 0.0, 0.0, 0.0, 5345.0, 0.0, -1.0, 0.0],
            },
            [],
            EffectInvocation(313107, 1, 7, 7, (0, 0, 0)),
        )
        self.assertEqual(fight.native_spell_grants[7][5345]["level"], 1)

    def test_exported_roots_match_class_catalog_and_extras_are_merged(self):
        from wakfu_server.spell_audit import catalog as classes
        from wakfu_server.combat_server_spell import compiled_runtime_catalog

        self.assertEqual(
            catalog()["6266"]["levels"][0][2],
            classes()["spells"]["6266"]["levels"][0][2],
        )
        self.assertTrue(catalog()["5345"]["levels"][0][2])
        self.assertIn("313166", compiled_runtime_catalog().effects)
