"""Native 5815 Pious fusion admission rejects unsafe one-body executions."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_server.combat_npc_fusion_preflight import (
    FUSION_POLICIES,
    fusion_partner_contract,
    validate_fusion_partner,
)


class NativePiouFusionPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        cls.casting, cls.level_index = native_casting_table(5815, 22)
        cls.roots = tuple(cls.casting["levels"][cls.level_index][2])
        cls.effects = npc_runtime_catalog(imported=True).effects
        cls.monsters = {
            -7: {"id": -7, "ref": 87},
            -8: {"id": -8, "ref": 88},
        }

    def actors(self, *, caster_hp=30, partner_hp=30, partner_id=-8, partner_ref=88):
        caster = SimpleNamespace(
            id=-7,
            team=1,
            hp=caster_hp,
            max_hp=100,
            controlled=False,
            pve_withdrawn=False,
            position=(0, 0, 0),
            physical_radius=0,
            direction=0,
        )
        actors = {-7: caster}
        if partner_id is not None:
            partner = SimpleNamespace(
                id=partner_id,
                team=1,
                hp=partner_hp,
                max_hp=100,
                controlled=False,
                pve_withdrawn=False,
                position=(1, 0, 0),
                physical_radius=0,
                direction=0,
            )
            actors[partner_id] = partner
        monsters = deepcopy(self.monsters)
        if partner_id is not None:
            monsters[partner_id] = {"id": partner_id, "ref": partner_ref}
        return SimpleNamespace(actors=actors), caster, actors.get(partner_id), monsters

    def validate(self, fight, target_id, monsters, **plan_overrides):
        target = fight.actors.get(target_id)
        plan = dict(
            actor_id=-7,
            target_id=target_id,
            spell_id=5815,
            evaluation_level=22,
            target=(0, 0, 0) if target is None else target.position,
        )
        plan.update(plan_overrides)
        return validate_fusion_partner(fight, plan, self.roots, self.effects, monsters)

    def test_published_5815_roots_define_all_four_pio_breeds(self):
        self.assertEqual(FUSION_POLICIES[5815]["health_percent_below"], 50)
        self.assertEqual(
            fusion_partner_contract(self.roots, self.effects),
            frozenset({87, 88, 90, 271}),
        )
        import re

        newborn_by_caster_breed = {}
        for root in self.roots:
            effect = self.effects[str(root)]
            if effect["effect_class"] == 307:
                breed = int(
                    re.fullmatch(r'IsBreedId\("caster",\s*(\d+)\)', effect["criteria"])[
                        1
                    ]
                )
                newborn_by_caster_breed[breed] = int(effect["parameters"][0])
        self.assertEqual(
            newborn_by_caster_breed,
            {87: 1268, 88: 1267, 90: 1269, 271: 1270},
        )

    def test_missing_enemy_dead_controlled_withdrawn_or_same_actor_rejects(self):
        cases = (
            ("lone", None, None, None),
            ("enemy", -8, 0, None),
            ("dead", -8, None, 0),
            ("same actor", -7, None, None),
            ("wrong breed", -8, None, None),
        )
        for label, partner_id, team, hp in cases:
            with self.subTest(label=label):
                fight, caster, partner, monsters = self.actors(
                    partner_id=partner_id,
                    partner_ref=123 if label == "wrong breed" else 88,
                )
                if partner is not None:
                    if team is not None:
                        partner.team = team
                    if hp is not None:
                        partner.hp = hp
                before = deepcopy((fight.actors, monsters))
                with self.assertRaises(ValueError):
                    self.validate(fight, partner_id, monsters)
                self.assertEqual((fight.actors, monsters), before)

    def test_player_or_retired_partner_and_non_piou_ref_reject(self):
        for label, mutate, ref in (
            ("player", lambda actor: setattr(actor, "controlled", True), 88),
            ("withdrawn", lambda actor: setattr(actor, "pve_withdrawn", True), 88),
            ("Piolina", lambda actor: None, 272),
            ("unknown species", lambda actor: None, 999999),
        ):
            with self.subTest(label=label):
                fight, _, partner, monsters = self.actors(partner_ref=ref)
                mutate(partner)
                before = deepcopy((fight.actors, monsters))
                with self.assertRaises(ValueError):
                    self.validate(fight, -8, monsters)
                self.assertEqual((fight.actors, monsters), before)

    def test_odd_maximum_hp_boundary_and_malformed_health_fail_closed(self):
        fight, _, partner, monsters = self.actors()
        partner.max_hp = 153
        partner.hp = 76
        self.assertIsNone(self.validate(fight, -8, monsters))

        partner.hp = 77
        with self.assertRaisesRegex(ValueError, "health threshold"):
            self.validate(fight, -8, monsters)

        partner.hp = True
        with self.assertRaisesRegex(ValueError, "health threshold"):
            self.validate(fight, -8, monsters)

        partner.hp = 30
        partner.max_hp = False
        with self.assertRaisesRegex(ValueError, "health threshold"):
            self.validate(fight, -8, monsters)

    def test_both_partners_must_be_strictly_below_half_health(self):
        for caster_hp, partner_hp in ((50, 30), (30, 50), (50, 50)):
            with self.subTest(caster_hp=caster_hp, partner_hp=partner_hp):
                fight, _, _, monsters = self.actors(
                    caster_hp=caster_hp, partner_hp=partner_hp
                )
                before = deepcopy((fight.actors, monsters))
                with self.assertRaisesRegex(ValueError, "below its health threshold"):
                    self.validate(fight, -8, monsters)
                self.assertEqual((fight.actors, monsters), before)

    def test_valid_same_color_pair_and_mixed_color_pair_are_admitted(self):
        for ref in (87, 88):
            with self.subTest(partner_ref=ref):
                fight, _, _, monsters = self.actors(partner_ref=ref)
                self.assertIsNone(self.validate(fight, -8, monsters))

    def test_policy_rejects_broken_5815_native_recipe_but_other_spells_are_untouched(
        self,
    ):
        fight, _, _, monsters = self.actors()
        broken = tuple(self.roots[:1])
        with self.assertRaisesRegex(ValueError, "recipe contract is unavailable"):
            validate_fusion_partner(
                fight,
                dict(actor_id=-7, target_id=-8, spell_id=5815),
                broken,
                self.effects,
                monsters,
            )
        # The dedicated policy is narrow: an unrelated root set keeps its
        # previous admission behavior.
        self.assertIsNone(
            validate_fusion_partner(
                fight,
                dict(actor_id=-7, target_id=None, spell_id=999999),
                broken,
                self.effects,
                monsters,
            )
        )

    def test_malformed_or_probabilistic_sacrifice_recipe_fails_closed(self):
        for field, value in (
            ("criteria", 'IsBreedId("caster",87)'),
            ("probability_base", 99),
            ("probability_per_level", 1),
            ("area_native", "circle-2"),
            ("native_execution_mode", 1),
            ("parameter_count", 2),
            ("parameters", (0, 0)),
            ("children", [999999]),
            ("maximum_level", 1),
            ("native_target_selector", {"class": "fcE", "mask": 1}),
        ):
            with self.subTest(field=field):
                effects = {
                    str(root): dict(self.effects[str(root)]) for root in self.roots
                }
                first_kill = next(
                    str(root)
                    for root in self.roots
                    if effects[str(root)]["effect_class"] == 28
                    and effects[str(root)]["native_target_selector"]["mask"] == 2
                )
                effects[first_kill][field] = value
                self.assertIsNone(
                    fusion_partner_contract(self.roots, effects, level=22)
                )
                fight, _, _, monsters = self.actors()
                before = deepcopy((fight.actors, monsters))
                with self.assertRaisesRegex(
                    ValueError, "NPC fusion recipe contract is unavailable"
                ):
                    validate_fusion_partner(
                        fight,
                        dict(
                            actor_id=-7,
                            target_id=-8,
                            spell_id=5815,
                            evaluation_level=22,
                            target=(1, 0, 0),
                        ),
                        self.roots,
                        effects,
                        monsters,
                    )
                self.assertEqual((fight.actors, monsters), before)

    def test_valid_partner_identity_cannot_substitute_for_an_empty_point_recipient(
        self,
    ):
        fight, _, _, monsters = self.actors()
        before = deepcopy((fight.actors, monsters))
        with self.assertRaisesRegex(ValueError, "actual native point recipient"):
            validate_fusion_partner(
                fight,
                dict(
                    actor_id=-7,
                    target_id=-8,
                    spell_id=5815,
                    evaluation_level=22,
                    target=(2, 0, 0),
                ),
                self.roots,
                self.effects,
                monsters,
            )
        self.assertEqual((fight.actors, monsters), before)


class NativeNpcRecipientRequirementTests(unittest.TestCase):
    """Classify only actual guaranteed direct point-consumption operands."""

    @classmethod
    def setUpClass(cls):
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        cls.casting, cls.index = native_casting_table(4944, 100)
        cls.roots = tuple(cls.casting["levels"][cls.index][2])
        summon_casting, summon_index = native_casting_table(5815, 22)
        cls.summon_roots = tuple(summon_casting["levels"][summon_index][2])
        cls.effects = npc_runtime_catalog(imported=True).effects

    def test_4944_classifies_only_the_guaranteed_direct_point_kill_root(self):
        from wakfu_server.combat_npc_consumption_preflight import (
            required_recipient_requirements,
        )

        requirements = required_recipient_requirements(
            dict(evaluation_level=100), self.roots, self.effects
        )
        self.assertEqual(
            [
                (row.effect_reference, row.level, row.minimum_count)
                for row in requirements
            ],
            [(154690, 100, 1)],
        )
        # 154688 is a separate self-heal group; its child 154689 heals self.
        self.assertEqual(self.effects["154688"]["effect_class"], 1047)
        self.assertEqual(self.effects["154689"]["effect_class"], 25)

    def test_nonconsuming_self_effect_and_optional_kill_branch_are_not_required(self):
        from wakfu_server.combat_npc_consumption_preflight import (
            required_recipient_requirements,
        )

        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=100), (154688,), self.effects
            ),
            (),
        )
        optional_effects = {}
        optional_effects["154690"] = dict(self.effects["154690"])
        optional_effects["154690"]["probability_base"] = 99
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=100), (154690,), optional_effects
            ),
            (),
        )
        conditional_effects = {}
        conditional_effects["154690"] = dict(self.effects["154690"])
        conditional_effects["154690"]["criteria"] = 'IsBreedId("caster",3735)'
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=100), (154690,), conditional_effects
            ),
            (),
        )
        # Published spell 5601 has a conditional family-28 root against breed
        # 3919; it is deliberately outside the unconditional operand contract.
        conditional_root = self.effects["174976"]
        self.assertEqual(conditional_root["effect_class"], 28)
        self.assertTrue(conditional_root["criteria"].strip())
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=100), (174975, 174976), self.effects
            ),
            (),
        )

    def test_delay_critical_and_caster_bound_kill_variants_are_not_required(self):
        from wakfu_server.combat_npc_consumption_preflight import (
            required_recipient_requirements,
        )

        delayed = {"154690": dict(self.effects["154690"])}
        delayed["154690"]["native_timing_definition"] = dict(
            delayed["154690"]["native_timing_definition"], ryH=1
        )
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=100), (154690,), delayed
            ),
            (),
        )

        critical = {"154690": dict(self.effects["154690"], variant=1)}
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=100), (154690,), critical
            ),
            (),
        )

        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=100),
                (154690,),
                self.effects,
                direct_target_policies={"154690": (28, False, True)},
            ),
            (),
        )

    def test_requirement_rejects_incompatible_catalog_and_level(self):
        from types import SimpleNamespace
        from wakfu_server.combat_npc_consumption_preflight import (
            RequiredRecipientRequirement,
            validate_required_recipients,
        )

        fight = SimpleNamespace()
        plan = dict(evaluation_level=100)
        requirement = RequiredRecipientRequirement(
            154690, 100, source_effects=self.effects
        )
        with self.assertRaisesRegex(ValueError, "Invalid native NPC operand admission"):
            validate_required_recipients(
                fight, plan, SimpleNamespace(effects={}), (requirement,)
            )
        with self.assertRaisesRegex(ValueError, "Invalid native NPC operand admission"):
            validate_required_recipients(
                fight,
                plan,
                SimpleNamespace(effects=self.effects),
                (
                    RequiredRecipientRequirement(
                        154690, 99, source_effects=self.effects
                    ),
                ),
            )

    def test_sealed_point_contract_cache_rebinds_effects_and_bypasses_replaced_getter(
        self,
    ):
        from unittest.mock import patch
        import wakfu_server.combat_npc_consumption_preflight as admission
        import wakfu_server.combat_effect_targets as target_contracts

        key = admission.published_contract_key(self.effects, (154690,), 100)
        self.assertIsNotNone(key, "fixture must use a sealed published effect catalog")
        self.assertEqual(self.effects.representation, "frozen_effect")
        admission._POINT_CONTRACT_CACHE.clear()
        original_builder = admission._uncached_required_recipient_requirements
        with patch.object(
            admission,
            "_uncached_required_recipient_requirements",
            wraps=original_builder,
        ) as builder:
            first = admission.required_recipient_requirements(
                dict(evaluation_level=100), (154690,), self.effects
            )
            second = admission.required_recipient_requirements(
                dict(evaluation_level=100), (154690,), self.effects
            )
        self.assertEqual(
            builder.call_count, 1, "second sealed lookup should hit neutral cache"
        )
        self.assertEqual([item.effect_reference for item in first], [154690])
        self.assertEqual([item.effect_reference for item in second], [154690])
        self.assertIs(first[0].source_effects, self.effects)
        self.assertIs(second[0].source_effects, self.effects)
        self.assertIsNot(
            first[0], second[0], "cache may retain refs, not requirement objects"
        )

        original_getter = target_contracts.native_selector_policy
        with patch.object(
            target_contracts,
            "native_selector_policy",
            wraps=original_getter,
        ) as replaced_getter, patch.object(
            admission,
            "_uncached_required_recipient_requirements",
            wraps=original_builder,
        ) as fallback_builder:
            refreshed = admission.required_recipient_requirements(
                dict(evaluation_level=100), (154690,), self.effects
            )
        self.assertEqual([item.effect_reference for item in refreshed], [154690])
        self.assertGreater(replaced_getter.call_count, 0)
        self.assertEqual(fallback_builder.call_count, 1)

    def test_mutable_and_custom_effect_mappings_never_reuse_stale_contracts(self):
        from collections.abc import Mapping
        from wakfu_server.combat_npc_consumption_preflight import (
            required_recipient_requirements,
        )

        class MutableEffectMapping(Mapping):
            def __init__(self, rows):
                self.rows = rows
                self.lookups = 0

            def __getitem__(self, key):
                return self.rows[key]

            def __iter__(self):
                return iter(self.rows)

            def __len__(self):
                return len(self.rows)

            def get(self, key, default=None):
                self.lookups += 1
                return self.rows.get(key, default)

        source_effect = dict(self.effects["154690"])
        mutable = MutableEffectMapping({"154690": source_effect})
        self.assertEqual(
            [
                row.effect_reference
                for row in required_recipient_requirements(
                    dict(evaluation_level=100), (154690,), mutable
                )
            ],
            [154690],
        )
        first_lookups = mutable.lookups
        source_effect["probability_base"] = 99
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=100), (154690,), mutable
            ),
            (),
        )
        self.assertGreater(mutable.lookups, first_lookups)

    def test_free_cell_307_birth_and_nonpoint_area_are_not_requirements(self):
        from wakfu_server.combat_npc_attack import npc_spell_catalog
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_consumption_preflight import (
            required_recipient_requirements,
        )

        catalog = npc_spell_catalog()
        free_cell = catalog["spells"]["6066"]
        self.assertTrue(free_cell["free_cell"])
        free_roots = tuple(free_cell["levels"][0][2])
        self.assertEqual(free_roots, (196973,))
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=1), free_roots, self.effects
            ),
            (),
        )

        summon_casting, summon_index = native_casting_table(1152, 10)
        self.assertTrue(summon_casting["free_cell"])
        summon_roots = tuple(summon_casting["levels"][summon_index][2])
        self.assertEqual(summon_roots, (10104,))
        self.assertEqual(self.effects["10104"]["effect_class"], 307)
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=10), summon_roots, self.effects
            ),
            (),
        )

        # The 5815 recipe's independent 307 birth root is not a consumption
        # operand; native birth still runs through its ordinary root handling.
        summon_root = next(
            root
            for root in self.summon_roots
            if self.effects[str(root)]["effect_class"] == 307
        )
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=22), (summon_root,), self.effects
            ),
            (),
        )

        # Published 4443 is a real circle-2 area cast. It has no direct point
        # consumption operand, so an empty target coordinate is not globally
        # forbidden by this helper.
        area_casting, area_index = native_casting_table(4443, 150)
        area_roots = tuple(area_casting["levels"][area_index][2])
        self.assertEqual(area_roots, (117188, 117493))
        self.assertTrue(
            all(
                self.effects[str(root)]["area_native"] == "circle-2"
                for root in area_roots
            )
        )
        self.assertEqual(
            required_recipient_requirements(
                dict(evaluation_level=150), area_roots, self.effects
            ),
            (),
        )


class PaidNativePiouFusionTests(unittest.TestCase):
    """Exercise the original 5815 native cast through NPC payment/creation."""

    @staticmethod
    def fight(
        caster_ref=87,
        partner_ref=88,
        monster_level=22,
        partner_level=None,
        enemy_ref=None,
        enemy_level=None,
    ):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_actor_snapshot import (
            build_npc_snapshot,
            build_player_snapshot,
            native_actor_catalog,
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.spells import encode_deck
        from wakfu_server.monsters import owned_instance

        partner_level = monster_level if partner_level is None else partner_level
        enemy_level = monster_level if enemy_level is None else enemy_level

        character, _, old_fight = SpellTransactionTests().native_server_fixture(
            8, 21, native_qi=False
        )
        old_player = old_fight.actors[7]
        player_position = (-8, -7, -1)
        caster_position = (-6, -7, -1)
        partner_position = (-5, -7, -1)
        player = Actor(
            7,
            0,
            player_position,
            old_player.hp,
            old_player.ap,
            old_player.mp,
            old_player.initiative,
            old_player.effective_level,
            old_player.owner_id,
            old_player.controlled,
            max_hp=old_player.max_hp,
        )
        monsters = {
            -7: owned_instance(
                caster_ref, monster_level, -7, map_id=1134, x=-6, y=-7, z=-1
            ),
            -8: owned_instance(
                partner_ref, partner_level, -8, map_id=1134, x=-5, y=-7, z=-1
            ),
        }
        if enemy_ref is not None:
            monsters[-9] = owned_instance(
                enemy_ref, enemy_level, -9, map_id=1134, x=-7, y=-8, z=-1
            )
        caster, partner = (
            Actor(
                identity,
                1,
                tuple(monster[key] for key in ("x", "y", "z")),
                monster["hp"],
                monster["ap"],
                monster["mp"],
                monster["initiative"],
                monster["level"],
                max_hp=monster["max_hp"],
            )
            for identity, monster in (
                (identity, monsters[identity]) for identity in (-7, -8)
            )
        )
        if enemy_ref is not None:
            enemy_data = monsters[-9]
            enemy = Actor(
                -9,
                0,
                tuple(enemy_data[key] for key in ("x", "y", "z")),
                enemy_data["hp"],
                enemy_data["ap"],
                enemy_data["mp"],
                enemy_data["initiative"],
                enemy_data["level"],
                max_hp=enemy_data["max_hp"],
            )
        else:
            enemy = None
        catalog = native_actor_catalog()
        player_snapshot = build_player_snapshot(
            character, player, wp_current=6, wp_maximum=6, running_effects=()
        )
        snapshots = {
            identity: build_npc_snapshot(
                monsters[identity],
                actor,
                wp_current=monsters[identity]["wp"],
                wp_maximum=monsters[identity]["wp"],
                running_effects=(),
            )
            for identity, actor in (
                [(-7, caster), (-8, partner)] + ([] if enemy is None else [(-9, enemy)])
            )
        }
        arena = local_arena(
            1134,
            100,
            player_position,
            [caster_position, partner_position]
            + ([] if enemy is None else [enemy.position]),
            relocate_monsters=False,
            compact=False,
            member_radii=[snapshots[identity].physical_radius for identity in monsters],
            player_radius=player_snapshot.physical_radius,
        )
        fight = Fight(
            100,
            [player, caster, partner] + ([] if enemy is None else [enemy]),
            arena["validated_cells"],
            {
                0: {player.position} | (set() if enemy is None else {enemy.position}),
                1: {caster.position, partner.position},
            },
            arena["valid_edges"],
        )
        fight.native_qi_snapshot = {
            name: arena[name] for name in ("x", "y", "width", "height", "cell_masks")
        }
        fight.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        freeze_terrain(fight)
        fight.native_obstacle_cells = frozenset()
        initialize_global_pv_collections(fight, (7, *monsters))
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots

        initialize_fight_snapshots(
            fight,
            characters={7: character},
            monsters=monsters,
            wp_resources={
                7: (6, 6),
                **{
                    identity: (monster["wp"], monster["wp"])
                    for identity, monster in monsters.items()
                },
            },
            running_effects={7: (), **{identity: () for identity in monsters}},
            initial_effect_uid=1,
        )
        fight.ready(3)
        return character, monsters, fight

    def _paid_5815_case(self, caster_ref, expected_birth_ref):
        import random
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        character, monsters, fight = self.fight(
            caster_ref=caster_ref, partner_ref=caster_ref
        )
        # Apply ordinary dispatched damage to both actual native actors.
        for identity in (-7, -8):
            target = fight.actors[identity]
            fight.apply_effect_damage(7, identity, target.hp - target.max_hp // 3)
            self.assertLess(target.hp * 2, target.max_hp)
        self.assertEqual(fight.current.id, -7)
        caster, partner = fight.actors[-7], fight.actors[-8]
        ap_before, wp_before = caster.ap, caster.effect_stats[4]
        before = snapshot(fight)
        rng = random.Random(5815)
        rng_before = rng.getstate()
        transaction = prepare_npc_spell(
            fight,
            dict(
                type="cast",
                spellId=5815,
                level=22,
                targetId=-8,
                target=list(partner.position),
            ),
            character,
            monsters,
            encode_deck([], []),
            action_id=2,
            rng=rng,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(rng.getstate(), rng_before)
        fresh = set(transaction.fight.actors) - set(fight.actors)
        self.assertEqual(len(fresh), 1)
        newborn = transaction.fight.actors[fresh.pop()]
        self.assertEqual(
            (transaction.fight.actors[-7].hp, transaction.fight.actors[-8].hp), (0, 0)
        )
        self.assertEqual(newborn.native_summon_source["ref"], expected_birth_ref)
        self.assertEqual(newborn.effective_level, newborn.native_summon_source["level"])
        self.assertTrue(
            any(state.reference == 4443 for state in newborn.state_ledger.entries)
        )
        self.assertEqual(newborn.effect_percentages[1], 25)
        from wakfu_server.combat_actor_snapshot import native_actor_catalog
        from wakfu_server.combat_maximum_resource import effective_maximum

        characteristic = native_actor_catalog()["characteristics"]["1"]
        self.assertEqual(
            newborn.max_hp,
            effective_maximum(
                newborn.effect_base_maxima[1],
                25,
                characteristic["hard_minimum"],
                characteristic["hard_maximum"],
            ),
        )
        self.assertEqual(
            transaction.plan["costs"]["ap"],
            7 - (transaction.fight.actors[-7].ap),
        )
        self.assertEqual(
            transaction.fight.actors[-7].ap,
            ap_before - transaction.plan["costs"]["ap"],
        )
        self.assertEqual(
            transaction.fight.actors[-7].effect_stats[4],
            wp_before - transaction.plan["costs"]["wp"],
        )
        self.assertTrue(transaction.packets)

    def test_paid_5815_consumes_two_pious_and_births_each_native_color(self):
        for caster_ref, newborn_ref in (
            (87, 1268),
            (88, 1267),
            (90, 1269),
            (271, 1270),
        ):
            with self.subTest(caster_ref=caster_ref, newborn_ref=newborn_ref):
                self._paid_5815_case(caster_ref, newborn_ref)

    def test_counterfactual_without_admission_guards_reproduces_empty_target_birth(
        self,
    ):
        import random
        from unittest.mock import patch
        import wakfu_server.combat_npc_fusion_preflight as fusion_preflight
        import wakfu_server.combat_npc_consumption_preflight as consumption_preflight
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.spells import encode_deck

        baseline_character, baseline_monsters, baseline_fight = self.fight()
        for identity in (-7, -8):
            target = baseline_fight.actors[identity]
            baseline_fight.apply_effect_damage(
                7, identity, target.hp - target.max_hp // 3
            )
        baseline_occupied = {actor.position for actor in baseline_fight.actors.values()}
        baseline_caster = baseline_fight.actors[-7]
        baseline_empty = min(
            (
                cell
                for cell in baseline_fight.walkable
                if cell not in baseline_occupied
                and cell[2] == baseline_caster.position[2]
                and 0
                < abs(cell[0] - baseline_caster.position[0])
                + abs(cell[1] - baseline_caster.position[1])
                <= 3
            ),
            key=lambda cell: (
                abs(cell[0] - baseline_caster.position[0])
                + abs(cell[1] - baseline_caster.position[1]),
                cell,
            ),
        )
        # Counterfactual baseline: suppress only the new admission gates,
        # leaving published roots, targeting, costs, QI, and paid execution
        # unaltered. This reproduces the original live failure.
        with (
            patch.object(
                fusion_preflight, "validate_fusion_partner", return_value=None
            ),
            patch.object(
                consumption_preflight,
                "validate_npc_consumption_recipients",
                return_value=None,
            ),
        ):
            baseline = prepare_npc_spell(
                baseline_fight,
                dict(
                    type="cast",
                    spellId=5815,
                    level=22,
                    targetId=None,
                    target=list(baseline_empty),
                ),
                baseline_character,
                baseline_monsters,
                encode_deck([], []),
                action_id=2,
                rng=random.Random(5815),
            )
        self.assertIsNone(baseline.plan["target_id"])
        self.assertEqual(baseline.fight.actors[-7].hp, 0)
        self.assertGreater(baseline.fight.actors[-8].hp, 0)
        baseline_births = set(baseline.fight.actors) - set(baseline_fight.actors)
        self.assertEqual(len(baseline_births), 1)
        self.assertEqual(
            baseline.fight.actors[baseline_births.pop()].native_summon_source["ref"],
            1268,
        )

    def test_paid_empty_target_rejects_before_resources_uid_rng_or_events_change(self):
        import random
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        character, monsters, fight = self.fight()
        for identity in (-7, -8):
            target = fight.actors[identity]
            fight.apply_effect_damage(7, identity, target.hp - target.max_hp // 3)
        self.assertEqual(fight.current.id, -7)
        occupied = {actor.position for actor in fight.actors.values()}
        caster = fight.actors[-7]
        empty = min(
            (
                cell
                for cell in fight.walkable
                if cell not in occupied
                and cell[2] == caster.position[2]
                and 0
                < abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1])
                <= 3
            ),
            key=lambda cell: (
                abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1]),
                cell,
            ),
        )
        before = snapshot(fight)
        before_rng = random.Random(5815)
        rng_state = before_rng.getstate()
        try:
            transaction = prepare_npc_spell(
                fight,
                dict(
                    type="cast",
                    spellId=5815,
                    level=22,
                    targetId=None,
                    target=list(empty),
                ),
                character,
                monsters,
                encode_deck([], []),
                action_id=2,
                rng=before_rng,
            )
        except ValueError as error:
            self.assertIn(
                "NPC fusion requires another living allied monster", str(error)
            )
        else:
            self.fail(
                "Empty-cell cast unexpectedly passed fusion preflight: "
                f"target_id={transaction.plan.get('target_id')}, "
                f"fresh={set(transaction.fight.actors) - set(fight.actors)}"
            )
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(before_rng.getstate(), rng_state)

    def test_paid_5815_invalid_health_pair_and_same_actor_preserve_all_state(self):
        import random
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        cases = ("half_health", "wrong_native_pair", "same_actor")
        for case in cases:
            with self.subTest(case=case):
                if case == "wrong_native_pair":
                    character, monsters, fight = self.fight(
                        caster_ref=87,
                        partner_ref=5,
                        monster_level=22,
                        partner_level=10,
                    )
                else:
                    character, monsters, fight = self.fight()
                self.assertEqual(fight.current.id, -7)
                caster, partner = fight.actors[-7], fight.actors[-8]
                if case == "half_health":
                    half_or_more = (caster.max_hp + 1) // 2
                    fight.apply_effect_damage(7, caster.id, caster.hp - half_or_more)
                    fight.apply_effect_damage(
                        7, partner.id, partner.hp - partner.max_hp // 3
                    )
                    target_id, target = -8, partner.position
                elif case == "wrong_native_pair":
                    fight.apply_effect_damage(7, caster.id, caster.hp // 3)
                    fight.apply_effect_damage(7, partner.id, partner.hp // 3)
                    target_id, target = -8, partner.position
                else:
                    fight.apply_effect_damage(7, caster.id, caster.hp // 3)
                    fight.apply_effect_damage(7, partner.id, partner.hp // 3)
                    target_id, target = -7, caster.position
                before = snapshot(fight)
                rng = random.Random(5815)
                rng_before = rng.getstate()
                with self.assertRaises(ValueError):
                    prepare_npc_spell(
                        fight,
                        dict(
                            type="cast",
                            spellId=5815,
                            level=22,
                            targetId=target_id,
                            target=list(target),
                        ),
                        character,
                        monsters,
                        encode_deck([], []),
                        action_id=2,
                        rng=rng,
                    )
                self.assertEqual(snapshot(fight), before)
                self.assertEqual(rng.getstate(), rng_before)


class NativeOraclePiouFusionForecastTests(unittest.TestCase):
    """The AI oracle must apply the same partner admission before forecasting."""

    def _oracle(self, character, monsters, fight):
        from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.spells import encode_deck

        runtime = RuntimeMessages(fight)
        oracle = NativeOracle(
            runtime,
            characters={7: character},
            monsters=monsters,
            decks={7: encode_deck([], [])},
            excluded_decks={7: ()},
            viewer_id=7,
            flags={"native_start_events": True, "native_area_callbacks": True},
        )
        return runtime, oracle

    def test_forecast_valid_partner_and_invalid_empty_cell_share_preflight(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monsters, fight = PaidNativePiouFusionTests.fight()
        for identity in (-7, -8):
            actor = fight.actors[identity]
            fight.apply_effect_damage(7, identity, actor.hp - actor.max_hp // 3)
        self.assertEqual(fight.current.id, -7)
        runtime, oracle = self._oracle(character, monsters, fight)
        partner = fight.actors[-8]
        before = snapshot(fight)
        valid = oracle.cast(
            runtime,
            dict(
                type="cast",
                spellId=5815,
                level=22,
                targetId=-8,
                target=list(partner.position),
            ),
            forecast=True,
        )
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(valid.plan["target_id"], -8)
        self.assertTrue(valid.packets)

        character, monsters, fight = PaidNativePiouFusionTests.fight()
        for identity in (-7, -8):
            actor = fight.actors[identity]
            fight.apply_effect_damage(7, identity, actor.hp - actor.max_hp // 3)
        runtime, oracle = self._oracle(character, monsters, fight)
        occupied = {actor.position for actor in fight.actors.values()}
        caster = fight.actors[-7]
        empty = min(
            (
                cell
                for cell in fight.walkable
                if cell not in occupied
                and cell[2] == caster.position[2]
                and 0
                < abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1])
                <= 3
            ),
            key=lambda cell: (
                abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1]),
                cell,
            ),
        )
        before = snapshot(fight)
        with self.assertRaisesRegex(
            ValueError, "NPC fusion requires another living allied monster"
        ):
            oracle.cast(
                runtime,
                dict(
                    type="cast",
                    spellId=5815,
                    level=22,
                    targetId=None,
                    target=list(empty),
                ),
                forecast=True,
            )
        self.assertEqual(snapshot(fight), before)


class NativeOracleGenericRecipientForecastTests(unittest.TestCase):
    """Generic operands are checked by the AI forecast before any commit."""

    @staticmethod
    def _oracle(character, monsters, fight):
        from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.spells import encode_deck

        runtime = RuntimeMessages(fight)
        oracle = NativeOracle(
            runtime,
            characters={7: character},
            monsters=monsters,
            decks={7: encode_deck([], [])},
            excluded_decks={7: ()},
            viewer_id=7,
            flags={"native_start_events": True, "native_area_callbacks": True},
        )
        return runtime, oracle

    def test_4944_valid_and_empty_target_forecasts_share_operand_gate(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monsters, fight = PaidNativePiouFusionTests.fight(
            caster_ref=3735, partner_ref=87, monster_level=100, partner_level=22
        )
        runtime, oracle = self._oracle(character, monsters, fight)
        player = fight.actors[7]
        before = snapshot(fight)
        valid = oracle.cast(
            runtime,
            dict(
                type="cast",
                spellId=4944,
                level=100,
                targetId=7,
                target=list(player.position),
            ),
            forecast=True,
        )
        self.assertEqual(valid.plan["target_id"], 7)
        self.assertTrue(valid.packets)
        self.assertEqual(snapshot(fight), before)

        character, monsters, fight = PaidNativePiouFusionTests.fight(
            caster_ref=3735, partner_ref=87, monster_level=100, partner_level=22
        )
        runtime, oracle = self._oracle(character, monsters, fight)
        occupied = {actor.position for actor in fight.actors.values()}
        caster = fight.actors[-7]
        empty = min(
            (
                cell
                for cell in fight.walkable
                if cell not in occupied
                and cell[2] == caster.position[2]
                and 0
                < abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1])
                <= 3
            ),
            key=lambda cell: (
                abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1]),
                cell,
            ),
        )
        before = snapshot(fight)
        with self.assertRaisesRegex(
            ValueError, "NPC point consumption requires a native recipient"
        ):
            oracle.cast(
                runtime,
                dict(
                    type="cast",
                    spellId=4944,
                    level=100,
                    targetId=None,
                    target=list(empty),
                ),
                forecast=True,
            )
        self.assertEqual(snapshot(fight), before)


class PaidNativeRecipientRequirementTests(unittest.TestCase):
    """Paid NPC entry applies generic operands before any root or resource cost."""

    def test_null_selector_keeps_full_provider_and_native_caster_center(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        import wakfu_server.combat_runtime_adapter as runtime_adapter
        from test_combat_npc_fusion_preflight import PaidNativePiouFusionTests
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_npc_consumption_preflight import (
            required_recipient_requirements,
            selected_native_recipients,
        )
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.combat_static_catalogs import DefinitionOverlay
        from wakfu_server.spells import encode_deck
        import random

        character, monsters, fight = PaidNativePiouFusionTests.fight(
            caster_ref=3735, partner_ref=87, monster_level=100, partner_level=22
        )
        compiled = npc_runtime_catalog(imported=True)
        factory, _ = server_runtime(
            character,
            monsters,
            encode_deck([], []),
            action_id=2,
            critical=False,
            rng=random.Random(154690),
            compiled=compiled,
        )
        effect = dict(factory.effects["154690"])
        effect["native_target_selector"] = None
        factory_with_null_selector = SimpleNamespace(
            effects=DefinitionOverlay(factory.effects, {"154690": effect}),
            contexts=factory.contexts,
        )
        caster = fight.actors[-7]
        other = fight.actors[-8]
        plan = dict(
            actor_id=caster.id,
            target_id=None,
            target=(other.position[0], other.position[1] - 2, other.position[2]),
            evaluation_level=100,
        )
        requirements = required_recipient_requirements(
            plan, (154690,), factory_with_null_selector.effects
        )
        self.assertEqual(tuple(row.effect_reference for row in requirements), (154690,))

        def must_not_project(*args):
            self.fail("Null-selector policy must use complete native_targets context")

        with patch.object(
            runtime_adapter,
            "native_point_target_projection",
            return_value=must_not_project,
        ):
            selected = selected_native_recipients(
                fight, plan, factory_with_null_selector, 154690, 100
            )
        with patch.object(
            runtime_adapter, "native_point_target_projection", return_value=None
        ):
            full = selected_native_recipients(
                fight, plan, factory_with_null_selector, 154690, 100
            )
        self.assertEqual(tuple(actor.id for actor in selected), (caster.id,))
        self.assertEqual(
            tuple(actor.id for actor in selected), tuple(actor.id for actor in full)
        )

    def test_point_projection_matches_full_provider_for_live_and_corpse_actors(self):
        import random
        from unittest.mock import patch
        import wakfu_server.combat_runtime_adapter as runtime_adapter
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        def cast(*, corpse, full_provider):
            character, monsters, fight = PaidNativePiouFusionTests.fight(
                caster_ref=3735,
                partner_ref=87,
                monster_level=100,
                partner_level=22,
                enemy_ref=5,
                enemy_level=10,
            )
            player = fight.actors[7]
            if corpse:
                fight.apply_effect_damage(7, player.id, player.hp)
                self.assertEqual(player.hp, 0)
            rng = random.Random(4944)
            action = dict(
                type="cast",
                spellId=4944,
                level=100,
                targetId=player.id,
                target=list(player.position),
            )
            if full_provider:
                with patch.object(
                    runtime_adapter, "native_point_target_projection", return_value=None
                ):
                    transaction = prepare_npc_spell(
                        fight,
                        action,
                        character,
                        monsters,
                        encode_deck([], []),
                        action_id=2,
                        rng=rng,
                    )
            else:
                transaction = prepare_npc_spell(
                    fight,
                    action,
                    character,
                    monsters,
                    encode_deck([], []),
                    action_id=2,
                    rng=rng,
                )
            return (
                snapshot(transaction.fight),
                transaction.packets,
                transaction.plan,
                rng.getstate(),
            )

        for corpse in (False, True):
            with self.subTest(corpse=corpse):
                projected = cast(corpse=corpse, full_provider=False)
                full = cast(corpse=corpse, full_provider=True)
                self.assertEqual(projected, full)

    def test_paid_4944_empty_point_rejects_before_self_heal_and_payment(self):
        from unittest.mock import patch
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_npc_consumption_preflight import (
            validate_npc_consumption_recipients,
        )
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        character, monsters, fight = PaidNativePiouFusionTests.fight(
            caster_ref=3735, partner_ref=87, monster_level=100, partner_level=22
        )
        caster = fight.actors[-7]
        fight.apply_effect_damage(7, caster.id, max(1, caster.max_hp // 3))
        occupied = {actor.position for actor in fight.actors.values()}
        empty = min(
            (
                cell
                for cell in fight.walkable
                if cell not in occupied
                and cell[2] == caster.position[2]
                and 0
                < abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1])
                <= 3
            ),
            key=lambda cell: (
                abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1]),
                cell,
            ),
        )
        before = snapshot(fight)
        caster_hp = caster.hp
        caster_ap = caster.ap
        with patch(
            "wakfu_server.combat_npc_consumption_preflight.validate_npc_consumption_recipients",
            wraps=validate_npc_consumption_recipients,
        ) as gate:
            with self.assertRaisesRegex(
                ValueError, "NPC point consumption requires a native recipient"
            ):
                prepare_npc_spell(
                    fight,
                    dict(
                        type="cast",
                        spellId=4944,
                        level=100,
                        targetId=None,
                        target=list(empty),
                    ),
                    character,
                    monsters,
                    encode_deck([], []),
                    action_id=2,
                )
        self.assertEqual(gate.call_count, 1)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual((caster.hp, caster.ap), (caster_hp, caster_ap))

    def test_paid_4944_valid_point_recipient_keeps_full_native_root(self):
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.spells import encode_deck

        character, monsters, fight = PaidNativePiouFusionTests.fight(
            caster_ref=3735, partner_ref=87, monster_level=100, partner_level=22
        )
        caster = fight.actors[-7]
        fight.apply_effect_damage(7, caster.id, max(1, caster.max_hp // 3))
        wounded_caster_hp = caster.hp
        player = fight.actors[7]
        tx = prepare_npc_spell(
            fight,
            dict(
                type="cast",
                spellId=4944,
                level=100,
                targetId=7,
                target=list(player.position),
            ),
            character,
            monsters,
            encode_deck([], []),
            action_id=2,
        )
        self.assertEqual(tx.plan["target_id"], 7)
        self.assertLess(tx.fight.actors[7].hp, player.hp)
        self.assertGreater(tx.fight.actors[-7].hp, wounded_caster_hp)
        self.assertTrue(tx.packets)

    def test_4944_keeps_native_selected_corpse_operand_without_hp_filter(self):
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.spells import encode_deck

        character, monsters, fight = PaidNativePiouFusionTests.fight(
            caster_ref=3735,
            partner_ref=87,
            monster_level=100,
            partner_level=22,
            enemy_ref=5,
            enemy_level=10,
        )
        player = fight.actors[7]
        self.assertEqual(fight.current.id, -7)
        fight.apply_effect_damage(7, player.id, player.hp)
        self.assertEqual(player.hp, 0)
        self.assertEqual(fight.current.id, -7)
        tx = prepare_npc_spell(
            fight,
            dict(
                type="cast",
                spellId=4944,
                level=100,
                targetId=7,
                target=list(player.position),
            ),
            character,
            monsters,
            encode_deck([], []),
            action_id=2,
        )
        self.assertEqual(tx.plan["target_id"], 7)
        self.assertEqual(tx.fight.actors[7].hp, 0)
        self.assertTrue(tx.packets)

    def test_duplicate_qi_and_area_identity_fails_closed_before_payment(self):
        from unittest.mock import patch
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck
        import wakfu_server.combat_effect_area_targets as area_target_module

        character, monsters, fight = PaidNativePiouFusionTests.fight(
            caster_ref=3735, partner_ref=87, monster_level=100, partner_level=22
        )
        player = fight.actors[7]
        before = snapshot(fight)
        with patch.object(area_target_module, "area_targets", return_value=(player,)):
            with self.assertRaisesRegex(
                ValueError, "Duplicate runtime actor identities"
            ):
                prepare_npc_spell(
                    fight,
                    dict(
                        type="cast",
                        spellId=4944,
                        level=100,
                        targetId=7,
                        target=list(player.position),
                    ),
                    character,
                    monsters,
                    encode_deck([], []),
                    action_id=2,
                )
        self.assertEqual(snapshot(fight), before)

    def test_registered_qf_without_hp_is_native_eligible_point_recipient(self):
        """A published Qq is selected from native PV metadata, without HP."""
        import random
        from test_combat_fake_fighter_area import NativeFakeFighterAreaTests
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_npc_consumption_preflight import (
            required_recipient_requirements,
            selected_native_recipients,
            validate_required_recipients,
        )
        from test_combat_npc_fusion_preflight import PaidNativePiouFusionTests
        from wakfu_server.combat_server_spell import server_runtime
        from wakfu_server.spells import encode_deck

        character, monsters, fight = PaidNativePiouFusionTests.fight(
            caster_ref=3735, partner_ref=87, monster_level=100, partner_level=22
        )
        caster = fight.actors[-7]
        # Create a published faW whose native bcR is true, using the real
        # constructor, definition, and NativeQIRegistry registration producer.
        area_tests = NativeFakeFighterAreaTests()
        _, handler, allocated, _ = area_tests.create()
        handler.fight = fight
        empty = next(
            cell
            for cell in sorted(fight.walkable)
            if cell not in {actor.position for actor in fight.actors.values()}
            and cell[2] == caster.position[2]
        )
        handler(
            {"effect_class": 339},
            {"parameters": [1150]},
            EffectInvocation(100, 1, caster.id, None, empty),
        )
        self.assertEqual(allocated, [901, 902])
        area = next(
            iter(
                __import__(
                    "wakfu_server.combat.combat_effect_area_targets",
                    fromlist=["area_targets"],
                ).area_targets(fight)
            )
        )
        self.assertFalse(hasattr(area, "hp"))
        self.assertEqual(area.position, empty)

        compiled = npc_runtime_catalog(imported=True)
        factory, _ = server_runtime(
            character,
            monsters,
            encode_deck([], []),
            action_id=2,
            critical=False,
            rng=random.Random(4944),
            compiled=compiled,
        )
        roots = (154690,)
        plan = dict(
            actor_id=caster.id,
            target_id=None,
            target=empty,
            evaluation_level=100,
        )
        requirements = required_recipient_requirements(plan, roots, factory.effects)
        self.assertEqual(len(requirements), 1)
        selected = selected_native_recipients(fight, plan, factory, 154690, 100)
        self.assertEqual(
            tuple(actor.id for actor in selected),
            (area.id,),
            msg=(
                str(compiled.effects["154690"].get("native_target_selector"))
                + " "
                + str(area)
            ),
        )
        self.assertEqual(
            validate_required_recipients(fight, plan, factory, requirements),
            ((154690, (area.id,)),),
        )
        from dataclasses import replace
        from types import SimpleNamespace
        from unittest.mock import patch
        import wakfu_server.combat_runtime_adapter as runtime_adapter

        native_point_target_projection = runtime_adapter.native_point_target_projection

        self.assertIsNotNone(
            native_point_target_projection(factory.contexts.native_targets)
        )
        native_provider = factory.contexts.native_targets
        adapter_owner = native_provider.__self__
        for method_name in ("targets", "_actor", "projected_targets"):
            with self.subTest(instance_override=method_name):
                with patch.object(adapter_owner, method_name, lambda *args: {}):
                    self.assertIsNone(native_point_target_projection(native_provider))
        custom_calls = []

        def custom_provider(*args):
            custom_calls.append(args)
            return native_provider(*args)

        custom_factory = SimpleNamespace(
            effects=factory.effects,
            contexts=replace(factory.contexts, native_targets=custom_provider),
        )
        self.assertIsNone(native_point_target_projection(custom_provider))
        full_provider_selected = selected_native_recipients(
            fight, plan, custom_factory, 154690, 100
        )
        self.assertEqual(len(custom_calls), 1)
        self.assertEqual(
            tuple(actor.id for actor in full_provider_selected),
            tuple(actor.id for actor in selected),
        )
        from wakfu_server.combat_effect_area import remove_owned_hour_area

        remove_owned_hour_area(fight, area.id)
        after_removal = selected_native_recipients(fight, plan, factory, 154690, 100)
        self.assertNotIn(area.id, {actor.id for actor in after_removal})

    def test_paid_ordinary_307_summon_accepts_native_empty_cell(self):
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_qi_snapshot import NativeQISnapshot
        from wakfu_server.combat_qi_surface_catalog import native_qi_surfaces
        from wakfu_server.spells import encode_deck

        character, monsters, fight = PaidNativePiouFusionTests.fight(
            caster_ref=5, partner_ref=5, monster_level=10, partner_level=10
        )
        self.assertEqual(fight.current.id, -7)
        casting, _ = native_casting_table(1152, 10)
        self.assertTrue(casting["free_cell"])
        self.assertEqual(self._native_root_class(10104), 307)
        occupied = {actor.position for actor in fight.actors.values()}
        caster = fight.actors[-7]
        terrain = NativeQISnapshot(fight.native_qi_snapshot)
        surfaces = native_qi_surfaces(1134)
        blockers = {
            actor.id: footprint(actor.position, actor.physical_radius)
            for actor in fight.actors.values()
            if actor.hp > 0
        }
        empty = min(
            (
                cell
                for cell in fight.walkable
                if cell not in occupied
                and cell[2] == caster.position[2]
                and 3
                <= abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1])
                <= 6
                and surfaces.j(terrain, *cell)
                and authoritative_visible(
                    1134,
                    caster.position,
                    cell,
                    fight,
                    blocking_footprints=blockers,
                )
            ),
            key=lambda cell: (
                abs(cell[0] - caster.position[0]) + abs(cell[1] - caster.position[1]),
                cell,
            ),
        )
        try:
            tx = prepare_npc_spell(
                fight,
                dict(
                    type="cast",
                    spellId=1152,
                    level=10,
                    targetId=None,
                    target=list(empty),
                ),
                character,
                monsters,
                encode_deck([], []),
                action_id=2,
            )
        except ValueError as error:
            self.fail(
                f"native empty summon candidate {empty} rejected: {vars(error)!r}"
            )
        fresh = set(tx.fight.actors) - set(fight.actors)
        self.assertEqual(len(fresh), 1)
        self.assertEqual(tx.plan["target_id"], None)
        self.assertTrue(tx.packets)

    @staticmethod
    def _native_root_class(reference):
        from wakfu_server.combat_npc_attack import npc_runtime_catalog

        return npc_runtime_catalog(imported=True).effects[str(reference)][
            "effect_class"
        ]
