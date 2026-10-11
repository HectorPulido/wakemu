"""Owned Drheller death and reinvocation through actual native spell dispatch."""
from copy import deepcopy
import random
import struct
import unittest

import test_enutrof_runtime as enutrof_fixture
import test_combat_spell_transaction as native_fixture
import test_aniripsa_grant_summon_pipeline as lifecycle_fixture
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class EnutrofCompanionLifecycleTests(unittest.TestCase):
    cast = enutrof_fixture.EnutrofRuntimeTests.cast
    fixture = enutrof_fixture.EnutrofRuntimeTests.fixture

    def test_tunnel_passive_reduces_companion_mp_and_teleports_on_real_ore_action(self):
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from class_spell_eligible_targets import eligible_cast_targets

        baseline = self.fixture()
        original = next(
            actor
            for actor in baseline[2].actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        fixture = self.fixture(passives=(8279,), actives=(8240,))
        companion = next(
            actor
            for actor in fixture[2].actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        self.assertEqual(companion.max_mp, original.max_mp - 3)
        deposit = next(
            row
            for row in fixture[2].native_effect_areas.values()
            if row["reference"] == 203 and row["owner_id"] == 7
        )
        consumed = self.cast(fixture, 8240, tuple(deposit["cell"]))
        fixture = (*fixture[:2], consumed.fight, *fixture[3:])
        character, monster, fight, deck, rng = fixture
        helper = lifecycle_fixture.AniripsaGrantSummonPipelineTests()
        for _ in range(20):
            if fight.current.id == companion.id:
                break
            helper.end_current_turn(fight, fixture)
        self.assertEqual(fight.current.id, companion.id)
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=20, critical=False, rng=rng
        )
        candidates = eligible_cast_targets(
            fight,
            character,
            deck,
            3541,
            actor_id=companion.id,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=3,
        )
        self.assertTrue(candidates["eligible"], candidates)
        cell = candidates["eligible"][0]["target"]
        from wakfu_server.combat_server_spell import prepare_server_spell

        tx = prepare_server_spell(
            struct.pack(">qqiih", companion.id, 3541, *cell),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=20,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=rng,
        )
        self.assertTrue(any(tx.outcomes))
        self.assertEqual(tx.fight.actors[companion.id].position, tuple(cell))
        self.assertTrue(
            any(
                row["reference"] == 203
                and row["owner_id"] == 7
                and tuple(row["cell"]) == tuple(cell)
                for row in tx.fight.native_effect_areas.values()
            )
        )

    def test_actual_enemy_spell_death_allows_new_owned_companion(self):
        from pathlib import Path
        import sys

        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_npc_attack import (
            ability,
            npc_runtime_catalog,
            npc_spell_catalog,
        )
        from wakfu_server.monsters import reference

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            3,
            6,
            native_qi=True,
            full_health=True,
            target_level=reference(5525)["max_level"],
            target_distance=1,
            variation_seed=17,
        )
        # The simplified transaction fixture's monster source omits level;
        # preserve the level of its actual native NPC constructor, not a boost.
        monster["level"] = fight.actors[-7].effective_level
        deck, rng = encode_deck((2008,), ()), random.Random(7)
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
        fight, _ = prepare_server_turn_start(
            character,
            {-7: monster},
            fight,
            deck,
            actor_id=fight.current.id,
            action_id=2,
            rng=rng,
            area_callbacks=True,
        )
        companion = next(
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_source", None)
        )
        old_id = companion.id
        rule = ability(monster)
        helper = lifecycle_fixture.AniripsaGrantSummonPipelineTests()
        for attempt in range(32):
            fixture = character, monster, fight, deck, rng
            for _ in range(20):
                if fight.current.id == -7:
                    break
                helper.end_current_turn(fight, fixture)
            self.assertEqual(fight.current.id, -7)
            companion = fight.actors[old_id]
            self.assertEqual(
                sum(
                    abs(fight.current.position[i] - companion.position[i])
                    for i in (0, 1)
                ),
                1,
            )
            before = snapshot(fight)
            preview = deepcopy(fight)
            factory, _ = server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=20 + attempt,
                critical=False,
                rng=rng,
                compiled=npc_runtime_catalog(),
            )
            dispatcher, _ = factory(
                preview,
                dict(
                    actor_id=-7,
                    spell_id=rule["spell_id"],
                    evaluation_level=rule["spell_level"],
                    target_id=old_id,
                    target=companion.position,
                    costs={key: rule[key] for key in ("ap", "mp", "wp")},
                ),
            )
            with preview.effect_resolution():
                for reference in npc_spell_catalog()["spells"][str(rule["spell_id"])][
                    "levels"
                ][rule["spell_level"] - 1][2]:
                    dispatcher.execute(
                        EffectInvocation(
                            reference,
                            rule["spell_level"],
                            -7,
                            old_id,
                            companion.position,
                            native_explicit_target=True,
                        )
                    )
            self.assertEqual(snapshot(fight), before)
            self.assertLess(preview.actors[old_id].hp, companion.hp)
            fight = preview
            if fight.actors[old_id].hp == 0:
                break
            helper.end_current_turn(fight, (character, monster, fight, deck, rng))
        else:
            self.fail(
                "Actual owned enemy attacks did not kill the native companion within32 turns"
            )
        self.assertTrue(getattr(fight, "native_death_event_deliveries", {}))
        fixture = character, monster, fight, deck, rng
        for _ in range(20):
            if fight.current.id == 7:
                break
            helper.end_current_turn(fight, fixture)
        self.assertEqual(fight.current.id, 7)
        uid = granted_spells(fight, 7)[2027]["uid"]
        _, adapter = server_runtime(
            character, {-7: monster}, deck, action_id=40, critical=False, rng=rng
        )
        candidates = eligible_cast_targets(
            fight,
            character,
            deck,
            uid,
            adapter=adapter,
            line_of_sight=lambda *args: True,
            limit=128,
            maximum_eligible=3,
        )
        self.assertTrue(candidates["eligible"], candidates)
        tx = self.cast(fixture, 2027, candidates["eligible"][0]["target"], action_id=40)
        replacements = [
            actor
            for actor in tx.fight.actors.values()
            if getattr(actor, "native_summon_source", None)
            and actor.id != old_id
            and actor.hp > 0
        ]
        self.assertEqual(len(replacements), 1)
        self.assertEqual(replacements[0].owner_id, 3)
        self.assertEqual(replacements[0].native_summon_source["controller_id"], 7)
        snapshot(tx.fight)
