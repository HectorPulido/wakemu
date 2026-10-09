import os, random, struct, unittest
from unittest.mock import patch
import test_combat_spell_transaction as fixture_module
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    server_runtime,
)
from wakfu_server.spells import encode_deck
from wakfu_server.combat_area_transaction import prepare_area_event
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_state_managers import state_manager, state_managers


@patch.dict(os.environ, {"WAKFU_NATIVE_GRANTED_CAST": "1"})
class NativeAreaEntryTests(unittest.TestCase):
    def setUp(self):
        policy = patch.dict(os.environ)
        policy.start()
        self.addCleanup(policy.stop)
        # Exercise the actual default producer, without an opt-in override.
        os.environ.pop("WAKFU_NATIVE_AREA_CALLBACKS", None)

    def test_real_feca_glyph_creation_and_turn_boundary_with_class_initialization(self):
        for level, damage in ((1, 5), (200, 145)):
            with self.subTest(level=level):
                (
                    character,
                    monster,
                    fight,
                ) = fixture_module.SpellTransactionTests().native_server_fixture(
                    1, level, native_qi=True
                )
                deck = encode_deck([6967], [])
                fight, _ = prepare_server_initialization(
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=1,
                    rng=random.Random(1),
                    fight_start=True,
                )
                before = snapshot(fight)
                tx = prepare_server_spell(
                    # Map1134 publishes (-5,-7) as surface(z=-1,index=0).
                    # Native6967 needs range2..3 and no LOS; its cross at
                    # distance3 includes the NPC on adjacent(-6,-7,-1).
                    struct.pack(">qqiih", 7, (7 << 32) | 6967, -5, -7, -1),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=2,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(1),
                )
                self.assertEqual(snapshot(fight), before)
                self.assertEqual(tx.fight.actors[-7].hp, 200)
                self.assertEqual(tx.fight.actors[7].ap, fight.actors[7].ap - 5)
                self.assertIsNone(tx.fight.native_active_spell_id)
                self.assertEqual(set(tx.fight.actors), {7, -7})
                self.assertEqual(
                    {row["reference"] for row in tx.fight.native_effect_areas.values()},
                    {1474, 1477},
                )
                for uid, row in tx.fight.native_effect_areas.items():
                    manager = state_manager(tx.fight, uid)
                    if row["reference"] == 1474:
                        self.assertIsNone(manager)
                    else:
                        self.assertNotIn(uid, tx.fight.actors)
                        self.assertFalse(hasattr(manager, "hp"))
                        self.assertTrue(manager.state_ledger.entries)
                runtime = RuntimeMessages(
                    tx.fight,
                    turn_start_provider=lambda preview, **boundary: prepare_area_event(
                        character,
                        {-7: monster},
                        preview,
                        deck,
                        event="turn_start",
                        rng=random.Random(1),
                        **boundary
                    ),
                )
                identity = tx.fight
                packets = runtime.end_turn(3, 7, tx.fight.actors[7].turn_count)
                self.assertIs(runtime.fight, identity)
                self.assertEqual(tx.fight.current.id, -7)
                self.assertEqual(tx.fight.actors[-7].hp, 200 - damage)
                self.assertTrue(runtime.pending)
                self.assertEqual(runtime.area_started_turn, (tx.fight.turn_id, -7))
                hp = tx.fight.actors[-7].hp
                runtime.acknowledge_turn(struct.pack(">i", 1))
                self.assertEqual(tx.fight.actors[-7].hp, hp)
                self.assertEqual(snapshot(fight), before)
