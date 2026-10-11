"""Actual Sadida doll turns and native action books, without fabricated grants."""
import os
import random
import struct
import unittest

import test_sadida_grant_pipeline as grants
import test_aniripsa_grant_summon_pipeline as turns
import test_combat_spell_transaction as native_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaDollActionsPipelineTests(unittest.TestCase):
    cast = grants.SadidaGrantPipelineTests.cast

    def born(self, spell, profile, *, passives=(), seed_cell=(-6, -7, -1)):
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_summon_spellbook import actor_action_book

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            10,
            200,
            native_qi=True,
            target_hp=20000,
            variation_seed=17,
            target_distance=4,
        )
        deck = encode_deck((spell,), passives)
        rng = random.Random(17)
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
        data = (character, monster, fight, deck, rng, packets)
        seeded = self.cast(data, 8137, target=seed_cell)
        data = (*data[:2], seeded.fight, *data[3:])
        cell = next(
            a["cell"]
            for a in seeded.fight.native_effect_areas.values()
            if a["reference"] == 1835
        )
        transformed = self.cast(data, spell, target=cell, action_id=11)
        data = (*data[:2], transformed.fight, *data[3:])
        actor = next(
            a
            for a in data[2].actors.values()
            if getattr(a, "native_summon_source", None)
            and a.hp > 0
            and actor_action_book(a)["profile"] == profile
        )
        return data, actor.id

    def test_native_doll_actions_have_actual_turn_and_enabled_effect_receipt(self):
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.fight_checkpoint_store import snapshot
        from class_spell_eligible_targets import eligible_cast_targets

        helper = turns.AniripsaGrantSummonPipelineTests()
        for spell, profile, actions in (
            (925, 3747, (5024, 8138)),
            (921, 3748, (5023,)),
            (918, 3749, (5021,)),
            (932, 3750, (5026,)),
            (930, 3751, (5025, 5356)),
        ):
            for action in actions:
                with self.subTest(profile=profile, action=action):
                    data, actor_id = self.born(
                        934 if action == 5356 else spell,
                        profile,
                        passives=(912,) if action == 8138 else (),
                        seed_cell=(-7, -7, -1) if action == 5356 else (-6, -7, -1),
                    )
                    character, monster, fight, deck, rng, _ = data
                    # Coherent injury supplies a real healing recipient; no
                    # effect/state or class threshold is inserted.
                    for recipient in (fight.actors[7], fight.actors[actor_id]):
                        set_hp_raw_current(recipient, max(1, recipient.hp // 2))
                    for _ in range(20):
                        if fight.current.id == actor_id:
                            break
                        helper.end_current_turn(fight, data[:5])
                    self.assertEqual(fight.current.id, actor_id)
                    actor = fight.actors[actor_id]
                    uid = next(
                        a["uid"]
                        for a in actor_action_book(actor)["actions"]
                        if a["reference"] == action
                    )
                    _, adapter = server_runtime(
                        character,
                        {-7: monster},
                        deck,
                        action_id=30,
                        critical=False,
                        rng=rng,
                    )

                    def los(origin, target, current):
                        return authoritative_visible(
                            character["map_id"],
                            origin,
                            target,
                            current,
                            blocking_footprints={
                                a.id: {a.position[:2]}
                                for a in current.actors.values()
                                if a.hp > 0
                            },
                        )

                    selection = eligible_cast_targets(
                        fight,
                        character,
                        deck,
                        uid,
                        adapter=adapter,
                        line_of_sight=los,
                        actor_id=actor_id,
                        limit=128,
                        maximum_eligible=16,
                    )
                    self.assertTrue(selection["eligible"], selection)
                    if action == 8138:
                        selection["eligible"] = [{"target": actor.position}]
                    accepted = []
                    failures = []
                    before = snapshot(fight)
                    for candidate in selection["eligible"]:
                        try:
                            tx = prepare_server_spell(
                                struct.pack(
                                    ">qqiih", actor_id, uid, *candidate["target"]
                                ),
                                character,
                                {-7: monster},
                                fight,
                                3,
                                deck,
                                action_id=30,
                                line_of_sight=los,
                                critical=False,
                                rng=rng,
                            )
                        except ValueError as error:
                            if action == 8138:
                                raise
                            failures.append(str(error))
                            continue
                        self.assertEqual(snapshot(fight), before)
                        if any(tx.outcomes):
                            accepted.append(tx)
                            break
                    self.assertTrue(
                        accepted, dict(selection=selection, failures=failures)
                    )
