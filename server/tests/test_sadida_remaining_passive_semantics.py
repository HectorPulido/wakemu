"""Owned Sadida passive consumers through real doll, tree and Voodoll casts."""
import os
import unittest

import test_sadida_grant_pipeline as grants
import test_sadida_semantic_qualification as semantic
import test_aniripsa_grant_summon_pipeline as turns

from wakfu_server.combat_diagnostics import combat_diagnostic_scope


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaRemainingPassiveSemanticsTests(unittest.TestCase):
    cast = grants.SadidaGrantPipelineTests.cast

    def fixture(self, passives=()):
        return semantic.SadidaSemanticQualificationTests().fixture_at_distance(
            3, passives=passives
        )

    @staticmethod
    def adopt(data, fight):
        return (*data[:2], fight, *data[3:])

    @staticmethod
    def profile_actors(fight, profile):
        from wakfu_server.combat_summon_spellbook import actor_action_book

        return [
            actor
            for actor in fight.actors.values()
            if getattr(actor, "native_summon_source", None)
            and actor.hp > 0
            and actor_action_book(actor)["profile"] == profile
        ]

    @staticmethod
    def contributions(fight, reference, target_id):
        from wakfu_server.combat_effect_removal import _identity_fields

        return [
            row
            for row in fight.owned_stat_effects.values()
            if row["target_id"] == target_id
            and _identity_fields(bytes.fromhex(row["payload"])).get(3) == reference
        ]

    def seed_transform(self, data, spell):
        seed = self.cast(data, 8137, target=(-7, -7, -1))
        data = self.adopt(data, seed.fight)
        cell = next(
            row["cell"]
            for row in seed.fight.native_effect_areas.values()
            if row["reference"] == 1835
        )
        transformed = self.cast(data, spell, target=cell, action_id=11)
        return self.adopt(data, transformed.fight)

    def test_doll_link_adds_native_resistance_to_real_owned_doll_only(self):
        # State8200 ->379540 checks916, then379541 gains100 RES_IN_PERCENT27.
        observations = {}
        for equipped in (False, True):
            data = self.fixture((916,) if equipped else ())
            enemy_before = dict(data[2].actors[-7].effect_stats)
            trace = []
            with combat_diagnostic_scope(lambda **row: trace.append(row), limit=8192):
                data = self.seed_transform(data, 921)
            dolls = self.profile_actors(data[2], 3748)
            self.assertEqual(len(dolls), 1, trace)
            doll = dolls[0]
            rows = self.contributions(data[2], 379541, doll.id)
            self.assertEqual(
                sum(row["actual"] for row in rows), 100 if equipped else 0, trace
            )
            self.assertTrue(all(row["stat_id"] == 27 for row in rows), rows)
            observations[equipped] = doll.effect_stats[27]
            self.assertEqual(data[2].actors[-7].effect_stats, enemy_before)
            self.assertFalse(self.contributions(data[2], 379541, 7))
        self.assertEqual(observations[True] - observations[False], 100)

    def test_wild_whispers_changes_actual_voodoll_replacement_and_property(self):
        import random
        import struct
        import test_combat_aptitude_healing_runtime as allies
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.fight_checkpoint_store import snapshot

        allies.AptitudeHealingRuntimeTests.setUpClass()
        for equipped in (False, True):
            with self.subTest(passive=equipped):
                (
                    fight,
                    characters,
                    monster,
                    decks,
                ) = allies.AptitudeHealingRuntimeTests().fixture(
                    active_spells=(914,),
                    passive_spells=(5058,) if equipped else (),
                    injury=0,
                    level=200,
                    caster_breed=10,
                    caster_aptitudes=(),
                    enemy_position=(-5, -7, -1),
                    second_player_position=(-6, -7, -1),
                    third_player_position=(-8, -1, -1),
                    compact_arena=False,
                )
                identity = granted_spells(fight, 7)[926]["uid"]

                def cast_on(current, target_id, action_id):
                    before = snapshot(current)
                    tx = prepare_server_spell(
                        struct.pack(
                            ">qqiih", 7, identity, *current.actors[target_id].position
                        ),
                        characters[7],
                        {-7: monster},
                        current,
                        3,
                        decks[7],
                        action_id=action_id,
                        critical=False,
                        rng=random.Random(17),
                        player_characters=characters,
                        deck_blobs=decks,
                        line_of_sight=lambda origin, destination, preview: authoritative_visible(
                            characters[7]["map_id"],
                            origin,
                            destination,
                            preview,
                            blocking_footprints={
                                a.id: {a.position[:2]}
                                for a in preview.actors.values()
                                if a.hp > 0
                            },
                        ),
                    )
                    self.assertEqual(snapshot(current), before)
                    self.assertTrue(any(tx.outcomes))
                    return tx

                # Native926 requires distinct player-character recipients at
                # range2–6; the prior linked target has3856/3857.
                first = cast_on(fight, 8, 10)
                first_dolls = self.profile_actors(first.fight, 3745)
                self.assertEqual(len(first_dolls), 1)
                first_id = first_dolls[0].id
                from wakfu_server.combat_runtime_messages import RuntimeMessages
                from wakfu_server.combat_server_spell import (
                    prepare_server_turn_end,
                    prepare_server_turn_start,
                    server_runtime,
                )
                from combat_audit_turns import advance_actual_turn

                current = first.fight
                rng = random.Random(17)
                providers = dict(player_characters=characters, deck_blobs=decks)
                runtime = RuntimeMessages(
                    current,
                    turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                        characters[7],
                        {-7: monster},
                        preview,
                        decks[7],
                        rng=rng,
                        **providers,
                        **boundary
                    ),
                    turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                        characters[7],
                        {-7: monster},
                        preview,
                        decks[7],
                        rng=rng,
                        area_callbacks=True,
                        **providers,
                        **boundary
                    ),
                    expiration_runtime_factory=lambda *, action_id: server_runtime(
                        characters[7],
                        {-7: monster},
                        decks[7],
                        action_id=action_id,
                        critical=False,
                        rng=rng,
                        **providers
                    )[0],
                )
                trace = []
                # Respect the native926 interval through actual owned/NPC
                # turn boundaries, preserving the first link throughout.
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=8192
                ):
                    second = None
                    for attempt in range(5):
                        try:
                            second = cast_on(current, 9, 12 + attempt)
                            break
                        except ValueError as error:
                            if (
                                str(error)
                                != "Native spell cast interval has not elapsed"
                            ):
                                raise
                        old_turn = current.turn_id
                        for _ in range(30):
                            advance_actual_turn(runtime)
                            if current.current.id == 7 and current.turn_id != old_turn:
                                break
                        else:
                            self.fail("Actual player turn did not return")
                        if attempt == 0:
                            from wakfu_server.combat_movement_runtime import (
                                apply_client,
                            )
                            from wakfu_server.combat_actor import actual_actor_stats
                            from wakfu_server.combat_area_transaction import (
                                prepare_area_movement,
                            )

                            # Native926 uses a relative constructor cell. A new
                            # owner cell prevents reusing the prior doll's cell.
                            apply_client(
                                runtime,
                                3,
                                struct.pack(">qiih", 7, -8, -6, -1),
                                lambda actor: actual_actor_stats(
                                    characters[7],
                                    actor,
                                    current.id,
                                    wp_current=actor.effect_stats[4],
                                    wp_maximum=actor.effect_maxima[4],
                                ),
                                area_provider=lambda preview, **boundary: prepare_area_movement(
                                    characters[7],
                                    {-7: monster},
                                    preview,
                                    decks[7],
                                    rng=rng,
                                    **providers,
                                    **boundary
                                ),
                            )
                    self.assertIsNotNone(second, "Native926 interval did not elapse")
                live = self.profile_actors(second.fight, 3745)
                self.assertEqual(
                    len(live),
                    2 if equipped else 1,
                    {
                        "actors": [
                            {
                                "id": a.id,
                                "hp": a.hp,
                                "max_hp": a.max_hp,
                                "states": [e.reference for e in a.state_ledger.entries],
                                "source": getattr(a, "native_summon_source", None),
                            }
                            for a in second.fight.actors.values()
                        ],
                        "trace": trace,
                    },
                )
                self.assertEqual(first_id in {actor.id for actor in live}, equipped)
                for doll in live:
                    count = doll.native_fight_property_counts.get(11, 0)
                    self.assertEqual(
                        count > 0, equipped, doll.native_fight_property_counts
                    )
                self.assertFalse(
                    any(
                        row.get("effect_reference") == 379564
                        and row.get("status") == "completed"
                        for row in trace
                    )
                )

    def next_player_turn_with_areas(self, data):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from combat_audit_turns import advance_actual_turn

        character, monster, fight, deck, rng, _ = data
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                character, {-7: monster}, preview, deck, rng=rng, **boundary
            ),
            turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                character,
                {-7: monster},
                preview,
                deck,
                rng=rng,
                area_callbacks=True,
                **boundary
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                critical=False,
                rng=rng,
            )[0],
        )
        previous = fight.turn_id
        for _ in range(20):
            advance_actual_turn(runtime)
            if (
                fight.current is not None
                and fight.current.id == 7
                and fight.turn_id != previous
            ):
                return
        self.fail("Actual owned turn did not return with native area callbacks")

    def test_understanding_ground_selects_native_tree_area_and_resistance(self):
        observations = {}
        for equipped in (False, True):
            with self.subTest(passive=equipped):
                data = self.fixture((7053,) if equipped else ())
                before = data[2].actors[7].effect_stats[27]
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=8192
                ):
                    data = self.seed_transform(data, 8137)
                    self.next_player_turn_with_areas(data)
                areas = {
                    row["reference"] for row in data[2].native_effect_areas.values()
                }
                self.assertIn(1850 if equipped else 1836, areas, trace)
                self.assertNotIn(1836 if equipped else 1850, areas)
                # Owned tree area applies8226; its379648 ->379649 grants50
                # resistance only when7053 is actually in the owner's deck.
                rows = self.contributions(data[2], 379649, 7)
                self.assertEqual(
                    sum(row["actual"] for row in rows), 50 if equipped else 0, trace
                )
                observations[equipped] = data[2].actors[7].effect_stats[27] - before
        self.assertEqual(observations[True] - observations[False], 50)

    def test_sylvan_gift_reaches_native_tree_hp_setter_without_enabling_false_heal(
        self,
    ):
        from unittest.mock import patch
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        observations = {}
        for equipped in (False, True):
            with self.subTest(passive=equipped):
                data = self.fixture((917,) if equipped else ())
                records = []
                execute = EffectDispatcher.execute

                def observe(dispatcher, invocation, **kwargs):
                    result = execute(dispatcher, invocation, **kwargs)
                    if invocation.reference in (379668, 379665):
                        records.append(
                            (
                                invocation.reference,
                                invocation.level,
                                invocation.target_id,
                                result,
                            )
                        )
                    return result

                with patch.object(EffectDispatcher, "execute", observe):
                    data = self.seed_transform(data, 8137)
                trees = self.profile_actors(data[2], 5577)
                self.assertEqual(len(trees), 1, records)
                tree = trees[0]
                applied = [row for row in records if row[0] == 379668 and row[3]]
                self.assertEqual(bool(applied), equipped, records)
                if equipped:
                    self.assertEqual({row[2] for row in applied}, {tree.id}, records)
                    # Native eYO16 amount is1+0.5*the actual inherited913
                    # level; second parameter1 sets maximum as well as HP.
                    expected = int(1 + 0.5 * applied[-1][1])
                    self.assertEqual(tree.hp, expected, records)
                    self.assertEqual(tree.max_hp, expected, records)
                self.assertFalse(
                    any(ref == 379665 and result for ref, _, _, result in records),
                    records,
                )
                observations[equipped] = (tree.hp, tree.max_hp)
        self.assertNotEqual(observations[True], observations[False])
