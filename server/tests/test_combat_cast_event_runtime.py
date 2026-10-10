"""Actual class initialization -> normal cast -> native post-cast states."""
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class CastEventRuntimeTests(unittest.TestCase):
    def test_cra_normal_cast_applies_original_post_cast_state_children_atomically(self):
        from tests.test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
        )
        from wakfu_server.spells import encode_deck

        character, creature, fight = SpellTransactionTests().native_server_fixture(
            9, 200, native_qi=True
        )
        deck = encode_deck([4820])
        initialized, _ = prepare_server_initialization(
            character,
            {-7: creature},
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(0),
            fight_start=True,
        )
        self.assertTrue(initialized.native_start_event_delivered)
        self.assertTrue(
            any(
                state.reference == 3419
                for state in initialized.actors[7].state_ledger.entries
            )
        )
        before = tuple(initialized.actors[7].state_ledger.entries)
        self.assertFalse(any(state.reference in (7758, 7793) for state in before))
        rng = random.Random(0)
        target = initialized.actors[-7].position
        transaction = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 4820, *target),
            character,
            {-7: creature},
            initialized,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        states = {
            state.reference: state
            for state in transaction.fight.actors[7].state_ledger.entries
        }
        # Native 350554 -> 352071 -> 352072/352074, evaluated normally.
        # Native carriers7758/7793 have duration0: their original children
        # 347094/349856 persist3430/7792 instead of retaining the carriers.
        applied = {
            event["state_id"]: event
            for event in transaction.fight.events
            if event["kind"] == "state_applied"
            and event["sequence"] > initialized.sequence
            and event["actor_id"] == 7
        }
        for reference in (7758, 7793):
            self.assertEqual(applied[reference]["level"], 3)
            self.assertEqual(applied[reference]["duration"], 0)
            self.assertTrue(applied[reference]["instant"])
        self.assertEqual(states[3430].level, 30)
        self.assertEqual(states[7792].level, 30)
        self.assertNotIn(7758, states)
        self.assertNotIn(7793, states)
        self.assertNotIn(7760, states)  # Original HasState(7757) branch is false.
        self.assertEqual(tuple(initialized.actors[7].state_ledger.entries), before)
        self.assertGreater(len(transaction.packets), 2)
        self.assertIsNone(initialized.native_active_spell_id)
        self.assertIsNone(transaction.fight.native_active_spell_id)

    def test_sacro_one_cast_helpers_expire_and_interrupted_cast_rolls_back(self):
        from unittest.mock import patch
        from tests.test_combat_lethal_reactions import (
            initialized_cinetosis_fixture,
            cinetosis_turn_runtime,
            native,
        )
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.fight_checkpoint_store import snapshot

        (
            character,
            creature,
            initialized,
            deck,
            rng,
            los,
            terrain,
        ) = initialized_cinetosis_fixture(
            [5028, 5041],
            monster_reference=3646,
            monster_level=12,
        )
        setup = prepare_server_spell(
            struct.pack(
                ">qqiih", 7, (7 << 32) | 5041, *initialized.actors[-7].position
            ),
            character,
            {-7: creature},
            initialized,
            3,
            deck,
            action_id=2,
            line_of_sight=los,
            critical=False,
            rng=rng,
        )
        initialized = setup.fight
        before = snapshot(initialized)
        execute = EffectDispatcher.execute
        created = []
        # Original Blood for Blood accepts a legal empty cell. Keep the NPC
        # alive while testing helper expiry, without fabricated target HP.
        empty_terrain = dict(
            terrain,
            cells={
                c
                for c in terrain["cells"]
                if c not in {a.position for a in initialized.actors.values()}
            },
        )
        empty = dict(
            native.target_candidates(
                native.catalog()["spells"]["5028"],
                200,
                empty_terrain,
                initialized.actors[7].position,
                native=native.native_casting_baseline(
                    native.native_casting_catalog()["5028"], 200
                ),
                spell_reference=5028,
            )
        )["empty_cell"]

        def observe(dispatcher, invocation, **kwargs):
            if invocation.reference == 416001:
                created.append(invocation)
            return execute(dispatcher, invocation, **kwargs)

        def cast(source, action_id):
            return prepare_server_spell(
                struct.pack(">qqiih", 7, (7 << 32) | 5028, *empty),
                character,
                {-7: creature},
                source,
                3,
                deck,
                action_id=action_id,
                line_of_sight=los,
                critical=False,
                rng=rng,
            )

        def helpers(source):
            return [
                row
                for row in source.native_owned_group_effects.values()
                if row.get("generic_effect") == 416001
            ]

        with patch.object(EffectDispatcher, "execute", observe):
            first = cast(initialized, 3)
            self.assertEqual(helpers(first.fight), [])
            # Two actual4AP casts require a native next turn. Preserve the
            # end/ACK/start resource producers instead of topping up AP.
            turns = cinetosis_turn_runtime(character, creature, first.fight, deck, rng)
            advance_actual_turn(turns)
            while turns.fight.current.id != 7:
                advance_actual_turn(turns)
            second = cast(turns.fight, 4)
        self.assertEqual(len(created), 2)
        self.assertEqual(helpers(first.fight), [])
        self.assertEqual(helpers(second.fight), [])
        self.assertEqual(snapshot(initialized), before)

        rng_before = rng.getstate()

        def interrupted(dispatcher, invocation, **kwargs):
            if invocation.reference == 255621:
                raise ValueError("interrupted ordinary root")
            return execute(dispatcher, invocation, **kwargs)

        with patch.object(EffectDispatcher, "execute", interrupted):
            with self.assertRaisesRegex(ValueError, "interrupted ordinary root"):
                cast(initialized, 3)
        self.assertEqual(snapshot(initialized), before)
        self.assertEqual(rng.getstate(), rng_before)
