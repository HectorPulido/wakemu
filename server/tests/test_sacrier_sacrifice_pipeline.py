"""Actual Sacrifice cast, incoming owned spell and deferred swap pipeline."""
import random
import struct
import unittest


class SacrificePipelineTests(unittest.TestCase):
    def fixture(self):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )
        from wakfu_server.spells import encode_deck

        source = SpellTransactionTests()
        character, creature, original = source.native_server_fixture(
            11, 200, native_qi=True
        )
        attacker_character, _, _ = source.native_server_fixture(15, 200)
        attacker_character = dict(attacker_character, id=8, account_id=4)
        protector, ally = original.actors[7], original.actors[-7]
        protector.position, ally.position = (-8, -7, -1), (-6, -7, -1)
        ally.team = 0
        protector.turn_count = ally.turn_count = 0
        set_hp_raw_current(protector, protector.max_hp)
        attacker = Actor(
            8,
            1,
            (-6, -6, -1),
            attacker_character["max_hp"],
            6,
            3,
            8,
            200,
            4,
            True,
            max_hp=attacker_character["max_hp"],
        )
        build_player_snapshot(
            attacker_character, attacker, wp_current=6, wp_maximum=6, running_effects=()
        ).install(attacker)
        terrain = local_arena(
            1134,
            0,
            protector.position,
            [ally.position, attacker.position],
            relocate_monsters=False,
        )
        fight = Fight(
            78,
            [protector, ally, attacker],
            terrain["validated_cells"],
            {0: {protector.position, ally.position}, 1: {attacker.position}},
            terrain["valid_edges"],
        )
        fight.native_qi_snapshot = {
            name: terrain[name] for name in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(
            terrain["native_qi_surface_provenance"]
        )
        freeze_terrain(fight)
        initialize_global_pv_collections(fight, (7, -7, 8))
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight,
                physical_radii={
                    identity: actor.physical_radius
                    for identity, actor in fight.actors.items()
                },
            ),
        )
        fight.ready(3)
        fight.ready(4)
        fight.native_effect_uid_next = 1
        characters = {7: character, 8: attacker_character}
        decks = {7: encode_deck([5044]), 8: encode_deck([6266])}
        return characters, {-7: creature}, decks, fight

    def run_attack(self, before_attack=None):
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            server_runtime,
            prepare_server_turn_start,
            prepare_server_turn_end,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from combat_audit_turns import advance_actual_turn

        characters, monsters, decks, fight = self.fixture()
        rng = random.Random(0)
        common = dict(player_characters=characters, deck_blobs=decks)
        fight, _ = prepare_server_initialization(
            characters[7],
            monsters,
            fight,
            3,
            decks[7],
            action_id=1,
            rng=rng,
            fight_start=False,
            **common
        )
        fight, _ = prepare_server_initialization(
            characters[8],
            monsters,
            fight,
            4,
            decks[8],
            action_id=2,
            rng=rng,
            fight_start=True,
            **common
        )

        def cast(identity, spell, target, state, action):
            return prepare_server_spell(
                struct.pack(
                    ">qqiih",
                    identity,
                    (identity << 32) | spell,
                    *state.actors[target].position
                ),
                characters[identity],
                monsters,
                state,
                characters[identity]["account_id"],
                decks[identity],
                action_id=action,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=rng,
                **common
            )

        runtime = RuntimeMessages(
            fight,
            turn_start_provider=lambda preview, **kwargs: prepare_server_turn_start(
                characters[7], monsters, preview, decks[7], rng=rng, **common, **kwargs
            ),
            turn_end_provider=lambda preview, **kwargs: prepare_server_turn_end(
                characters[7], monsters, preview, decks[7], rng=rng, **common, **kwargs
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
        for _ in range(4):
            if runtime.fight.current.id == 7:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, 7)
        protected = cast(7, 5044, -7, runtime.fight, 2)
        runtime.fight = protected.fight
        self.assertIn(
            89,
            {
                state.reference
                for state in runtime.fight.actors[-7].state_ledger.entries
            },
        )
        for _ in range(4):
            if runtime.fight.current.id == 8:
                break
            advance_actual_turn(runtime)
        self.assertEqual(runtime.fight.current.id, 8)
        if before_attack is not None:
            before_attack(runtime.fight)
        before = {
            identity: (actor.hp, actor.position)
            for identity, actor in runtime.fight.actors.items()
        }
        attacked = cast(8, 6266, -7, runtime.fight, 10)
        return attacked, runtime.fight, before

    def test_direct_owned_attack_redirects_damage_then_swaps_at_cast_boundary(self):
        attacked, original, before = self.run_attack()
        self.assertIn(
            4800, {state.reference for state in original.actors[7].state_ledger.entries}
        )
        self.assertNotIn(
            4800,
            {state.reference for state in original.actors[-7].state_ledger.entries},
        )
        self.assertEqual(attacked.fight.actors[-7].hp, before[-7][0])
        self.assertLess(attacked.fight.actors[7].hp, before[7][0])
        self.assertEqual(attacked.fight.actors[7].position, before[-7][1])
        self.assertEqual(attacked.fight.actors[-7].position, before[7][1])
        self.assertEqual(original.actors[7].position, before[7][1])

    def test_redirect_crossing_low_hp_threshold_removes_sacrifice_and_owner_state(self):
        from wakfu_server.combat_hp_raw import set_hp_raw_current

        def near_threshold(fight):
            protector = fight.actors[7]
            set_hp_raw_current(protector, protector.max_hp // 10 + 1)

        attacked, original, before = self.run_attack(near_threshold)
        self.assertEqual(attacked.fight.actors[-7].hp, before[-7][0])
        self.assertLess(
            attacked.fight.actors[7].hp * 10, attacked.fight.actors[7].max_hp
        )
        self.assertNotIn(
            89,
            {
                state.reference
                for state in attacked.fight.actors[-7].state_ledger.entries
            },
        )
        self.assertNotIn(
            4800,
            {
                state.reference
                for state in attacked.fight.actors[7].state_ledger.entries
            },
        )
        self.assertIn(
            89, {state.reference for state in original.actors[-7].state_ledger.entries}
        )


if __name__ == "__main__":
    unittest.main()
