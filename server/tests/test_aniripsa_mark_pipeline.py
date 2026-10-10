"""Owned Aniripsa marks: real KO source, nearby recipients and carrier cleanup."""
import os
import random
import struct
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaMarkPipelineTests(unittest.TestCase):
    def fixture(self, *, passive=None, injury=0, active_spells=(645, 636, 779, 7985)):
        import audit_active_spells as audit
        from wakfu_server.monsters import owned_instance
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_ready import prepare_ready
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
            prepare_server_turn_start,
            prepare_server_turn_end,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        origin, victim, neighbor = (-8, -7, -1), (-6, -7, -1), (-5, -7, -1)
        terrain = audit.bounded_arena(
            audit.map_geometry(1134), origin, [victim, neighbor], radius=12
        )
        extra = owned_instance(
            5574, 133, -8, map_id=1134, x=neighbor[0], y=neighbor[1], z=neighbor[2]
        )
        character, creature, fight = audit.fixture(
            7,
            200,
            victim,
            terrain,
            origin,
            ready=False,
            monster_reference=5574,
            monster_level=133,
            extra_monsters=(extra,),
            character_fixture=lambda row: row.update(hp=row["hp"] - injury),
        )
        deck = encode_deck(active_spells, [passive] if passive else [])
        monsters = {-7: creature, -8: extra}
        rng = random.Random(0)

        def initialize(preview, action_id):
            return prepare_server_initialization(
                character,
                monsters,
                preview,
                3,
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
            )

        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
            actor_effects,
        )

        def stats(actor):
            if actor.id == 7:
                return actual_actor_stats(
                    character,
                    actor,
                    fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=audit.BREEDS[7]["resources"]["WP"],
                )
            creature_record = monsters[actor.id]
            return actual_monster_actor_stats(
                creature_record,
                actor,
                fight.id,
                wp_current=creature_record["wp"],
                wp_maximum=creature_record["wp"],
            )

        fight, _, _ = prepare_ready(
            fight,
            3,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
        )
        runtime = RuntimeMessages(
            fight,
            turn_start_provider=lambda preview, **kw: prepare_server_turn_start(
                character, monsters, preview, deck, rng=rng, **kw
            ),
            turn_end_provider=lambda preview, **kw: prepare_server_turn_end(
                character, monsters, preview, deck, rng=rng, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character, monsters, deck, action_id=action_id, critical=False, rng=rng
            )[0],
        )
        return character, monsters, deck, runtime, rng

    def cast(self, fixture, reference=645, target_id=-7):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from combat_audit_turns import advance_actual_turn

        character, monsters, deck, runtime, rng = fixture
        for _ in range(6):
            if runtime.fight.current.id == 7:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, 7)
        result = prepare_server_spell(
            struct.pack(
                ">qqiih",
                7,
                (7 << 32) | reference,
                *runtime.fight.actors[target_id].position
            ),
            character,
            monsters,
            runtime.fight,
            3,
            deck,
            action_id=50 + runtime.fight.turn_id,
            critical=False,
            rng=rng,
            line_of_sight=lambda *args: True,
        )
        runtime.fight = result.fight
        return result

    def test_marked_enemy_ko_explodes_once_on_nearby_enemy_with_native_corpse_guard(
        self,
    ):
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from combat_audit_turns import advance_actual_turn

        fixture = self.fixture()
        marked = self.cast(fixture)
        runtime = fixture[3]
        self.assertIn(
            3882,
            {row.reference for row in marked.fight.actors[-7].state_ledger.entries},
        )
        # Exact PA.on operand establishes a near-death victim; the actual owned
        # second cast supplies the lethal runner and emits the KO boundary.
        set_hp_raw_current(runtime.fight.actors[-7], 1)
        advance_actual_turn(runtime)
        before = runtime.fight.actors[-8].hp
        killed = self.cast(fixture, 636)
        self.assertEqual(killed.fight.actors[-7].hp, 0)
        self.assertLess(killed.fight.actors[-8].hp, before)
        print("ANI04 explosion_delta", killed.fight.actors[-8].hp - before, flush=True)
        # eZi inherits eZR.bcd: no flag15, special PL or own1010 mask
        # on367425. The dead carrier remains until lifecycle retirement;
        # removing it here would weaken the original corpse guard.
        self.assertIn(
            3882,
            {row.reference for row in killed.fight.actors[-7].state_ledger.entries},
        )
        self.assertEqual(
            sum(
                row.get("kind") == "death" and row.get("actor_id") == -7
                for row in killed.fight.events
            ),
            1,
        )

    def healing_with_retraso(self, enabled):
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from combat_audit_turns import advance_actual_turn

        fixture = self.fixture(passive=5451 if enabled else None)
        runtime = fixture[3]
        set_hp_raw_current(runtime.fight.actors[7], runtime.fight.actors[7].max_hp // 2)
        before = runtime.fight.actors[7].hp
        result = self.cast(fixture, 779, 7)
        immediate = result.fight.actors[7].hp - before
        deferred = tuple(
            row
            for row in result.fight.actors[7].state_ledger.entries
            if row.reference == 3899
        )
        after_heal = result.fight.actors[7].hp
        from wakfu_server.combat_area_transaction import prepare_area_movement

        origin = runtime.fight.actors[7].position
        destination = (-9, -7, -1)
        runtime.fight.move(3, 7, [destination])
        runtime.fight, _ = prepare_area_movement(
            fixture[0],
            fixture[1],
            runtime.fight,
            fixture[2],
            actor_id=7,
            action_id=80,
            path=[destination],
            origin=origin,
            rng=fixture[4],
        )
        return (
            immediate,
            deferred,
            runtime.fight.actors[7].hp - after_heal,
            runtime.fight,
        )

    def test_retraso_halves_real_healing_runner_and_heals_deferred_amount_on_movement(
        self,
    ):
        baseline, baseline_states, baseline_heal, _ = self.healing_with_retraso(False)
        reduced, states, healing, fight = self.healing_with_retraso(True)
        print(
            "ANI07 baseline/reduced/deferred/healed",
            baseline,
            reduced,
            [row.level for row in states],
            healing,
            flush=True,
        )
        self.assertGreater(baseline, 0)
        self.assertFalse(baseline_states)
        self.assertEqual(baseline_heal, 0)
        self.assertLess(reduced, baseline)
        self.assertEqual(len(states), 1)
        self.assertEqual(states[0].caster_id, 7)
        self.assertEqual(states[0].target_id, 7)
        self.assertEqual(states[0].level, baseline - reduced)
        self.assertEqual(healing, states[0].level)
        self.assertNotIn(
            3899, {row.reference for row in fight.actors[7].state_ledger.entries}
        )

    def test_fuente_salvadora_creates_owned_area_and_expires_on_actual_owner_turns(
        self,
    ):
        from combat_audit_turns import advance_actual_turn

        fixture = self.fixture()
        original = fixture[3].fight
        created = self.cast(fixture, 7985, 7)
        self.assertFalse(getattr(original, "native_effect_areas", {}))
        areas = list(created.fight.native_effect_areas.values())
        self.assertEqual(len(areas), 1)
        area = areas[0]
        self.assertEqual(area["reference"], 1812)
        self.assertEqual(area["owner_id"], 7)
        self.assertEqual(area["level"], 200)
        self.assertEqual(area["cell"], created.fight.actors[7].position)
        runtime = fixture[3]
        for _ in range(15):
            if area["uid"] not in runtime.fight.native_effect_areas:
                break
            advance_actual_turn(runtime)
        self.assertNotIn(area["uid"], runtime.fight.native_effect_areas)

    def test_reintegro_end_with_adjacent_ally_heals_allied_player_and_consumes_mark(
        self,
    ):
        from combat_audit_turns import advance_actual_turn

        fixture = self.allied_fixture((1534,))
        marked = self.allied_cast(fixture, 1534, 8)
        self.assertIn(
            3888, {row.reference for row in marked.fight.actors[8].state_ledger.entries}
        )
        runtime = fixture[0]
        before = runtime.fight.actors[8].hp
        for _ in range(8):
            advance_actual_turn(runtime)
            if 3888 not in {
                row.reference for row in runtime.fight.actors[8].state_ledger.entries
            }:
                break
        self.assertGreater(runtime.fight.actors[8].hp, before)
        self.assertNotIn(
            3888,
            {row.reference for row in runtime.fight.actors[8].state_ledger.entries},
        )
        print(
            "ANI04 Reintegro ally healing",
            runtime.fight.actors[8].hp - before,
            flush=True,
        )

    def allied_fixture(self, active_spells):
        from test_combat_aptitude_healing_runtime import AptitudeHealingRuntimeTests
        from wakfu_server.combat_retained_runtime import native_retained_metadata
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            server_runtime,
            prepare_server_turn_start,
            prepare_server_turn_end,
        )

        helper = AptitudeHealingRuntimeTests()
        helper.active_retained_metadata = native_retained_metadata()
        fight, characters, monster, decks = helper.fixture(
            active_spells=active_spells,
            level=200,
            injury=500,
            caster_aptitudes=(),
        )
        monsters = {-7: monster}
        common = dict(player_characters=characters, deck_blobs=decks)
        rng = random.Random(0)
        runtime = RuntimeMessages(
            fight,
            turn_start_provider=lambda preview, **kw: prepare_server_turn_start(
                characters[7], monsters, preview, decks[7], rng=rng, **common, **kw
            ),
            turn_end_provider=lambda preview, **kw: prepare_server_turn_end(
                characters[7], monsters, preview, decks[7], rng=rng, **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                monsters,
                decks[7],
                action_id=action_id,
                critical=False,
                rng=rng,
                **common
            )[0],
        )
        return runtime, characters, monsters, decks, rng

    def allied_cast(self, fixture, reference, target, caster_id=7):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from combat_audit_turns import advance_actual_turn

        runtime, characters, monsters, decks, rng = fixture
        for _ in range(8):
            if runtime.fight.current.id == caster_id:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, caster_id)
        result = prepare_server_spell(
            struct.pack(
                ">qqiih",
                caster_id,
                (caster_id << 32) | reference,
                *runtime.fight.actors[target].position
            ),
            characters[caster_id],
            monsters,
            runtime.fight,
            characters[caster_id]["account_id"],
            decks[caster_id],
            action_id=100 + runtime.fight.turn_id,
            critical=False,
            rng=rng,
            line_of_sight=lambda *args: True,
            player_characters=characters,
            deck_blobs=decks,
        )
        runtime.fight = result.fight
        return result

    def test_hmill_direct_hit_heals_nearby_allied_player_and_consumes_mark(self):
        from combat_audit_turns import advance_actual_turn

        fixture = self.allied_fixture((636, 645))
        from wakfu_server.combat_qi_fight import move_registered_actor

        move_registered_actor(
            fixture[0].fight, fixture[0].fight.actors[8], (-6, -8, -1)
        )
        marked = self.allied_cast(fixture, 636, -7)
        self.assertIn(
            3885,
            {row.reference for row in marked.fight.actors[-7].state_ledger.entries},
        )
        advance_actual_turn(fixture[0])
        before = fixture[0].fight.actors[8].hp
        mark_uid = next(
            row.uid
            for row in marked.fight.actors[-7].state_ledger.entries
            if row.reference == 3885
        )
        zone = self.allied_cast(fixture, 645, -7)
        self.assertEqual(zone.fight.actors[8].hp, before)
        self.assertIn(
            mark_uid, {row.uid for row in zone.fight.actors[-7].state_ledger.entries}
        )
        advance_actual_turn(fixture[0])
        result = self.allied_cast(fixture, 636, -7)
        self.assertGreater(result.fight.actors[8].hp, before)
        self.assertNotIn(
            mark_uid, {row.uid for row in result.fight.actors[-7].state_ledger.entries}
        )
        print(
            "ANI04 Hmill ally healing", result.fight.actors[8].hp - before, flush=True
        )

    def test_breo_copies_other_target_healing_then_full_hp_consumes_mark(self):
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from combat_audit_turns import advance_actual_turn

        fixture = self.allied_fixture((1539, 779))
        marked = self.allied_cast(fixture, 1539, 8)
        self.assertIn(
            3919, {row.reference for row in marked.fight.actors[8].state_ledger.entries}
        )
        before = marked.fight.actors[8].hp
        other_before = marked.fight.actors[9].hp
        result = self.allied_cast(fixture, 779, 9)
        self.assertGreater(result.fight.actors[9].hp, other_before)
        self.assertGreater(result.fight.actors[8].hp, before)
        print(
            "ANI04 Breo copied healing", result.fight.actors[8].hp - before, flush=True
        )
        set_hp_raw_current(result.fight.actors[8], result.fight.actors[8].max_hp - 1)
        advance_actual_turn(fixture[0])
        filled = self.allied_cast(fixture, 779, 8)
        self.assertEqual(filled.fight.actors[8].hp, filled.fight.actors[8].max_hp)
        states = {row.reference for row in filled.fight.actors[8].state_ledger.entries}
        self.assertNotIn(3919, states)
        self.assertIn(3902, states)

    def test_ting_crossing_half_hp_heals_explodes_and_consumes_mark(self):
        from unittest.mock import patch
        from test_combat_spell_transaction import SpellTransactionTests
        from test_sacrier_sacrifice_pipeline import SacrificePipelineTests
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
            prepare_server_turn_start,
            prepare_server_turn_end,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_qi_fight import move_registered_actor
        from wakfu_server.spells import encode_deck

        original = SpellTransactionTests.native_server_fixture

        def native_fixture(instance, breed, *args, **kwargs):
            return original(instance, 7 if breed == 11 else breed, *args, **kwargs)

        with patch.object(
            SpellTransactionTests, "native_server_fixture", native_fixture
        ):
            characters, monsters, decks, fight = SacrificePipelineTests().fixture()
        decks[7] = encode_deck((638,))
        move_registered_actor(fight, fight.actors[8], (-8, -6, -1))
        rng = random.Random(0)
        common = dict(player_characters=characters, deck_blobs=decks)
        for identity, starts in ((7, False), (8, True)):
            fight, _ = prepare_server_initialization(
                characters[identity],
                monsters,
                fight,
                characters[identity]["account_id"],
                decks[identity],
                action_id=identity,
                rng=rng,
                fight_start=starts,
                **common
            )
        runtime = RuntimeMessages(
            fight,
            turn_start_provider=lambda preview, **kw: prepare_server_turn_start(
                characters[7], monsters, preview, decks[7], rng=rng, **common, **kw
            ),
            turn_end_provider=lambda preview, **kw: prepare_server_turn_end(
                characters[7], monsters, preview, decks[7], rng=rng, **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                monsters,
                decks[7],
                action_id=action_id,
                critical=False,
                rng=rng,
                **common
            )[0],
        )
        fixture = (runtime, characters, monsters, decks, rng)
        marked = self.allied_cast(fixture, 638, 7)
        self.assertIn(
            3884, {row.reference for row in marked.fight.actors[7].state_ledger.entries}
        )
        set_hp_raw_current(
            runtime.fight.actors[7], runtime.fight.actors[7].max_hp // 2 + 1
        )
        first_event = len(runtime.fight.events)
        neighbor_before = runtime.fight.actors[8].hp
        result = self.allied_cast(fixture, 6266, 7, caster_id=8)
        self.assertGreater(result.fight.actors[7].hp, 0)
        self.assertLess(result.fight.actors[7].hp * 2, result.fight.actors[7].max_hp)
        heals = [
            row
            for row in result.fight.events[first_event:]
            if row.get("kind") == "healing" and row.get("target_id") == 7
        ]
        self.assertTrue(heals)
        self.assertGreater(sum(row["amount"] for row in heals), 0)
        self.assertLess(result.fight.actors[8].hp, neighbor_before)
        self.assertNotIn(
            3884, {row.reference for row in result.fight.actors[7].state_ledger.entries}
        )
        print(
            "ANI04 Ting healing/neighbor",
            sum(row["amount"] for row in heals),
            result.fight.actors[8].hp - neighbor_before,
            flush=True,
        )
