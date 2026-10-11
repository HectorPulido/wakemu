"""Sadida acquired seed, tree and Voodoll actions through actual native casting."""
import os
import struct
import unittest

import test_sadida_initialization_pipeline as initialization


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaGrantPipelineTests(unittest.TestCase):
    fixture = initialization.SadidaInitializationPipelineTests.fixture

    def cast(self, data, reference, *, target=None, action_id=10):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monster, fight, deck, rng, _ = data
        grants = granted_spells(fight, 7)
        identity = (
            grants[reference]["uid"] if reference in grants else (7 << 32) | reference
        )
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=action_id, critical=False, rng=rng
        )

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

        if target is None:
            selection = eligible_cast_targets(
                fight,
                character,
                deck,
                identity,
                adapter=adapter,
                line_of_sight=los,
                actor_id=7,
                limit=128,
                maximum_eligible=16,
            )
            self.assertTrue(selection["eligible"], selection)
            candidates = selection["eligible"]
            if reference == 8137:
                occupied = {a.position for a in fight.actors.values() if a.hp > 0}
                candidates = [
                    row for row in candidates if tuple(row["target"]) not in occupied
                ]
                self.assertTrue(candidates, selection)
            target = candidates[0]["target"]
        before = snapshot(fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, identity, *target),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=action_id,
            line_of_sight=los,
            critical=False,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertTrue(any(tx.outcomes))
        return tx

    def test_actual_semilla_produces_owned_seed_area(self):
        from wakfu_server.combat_qi_fight import current_registry

        data = self.fixture()
        tx = self.cast(data, 8137)
        self.assertTrue(tx.fight.native_effect_areas)
        areas = list(tx.fight.native_effect_areas.values())
        self.assertTrue(
            any(a.get("reference") == 1835 for a in areas),
            [(a.get("reference"), a.get("caster_id")) for a in areas],
        )
        current_registry(tx.fight)

    def test_actual_vudul_grant_registers_profile_and_native_book(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_summon import fresh_summon_slot_owned
        from wakfu_server.combat_qi_fight import current_registry

        tx = self.cast(self.fixture(), 926)
        actors = [
            a
            for a in tx.fight.actors.values()
            if getattr(a, "native_summon_source", None) and a.hp > 0
        ]
        self.assertEqual(len(actors), 1)
        actor = actors[0]
        self.assertEqual(actor_action_book(actor)["profile"], 3745)
        self.assertEqual(
            {a["reference"] for a in actor_action_book(actor)["actions"]}, {8140}
        )
        self.assertTrue(fresh_summon_slot_owned(tx.fight, actor))
        self.assertEqual(actor.team, tx.fight.actors[7].team)
        self.assertIn(3616, {s.reference for s in actor.state_ledger.entries})
        current_registry(tx.fight)
