"""Paid native bomb chains and two-owner dial replacement isolation."""
import os
import random
import struct
import unittest

import test_rogue_runtime_pipeline as rogue
import test_aniripsa_grant_summon_pipeline as turns
import xelor_multiowner_fixture as multi
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.fight_checkpoint_store import snapshot
from tools.combat_audit_turns import advance_actual_turn


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class MultiOwnerPortalBombDialTests(unittest.TestCase):
    def test_same_owner_paid_adjacent_bombs_chain_without_duplicate_birth(self):
        helper = rogue.RogueRuntimePipelineTests()
        data = helper.fixture()
        data, _ = helper.cast(data, 7906)
        first = helper.summons(data[2], (3795, 3796, 3797))[0]
        first_id = first.id
        turns.AniripsaGrantSummonPipelineTests().next_player_turn(data[2], data)
        self.assertGreater(data[2].actors[first_id].hp, 0)
        data, _ = helper.cast(data, 7906, action_id=11)
        bombs = helper.summons(data[2], (3795, 3796, 3797))
        self.assertEqual(len(bombs), 2)
        self.assertEqual({a.native_summon_source["controller_id"] for a in bombs}, {7})
        self.assertEqual(
            sum(abs(bombs[0].position[i] - bombs[1].position[i]) for i in (0, 1)), 1
        )
        identities = {actor.id for actor in bombs}
        data, _ = helper.cast(
            data, 6495, data[2].actors[first_id].position, action_id=12
        )
        self.assertEqual(helper.summons(data[2], (3795, 3796, 3797)), [])
        self.assertTrue(
            all(data[2].actors[identity].hp == 0 for identity in identities)
        )
        self.assertEqual(
            {
                a.id
                for a in data[2].actors.values()
                if getattr(a, "native_summon_source", None)
            },
            identities,
        )

    def test_recasting_one_of_two_real_dials_preserves_foreign_hours_and_dial(self):
        fight, characters, monster, decks = multi.TwoXelorFixture().fixture(
            level=1,
            caster_breed=5,
            compact_arena=False,
            second_player_position=(-8, -5, -1),
            third_player_position=(-9, -7, -1),
        )
        rng = random.Random(0)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                **common
            )[0],
        )

        def advance_to(owner):
            for _ in range(32):
                if runtime.fight.current.id == owner:
                    return
                advance_actual_turn(runtime)
            self.fail("Actual owner turn did not arrive")

        def cast_dial(owner, action_id):
            from tools.class_spell_eligible_targets import eligible_cast_targets

            _, adapter = server_runtime(
                characters[owner],
                {-7: monster},
                decks[owner],
                action_id=action_id,
                critical=False,
                **common
            )
            uid = granted_spells(runtime.fight, owner)[5345]["uid"]
            los = lambda a, b, p: authoritative_visible(1134, a, b, p)
            selected = eligible_cast_targets(
                runtime.fight,
                characters[owner],
                decks[owner],
                uid,
                adapter=adapter,
                actor_id=owner,
                limit=512,
                maximum_eligible=16,
                line_of_sight=los,
            )
            self.assertTrue(selected["eligible"], selected)
            cell = tuple(selected["eligible"][0]["target"])
            before = snapshot(runtime.fight)
            old_ids = set(runtime.fight.actors)
            tx = prepare_server_spell(
                struct.pack(">qqiih", owner, uid, *cell),
                characters[owner],
                {-7: monster},
                runtime.fight,
                characters[owner]["account_id"],
                decks[owner],
                action_id=action_id,
                line_of_sight=los,
                critical=False,
                **common
            )
            self.assertEqual(snapshot(runtime.fight), before)
            self.assertTrue(any(tx.outcomes))
            born = set(tx.fight.actors) - old_ids
            self.assertEqual(len(born), 1)
            runtime.fight = tx.fight
            return born.pop()

        born = {}
        for owner in (7, 8):
            advance_to(owner)
            born[owner] = cast_dial(owner, 10 + owner)
        old_hours = {
            uid
            for uid, row in runtime.fight.native_effect_areas.items()
            if row.get("owner_id") == 7 and 1546 <= row["reference"] <= 1558
        }
        foreign_hours = {
            uid: dict(row)
            for uid, row in runtime.fight.native_effect_areas.items()
            if row.get("owner_id") == 8 and 1546 <= row["reference"] <= 1558
        }
        self.assertTrue(old_hours)
        self.assertTrue(foreign_hours)
        advance_to(7)
        foreign_hours = {
            uid: dict(runtime.fight.native_effect_areas[uid]) for uid in foreign_hours
        }
        foreign_hp = runtime.fight.actors[born[8]].hp
        replacement = cast_dial(7, 40)
        self.assertNotEqual(replacement, born[7])
        self.assertEqual(runtime.fight.actors[born[7]].hp, 0)
        self.assertGreater(runtime.fight.actors[replacement].hp, 0)
        self.assertTrue(old_hours.isdisjoint(runtime.fight.native_effect_areas))
        self.assertEqual(runtime.fight.actors[born[8]].hp, foreign_hp)
        for uid, row in foreign_hours.items():
            self.assertEqual(runtime.fight.native_effect_areas[uid], row)
