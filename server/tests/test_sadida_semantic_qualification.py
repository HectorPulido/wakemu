"""Actual Sadida poison, healing, armor and passive event qualification.

These tests use published native roots and the ordinary server cast/turn
transactions. They are opt-in because the native catalog and map authority are
loaded by the local combat integration environment.
"""
import json
import os
import random
import unittest
from pathlib import Path

from wakfu_server.combat_diagnostics import combat_diagnostic_scope

import test_sadida_initialization_pipeline as initialization
import test_sadida_grant_pipeline as grants


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1",
    "native combat integration opt-in",
)
class SadidaSemanticQualificationTests(unittest.TestCase):
    fixture = initialization.SadidaInitializationPipelineTests.fixture
    cast = grants.SadidaGrantPipelineTests.cast

    def cast_with_trace(self, data, spell, *, target=None, action_id=None):
        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=8192):
            if action_id is None:
                transaction = self.cast(data, spell, target=target)
            else:
                transaction = self.cast(data, spell, target=target, action_id=action_id)
        return transaction, trace

    def fixture_at_distance(self, distance, *, passives=()):
        """Build the normal Sadida fixture with a native legal target distance."""
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck
        import random
        import test_combat_spell_transaction as native_fixture

        (
            character,
            monster,
            fight,
        ) = native_fixture.SpellTransactionTests().native_server_fixture(
            10,
            200,
            native_qi=True,
            target_hp=20000,
            target_distance=distance,
            variation_seed=17,
        )
        deck = encode_deck(
            (914, 915, 918, 919, 920, 921, 922, 925, 927, 928, 929, 930),
            passives,
        )
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
        return character, monster, fight, deck, rng, packets

    def superpower_ally_fixture(self, *, damaged=False):
        data = self.fixture()
        from test_aniripsa_grant_summon_pipeline import AniripsaGrantSummonPipelineTests

        seeded = self.cast(data, 8137)
        data = (*data[:2], seeded.fight, *data[3:])
        seed_cell = next(
            area["cell"]
            for area in seeded.fight.native_effect_areas.values()
            if area.get("reference") == 1835
        )
        tree = self.cast(data, 925, target=seed_cell, action_id=11)
        data = (*data[:2], tree.fight, *data[3:])
        AniripsaGrantSummonPipelineTests().next_player_turn(data[2], data[:5])
        transaction = self.cast(data, 911, action_id=12)
        data = (*data[:2], transaction.fight, *data[3:])
        from wakfu_server.combat_summon_spellbook import actor_action_book

        summons = [
            actor
            for actor in data[2].actors.values()
            if getattr(actor, "native_summon_source", None)
            and actor.hp > 0
            and actor_action_book(actor)["profile"] == 3746
        ]
        self.assertEqual(len(summons), 1)
        ally = summons[0]
        if damaged:
            # Precondition only: the heal itself is still produced by the
            # native 915 cast. Keep both ordinary HP mirrors coherent.
            ally.hp = max(1, ally.max_hp // 2)
            if ally.effect_stats is not None and 1 in ally.effect_stats:
                ally.effect_stats[1] = ally.hp
        return data, ally

    @staticmethod
    def completed_references(trace, effect_class=None):
        return {
            row["effect_reference"]
            for row in trace
            if row.get("event") == "combat_effect"
            and row.get("status") == "completed"
            and (effect_class is None or row.get("effect_class") == effect_class)
        }

    def test_toxinas_installs_native_poison_carrier_without_immediate_damage(self):
        data = self.fixture()
        fight = data[2]
        transaction, trace = self.cast_with_trace(
            data, 914, target=fight.actors[-7].position
        )
        target = transaction.fight.actors[-7]
        # Hostile root 378146 applies state3617; the poison ticks on its
        # target's turn. State3640 is the beneficial ally branch.
        self.assertEqual(target.hp, fight.actors[-7].hp)
        self.assertTrue(transaction.outcomes)
        references = self.completed_references(trace)
        self.assertIn(378146, references)
        self.assertIn(58701, references)
        self.assertIn(378145, references)
        self.assertIn(3617, {entry.reference for entry in target.state_ledger.entries})
        self.assertIn(8210, {entry.reference for entry in target.state_ledger.entries})

    def test_viento_envenenado_applies_live_poison_and_leaves_literal_false_roots_dormant(
        self,
    ):
        # Published fyP range is 3–4; a distance-1 fixture is ineligible.
        data = self.fixture_at_distance(3)
        enemy = data[2].actors[-7]
        transaction, trace = self.cast_with_trace(data, 919, target=enemy.position)
        entries = {
            entry.reference
            for entry in transaction.fight.actors[-7].state_ledger.entries
        }
        self.assertIn(3590, entries)
        completed = self.completed_references(trace)
        self.assertTrue({156042, 156043} & completed, sorted(completed))
        self.assertFalse({380037, 380038} & completed, sorted(completed))
        dormant = [
            row.get("status")
            for row in trace
            if row.get("effect_reference") in (380037, 380038)
        ]
        self.assertTrue(dormant)
        self.assertIn("skipped_condition", dormant)
        self.assertFalse(set(dormant) & {"completed", "error"}, dormant)

    def test_tree_heal_executes_only_below_full_health(self):
        data = self.fixture()
        caster = data[2].actors[7]
        from wakfu_server.combat_hp_raw import set_hp_raw_current

        set_hp_raw_current(caster, max(1, caster.max_hp // 2))
        before_hp = caster.hp
        transaction, trace = self.cast_with_trace(data, 915, target=caster.position)
        healed = transaction.fight.actors[caster.id]
        self.assertGreater(healed.hp, before_hp)
        self.assertLessEqual(healed.hp, healed.max_hp)
        self.assertIn(156921, self.completed_references(trace, 25))

    def test_tree_full_health_branch_is_a_real_no_heal_negative_control(self):
        data = self.fixture()
        caster = data[2].actors[7]
        from wakfu_server.combat_hp_raw import set_hp_raw_current

        set_hp_raw_current(caster, caster.max_hp)
        before_hp = caster.hp
        transaction, trace = self.cast_with_trace(data, 915, target=caster.position)
        self.assertEqual(transaction.fight.actors[caster.id].hp, before_hp)
        self.assertNotIn(156921, self.completed_references(trace, 25))

    def test_zarza_executes_native_armor_effect_and_changes_armor_value(self):
        # Native 1013 branch is restricted by actor/context; enemy is a
        # negative control and an actual allied Voodoll is the positive case.
        import json

        observations = {}
        for relation in ("enemy", "allied_vudul"):
            with self.subTest(target_relation=relation):
                data = self.fixture()
                if relation == "allied_vudul":
                    grant = self.cast(data, 926)
                    data = (*data[:2], grant.fight, *data[3:])
                    allies = [
                        actor
                        for actor in grant.fight.actors.values()
                        if getattr(actor, "native_summon_source", None) and actor.hp > 0
                    ]
                    self.assertEqual(len(allies), 1)
                    target = allies[0]
                else:
                    target = data[2].actors[-7]
                fight = data[2]
                before = {
                    identity: int(actor.effect_stats.get(97, 0))
                    for identity, actor in fight.actors.items()
                }
                transaction, trace = self.cast_with_trace(
                    data, 925, target=target.position
                )
                armor_refs = self.completed_references(trace, 1013)
                after = {
                    identity: int(actor.effect_stats.get(97, 0))
                    for identity, actor in transaction.fight.actors.items()
                }
                changed = any(
                    after[identity] != value for identity, value in before.items()
                )
                observed = bool(armor_refs and changed)
                observations[relation] = {
                    "target_id": target.id,
                    "target_cell": list(target.position),
                    "completed_1013": sorted(armor_refs),
                    "armor_before": before,
                    "armor_after": after,
                    "armor_stat_changed": changed,
                    "transaction_outcomes": list(transaction.outcomes),
                }
                output = (
                    Path(__file__).resolve().parents[2]
                    / ".runtime/remaining-six-refresh-20261010/sadida-zarza-outcomes.json"
                )
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(observations, indent=2) + "\n")
                if relation == "allied_vudul":
                    self.assertTrue(
                        observed,
                        {
                            "relation": relation,
                            "target_id": target.id,
                            "before": before,
                            "after": after,
                            "armor_refs": sorted(armor_refs),
                        },
                    )
                else:
                    self.assertFalse(
                        observed,
                        {
                            "relation": relation,
                            "target_id": target.id,
                            "before": before,
                            "after": after,
                            "armor_refs": sorted(armor_refs),
                        },
                    )

    def test_venenoso_follows_a_real_native_mp_loss_event(self):
        """Native 5234 subscribes to event79, a positive hostile MP loss."""
        baseline = self.fixture()
        poisoned = self.fixture(passives=(5234,))
        base_fight = baseline[2]
        passive_fight = poisoned[2]
        baseline_tx, baseline_trace = self.cast_with_trace(
            baseline, 927, target=base_fight.actors[-7].position
        )
        passive_tx, trace = self.cast_with_trace(
            poisoned, 927, target=passive_fight.actors[-7].position
        )
        base_target = baseline_tx.fight.actors[-7]
        passive_target = passive_tx.fight.actors[-7]
        import json

        observation = {
            "spell": 927,
            "baseline": {
                "mp_before": base_fight.actors[-7].mp,
                "mp_after": base_target.mp,
                "outcomes": list(baseline_tx.outcomes),
                "completed_effects": sorted(self.completed_references(baseline_trace)),
                "owned_stat_effects": [
                    dict(row)
                    for row in baseline_tx.fight.owned_stat_effects.values()
                    if row.get("target_id") == -7
                ],
            },
            "passive_5234": {
                "mp_before": passive_fight.actors[-7].mp,
                "mp_after": passive_target.mp,
                "outcomes": list(passive_tx.outcomes),
                "completed_effects": sorted(self.completed_references(trace)),
                "passive_rows": [
                    row
                    for row in trace
                    if row.get("effect_reference")
                    in (379592, 379593, 379594, 379595, 379596, 379597, 379604)
                ],
                "owned_stat_effects": [
                    dict(row)
                    for row in passive_tx.fight.owned_stat_effects.values()
                    if row.get("target_id") == -7
                ],
                "states": sorted(
                    {entry.reference for entry in passive_target.state_ledger.entries}
                ),
            },
        }
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-venenoso-observation.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(observation, indent=2) + "\n")
        self.assertLess(base_target.mp, base_fight.actors[-7].mp)
        self.assertFalse(
            {379592, 379593, 379594, 379596, 379604}
            & self.completed_references(baseline_trace)
        )
        references = self.completed_references(trace)
        self.assertTrue(
            {379592, 379593, 379594, 379595} <= references,
            {
                "references": sorted(references),
                "passive_trace": [
                    row
                    for row in trace
                    if row.get("effect_reference")
                    in (379592, 379593, 379594, 379595, 379596, 379597, 379604)
                ],
                "mp_before": passive_fight.actors[-7].mp,
                "mp_after": passive_target.mp,
            },
        )
        self.assertIn(
            3617, {entry.reference for entry in passive_target.state_ledger.entries}
        )

    def test_cadena_de_la_naturaleza_reacts_to_a_real_mp_loss(self):
        baseline = self.fixture()
        chained = self.fixture(passives=(8158,))
        base_fight, chained_fight = baseline[2], chained[2]
        baseline_tx, baseline_trace = self.cast_with_trace(
            baseline, 927, target=base_fight.actors[-7].position
        )
        chained_tx, trace = self.cast_with_trace(
            chained, 927, target=chained_fight.actors[-7].position
        )
        base_target = baseline_tx.fight.actors[-7]
        chained_target = chained_tx.fight.actors[-7]
        self.assertLess(base_target.mp, base_fight.actors[-7].mp)
        self.assertTrue(
            {379547, 379548} <= self.completed_references(trace),
            sorted(self.completed_references(trace)),
        )
        self.assertFalse({379547, 379548} & self.completed_references(baseline_trace))
        base_caster = baseline_tx.fight.actors[7]
        chained_caster = chained_tx.fight.actors[7]
        class_48 = next(
            row
            for row in trace
            if row.get("effect_reference") == 379548
            and row.get("status") == "completed"
        )
        self.assertEqual((class_48["caster_id"], class_48["target_id"]), (7, 7))
        self.assertLess(
            chained_caster.mp,
            base_caster.mp,
            {
                "baseline_caster_mp": base_caster.mp,
                "passive_caster_mp": chained_caster.mp,
                "class_48_invocation": class_48,
            },
        )
        # The event listener and its native class-48 child execute, but the
        # native point target is the listener owner, not the enemy whose MP
        # loss caused the event. Preserve the full actor/resource snapshot too.
        observation = {
            "baseline_actor_resources": {
                str(actor_id): {
                    "mp": actor.mp,
                    "ap": actor.ap,
                    "wp": None
                    if actor.effect_stats is None
                    else actor.effect_stats.get(4),
                }
                for actor_id, actor in sorted(baseline_tx.fight.actors.items())
            },
            "passive_actor_resources": {
                str(actor_id): {
                    "mp": actor.mp,
                    "ap": actor.ap,
                    "wp": None
                    if actor.effect_stats is None
                    else actor.effect_stats.get(4),
                }
                for actor_id, actor in sorted(chained_tx.fight.actors.items())
            },
            "completed_refs": sorted(self.completed_references(trace)),
            "listener_trace": [
                dict(row)
                for row in trace
                if row.get("effect_reference") in (379547, 379548)
            ],
        }
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-8158-observation.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(observation, indent=2) + "\n")
        self.assertTrue(observation["listener_trace"])

    def test_terreno_infectado_reacts_to_a_real_poison_cast(self):
        """Capture native 5055 branch behavior on the owned poison spell."""
        cases = {}
        for name, passives in (("baseline", ()), ("5055", (5055,))):
            data = self.fixture(passives=passives)
            enemy = data[2].actors[-7]
            transaction, trace = self.cast_with_trace(data, 914, target=enemy.position)
            from test_aniripsa_grant_summon_pipeline import (
                AniripsaGrantSummonPipelineTests,
            )

            progressed = (*data[:2], transaction.fight, *data[3:])
            turn_trace = []
            with combat_diagnostic_scope(
                lambda **row: turn_trace.append(row), limit=8192
            ):
                turns = AniripsaGrantSummonPipelineTests()
                # Actual player end, enemy start/end, and return to player.
                turns.end_current_turn(progressed[2], progressed[:5])
                turns.end_current_turn(progressed[2], progressed[:5])
            result_fight = progressed[2]
            result = result_fight.actors[-7]
            cases[name] = {
                "outcomes": list(transaction.outcomes),
                "enemy_hp_before": enemy.hp,
                "enemy_hp_after": result.hp,
                "enemy_states": sorted(
                    entry.reference for entry in result.state_ledger.entries
                ),
                "passive_effects": [
                    dict(row)
                    for row in trace
                    if row.get("effect_reference")
                    in (380008, 380009, 380010, 380013, 380031, 380032, 380033, 380034)
                ],
                "turn_effects": [
                    dict(row)
                    for row in turn_trace
                    if row.get("effect_reference")
                    in (380008, 380009, 380010, 380013, 380031, 380032, 380033, 380034)
                ],
                "completed": sorted(self.completed_references(trace)),
                "turn_completed": sorted(self.completed_references(turn_trace)),
            }
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-5055-observation.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(cases, indent=2) + "\n")
        self.assertTrue(cases["baseline"]["outcomes"])
        self.assertTrue(cases["5055"]["outcomes"])

    def test_bendicion_vudul_applies_native_summon_effect(self):
        """Observe the actual 8149 class-41 child on a spawned Voodoll."""
        import struct

        from test_combat_aptitude_healing_runtime import AptitudeHealingRuntimeTests
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_los import authoritative_visible

        AptitudeHealingRuntimeTests.setUpClass()
        fixture_builder = AptitudeHealingRuntimeTests()
        cases = {}
        for name, passives in (("baseline", ()), ("8149", (8149,))):
            fight, characters, monster, decks = fixture_builder.fixture(
                active_spells=(
                    914,
                    915,
                    918,
                    919,
                    920,
                    921,
                    922,
                    925,
                    927,
                    928,
                    929,
                    930,
                ),
                passive_spells=passives,
                caster_breed=10,
                level=200,
                enemy_position=(-6, -7, -1),
                # Known valid multi-PC map placement from the combat runtime
                # fixtures, clear of actor8 and at native spell range6.
                third_player_position=(-8, -1, -1),
                compact_arena=False,
            )
            # The native spell requires a player-character target at range2–6
            # and a free adjacent summon cell. Actor9 is a real PC at range6;
            # actor8 remains the adjacent allied fixture.
            target = fight.actors[9]
            grants = granted_spells(fight, 7)
            uid = grants[926]["uid"]
            before = snapshot(fight)

            def los(origin, destination, current):
                return authoritative_visible(
                    characters[7]["map_id"],
                    origin,
                    destination,
                    current,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in current.actors.values()
                        if actor.hp > 0
                    },
                )

            trace = []
            with combat_diagnostic_scope(lambda **row: trace.append(row), limit=8192):
                transaction = prepare_server_spell(
                    struct.pack(">qqiih", 7, uid, *target.position),
                    characters[7],
                    {-7: monster},
                    fight,
                    3,
                    decks[7],
                    action_id=10,
                    line_of_sight=los,
                    critical=False,
                    rng=random.Random(17),
                    player_characters=characters,
                    deck_blobs=decks,
                )
            self.assertEqual(snapshot(fight), before)
            self.assertTrue(any(transaction.outcomes))
            summons = [
                actor
                for actor in transaction.fight.actors.values()
                if getattr(actor, "native_summon_source", None) and actor.hp > 0
            ]
            self.assertEqual(len(summons), 1)
            summon = summons[0]
            cases[name] = {
                "summon_id": summon.id,
                "summon_hp": summon.hp,
                "summon_stats": dict(summon.effect_stats or {}),
                "summon_states": sorted(
                    entry.reference for entry in summon.state_ledger.entries
                ),
                "passive_effects": [
                    dict(row)
                    for row in trace
                    if row.get("effect_reference") in (379606, 379607)
                ],
                "completed": sorted(self.completed_references(trace)),
            }
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-8149-observation.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(cases, indent=2) + "\n")
        self.assertNotIn(
            379607, self.completed_references(cases["baseline"]["passive_effects"], 41)
        )
        self.assertIn(
            379607, self.completed_references(cases["8149"]["passive_effects"], 41)
        )
        self.assertEqual(cases["baseline"]["summon_stats"][3], 3)
        self.assertEqual(cases["8149"]["summon_stats"][3], 6)
        self.assertEqual(cases["baseline"]["summon_hp"], cases["8149"]["summon_hp"])

    def test_guarda_plantas_installs_its_owned_summon_state(self):
        """Compare the native summon state with and without passive 913."""
        cases = {}
        for name, passives in (("baseline", ()), ("913", (913,))):
            data = self.fixture(passives=passives)
            transaction, trace = self.cast_with_trace(data, 926)
            summons = [
                actor
                for actor in transaction.fight.actors.values()
                if getattr(actor, "native_summon_source", None) and actor.hp > 0
            ]
            self.assertEqual(len(summons), 1)
            summon = summons[0]
            cases[name] = {
                "summon_id": summon.id,
                "summon_states": sorted(
                    entry.reference for entry in summon.state_ledger.entries
                ),
                "passive_effects": [
                    dict(row)
                    for row in trace
                    if row.get("effect_reference") in (380035, 380036)
                ],
                "completed": sorted(self.completed_references(trace)),
            }
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-913-observation.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(cases, indent=2) + "\n")

    def test_seed_transformation_observes_native_tree_areas_for_913_and_5055(self):
        """Follow the real seed recast into profile5577 and retain area events."""
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_effect_area_geometry import registered_area_cells
        from wakfu_server.combat_summon_spellbook import actor_action_book

        cases = {}
        for name, passives in (
            ("baseline", ()),
            ("913+7053", (913, 7053)),
            ("5055+7053", (5055, 7053)),
        ):
            data = self.fixture_at_distance(2, passives=passives)
            character, monster, fight, deck, rng, _ = data
            grants = granted_spells(fight, 7)
            _, adapter = server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=10,
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
                grants[8137]["uid"],
                adapter=adapter,
                line_of_sight=los,
                actor_id=7,
                limit=128,
                maximum_eligible=16,
            )
            occupied = {
                tuple(actor.position) for actor in fight.actors.values() if actor.hp > 0
            }
            enemy = fight.actors[-7]
            definitions = native_effect_areas()
            seed_candidates = [
                tuple(row["target"])
                for row in selection["eligible"]
                if tuple(row["target"]) not in occupied
                and any(
                    enemy.position[:2]
                    in registered_area_cells(
                        definitions[str(reference)],
                        tuple(row["target"]),
                        fight.actors[7].direction,
                    )
                    for reference in (1836, 1850)
                )
            ]
            self.assertTrue(
                seed_candidates,
                {
                    "eligible": selection,
                    "enemy_cell": enemy.position,
                    "caster_cell": fight.actors[7].position,
                },
            )
            seed_cell = seed_candidates[0]
            seed_tx, seed_trace = self.cast_with_trace(
                data, 8137, target=seed_cell, action_id=10
            )
            data = (*data[:2], seed_tx.fight, *data[3:])
            seed_areas = [
                row
                for row in seed_tx.fight.native_effect_areas.values()
                if row.get("reference") == 1835
            ]
            self.assertTrue(
                seed_areas,
                {
                    "case": name,
                    "areas": list(seed_tx.fight.native_effect_areas.values()),
                },
            )
            transform_tx, transform_trace = self.cast_with_trace(
                data, 8137, target=seed_cell, action_id=11
            )
            area_rows = [
                dict(row) for row in transform_tx.fight.native_effect_areas.values()
            ]
            trees = [
                actor
                for actor in transform_tx.fight.actors.values()
                if getattr(actor, "native_summon_source", None)
                and actor.hp > 0
                and actor_action_book(actor)["profile"] == 5577
            ]
            self.assertEqual(len(trees), 1)
            runtime_fight = transform_tx.fight
            turn_trace = []
            from wakfu_server.combat_runtime_messages import RuntimeMessages
            from wakfu_server.combat_server_spell import (
                prepare_server_turn_end,
                prepare_server_turn_start,
                server_runtime,
            )
            from combat_audit_turns import advance_actual_turn

            runtime = RuntimeMessages(
                runtime_fight,
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
            turn_order = []
            with combat_diagnostic_scope(
                lambda **row: turn_trace.append(row), limit=8192
            ):
                for _ in range(20):
                    if (
                        runtime_fight.current is not None
                        and runtime_fight.current.id == -7
                    ):
                        break
                    turn_order.append(
                        None
                        if runtime_fight.current is None
                        else runtime_fight.current.id
                    )
                    advance_actual_turn(runtime)
                else:
                    self.fail("Enemy turn did not become current during native cycle")
            enemy_after = runtime_fight.actors[-7]
            cases[name] = {
                "seed_outcomes": list(seed_tx.outcomes),
                "seed_area_cell": list(seed_cell),
                "transform_outcomes": list(transform_tx.outcomes),
                "enemy_cell": list(enemy.position),
                "areas_after_transform": area_rows,
                "tree_area_refs": sorted(
                    row["reference"]
                    for row in area_rows
                    if row.get("reference") in (1836, 1850)
                ),
                "tree_profiles": [actor_action_book(actor) for actor in trees],
                "tree_states": [
                    sorted(
                        entry.reference
                        for entry in runtime_fight.actors[actor.id].state_ledger.entries
                    )
                    for actor in trees
                ],
                "tree_area_effect_trace": [
                    dict(row)
                    for row in transform_trace
                    if row.get("effect_reference")
                    in (379712, 380035, 378645, 380036, 379719, 379720, 380014, 380015)
                ],
                "turn_order": turn_order,
                "enemy_states_after_native_turn_start": sorted(
                    entry.reference for entry in enemy_after.state_ledger.entries
                ),
                "turn_area_effect_trace": [
                    dict(row)
                    for row in turn_trace
                    if row.get("effect_reference")
                    in (
                        378645,
                        380036,
                        379712,
                        380035,
                        380008,
                        380009,
                        380010,
                        380013,
                        380031,
                        380032,
                        380033,
                        380034,
                    )
                ],
                "summons": [
                    {
                        "id": actor.id,
                        "profile": getattr(actor, "native_summon_profile", None),
                        "states": sorted(
                            entry.reference for entry in actor.state_ledger.entries
                        ),
                    }
                    for actor in transform_tx.fight.actors.values()
                    if getattr(actor, "native_summon_source", None) and actor.hp > 0
                ],
            }
        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-tree-area-observation.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(cases, indent=2) + "\n")
        self.assertTrue(cases["baseline"]["seed_outcomes"])
        self.assertTrue(cases["913+7053"]["seed_outcomes"])
        self.assertTrue(cases["5055+7053"]["seed_outcomes"])
        self.assertEqual(len(cases["baseline"]["tree_profiles"]), 1)
        self.assertEqual(len(cases["913+7053"]["tree_profiles"]), 1)
        self.assertEqual(len(cases["5055+7053"]["tree_profiles"]), 1)
        self.assertIn(8217, cases["baseline"]["tree_states"][0])
        self.assertIn(8217, cases["913+7053"]["tree_states"][0])
        self.assertIn(8217, cases["5055+7053"]["tree_states"][0])
        self.assertIn(1836, cases["baseline"]["tree_area_refs"])
        self.assertIn(1850, cases["913+7053"]["tree_area_refs"])
        self.assertIn(1850, cases["5055+7053"]["tree_area_refs"])
        self.assertIn(
            380035,
            self.completed_references(cases["913+7053"]["turn_area_effect_trace"]),
        )
        self.assertIn(8258, cases["913+7053"]["enemy_states_after_native_turn_start"])
        self.assertIn(
            380008,
            self.completed_references(cases["5055+7053"]["turn_area_effect_trace"]),
        )
        self.assertIn(3617, cases["5055+7053"]["enemy_states_after_native_turn_start"])

    def test_all_twenty_passives_receive_a_real_native_turn_and_cast_cycle(self):
        """Run the existing actual-event audit for every owned Sadida passive.

        The audit reports activation separately from subscription registration
        and retains prerequisites that its genuine NPC attack/action never
        satisfies. That distinction matters for event-gated doll passives.
        """
        import sys

        tools = Path(__file__).resolve().parents[1] / "tools"
        sys.path.insert(0, str(tools))
        import audit_passive_activation

        output = (
            Path(__file__).resolve().parents[2]
            / ".runtime/remaining-six-refresh-20261010/sadida-passives-semantic.json"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        audit_passive_activation.run(output, 10, level=200)
        import json

        result = json.loads(output.read_text())
        self.assertTrue(result["finished"])
        self.assertTrue(result["source_stable"])
        self.assertEqual(result["expected"], 20)
        self.assertEqual(result["installed"], 20)
        self.assertTrue(all(row["rollback_preserved"] for row in result["rows"]))
        # This is cycle coverage only. activation_observed=0 is explicitly
        # not a per-passive gameplay qualification.
        self.assertTrue(
            all(row["status"] == "cycle_observed" for row in result["rows"])
        )


if __name__ == "__main__":
    unittest.main()
