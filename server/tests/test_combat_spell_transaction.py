import struct
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.spells import encode_deck
from wakfu_server.spell_audit import catalog
from wakfu_server.combat_conditions import ConditionActor, ConditionContext
from wakfu_server.combat_conditional_costs import ConditionalCostContext
from wakfu_server.combat_effect_dispatch import (
    EffectDispatcher,
    UnsupportedEffectExecution,
)
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)


class SpellTransactionTests(unittest.TestCase):
    def setUp(self):
        pc = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 6, 3, 5, 1)
        self.fight = Fight(
            77,
            [pc, npc],
            {pc.position, npc.position},
            {0: {pc.position}, 1: {npc.position}},
        )
        for slot, actor in enumerate(self.fight.actors.values()):
            # This compact fixture owns a two-actor native QI population.
            actor.native_obstacle_id = slot
            actor.native_fight_properties = frozenset()
            actor.spell_ap_cost_modifiers = (
                {}
            )  # Explicit bare fixture, no native modifiers.
            actor.effect_stats = {92: 0, 97: 0, 100: 0}
            actor.effect_maxima = {92: 0}
            actor.effect_frozen = frozenset()
            actor.physical_radius = 0
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )

        self.fight.native_qi_snapshot = dict(
            x=0, y=0, width=3, height=1, cell_masks=[0, 0, 0]
        )
        install_fresh_actor_slots(
            self.fight,
            prepare_fresh_actor_slots(
                self.fight,
                physical_radii={
                    identity: actor.physical_radius
                    for identity, actor in self.fight.actors.items()
                },
            ),
        )
        self.fight.ready(3)
        # The synthetic owned terrain and its patched native LOS columns use
        # this explicit test map identity; real server fixtures use map1134.
        self.character = dict(id=7, breed=15, level=1, map_id=999999)
        self.body = struct.pack(">qqiih", 7, (7 << 32) | 6266, 1, 0, 0)
        # This transaction fixture owns a compact native Vz terrain domain;
        # the shared Sf program, QI population and target selectors still run.
        from wakfu_server.combat_native_los_ray import static_ray, topology_columns

        static_ray.cache_clear()
        self.addCleanup(static_ray.cache_clear)
        terrain = patch(
            "wakfu_server.combat_native_los_ray.topology_columns",
            side_effect=lambda map_id: {(x, 0): ((0, 0, False),) for x in range(3)}
            if map_id == 999999
            else topology_columns(map_id),
        )
        terrain.start()
        self.addCleanup(terrain.stop)

        # Use the native player default and NPC ref1740 profile heights for
        # these synthetic map actors.
        from wakfu_server.combat_actor_snapshot import native_actor_catalog

        actor_catalog = native_actor_catalog()
        self.fight.actors[7].native_los_height = actor_catalog[
            "default_actor_los_height"
        ]
        self.fight.actors[-7].native_los_height = actor_catalog["npc_profiles"]["1740"][
            "native_los_height"
        ]

    def cast_authority(self, deck=(6266,)):
        # This focused fixture has no range modifiers; install that explicit
        # empty snapshot only after any fresh actor snapshot has been built.
        for actor in self.fight.actors.values():
            if actor.spell_range_modifiers is None:
                actor.spell_range_modifiers = {}
        context = ConditionContext(
            {
                "caster": ConditionActor(
                    state_ids=frozenset(),
                    deck_spell_ids=frozenset(deck),
                    excluded_deck_spell_ids=frozenset(),
                    is_player=True,
                    is_carried=False,
                    fight_properties=frozenset(),
                    characteristics={"RANGE": 0},
                )
            }
        )

        def produce(request, preview):
            from wakfu_server.combat_casting_context import NativeOwnedCastingContext

            def metadata(fight, actor):
                return SimpleNamespace(
                    native_instance_id=999999,
                    targeting=dict(
                        is_eGj=True,
                        is_amO=True,
                        is_Qq=False,
                        is_eHH=True,
                        bEe=True,
                        UNTARGETTABLE_BY_OTHER=False,
                        buX=False,
                        dTE=False,
                        bcN=actor.native_obstacle_id,
                        baF=True,
                        dpu_id=actor.id,
                        dpr_id=actor.id,
                    ),
                )

            metadata.properties = lambda f, a: a.native_fight_properties
            adapter = SimpleNamespace(_actor=metadata, actor_authority=metadata)

            def query(rule, spell_id, level):
                invocation = SimpleNamespace(
                    caster_id=request["actor_id"], cell=request["target"]
                )
                casting = NativeOwnedCastingContext(
                    adapter, preview, request, invocation, context, rule
                )
                casting.resolve_target_fighter()
                return dict(
                    result=casting.eligibility(),
                    aligned=casting.alignment(),
                    target_id=None if casting.target is None else casting.target.id,
                )

            return ConditionalCostContext(
                replace(context, native_casting_query=query),
                preview.current.spell_ap_cost_modifiers,
            )

        return produce

    def factory(self, preview, plan):
        packets = []
        damage = NativeDamageHandler(
            preview,
            packets,
            action_id=1,
            allocate_uid=lambda: 99,
            rng=lambda: 0.99,
            context=lambda *args: DamageExecutionContext(
                False, True, False, True, 11, False
            ),
        )
        # This test resolver deliberately selects the previously audited normal
        # branch. Production requires native target/variant/trigger resolution.
        dispatcher = EffectDispatcher(
            catalog()["effects"],
            {5: damage},
            resolve=lambda effect, invocation: (invocation,)
            if effect["variant"] == 0 and invocation.reference in (339522, 339526)
            else (),
            condition_context=lambda _: ConditionContext({}, caster_target_distance=1),
            probability_accepts=lambda probability, _: probability == 100,
            group_cells=lambda *args: (),
            actor_position=lambda uid: preview.actors[uid].position,
        )
        return dispatcher, packets

    def execute(self, factory=None):
        return prepare_spell_transaction(
            self.body,
            self.character,
            self.fight,
            3,
            encode_deck([6266]),
            wp_current=6,
            action_id=1,
            line_of_sight=lambda *args: True,
            runtime_factory=factory or self.factory,
            conditional_context=self.cast_authority(),
        )

    def test_real_native_spell_roots_share_cost_and_damage_transaction(self):
        result = self.execute()
        self.assertLess(result.fight.actors[-7].hp, 20)
        self.assertEqual(result.fight.actors[7].ap, 2)
        self.assertEqual(
            [p[0] for p in result.packets], [13494, 13420, 12588, 12678, 12613]
        )
        self.assertEqual((self.fight.actors[7].ap, self.fight.actors[-7].hp), (6, 20))

    def test_explicit_critical_branch_is_encoded_in_both_cast_notifications(self):
        result = prepare_spell_transaction(
            self.body,
            self.character,
            self.fight,
            3,
            encode_deck([6266]),
            wp_current=6,
            action_id=1,
            line_of_sight=lambda *args: True,
            runtime_factory=self.factory,
            conditional_context=self.cast_authority(),
            critical=True,
        )
        self.assertEqual(
            next(payload for op, payload in result.packets if op == 12588)[39], 1
        )
        self.assertEqual(
            next(payload for op, payload in result.packets if op == 12678)[24], 1
        )
        self.assertEqual(self.fight.actors[7].ap, 6)

    def test_missing_handler_rolls_back_costs_and_damage(self):
        def factory(preview, plan):
            dispatcher, packets = self.factory(preview, plan)
            dispatcher.handlers.clear()
            return dispatcher, packets

        with self.assertRaises(UnsupportedEffectExecution):
            self.execute(factory)
        self.assertEqual((self.fight.actors[7].ap, self.fight.actors[-7].hp), (6, 20))

    def test_invalid_queued_packet_rejects_entire_cast(self):
        self.fight.actors[7].effect_stats[100] = 1
        self.fight.actors[-7].effect_stats[97] = 1

        def factory(preview, plan):
            dispatcher, packets = self.factory(preview, plan)
            packets.append((12613, "not bytes"))
            return dispatcher, packets

        with self.assertRaises(ValueError):
            self.execute(factory)
        self.assertEqual((self.fight.actors[7].ap, self.fight.actors[-7].hp), (6, 20))
        self.assertEqual(self.fight.actors[7].effect_stats[100], 1)
        self.assertEqual(self.fight.actors[-7].effect_stats[97], 1)

    def test_wp_effects_survive_transaction_and_costs_share_snapshot(self):
        self.fight.actors[7].effect_stats.update({2: 6, 3: 3, 4: 6})

        def factory(preview, plan):
            dispatcher, packets = self.factory(preview, plan)
            damage = dispatcher.handlers[5]

            def gain_after_damage(effect, values, invocation):
                result = damage(effect, values, invocation)
                preview.actors[7].effect_stats[4] += 1
                return result

            dispatcher.handlers[5] = gain_after_damage
            return dispatcher, packets

        result = self.execute(factory)
        self.assertEqual(result.wp_remaining, 7)
        self.assertEqual(result.fight.actors[7].effect_stats[2], 2)
        self.assertEqual(self.fight.actors[7].effect_stats[4], 6)

    def test_inconsistent_wp_snapshot_rejects_before_runtime(self):
        self.fight.actors[7].effect_stats[4] = 5
        with self.assertRaisesRegex(ValueError, "WP snapshot"):
            self.execute()
        self.assertEqual(self.fight.actors[7].ap, 6)

    def test_native_actor_snapshots_feed_real_spell_damage_and_resource_updates(self):
        from wakfu_server.combat_actor_snapshot import (
            build_player_snapshot,
            build_npc_snapshot,
        )
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum

        character = effective_character(
            dict(
                self.character,
                hp=60,
                max_hp=maximum(15, 1),
                builds={},
                inventory_items=[],
            )
        )
        self.character = character
        caster = self.fight.actors[7]
        caster.max_hp = character["max_hp"]
        for actor in self.fight.actors.values():
            actor.effect_stats = actor.effect_maxima = actor.effect_minima = None
            actor.effect_frozen = actor.physical_radius = None
            actor.spell_ap_cost_modifiers = None
        build_player_snapshot(
            character, caster, wp_current=6, wp_maximum=6, running_effects=()
        ).install(caster)
        target = self.fight.actors[-7]
        target.effective_level = 15
        build_npc_snapshot(
            dict(id=-7, ref=1740),
            target,
            wp_current=4,
            wp_maximum=4,
            running_effects=(),
        ).install(target)
        result = self.execute()
        self.assertLess(result.fight.actors[-7].hp, 20)
        self.assertEqual(
            result.fight.actors[7].effect_stats[2], result.fight.actors[7].ap
        )
        self.assertEqual(
            result.fight.actors[-7].effect_stats[1], result.fight.actors[-7].hp
        )
        self.assertEqual(self.fight.actors[-7].hp, 20)

    def test_commit_prepares_all_actor_packets_and_updates_runtime(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        runtime = RuntimeMessages(self.fight)
        transaction = self.execute()
        seen = []

        def serialize(actor, fight):
            self.assertIs(fight, transaction.fight)
            seen.append(actor.id)
            return b"owned-stats"

        packets = commit_spell_transaction(
            runtime, transaction, stats_serializer=serialize
        )
        self.assertEqual(set(seen), {7, -7})
        self.assertIs(runtime.fight, transaction.fight)
        self.assertEqual(runtime.action_id, 1)
        self.assertEqual(
            [opcode for opcode, _ in packets][-4:], [13420, 12873, 12873, 13420]
        )

    def test_serializer_failure_does_not_commit_damage_costs_or_action_id(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        runtime = RuntimeMessages(self.fight)
        transaction = self.execute()

        def serialize(actor, fight):
            if actor.id == -7:
                raise ValueError("missing native data")
            return b"owned-stats"

        with self.assertRaises(ValueError):
            commit_spell_transaction(runtime, transaction, stats_serializer=serialize)
        self.assertIs(runtime.fight, self.fight)
        self.assertEqual(
            (runtime.action_id, self.fight.actors[7].ap, self.fight.actors[-7].hp),
            (0, 6, 20),
        )

    def test_stale_transaction_rejects_after_resource_change_without_event(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        runtime = RuntimeMessages(self.fight)
        transaction = self.execute()
        self.fight.spend(3, 7, ap=1)
        with self.assertRaisesRegex(ValueError, "Combat changed"):
            commit_spell_transaction(
                runtime, transaction, stats_serializer=lambda *args: b"stats"
            )
        self.assertEqual((runtime.action_id, self.fight.actors[7].ap), (0, 5))

    def native_server_fixture(
        self,
        breed,
        level,
        *,
        target_hp=200,
        full_health=False,
        caster_aptitudes=(),
        native_qi=False,
        target_ref=5525,
        target_level=1,
        owned_cosmetics=None,
        target_distance=2,
        target_position=None,
        variation_seed=None,
        compact=None,
    ):
        from wakfu_server.combat_actor_snapshot import (
            build_player_snapshot,
            build_npc_snapshot,
            native_npc_creation_values,
        )
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum

        from test_aptitude_catalog_coverage import aptitude_sheet
        from wakfu_server.wire import proto_field
        from wakfu_server.equipment_stats import combat_resources

        character = effective_character(
            dict(
                id=7,
                account_id=3,
                map_id=1134,  # Explicit native POSITION rE.Vp property.
                breed=breed,
                level=level,
                hp=maximum(breed, level) if full_health else 60,
                max_hp=maximum(breed, level),
                builds={
                    0: {
                        "sheet": proto_field(24, 0xFFFFFFFF).hex(),
                        "aptitudes": aptitude_sheet(caster_aptitudes).hex(),
                    }
                }
                if caster_aptitudes
                else {},
                inventory_items=[],
            )
        )
        if owned_cosmetics is not None:
            character["account_id"] = owned_cosmetics.account_id
            character["owned_cosmetics"] = owned_cosmetics.to_record()
        resources = combat_resources(
            character, base_ap=6, base_mp=3, base_initiative=10
        )
        caster = Actor(
            7,
            0,
            (0, 0, 0),
            character["hp"],
            resources["ap"],
            resources["mp"],
            resources["initiative"],
            level,
            3,
            True,
            max_hp=character["max_hp"],
        )
        monster = dict(id=-7, ref=target_ref, map_id=1134)
        if (target_ref, target_level) == (5525, 1):
            target = Actor(-7, 1, (target_distance, 0, 0), target_hp, 6, 3, 5, 1)
        else:
            values = native_npc_creation_values(target_ref, target_level)
            target = Actor(
                -7,
                1,
                (target_distance, 0, 0),
                values[1]["current"],
                values[2]["current"],
                values[3]["current"],
                5,
                target_level,
                max_hp=values[1]["maximum"],
            )
        terrain = None
        if native_qi:
            from wakfu_server.combat_terrain import local_arena

            caster.position = (-8, -7, -1)
            target.position = (
                tuple(target_position)
                if target_position is not None
                else (-8 + target_distance, -7, -1)
            )
            terrain = local_arena(
                1134,
                7,
                caster.position,
                target.position,
                # Tests keep exact distance-dependent spell criteria. Preserve
                # both actor seeds instead of selecting a relocated formation.
                relocate_monsters=False,
                variation_seed=variation_seed,
                compact=compact,
            )
        caster_snapshot = npc_snapshot = None
        if native_qi:
            # QI needs the actors' actual native footprint radii at creation.
            caster_snapshot = build_player_snapshot(
                character, caster, wp_current=6, wp_maximum=6, running_effects=()
            )
            npc_snapshot = build_npc_snapshot(
                monster, target, wp_current=0, wp_maximum=0, running_effects=()
            )
        fight = Fight(
            78,
            [caster, target],
            terrain["validated_cells"]
            if terrain
            else {(x, y, 0) for x in range(-5, 12) for y in range(-5, 6)},
            {0: {caster.position}, 1: {target.position}},
            terrain["valid_edges"] if terrain else None,
        )
        if native_qi:
            from wakfu_server.combat_global_pv_collections import (
                initialize_global_pv_collections,
            )
            from wakfu_server.combat_qi_fight import (
                prepare_fresh_actor_slots,
                install_fresh_actor_slots,
            )

            from wakfu_server.combat_geometry_snapshot import freeze_terrain

            # Copy the installed map's actual selected surfaces at creation;
            # synthetic z=0 cells cannot establish map1134 QI.j authority.
            fight.native_qi_snapshot = {
                name: terrain[name]
                for name in ("x", "y", "width", "height", "cell_masks")
            }
            fight.native_qi_surface_provenance = dict(
                terrain["native_qi_surface_provenance"]
            )
            freeze_terrain(fight)
            initialize_global_pv_collections(fight, (7, -7))
            registry = prepare_fresh_actor_slots(
                fight,
                physical_radii={
                    7: caster_snapshot.physical_radius,
                    -7: npc_snapshot.physical_radius,
                },
            )
            install_fresh_actor_slots(fight, registry)
        fight.ready(3)
        caster.direction = 0
        target.direction = 3
        if native_qi:
            caster_snapshot.install(caster)
            npc_snapshot.install(target)
        else:
            build_player_snapshot(
                character, caster, wp_current=6, wp_maximum=6, running_effects=()
            ).install(caster)
            build_npc_snapshot(
                monster, target, wp_current=0, wp_maximum=0, running_effects=()
            ).install(target)
        fight.native_effect_uid_next = 1
        # This fixture emits an explicitly empty QL obstacle table, as bootstrap does.
        fight.native_obstacle_cells = frozenset()
        return character, monster, fight

    def test_native_server_fixture_defaults_preserve_legacy_actor_and_map(self):
        _character, monster, fight = self.native_server_fixture(8, 21)

        self.assertEqual(monster, dict(id=-7, ref=5525, map_id=1134))
        self.assertEqual(fight.actors[-7].position, (2, 0, 0))
        self.assertIsNone(fight.native_qi_slots)

    def test_native_server_fixture_registers_opt_in_profile_before_qi(self):
        from wakfu_server.combat_qi_fight import current_registry

        _character, monster, fight = self.native_server_fixture(
            8, 21, native_qi=True, target_ref=4085, target_level=23
        )
        actor = fight.actors[-7]
        registry = current_registry(fight)
        row = next(
            slot
            for slot in registry.slots
            if slot is not None and slot["identity"] == ["actor", -7]
        )

        self.assertEqual((monster["ref"], actor.effective_level), (4085, 23))
        self.assertEqual(tuple(row["position"]), actor.position[:2])
        self.assertEqual(row["radius"], actor.physical_radius)
        self.assertEqual(row["identity"], ["actor", actor.id])

    def test_level245_owned_native_cast_uses_full_curve_without_mutating_source(self):
        import random
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_initialization,
        )
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.spell_audit import costs_catalog

        character, monster, fight = self.native_server_fixture(
            8,
            245,
            full_health=True,
            native_qi=True,
            target_ref=4168,
            target_level=190,
        )
        deck = encode_deck([4780])
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(1),
            fight_start=True,
        )
        caster, target = fight.actors[7], fight.actors[-7]
        before = (caster.ap, caster.mp, caster.hp, target.hp)

        def line_of_sight(origin, destination, current):
            return authoritative_visible(
                character["map_id"],
                origin,
                destination,
                current,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in current.actors.values()
                    if actor.hp > 0
                },
            )

        result = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 4780, *target.position),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=2,
            line_of_sight=line_of_sight,
            critical=False,
            rng=random.Random(1),
        )
        ap_cost = costs_catalog()["4780"]["levels"][244][0]
        self.assertGreater(ap_cost, 0)
        self.assertEqual(result.fight.actors[7].ap, before[0] - ap_cost)
        self.assertLess(result.fight.actors[-7].hp, before[3])
        self.assertEqual(result.fight.actors[7].effective_level, 245)
        self.assertEqual((caster.ap, caster.mp, caster.hp, target.hp), before)

    def test_server_entry_conditional_spell_damage_and_displacement_share_transaction(
        self,
    ):
        import random
        from wakfu_server.combat_server_spell import prepare_server_spell

        character, monster, fight = self.native_server_fixture(2, 19, native_qi=True)
        # Forced movement uses the installed map's surface-selection authority.
        # The old synthetic z=0 grid was not a surface of map 1134.
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_geometry_snapshot import freeze_terrain

        fight.actors[7].position = (-8, -7, -1)
        fight.actors[-7].position = (-6, -7, -1)
        terrain = local_arena(1134, 7, (-8, -7, -1), (-6, -7, -1))
        fight.walkable = terrain["validated_cells"]
        fight.edges = terrain["valid_edges"]
        freeze_terrain(fight)
        body = struct.pack(">qqiih", 7, (7 << 32) | 7320, -6, -7, -1)
        result = prepare_server_spell(
            body,
            character,
            {-7: monster},
            fight,
            3,
            encode_deck([7320]),
            action_id=1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.assertEqual(result.fight.actors[7].ap, 4)
        self.assertLess(result.fight.actors[-7].hp, 200)
        self.assertGreater(result.fight.actors[-7].position[0], -6)
        self.assertEqual(
            (fight.actors[7].ap, fight.actors[-7].hp, fight.actors[-7].position),
            (6, 200, (-6, -7, -1)),
        )
        self.assertGreaterEqual(sum(op == 12613 for op, _ in result.packets), 2)

    def test_owned_native_carry_spell_uses_normal_origin_and_keeps_source_atomic(self):
        import random
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_initialization,
        )
        from wakfu_server.combat_qi_fight import move_registered_actor, current_registry
        from wakfu_server.combat_carrying import carrying_relations
        from wakfu_server.combat_spell_grant_book import grant_record

        # Native class extra6847 reaches family334 through290560/290561/290562.
        # It is granted by actual class initialization, never inserted in deck.
        character, monster, fight = self.native_server_fixture(12, 200, native_qi=True)
        deck = encode_deck([4705])
        fight, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(1),
            fight_start=True,
        )
        extra = grant_record(fight, 7, 6847)
        self.assertIsNotNone(extra, "Actual Pandawa initialization must grant Karcham")
        target = fight.actors[-7]
        destination = (-7, -7, -1)
        self.assertIn(destination, fight.walkable)
        move_registered_actor(fight, target, destination)
        original_ap = fight.actors[7].ap
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, extra["uid"], *destination),
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=2,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        carrier, carried = result.fight.actors[7], result.fight.actors[-7]
        self.assertTrue(carrying_relations(result.fight, carried)["is_carried"])
        self.assertEqual(carried.position, carrier.position)
        self.assertFalse(
            current_registry(result.fight).slots[carried.native_obstacle_id]["indexed"]
        )
        self.assertTrue(any(opcode == 12613 for opcode, _ in result.packets))
        self.assertEqual(
            (fight.actors[7].ap, target.position), (original_ap, destination)
        )
        self.assertFalse(carrying_relations(fight, target)["is_carried"])
        throw = grant_record(result.fight, 7, 6848)
        self.assertIsNotNone(
            throw, "Actual carried-state lifecycle must expose Chamrak"
        )
        throw_cell = (-6, -7, -1)
        self.assertIn(throw_cell, result.fight.walkable)
        released = prepare_server_spell(
            struct.pack(">qqiih", 7, throw["uid"], *throw_cell),
            character,
            {-7: monster},
            result.fight,
            3,
            deck,
            action_id=3,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.assertFalse(
            carrying_relations(released.fight, released.fight.actors[-7])["is_carried"]
        )
        self.assertEqual(released.fight.actors[-7].position, throw_cell)
        self.assertTrue(
            current_registry(released.fight).slots[carried.native_obstacle_id][
                "indexed"
            ]
        )
        self.assertTrue(carrying_relations(result.fight, carried)["is_carried"])

    def test_server_entry_native_transposition_swaps_and_keeps_original_until_commit(
        self,
    ):
        import random
        from wakfu_server.combat_server_spell import prepare_server_spell

        character, monster, fight = self.native_server_fixture(
            11, 6, native_qi=True, target_distance=2
        )
        caster = fight.actors[7]
        target = fight.actors[-7]
        body = struct.pack(">qqiih", 7, (7 << 32) | 5043, -6, -7, -1)
        result = prepare_server_spell(
            body,
            character,
            {-7: monster},
            fight,
            3,
            encode_deck([5043]),
            action_id=1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.assertEqual(result.fight.actors[7].position, (-6, -7, -1))
        self.assertEqual(result.fight.actors[-7].position, (-8, -7, -1))
        self.assertEqual(result.fight.actors[7].ap, 5)
        self.assertEqual(result.wp_remaining, 5)
        self.assertEqual(caster.position, (-8, -7, -1))
        self.assertEqual(target.position, (-6, -7, -1))
        self.assertEqual(caster.ap, 6)
        self.assertEqual(
            [op for op, _ in result.packets][:5], [13494, 13420, 12588, 12678, 12613]
        )

    def test_server_entry_executes_full_native_roots_without_spell_whitelist(self):
        import random
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_actor_snapshot import (
            build_player_snapshot,
            build_npc_snapshot,
        )
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health import maximum

        character = effective_character(
            dict(
                self.character,
                hp=60,
                max_hp=maximum(15, 1),
                builds={},
                inventory_items=[],
            )
        )
        caster = self.fight.actors[7]
        caster.max_hp = character["max_hp"]
        for actor in self.fight.actors.values():
            actor.effect_stats = actor.effect_maxima = actor.effect_minima = None
            actor.effect_frozen = actor.physical_radius = None
            actor.spell_ap_cost_modifiers = None
            actor.direction = 0 if actor.controlled else 3
        build_player_snapshot(
            character, caster, wp_current=6, wp_maximum=6, running_effects=()
        ).install(caster)
        monster = dict(id=-7, ref=1740)
        target = self.fight.actors[-7]
        target.effective_level = 15
        build_npc_snapshot(
            monster, target, wp_current=4, wp_maximum=4, running_effects=()
        ).install(target)
        self.fight.native_effect_uid_next = 1
        result = prepare_server_spell(
            self.body,
            character,
            {-7: monster},
            self.fight,
            3,
            encode_deck([6266]),
            action_id=1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=random.Random(1),
        )
        self.assertLess(result.fight.actors[-7].hp, 20)
        self.assertEqual(self.fight.actors[-7].hp, 20)
        self.assertEqual(result.fight.actors[7].ap, 2)
