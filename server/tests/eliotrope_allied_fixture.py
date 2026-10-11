"""Actual multiplayer authority for Eliotrope friendly-only gift consumers."""
import random
import struct
from unittest.mock import patch

import test_combat_aptitude_healing_runtime as allied


class EliotropeAlliedFixture:
    setUpClass = allied.AptitudeHealingRuntimeTests.__dict__["setUpClass"]

    def allied_fixture(
        self,
        *,
        passives=(),
        target_distance=4,
        ally_spells=(),
        ally_position=(-7, -7, -1),
        compact_arena=True
    ):
        from wakfu_server.spells import encode_deck

        def loadout(*args, **kwargs):
            return (
                encode_deck(ally_spells)
                if not args and not kwargs
                else encode_deck(*args, **kwargs)
            )

        # Configure the existing real multiplayer fixture's empty allied decks
        # before Ready. This does not mock a casting or combat authority.
        with patch("wakfu_server.spells.encode_deck", side_effect=loadout):
            (
                fight,
                characters,
                monster,
                decks,
            ) = allied.AptitudeHealingRuntimeTests.fixture(
                self,
                active_spells=(4668, 4692, 4699),
                passive_spells=passives,
                caster_breed=18,
                level=200,
                caster_aptitudes=(),
                injury=0,
                compact_arena=compact_arena,
                enemy_position=(-8 + target_distance, -7, -1),
                third_player_position=(-9, -7, -1),
                second_player_position=ally_position,
                initialization_seed=17,
            )
        return (
            characters[7],
            monster,
            fight,
            decks[7],
            random.Random(17),
            (),
            characters,
            decks,
        )

    def allied_cast(self, data, reference, *, target=None, action_id=10, actor_id=7):
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monster, fight, deck, rng, _, characters, decks = data
        grant = granted_spells(fight, actor_id).get(reference)
        identity = grant["uid"] if grant is not None else (actor_id << 32) | reference
        target = fight.actors[8].position if target is None else target

        def los(origin, destination, current):
            return authoritative_visible(
                character["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in current.actors.values() if a.hp > 0
                },
            )

        before = snapshot(fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", actor_id, identity, *target),
            characters[actor_id],
            {-7: monster},
            fight,
            characters[actor_id]["account_id"],
            decks[actor_id],
            action_id=action_id,
            line_of_sight=los,
            critical=False,
            rng=rng,
            player_characters=characters,
            deck_blobs=decks,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(tx.outcomes))
        return tx

    def advance_to(self, data, identity):
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from combat_audit_turns import advance_actual_turn

        character, monster, fight, deck, rng, _, characters, decks = data
        authority = dict(player_characters=characters, deck_blobs=decks)
        for _ in range(24):
            if fight.current.id == identity:
                return
            runtime = RuntimeMessages(
                fight,
                turn_end_provider=lambda p, **b: prepare_server_turn_end(
                    character, {-7: monster}, p, deck, rng=rng, **authority, **b
                ),
                turn_start_provider=lambda p, **b: prepare_server_turn_start(
                    character, {-7: monster}, p, deck, rng=rng, **authority, **b
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    character,
                    {-7: monster},
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                    **authority
                )[0],
            )
            advance_actual_turn(runtime)
        self.fail("Actual multiplayer turn not reached")
