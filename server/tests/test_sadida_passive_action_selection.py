"""Native summon casting-selection changes from Sadida controller passives."""
import os
import random
import unittest

import test_sadida_grant_pipeline as grants
import test_combat_spell_transaction as native_fixture


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaPassiveActionSelectionTests(unittest.TestCase):
    def test_8157_controller_deck_changes_ghulotona_range_table(self):
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            server_runtime,
        )
        from wakfu_server.spells import encode_deck
        from wakfu_server.combat_summon_spellbook import actor_action_book

        observations = {}
        for label, passives in (("baseline", ()), ("8157", (8157,))):
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
            deck = encode_deck((921,), passives)
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
            seeded = grants.SadidaGrantPipelineTests().cast(data, 8137)
            data = (*data[:2], seeded.fight, *data[3:])
            seed = next(
                row
                for row in seeded.fight.native_effect_areas.values()
                if row.get("reference") == 1835
            )
            transformed = grants.SadidaGrantPipelineTests().cast(
                data,
                921,
                target=seed.get("cell", seed.get("position")),
                action_id=11,
            )
            data = (*data[:2], transformed.fight, *data[3:])
            dolls = [
                actor
                for actor in data[2].actors.values()
                if getattr(actor, "native_summon_source", None)
                and actor.hp > 0
                and actor_action_book(actor)["profile"] == 3748
            ]
            self.assertEqual(len(dolls), 1)
            doll_id = dolls[0].id
            character, monster, fight, deck, rng, _ = data
            import test_aniripsa_grant_summon_pipeline as turn_helpers

            helper = turn_helpers.AniripsaGrantSummonPipelineTests()
            for _ in range(20):
                if fight.current is not None and fight.current.id == doll_id:
                    break
                helper.end_current_turn(fight, data[:5])
            self.assertEqual(
                fight.current.id,
                doll_id,
                "The owned Ghulotona must be the real current actor for native cast validation",
            )
            doll = fight.actors[doll_id]
            action = next(
                row
                for row in actor_action_book(doll)["actions"]
                if row["reference"] == 5023
            )
            _, adapter = server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=30,
                critical=False,
                rng=rng,
            )

            def los(origin, destination, current):
                return authoritative_visible(
                    character["map_id"],
                    origin,
                    destination,
                    current,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in current.actors.values()
                        if actor.hp > 0
                    },
                )

            selection = eligible_cast_targets(
                fight,
                character,
                deck,
                action["uid"],
                adapter=adapter,
                line_of_sight=los,
                actor_id=doll_id,
                limit=128,
                maximum_eligible=1,
            )
            diagnosed = [
                row["native_casting_diagnostic"]["selected_casting_flags"]
                for row in selection["rejected"]
                if isinstance(row.get("native_casting_diagnostic"), dict)
                and isinstance(
                    row["native_casting_diagnostic"].get("selected_casting_flags"),
                    dict,
                )
            ]
            if selection["eligible"]:
                diagnosed.extend(
                    row["plan"]["native_casting_flags"]
                    for row in selection["eligible"]
                    if isinstance(row.get("plan", {}).get("native_casting_flags"), dict)
                )
            maxima = sorted({row["maximum"] for row in diagnosed})
            self.assertTrue(
                diagnosed,
                {
                    "status": selection["status"],
                    "doll": doll.position,
                    "rejected": [
                        {
                            "target": row.get("target"),
                            "status": row.get("status"),
                            "reason": row.get("reason"),
                            "native_casting_result": row.get("native_casting_result"),
                            "validation_code": row.get("validation_code"),
                            "authority_unresolved": row.get("authority_unresolved"),
                        }
                        for row in selection["rejected"][:8]
                    ],
                },
            )
            observations[label] = {
                "doll_id": doll_id,
                "doll_cell": list(doll.position),
                "selection_status": selection["status"],
                "maximum_ranges_observed": maxima,
            }
        self.assertIn(3, observations["baseline"]["maximum_ranges_observed"])
        self.assertEqual(observations["8157"]["maximum_ranges_observed"], [5])
