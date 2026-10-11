"""Actual Feca protection branches, costs and preview isolation."""
import os
import random
import struct
import unittest
import test_combat_aptitude_healing_runtime as allied


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class FecaProtectionPipelineTests(unittest.TestCase):
    fixture = allied.AptitudeHealingRuntimeTests.fixture
    setUpClass = allied.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    def test_shields_on_self_and_ally_preserve_hp_and_pay_once(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        for spell, carrier, auxiliary, ap in (
            (6972, 6325, 6352, 2),
            (6978, 6334, 6357, 3),
            (6980, 6336, 6359, 3),
        ):
            for target in (7, 8):
                with self.subTest(spell=spell, target=target):
                    fight, characters, monster, decks = self.fixture(
                        active_spells=(spell,),
                        caster_breed=1,
                        level=200,
                        caster_aptitudes=(),
                        enemy_position=(-5, -7, -1),
                    )
                    original = snapshot(fight)
                    hp = fight.actors[target].hp
                    tx = prepare_server_spell(
                        struct.pack(
                            ">qqiih",
                            7,
                            (7 << 32) | spell,
                            *fight.actors[target].position
                        ),
                        characters[7],
                        {-7: monster},
                        fight,
                        3,
                        decks[7],
                        action_id=10,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=random.Random(7),
                        player_characters=characters,
                        deck_blobs=decks,
                    )
                    states = {
                        entry.reference: entry.level
                        for entry in tx.fight.actors[target].state_ledger.entries
                    }
                    self.assertIn(carrier, states)
                    self.assertIn(auxiliary, states)
                    self.assertGreater(states[carrier], 0)
                    self.assertEqual(tx.fight.actors[target].hp, hp)
                    self.assertEqual(tx.plan["costs"]["ap"], ap)
                    self.assertEqual(tx.fight.actors[7].ap, fight.actors[7].ap - ap)
                    self.assertEqual(snapshot(fight), original)

    def test_empty_glyph_movement_is_not_a_damage_trigger(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client

        fight, characters, monster, decks = self.fixture(
            active_spells=(6967,),
            caster_breed=1,
            level=200,
            caster_aptitudes=(),
            enemy_position=(-5, -7, -1),
        )
        rng = random.Random(7)
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 6967, -8, -9, -1),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
            player_characters=characters,
            deck_blobs=decks,
        )
        self.assertEqual(
            {a["reference"] for a in tx.fight.native_effect_areas.values()},
            {1474, 1477},
        )
        runtime = RuntimeMessages(tx.fight)
        _, adapter = server_runtime(
            characters[7],
            {-7: monster},
            decks[7],
            action_id=11,
            critical=False,
            rng=rng,
        )
        hp = {key: actor.hp for key, actor in runtime.fight.actors.items()}

        def provider(preview, **kwargs):
            return prepare_area_movement(
                characters[7],
                {-7: monster},
                preview,
                decks[7],
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
                **kwargs
            )

        apply_client(
            runtime,
            3,
            struct.pack(">qiih", 7, -8, -8, -1),
            lambda actor: b"",
            area_provider=provider,
        )
        self.assertEqual(runtime.fight.actors[7].position, (-8, -8, -1))
        self.assertEqual(
            {key: actor.hp for key, actor in runtime.fight.actors.items()}, hp
        )
        self.assertEqual(runtime.fight.actors[7].mp, fight.actors[7].mp - 1)

    def test_orbe_delivers_armor_at_actual_turn_boundary(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from combat_audit_turns import advance_actual_turn
        from wakfu_server.combat_spell_grant import granted_spells

        fight, characters, monster, decks = self.fixture(
            active_spells=(6978,),
            caster_breed=1,
            level=200,
            caster_aptitudes=(),
            enemy_position=(-9, -7, -1),
        )
        self.assertIn(7009, granted_spells(fight, 7))
        rng = random.Random(7)
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 6978, *fight.actors[7].position),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
            player_characters=characters,
            deck_blobs=decks,
        )
        carrier = next(
            s.level
            for s in tx.fight.actors[7].state_ledger.entries
            if s.reference == 6334
        )
        runtime = RuntimeMessages(
            tx.fight,
            turn_end_provider=lambda preview, **kwargs: prepare_server_turn_end(
                characters[7],
                {-7: monster},
                preview,
                decks[7],
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
                **kwargs
            ),
            turn_start_provider=lambda preview, **kwargs: prepare_server_turn_start(
                characters[7],
                {-7: monster},
                preview,
                decks[7],
                rng=rng,
                area_callbacks=True,
                player_characters=characters,
                deck_blobs=decks,
                **kwargs
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                rng=rng,
                player_characters=characters,
                deck_blobs=decks,
            )[0],
        )
        before_armor = runtime.fight.actors[7].effect_stats.get(97, 0)
        advance_actual_turn(runtime)
        actor = runtime.fight.actors[7]
        self.assertEqual(
            actor.effect_stats.get(97, 0) - before_armor,
            min(
                carrier,
                round(actor.max_hp * actor.effect_stats[88] / 100) - before_armor,
            ),
        )
        self.assertNotIn(6334, {s.reference for s in actor.state_ledger.entries})

        from wakfu_server.combat_npc_spell import prepare_npc_spell, owned_spells

        for _ in range(3):
            if runtime.fight.current.id == -7:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, -7)
        self.assertIn(7962, owned_spells(runtime.fight, {-7: monster}))
        hp, armor = runtime.fight.actors[7].hp, runtime.fight.actors[7].effect_stats[97]
        from wakfu_server.combat_tactical_ai import NativeProvider

        provider = NativeProvider(
            characters[7],
            {-7: monster},
            decks[7],
            player_characters=characters,
            deck_blobs=decks,
        )
        hit = provider.preview(
            runtime.fight,
            dict(
                type="cast",
                spellId=7962,
                level=1,
                targetId=7,
                target=runtime.fight.actors[7].position,
            ),
            30,
            forecast=True,
        )
        self.assertEqual(hit.fight.actors[7].hp, hp)
        self.assertLess(hit.fight.actors[7].effect_stats[97], armor)
        self.assertGreaterEqual(hit.fight.actors[7].effect_stats[97], 0)

    def test_egida_and_owned_shield_magnetism_use_real_ally_context(self):
        from wakfu_server.combat_server_spell import prepare_server_spell

        for spells in ((6986,), (6972, 6987)):
            with self.subTest(spells=spells):
                fight, characters, monster, decks = self.fixture(
                    active_spells=spells,
                    caster_breed=1,
                    level=200,
                    caster_aptitudes=(),
                )

                def cast(spell):
                    return prepare_server_spell(
                        struct.pack(
                            ">qqiih", 7, (7 << 32) | spell, *fight.actors[8].position
                        ),
                        characters[7],
                        {-7: monster},
                        fight,
                        3,
                        decks[7],
                        action_id=10,
                        line_of_sight=lambda *args: True,
                        critical=False,
                        rng=random.Random(7),
                        player_characters=characters,
                        deck_blobs=decks,
                    )

                if len(spells) > 1:
                    fight = cast(6972).fight
                tx = cast(spells[-1])
                if spells[-1] == 6986:
                    self.assertIn(
                        6365,
                        {s.reference for s in tx.fight.actors[8].state_ledger.entries},
                    )
                    self.assertEqual(tx.plan["costs"]["wp"], 1)
                else:
                    self.assertEqual(tx.fight.actors[7].position, (-10, -7, -1))
                    self.assertEqual(
                        tx.fight.actors[8].position, fight.actors[8].position
                    )

    def test_maestro_escudos_caps_real_additive_carrier_without_cycle(self):
        from wakfu_server.combat_server_spell import prepare_server_spell

        fight, characters, monster, decks = self.fixture(
            active_spells=(6972,),
            passive_spells=(6991,),
            caster_breed=1,
            level=200,
            caster_aptitudes=(),
        )
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 6972, *fight.actors[8].position),
            characters[7],
            {-7: monster},
            fight,
            3,
            decks[7],
            action_id=10,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(7),
            player_characters=characters,
            deck_blobs=decks,
        )
        carriers = [
            s for s in tx.fight.actors[8].state_ledger.entries if s.reference == 6352
        ]
        self.assertEqual(len(carriers), 1)
        self.assertEqual(carriers[0].level, 3)

    def test_all_eighteen_legal_passives_allow_actual_allied_shield_cast(self):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.fight_checkpoint_store import snapshot

        for passive in range(6988, 7006):
            with self.subTest(passive=passive):
                fight, characters, monster, decks = self.fixture(
                    active_spells=(6972,),
                    passive_spells=(passive,),
                    caster_breed=1,
                    level=200,
                    caster_aptitudes=(),
                )
                before = snapshot(fight)
                tx = prepare_server_spell(
                    struct.pack(
                        ">qqiih", 7, (7 << 32) | 6972, *fight.actors[8].position
                    ),
                    characters[7],
                    {-7: monster},
                    fight,
                    3,
                    decks[7],
                    action_id=10,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=random.Random(7),
                    player_characters=characters,
                    deck_blobs=decks,
                )
                self.assertIn(
                    6325, {s.reference for s in tx.fight.actors[8].state_ledger.entries}
                )
                self.assertEqual(snapshot(fight), before)
