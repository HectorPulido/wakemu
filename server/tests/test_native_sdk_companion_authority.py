"""Actual owned sidekick admission stays distinct from human SDK authority."""
import copy
import sys
from pathlib import Path
from unittest.mock import patch

_AI = Path(__file__).resolve().parents[1] / "ai-service"
if str(_AI) not in sys.path:
    sys.path.insert(0, str(_AI))

from test_combat_companions_postgres import OwnedCompanionCombatPostgresTests
from wakfu_server.combat_companions import admit_owned_companions, fighter_stats
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_ai.native.native_store import load_authorities
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_ai.native.native_stats import NativeStats


class NativeSDKCompanionAuthorityTests(OwnedCompanionCombatPostgresTests):
    def test_real_admitted_companion_uses_native_source_not_human_character(self):
        # Reuse genuine grant/use/company admission and original bje snapshot,
        # equipment and QI registration, not a manufactured controlled NPC.
        with self.store.connection() as db:
            admitted = admit_owned_companions(
                db, self.store, self.session, self.fight, owner_character=self.main
            )
        fight = admitted["fight"]
        runtime = RuntimeMessages(fight)
        actor = fight.actors[self.companion_id]
        source = fight.native_companion_sources[str(actor.id)]
        self.assertTrue(actor.controlled)
        self.assertFalse(actor.native_controlled_by_ai)
        self.assertEqual(source["native_actor_type"], 5)
        self.assertEqual(source["owner_character_id"], self.main["id"])
        original_character = self.store.character
        character_reads = []

        def character(account_id, character_id, *args, **kwargs):
            character_reads.append(character_id)
            if character_id == self.companion_id:
                raise AssertionError(
                    "A sidekick identity must not enter human hydration"
                )
            return original_character(account_id, character_id, *args, **kwargs)

        with patch.object(self.store, "character", side_effect=character):
            authority = load_authorities(
                runtime, self.store, {-200: self.enemy}, viewer_id=self.main["id"]
            )
        self.assertIn(self.main["id"], character_reads)
        self.assertNotIn(actor.id, character_reads)
        self.assertEqual(set(authority["characters"]), {self.main["id"]})
        self.assertEqual(set(authority["monsters"]), {-200})
        self.assertEqual(set(authority["companions"]), {actor.id})
        self.assertEqual(authority["companions"][actor.id], source)
        self.assertEqual(set(authority["decks"]), {self.main["id"]})
        oracle = NativeOracle(
            runtime,
            characters=authority["characters"],
            monsters=authority["monsters"],
            decks=authority["decks"],
            excluded_decks=authority["excluded_decks"],
            viewer_id=self.main["id"],
            flags={},
        )
        self.assertEqual(oracle.descriptor(fight, actor), source)
        self.assertEqual(oracle.authorities()["companions"][actor.id], source)
        self.assertTrue(oracle.owned_spells(fight, actor.id))
        serializer = NativeStats(
            characters=authority["characters"],
            monsters=authority["monsters"],
            fight_id=fight.id,
            registrations=authority["registrations"],
            map_id=self.main["map_id"],
        )
        self.assertEqual(serializer(actor, fight), fighter_stats(fight, actor))
        candidate = oracle.fork()
        candidate_actor = candidate.fight.actors[actor.id]
        self.assertIsNot(candidate_actor, actor)
        self.assertEqual(oracle.descriptor(candidate.fight, candidate_actor), source)
        self.assertEqual(
            serializer.for_fight(candidate.fight)(candidate_actor, candidate.fight),
            fighter_stats(candidate.fight, candidate_actor),
        )
        self.assertTrue(actor.controlled)
        self.assertEqual(source, fight.native_companion_sources[str(actor.id)])

        # The registration proof remains mandatory; account ownership or a
        # numeric collision cannot turn another source into a sidekick.
        for change in (
            {"account_id": self.account + 1000},
            {"owner_character_id": -200},
            {"native_actor_type": 0},
        ):
            invalid = copy.deepcopy(fight)
            invalid.native_companion_sources[str(actor.id)].update(change)
            with self.assertRaises(ValueError):
                load_authorities(
                    RuntimeMessages(invalid),
                    self.store,
                    {-200: self.enemy},
                    viewer_id=self.main["id"],
                )
        forged = copy.deepcopy(fight)
        forged.native_companion_sources[str(actor.id)]["ref"] = 5525
        with self.assertRaises(ValueError):
            serializer(forged.actors[actor.id], forged)

    def test_descriptor_keeps_player_monster_summon_and_sidekick_sources_distinct(self):
        with self.store.connection() as db:
            admitted = admit_owned_companions(
                db, self.store, self.session, self.fight, owner_character=self.main
            )
        fight = admitted["fight"]
        authority = load_authorities(
            RuntimeMessages(fight),
            self.store,
            {-200: self.enemy},
            viewer_id=self.main["id"],
        )
        oracle = NativeOracle(
            RuntimeMessages(fight),
            characters=authority["characters"],
            monsters=authority["monsters"],
            decks=authority["decks"],
            excluded_decks=authority["excluded_decks"],
            viewer_id=self.main["id"],
            flags={},
        )
        self.assertEqual(
            oracle.descriptor(fight, fight.actors[self.main["id"]]),
            oracle.characters[self.main["id"]],
        )
        self.assertEqual(
            oracle.descriptor(fight, fight.actors[-200]), oracle.monsters[-200]
        )
        self.assertEqual(
            oracle.descriptor(fight, fight.actors[self.companion_id]),
            oracle.companions[self.companion_id],
        )

        # Use the existing actual839 constructor/builder fixture, rather than
        # fabricating a registration merely to reach the SDK summon branch.
        from test_native_recovery_actual839 import Actual839Tests
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        helper = Actual839Tests()
        self.addCleanup(helper.doCleanups)
        from wakfu_server import native_catalog
        from wakfu_server.spell_audit import catalog as published_spell_catalog
        from wakfu_server.combat_static_catalogs import CompiledEffects

        # The older constructor fixture asks for the complete original tree
        # document. Supply the same current published spell records and pinned
        # source effects without rebuilding/decoding its 67MB JSON document.
        published = dict(
            spells=published_spell_catalog()["spells"],
            effects=CompiledEffects.from_published("player").source_effects,
        )
        original_load = native_catalog.load

        def bounded_constructor_source(path):
            if Path(path).name == "spell-effect-trees.json":
                return published
            return original_load(path)

        with patch.object(
            native_catalog, "load", side_effect=bounded_constructor_source
        ):
            summon_fight, handler, _, _ = helper.fixture()
        self.assertTrue(
            handler(
                dict(effect_class=839, parameters=[], target_masks=(None,) * 7),
                {},
                EffectInvocation(388786, 1, -7, 7, (1, 1, 0)),
            )
        )
        summon = summon_fight.actors[902]
        descriptor = oracle.descriptor(summon_fight, summon)
        self.assertEqual(descriptor["id"], summon.id)
        self.assertEqual(descriptor["ref"], 1549)
        self.assertEqual(descriptor["caster_id"], -7)
        forged = copy.deepcopy(summon_fight)
        forged.native_summon_registrations[summon.id]["actor_id"] = summon.id + 1
        with self.assertRaises(ValueError):
            oracle.descriptor(forged, forged.actors[summon.id])
        forged = copy.deepcopy(fight)
        forged.native_companion_sources[str(self.companion_id)]["account_id"] += 1
        with self.assertRaises(ValueError):
            oracle.descriptor(forged, forged.actors[self.companion_id])
