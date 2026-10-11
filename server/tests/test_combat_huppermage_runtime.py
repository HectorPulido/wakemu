"""Huppermage acceptance through native initialization and owned spell casts."""
import os
import random
import struct
import unittest
import json
import hashlib
from unittest.mock import patch


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class HuppermageRuntimeTests(unittest.TestCase):
    def setUp(self):
        from wakfu_server import native_catalog

        with native_catalog._database().connection() as db:
            row = db.execute(
                "SELECT d.revision,d.raw,d.sha256 FROM native_catalog_documents d "
                "JOIN native_catalog_releases r USING(revision) "
                "WHERE d.path='native-spell-resource-costs.json' AND r.complete "
                "ORDER BY r.completed_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            self.fail("Complete staged resource-cost catalog required")
        raw = bytes(row["raw"])
        self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])
        document = json.loads(raw)
        self.cost_catalog = document["spells"]
        self.cost_patch = patch(
            "wakfu_server.combat_spell_resource_costs.catalog",
            return_value=self.cost_catalog,
        )
        self.cost_patch.start()
        self.addCleanup(self.cost_patch.stop)

    def fixture(self, spell, passives=(), *, target_distance=2):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            19,
            200,
            target_hp=2000,
            native_qi=True,
            target_distance=target_distance,
            variation_seed=17,
        )
        deck = encode_deck(
            spell if isinstance(spell, (tuple, list)) else [spell], passives
        )
        rng = random.Random(0)
        fight, packets = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        self.assertTrue(packets)
        self.assertTrue(
            {4069, 4464, 7562}.issubset(
                {state.reference for state in fight.actors[7].state_ledger.entries}
            )
        )
        return character, monster, fight, deck, rng

    def test_four_elemental_casts_create_matching_native_rune(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_diagnostics import combat_diagnostic_scope

        for spell, rune in ((5562, 4064), (5564, 4065), (5567, 4066), (5570, 4067)):
            with self.subTest(spell=spell, rune=rune):
                character, monster, fight, deck, rng = self.fixture(spell)
                original = snapshot(fight)
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=4096
                ):
                    transaction = prepare_server_spell(
                        struct.pack(
                            ">qqiih", 7, (7 << 32) | spell, *fight.actors[-7].position
                        ),
                        character,
                        {-7: monster},
                        fight,
                        3,
                        deck,
                        action_id=2,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=rng,
                    )
                caster = transaction.fight.actors[7]
                self.assertIn(
                    rune, {s.reference for s in caster.state_ledger.entries}, trace
                )
                self.assertLess(transaction.fight.actors[-7].hp, fight.actors[-7].hp)
                self.assertLess(caster.ap, fight.actors[7].ap)
                self.assertEqual(snapshot(fight), original)

    def test_owned_spell_pays_actual_breeze_atomically(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monster, fight, deck, rng = self.fixture(5594)
        before = fight.actors[7].effect_stats[111]
        self.assertEqual(before, 50 + 75 * fight.actors[7].effect_maxima[4])
        original = snapshot(fight)
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        activations = []
        original_activate = EffectDispatcher.execute_activation

        def capture_activation(dispatcher, invocation, *args, **kwargs):
            activations.append(invocation.reference)
            return original_activate(dispatcher, invocation, *args, **kwargs)

        with patch.object(EffectDispatcher, "execute_activation", capture_activation):
            transaction = prepare_server_spell(
                struct.pack(">qqiih", 7, (7 << 32) | 5594, *fight.actors[-7].position),
                character,
                {-7: monster},
                fight,
                3,
                deck,
                action_id=2,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
            )
        self.assertIn(
            309165, activations, "Native state4069 must receive paid Breeze2246"
        )
        receipt = transaction.plan["extra_resource_payment"]
        self.assertEqual(
            receipt, (dict(stat_id=111, requested_delta=-200, actual_delta=-200),)
        )
        self.assertEqual(transaction.fight.actors[7].effect_stats[111], before - 200)
        self.assertLess(transaction.fight.actors[-7].hp, fight.actors[-7].hp)
        self.assertEqual(snapshot(fight), original)
        rng_before = rng.getstate()
        with patch(
            "wakfu_server.combat_effect_runtime.NativeEffectRuntimeFactory.__call__",
            side_effect=ValueError("rollback probe"),
        ):
            with self.assertRaisesRegex(ValueError, "rollback probe"):
                prepare_server_spell(
                    struct.pack(
                        ">qqiih", 7, (7 << 32) | 5594, *fight.actors[-7].position
                    ),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=2,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=rng,
                )
        self.assertEqual(snapshot(fight), original)
        self.assertEqual(rng.getstate(), rng_before)
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import prepare_server_turn_end

        spent = transaction.fight
        runtime = RuntimeMessages(
            spent,
            turn_end_provider=lambda candidate, **kwargs: prepare_server_turn_end(
                character, {-7: monster}, candidate, deck, **kwargs
            ),
        )
        runtime.end_turn(3, 7, spent.current.turn_count)
        self.assertEqual(runtime.fight.actors[7].effect_stats[111], before)

    def test_actual_rune_unlocks_three_owned_granted_actions(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot
        from tools.class_spell_eligible_targets import eligible_cast_targets

        character, monster, initial, deck, rng = self.fixture(5562)
        elemental = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 5562, *initial.actors[-7].position),
            character,
            {-7: monster},
            initial,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        fight = elemental.fight
        self.assertIn(
            5371, {row.reference for row in fight.actors[7].state_ledger.entries}
        )
        grants = granted_spells(fight, 7)
        self.assertTrue({5573, 5574, 5578} <= set(grants))
        original = snapshot(fight)
        _, adapter = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=3,
            critical=False,
            rng=random.Random(17),
        )
        for spell in (5573, 5574, 5578):
            with self.subTest(spell=spell):
                selection = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    grants[spell]["uid"],
                    adapter=adapter,
                    line_of_sight=lambda *args: True,
                    actor_id=7,
                    limit=64,
                    maximum_eligible=1,
                )
                self.assertTrue(selection["eligible"], selection)
                target = selection["eligible"][0]["target"]
                transaction = prepare_server_spell(
                    struct.pack(">qqiih", 7, grants[spell]["uid"], *target),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=3,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(17),
                )
                states = {
                    row.reference
                    for row in transaction.fight.actors[7].state_ledger.entries
                }
                if spell == 5573:
                    self.assertIn(4121, states)
                elif spell == 5578:
                    self.assertIn(7774, states)
                else:
                    self.assertTrue(
                        any(
                            row["reference"] == 1049
                            for row in transaction.fight.native_effect_areas.values()
                        )
                    )
                self.assertEqual(snapshot(fight), original)

    def test_real_rune_provides_missing_nominal_active_contexts(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.fight_checkpoint_store import snapshot
        from tools.class_spell_eligible_targets import eligible_cast_targets

        references = (5566, 5577, 7754, 7809)
        character, monster, initial, deck, rng = self.fixture((5562, *references))
        elemental = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 5562, *initial.actors[-7].position),
            character,
            {-7: monster},
            initial,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        fight = elemental.fight
        self.assertIn(
            5371, {row.reference for row in fight.actors[7].state_ledger.entries}
        )
        original = snapshot(fight)
        _, adapter = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=3,
            critical=False,
            rng=random.Random(17),
        )
        for spell in references:
            with self.subTest(spell=spell):
                selection = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    (7 << 32) | spell,
                    adapter=adapter,
                    line_of_sight=lambda *args: True,
                    actor_id=7,
                    limit=64,
                    maximum_eligible=1,
                )
                self.assertTrue(selection["eligible"], selection)
                transaction = prepare_server_spell(
                    struct.pack(
                        ">qqiih",
                        7,
                        (7 << 32) | spell,
                        *selection["eligible"][0]["target"]
                    ),
                    character,
                    {-7: monster},
                    fight,
                    3,
                    deck,
                    action_id=3,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(17),
                )
                self.assertTrue(transaction.packets)
                if transaction.plan["costs"]["ap"] > 0:
                    self.assertLess(transaction.fight.actors[7].ap, fight.actors[7].ap)
                self.assertEqual(snapshot(fight), original)
