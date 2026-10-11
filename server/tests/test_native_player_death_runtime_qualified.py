"""Real NPC damage, reversible player KO and explicit final state2."""
import os
import struct
import unittest
from unittest.mock import patch
import test_combat_resurrection_runtime as resurrection
from wakfu_server.combat_death import death_messages
from wakfu_server.combat_global_pv_collections import global_fighter_guards
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import snapshot


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class NativePlayerDeathRuntimeTests(unittest.TestCase):
    def corpse(self):
        helper = resurrection.ResurrectionRuntimeTests()
        data = helper.fixture()
        fight, characters, monster, decks, rng = data
        for index in range(100):
            if fight.actors[8].hp == 0:
                break
            hp = fight.actors[8].hp
            fight, _ = helper.damage(
                fight, characters, monster, decks, rng, 100 + index
            )
            self.assertLess(fight.actors[8].hp, hp)
        self.assertEqual(fight.actors[8].hp, 0)
        self.assertEqual(fight.phase, "active")
        self.assertGreater(fight.actors[7].hp, 0)
        self.assertGreater(fight.actors[9].hp, 0)
        self.assertEqual(
            global_fighter_guards(fight, 8), dict(baF=False, baG=True, baK=False)
        )
        return helper, data, fight

    @staticmethod
    def states(packets):
        return [
            struct.unpack(">iiiqB", body)[3:] for op, body in packets if op == 12727
        ]

    def test_actual_controlled_ko_preserves_qi_and_native_resurrection(self):
        helper, data, fight = self.corpse()
        runtime = RuntimeMessages(fight)
        actor = fight.actors[8]
        slot = actor.native_obstacle_id
        packets = death_messages(runtime, 8)
        self.assertEqual(self.states(packets), [(8, 0)])
        self.assertEqual(
            global_fighter_guards(fight, 8), dict(baF=False, baG=True, baK=False)
        )
        self.assertEqual(actor.native_obstacle_id, slot)
        self.assertEqual(current_registry(fight).slots[slot]["identity"], ["actor", 8])
        before = snapshot(fight)
        with self.assertRaisesRegex(ValueError, "already reported"):
            death_messages(runtime, 8)
        self.assertEqual(snapshot(fight), before)
        tx = helper.resurrect(data, fight, action_id=300)
        self.assertEqual(snapshot(fight), before)
        self.assertGreater(tx.fight.actors[8].hp, 0)
        self.assertEqual(
            global_fighter_guards(tx.fight, 8), dict(baF=True, baG=False, baK=False)
        )
        self.assertIn(8, tx.fight.order)
        self.assertEqual(self.states(tx.packets), [(8, 1)])

    def test_explicit_final_state2_retires_positive_id_once_and_cannot_revive(self):
        helper, data, fight = self.corpse()
        runtime = RuntimeMessages(fight)
        death_messages(runtime, 8)
        # A new runtime/reconnect must derive KO from the durable native writer.
        runtime = RuntimeMessages(fight)
        slot = fight.actors[8].native_obstacle_id
        packets = death_messages(runtime, 8, fighter_state=2)
        self.assertEqual(self.states(packets), [(8, 2)])
        self.assertEqual(
            global_fighter_guards(fight, 8), dict(baF=False, baG=False, baK=True)
        )
        self.assertEqual(fight.actors[8].native_obstacle_id, -1)
        self.assertIsNone(current_registry(fight).slots[slot])
        self.assertIn(8, fight.actors)
        before = snapshot(fight)
        rng_before = data[4].getstate()
        with self.assertRaisesRegex(ValueError, "already reported"):
            death_messages(runtime, 8, fighter_state=2)
        self.assertEqual(snapshot(fight), before)
        with self.assertRaises(ValueError):
            helper.resurrect(data, fight, action_id=301)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(data[4].getstate(), rng_before)

    def test_unregistered_hp_zero_and_interrupted_finalization_are_atomic(self):
        helper, data, fight = self.corpse()
        from wakfu_server.combat_qi_registry import NativeQIRegistry

        runtime = RuntimeMessages(fight)
        before = snapshot(fight)
        with patch.object(
            NativeQIRegistry, "remove", side_effect=ValueError("interrupted final QI")
        ):
            with self.assertRaisesRegex(ValueError, "interrupted final QI"):
                death_messages(runtime, 8, fighter_state=2)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(runtime.action_id, 0)
        self.assertFalse(getattr(runtime, "_reported_deaths", set()))
        # Fail after private QI removal, during serialization, before commit.
        for method in ("serialized_slots", "serialized_byte_topology"):
            with patch.object(
                NativeQIRegistry,
                method,
                side_effect=ValueError("interrupted final serialization"),
            ):
                with self.assertRaisesRegex(
                    ValueError, "interrupted final serialization"
                ):
                    death_messages(runtime, 8, fighter_state=2)
            self.assertEqual(snapshot(fight), before)
            self.assertEqual(runtime.action_id, 0)
        for method in ("_prefix", "_flush"):
            with patch.object(
                RuntimeMessages,
                method,
                side_effect=ValueError("interrupted wire preflight"),
            ):
                with self.assertRaisesRegex(ValueError, "interrupted wire preflight"):
                    death_messages(runtime, 8, fighter_state=2)
            self.assertEqual(snapshot(fight), before)
            self.assertEqual(runtime.action_id, 0)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(runtime.action_id, 0)
        self.assertFalse(getattr(runtime, "_reported_deaths", set()))
        # A malformed checkpoint is a negative input, not a gameplay producer.
        from copy import deepcopy

        invalid = deepcopy(data[0])
        invalid.actors[8].hp = 0
        invalid_runtime = RuntimeMessages(invalid)
        before = snapshot(invalid)
        with self.assertRaisesRegex(ValueError, "no owned corpse registration"):
            death_messages(invalid_runtime, 8)
        self.assertEqual(snapshot(invalid), before)
        self.assertEqual(invalid_runtime.action_id, 0)

    def test_controlled_summon_default_delivery_stays_final_on_legacy_wire_fixture(
        self,
    ):
        # This small wire-policy control does not qualify summon birth/death semantics.
        # It guards against broadening the ordinary-player KO default to summons.
        from types import SimpleNamespace

        actor = SimpleNamespace(
            id=50,
            hp=0,
            controlled=True,
            native_summon_source={"source": "unit-classification"},
        )
        fight = SimpleNamespace(id=78, actors={50: actor})
        runtime = SimpleNamespace(
            fight=fight,
            _prefix=lambda: struct.pack(">iii", 78, 1, -1),
            _flush=lambda: (13420, b""),
        )
        packets = death_messages(runtime, 50)
        self.assertEqual(self.states(packets), [(50, 2)])

    def test_actual_second_lethal_damage_delivers_ko_after_resurrection(self):
        for fresh_runtime in (False, True):
            with self.subTest(fresh_runtime=fresh_runtime):
                helper, data, fight = self.corpse()
                runtime = RuntimeMessages(fight)
                death_messages(runtime, 8)
                revived = helper.resurrect(data, fight, action_id=400)
                runtime.fight = revived.fight
                runtime.prepare_delivery(revived.packets)
                self.assertNotIn(8, runtime._reported_deaths)
                corpse = revived.fight
                for index in range(100):
                    if corpse.actors[8].hp == 0:
                        break
                    corpse, _ = helper.damage(corpse, *data[1:], action_id=401 + index)
                self.assertEqual(corpse.actors[8].hp, 0)
                if fresh_runtime:
                    runtime = RuntimeMessages(corpse)
                else:
                    runtime.fight = corpse
                self.assertEqual(self.states(death_messages(runtime, 8)), [(8, 0)])
                self.assertTrue(global_fighter_guards(corpse, 8)["baG"])
