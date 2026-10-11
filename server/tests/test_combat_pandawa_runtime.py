"""Pandawa owned grants, native barrel and carry lifecycle without injected states."""
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class PandawaRuntimeTests(unittest.TestCase):
    def fixture(self, passives=(), *, actives=(4702, 4712), target_distance=1):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            12,
            200,
            target_hp=2000,
            native_qi=True,
            target_distance=target_distance,
            variation_seed=17,
        )
        deck = encode_deck(list(actives), passives)
        rng = random.Random(0)
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        return character, monster, fight, deck, rng

    def cast(self, fixture, spell, *, target=None, action_id=2):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.fight_checkpoint_store import snapshot
        from tools.class_spell_eligible_targets import eligible_cast_targets

        character, monster, fight, deck, rng = fixture
        grants = granted_spells(fight, 7)
        uid = grants[spell]["uid"] if spell in grants else (7 << 32) | spell
        if target is None:
            _, adapter = server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=rng,
            )
            selection = eligible_cast_targets(
                fight,
                character,
                deck,
                uid,
                adapter=adapter,
                line_of_sight=lambda *args: True,
                actor_id=7,
                limit=128,
                maximum_eligible=1,
            )
            self.assertTrue(selection["eligible"], selection)
            target = selection["eligible"][0]["target"]
        before = snapshot(fight)
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *target),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=action_id,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(result.outcomes))
        return result

    def adopt(self, fixture, fight):
        return (*fixture[:2], fight, *fixture[3:])

    def test_ready_grants_and_native_barrel_constructor(self):
        from wakfu_server.combat_spell_grant import granted_spells

        fixture = self.fixture()
        self.assertTrue(
            {4718, 6847, 6848, 8591, 8592} <= set(granted_spells(fixture[2], 7))
        )
        result = self.cast(fixture, 4718)
        barrels = [
            actor
            for actor in result.fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        ]
        self.assertEqual(len(barrels), 1)
        barrel = barrels[0]
        self.assertEqual(barrel.native_summon_action_book["profile"], 3794)
        self.assertTrue(
            {1304, 4230} <= {entry.reference for entry in barrel.state_ledger.entries}
        )
        self.assertGreaterEqual(barrel.native_obstacle_id, 0)

    def test_owned_enemy_carry_then_legitimate_throw(self):
        fixture = self.fixture()
        enemy = fixture[2].actors[-7]
        carried = self.cast(fixture, 6847, target=enemy.position)
        self.assertEqual(
            carried.fight.actors[-7].position, carried.fight.actors[7].position
        )
        fixture = self.adopt(fixture, carried.fight)
        thrown = self.cast(fixture, 6848, action_id=3)
        self.assertNotEqual(
            thrown.fight.actors[-7].position, thrown.fight.actors[7].position
        )

    def test_owned_drunkenness_self_action_uses_native_state_transition(self):
        fixture = self.fixture()
        result = self.cast(fixture, 8592, target=fixture[2].actors[7].position)
        states = {
            entry.reference for entry in result.fight.actors[7].state_ledger.entries
        }
        self.assertTrue(states & {3300, 6107, 3316}, states)

    def next_owned_turn(self, fixture):
        from test_aniripsa_cunejo_area_pipeline import AreaEnabledFixture

        helper = AreaEnabledFixture()
        helper.next_player_turn(fixture[2], fixture)
        return fixture

    def test_barrel_carry_end_turn_drunk_and_passive_armor(self):
        for passive in (None, 8597):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                from wakfu_server.combat_server_spell import server_runtime
                from wakfu_server.combat_spell_grant import granted_spells
                from tools.class_spell_eligible_targets import eligible_cast_targets

                character, monster, fight, deck, rng = fixture
                _, adapter = server_runtime(
                    character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
                )
                selection = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    granted_spells(fight, 7)[4718]["uid"],
                    adapter=adapter,
                    line_of_sight=lambda *args: True,
                    actor_id=7,
                    limit=128,
                    maximum_eligible=16,
                )
                carry = None
                rejected = []
                for candidate in selection["eligible"]:
                    barrel_result = self.cast(fixture, 4718, target=candidate["target"])
                    next_fixture = self.adopt(fixture, barrel_result.fight)
                    barrel = next(
                        a
                        for a in next_fixture[2].actors.values()
                        if getattr(a, "native_summon_source", None)
                    )
                    try:
                        carry = self.cast(
                            next_fixture, 6847, target=barrel.position, action_id=3
                        )
                    except ValueError as error:
                        rejected.append(str(error))
                        continue
                    fixture = self.adopt(next_fixture, carry.fight)
                    break
                self.assertIsNotNone(carry, (selection, rejected))
                self.assertIn(
                    6776,
                    {s.reference for s in fixture[2].actors[7].state_ledger.entries},
                )
                before_armor = fixture[2].actors[7].effect_stats.get(97, 0)
                from unittest.mock import patch
                from wakfu_server import combat_server_spell

                original_end = combat_server_spell.prepare_server_turn_end
                owned_end = []

                def observe_end(*args, **kwargs):
                    result = original_end(*args, **kwargs)
                    if kwargs["actor_id"] == 7:
                        end_actor = result[0].actors[7]
                        owned_end.append(
                            (
                                {
                                    entry.reference
                                    for entry in end_actor.state_ledger.entries
                                },
                                end_actor.effect_stats.get(97, 0),
                            )
                        )
                    return result

                with patch.object(
                    combat_server_spell, "prepare_server_turn_end", observe_end
                ):
                    fixture = self.next_owned_turn(fixture)
                self.assertEqual(len(owned_end), 1)
                # State3300 has a native one-turn target clock. Observe the
                # actual end reaction before the following start can expire it.
                states, armor = owned_end[0]
                self.assertIn(3300, states)
                if passive == 8597:
                    self.assertGreater(armor, before_armor)
                else:
                    self.assertEqual(armor, before_armor)

    def test_milk_cloud_owns_native_glyph_and_expires_on_real_turns(self):
        fixture = self.fixture(actives=(4708,))
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import eligible_cast_targets

        character, monster, fight, deck, rng = fixture
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
        )
        selection = eligible_cast_targets(
            fight,
            character,
            deck,
            granted_spells(fight, 7)[4718]["uid"],
            adapter=adapter,
            line_of_sight=lambda *args: True,
            actor_id=7,
            limit=128,
            maximum_eligible=16,
        )
        result, rejected = None, []
        for candidate in selection["eligible"]:
            created = self.cast(fixture, 4718, target=candidate["target"])
            next_fixture = self.next_owned_turn(self.adopt(fixture, created.fight))
            barrel = next(
                a
                for a in next_fixture[2].actors.values()
                if getattr(a, "native_summon_source", None)
            )
            try:
                result = self.cast(
                    next_fixture, 4708, target=barrel.position, action_id=30
                )
            except ValueError as error:
                rejected.append(str(error))
                continue
            fixture = next_fixture
            break
        self.assertIsNotNone(result, (selection, rejected))
        fixture = self.adopt(fixture, result.fight)
        areas = {
            uid: row
            for uid, row in fixture[2].native_effect_areas.items()
            if row["reference"] == 837
        }
        self.assertTrue(areas, result.outcomes)
        self.assertTrue(all(row["owner_id"] == 7 for row in areas.values()))
        for _ in range(6):
            if not set(areas) & set(fixture[2].native_effect_areas):
                break
            fixture = self.next_owned_turn(fixture)
        self.assertFalse(set(areas) & set(fixture[2].native_effect_areas))
        # Qs.b keeps a retired manager only while actual Qf/state children
        # still require it; an empty removed glyph need not leave a tombstone.
        self.assertFalse(
            set(areas)
            & {row["manager_id"] for row in fixture[2].native_retained_records.values()}
        )

    def test_cocktail_passive_switches_real_drunk_damage_to_healing(self):
        for passive in (None, 4722):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                actor = fixture[2].actors[7]
                before_damage = actor.effect_stats.get(48, 0)
                before_healing = actor.effect_stats.get(114, 0)
                result = self.cast(fixture, 8592, target=actor.position)
                current = result.fight.actors[7]
                self.assertIn(3300, {s.reference for s in current.state_ledger.entries})
                self.assertEqual(
                    current.effect_stats.get(48, 0) - before_damage,
                    50 if passive is None else 0,
                )
                self.assertEqual(
                    current.effect_stats.get(114, 0) - before_healing,
                    25 if passive == 4722 else 0,
                )

    def test_barrel_provides_missing_active_and_toneport_contexts(self):
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from tools.class_spell_eligible_targets import eligible_cast_targets

        for spell in (4714, 6844, 8591):
            with self.subTest(spell=spell):
                fixture = self.fixture(actives=(4714, 6844))
                character, monster, fight, deck, rng = fixture
                _, adapter = server_runtime(
                    character, {-7: monster}, deck, action_id=2, critical=False, rng=rng
                )
                selection = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    granted_spells(fight, 7)[4718]["uid"],
                    adapter=adapter,
                    line_of_sight=lambda *args: True,
                    actor_id=7,
                    limit=128,
                    maximum_eligible=16,
                )
                result, rejected = None, []
                for candidate in selection["eligible"]:
                    created = self.cast(fixture, 4718, target=candidate["target"])
                    next_fixture = self.adopt(fixture, created.fight)
                    barrel = next(
                        a
                        for a in next_fixture[2].actors.values()
                        if getattr(a, "native_summon_source", None)
                    )
                    try:
                        result = self.cast(
                            next_fixture, spell, target=barrel.position, action_id=3
                        )
                    except ValueError as error:
                        rejected.append(str(error))
                        continue
                    break
                self.assertIsNotNone(result, (selection, rejected))
                self.assertEqual(result.plan["spell_id"], spell)

    def test_firm_step_changes_actual_toneportation_casting_flags(self):
        for passive in (None, 8595):
            with self.subTest(passive=passive):
                fixture = self.fixture(() if passive is None else (passive,))
                created = self.cast(fixture, 4718)
                fixture = self.adopt(fixture, created.fight)
                barrel = next(
                    a
                    for a in fixture[2].actors.values()
                    if getattr(a, "native_summon_source", None)
                )
                result = self.cast(fixture, 8591, target=barrel.position, action_id=3)
                flags = result.plan["native_casting_flags"]
                self.assertEqual(flags["line_of_sight"], passive is None)
                self.assertEqual(flags["linear"], passive == 8595)
