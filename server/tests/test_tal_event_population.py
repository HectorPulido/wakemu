"""Scoped event-child population and original replay-to-marker contracts."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from postgres_case import PostgresCase
import test_combat_effect_resolver as resolver_fixture


class TalEventPopulationTests(PostgresCase):
    def source(self):
        return json.loads(
            (
                Path(__file__).parent / "fixtures/tal_event_population_native.json"
            ).read_text()
        )

    def policy(self):
        from wakfu_server import combat_encounter_event_population as policy
        from wakfu_server import combat_encounter_roles as roles

        for module in (policy, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        return policy, roles, roles.role_assignment(1400, [5500])

    def scene(self):
        policy, roles, assignment = self.policy()
        f = resolver_fixture.NativeResolverTests()
        f.setUp()
        pc, pyramid, boss = f.actors
        pc.controlled, pc.team = True, assignment.player_team
        for actor in (pyramid, boss):
            actor.controlled, actor.team = False, assignment.npc_team
        boss.id = -200
        f.native[-200] = f.native.pop(3)
        boss.state_ledger = SimpleNamespace(
            entries=(
                SimpleNamespace(
                    uid=1,
                    reference=8231,
                    caster_id=boss.id,
                    target_id=boss.id,
                    effect_ids=(378826,),
                ),
            )
        )
        fight = SimpleNamespace(
            phase="placement",
            actors={actor.id: actor for actor in f.actors},
            native_encounter_roles=assignment.record(),
            native_npc_initialization_receipts={
                boss.id: dict(ref=5500, initialized=True)
            },
            native_owned_group_effects={
                index: dict(
                    invocation=dict(
                        reference=listener,
                        state_uid=1,
                        caster_id=boss.id,
                        target_id=boss.id,
                    )
                )
                for index, listener in enumerate((378827, 378829, 378831, 378833), 3)
            },
        )
        policy.freeze_event_population_policy(fight, roles=assignment)
        fight.phase = "active"
        f.resolver.fresh_group_population = (
            lambda effect, invocation: policy.permits_event_group_population(
                fight, effect, invocation
            )
        )
        native = self.source()
        f.resolver.direct_target_policies = native["direct"]
        invocation = replace(
            f.invocation,
            reference=379873,
            caster_id=pc.id,
            target_id=boss.id,
            cell=boss.position,
            state_uid=1,
            native_explicit_target=True,
            wakemu_fresh_child_selection=True,
            native_trigger_context=dict(
                uid=700,
                generic_effect=149450,
                native_events_verified=True,
                caster_id=pc.id,
                target_id=boss.id,
                manager_actor_id=boss.id,
                channel=2,
                event_ids=(0, 2, 5),
            ),
        )
        return policy, roles, assignment, f, fight, native, invocation

    def test_all_four_native_event_descriptors_and_unchosen_replay_boundaries(self):
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        policy, roles, assignment, f, fight, native, invocation = self.scene()
        self.assertEqual(len(fight.native_encounter_event_population["effects"]), 4)
        for reference, event in ((379873, 5), (379882, 6), (379884, 8), (379886, 7)):
            with self.subTest(reference=reference):
                effect = ImmutableCatalog(native["effects"][str(reference)])
                current = replace(
                    invocation,
                    reference=reference,
                    native_trigger_context=dict(
                        invocation.native_trigger_context, event_ids=(0, 2, event)
                    ),
                )
                self.assertTrue(
                    policy.permits_event_group_population(fight, effect, current)
                )
                self.assertEqual(
                    [row.target_id for row in f.resolver(effect, current)], [1, 2, -200]
                )
                for changes in (
                    dict(native_preselected_target=True),
                    dict(wakemu_fresh_child_selection=False),
                    dict(wakemu_rebound_child_selection=True),
                    dict(native_trigger_context=None),
                ):
                    with self.subTest(changes=changes):
                        changed = replace(current, **changes)
                        self.assertFalse(
                            policy.permits_event_group_population(
                                fight, effect, changed
                            )
                        )
                        self.assertEqual(
                            [row.target_id for row in f.resolver(effect, changed)],
                            [-200],
                        )
        effect = native["effects"]["379873"]
        for changes in (
            dict(channel=3),
            dict(event_ids=(6,)),
            dict(caster_id=-200),
            dict(target_id=1),
            dict(manager_actor_id=1),
            dict(native_events_verified=False),
        ):
            with self.subTest(source=changes):
                self.assertFalse(
                    policy.permits_event_group_population(
                        fight,
                        effect,
                        replace(
                            invocation,
                            native_trigger_context=dict(
                                invocation.native_trigger_context, **changes
                            ),
                        ),
                    )
                )
        for changes in (
            dict(parameters=[1, 0]),
            dict(criteria="True"),
            dict(area_class="anA"),
            dict(native_target_selector={"class": "fcE", "mask": 1}),
        ):
            with self.subTest(descriptor=changes), self.assertRaisesRegex(
                ValueError, "descriptor changed"
            ):
                policy.permits_event_group_population(
                    fight, dict(effect, **changes), invocation
                )
        self.assertFalse(
            policy.permits_event_group_population(
                fight, effect, replace(invocation, state_uid=999)
            )
        )
        original = fight.native_owned_group_effects.pop(3)
        self.assertFalse(
            policy.permits_event_group_population(fight, effect, invocation)
        )
        fight.native_owned_group_effects[3] = original
        fight.native_encounter_event_population = None
        self.assertEqual(
            [row.target_id for row in f.resolver(effect, invocation)], [-200]
        )

    def test_immutable_scope_catalog_and_absence_pin(self):
        policy, roles, assignment, f, fight, native, invocation = self.scene()
        effect = native["effects"]["379873"]
        frozen = deepcopy(fight.native_encounter_event_population)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM encounter_event_population_active WHERE map_id=1400"
            )
        fight.phase = "placement"
        self.assertEqual(
            policy.freeze_event_population_policy(fight, roles=assignment), frozen
        )
        absent = SimpleNamespace(phase="placement")
        self.assertIsNone(
            policy.freeze_event_population_policy(absent, roles=assignment)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_event_population_active VALUES "
                "(1400,ARRAY[5500],'wakemu-tal-pyramid-element-event-population-v1')"
            )
        self.assertIsNone(
            policy.freeze_event_population_policy(absent, roles=assignment)
        )
        self.assertFalse(
            policy.permits_event_group_population(absent, effect, invocation)
        )
        fight.native_encounter_event_population = dict(frozen, authority="forged")
        with self.assertRaisesRegex(ValueError, "policy changed"):
            policy.permits_event_group_population(fight, effect, invocation)
        fight.native_encounter_event_population = frozen
        with patch.object(
            roles,
            "frozen_roles",
            return_value=SimpleNamespace(map_id=1, monster_references=(5500,)),
        ), self.assertRaisesRegex(ValueError, "scope"):
            policy.permits_event_group_population(fight, effect, invocation)
        for table in (
            "encounter_event_population_versions",
            "encounter_event_population_effects",
        ):
            with self.subTest(table=table), self.assertRaisesRegex(
                psycopg.Error, "immutable"
            ), self.store.connection() as db:
                db.execute("DELETE FROM " + table)
        with self.assertRaisesRegex(
            psycopg.Error, "outside.*inventory"
        ), self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_event_population_effects VALUES "
                "('wakemu-tal-pyramid-element-event-population-v1',999,330,0,0,'[]'::jsonb,"
                "'True','anD',378826,378827,5,2)"
            )

    def test_real_native_event_replay_selects_pyramid_and_retains_original_marker(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_state_ledger import RunningState
        from wakfu_server.combat_qi_fight import (
            install_fresh_actor_slots,
            prepare_fresh_actor_slots,
        )
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )
        from wakfu_server.combat_effect_resolver import (
            NativeEffectResolver,
            EffectResolutionContext,
        )
        from wakfu_server.combat_retained_runtime import (
            NativeRetainedRuntime,
            native_retained_condition_effects,
        )
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_stat_handler import NativeStatHandler
        from wakfu_server.combat_state_handler import (
            NativeStateHandler,
            StateCarrierContext,
        )
        from wakfu_server.combat_event_replay import (
            NativeEventReplay,
            NativeCloneAuthority,
            NativeEventSource,
        )
        from wakfu_server.combat_conditions import ConditionContext
        from wakfu_server.combat_static_catalogs import ImmutableCatalog

        policy, roles, assignment = self.policy()
        native = self.source()
        pc = Actor(7, assignment.player_team, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        boss = Actor(-7, assignment.npc_team, (1, 0, 0), 100, 6, 3, 5, 1)
        pyramid = Actor(-8, assignment.npc_team, (2, 0, 0), 100, 6, 3, 4, 1)
        fight = Fight(
            77,
            [pc, boss, pyramid],
            {a.position for a in (pc, boss, pyramid)},
            {
                assignment.player_team: {pc.position},
                assignment.npc_team: {boss.position, pyramid.position},
            },
        )
        fight.native_encounter_roles = assignment.record()
        fight.native_npc_initialization_receipts = {
            boss.id: dict(ref=5500, initialized=True)
        }
        policy.freeze_event_population_policy(fight, roles=assignment)
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=3, height=1, cell_masks=[0, 0, 0]
        )
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight, physical_radii={a.id: 0 for a in (pc, boss, pyramid)}
            ),
        )
        fight.ready(3)
        fight.native_effect_uid_next = 1
        packets = []
        timing = NativeEffectTimingProvider(native)
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan=dict(spell_id=6266, evaluation_level=1),
            state_catalog=native,
            action_id=1,
            timing=timing,
            metadata={
                "effects": deepcopy(native["metadata"]),
                "states": deepcopy(native["state_metadata"]),
            },
        )
        # Construct the unit's state premises through the actual NPC constructor
        # API, including canonical wire and central retained registration. Its
        # unrelated initial child programs are outside this replay contract.
        state_handler = NativeStateHandler(
            fight,
            packets,
            native,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            execute_child=lambda inv: False,
            applied_state_scope=retention.applied_state_scope,
            context=lambda *args: None,
        )
        for target, reference, level in (
            (boss, 8231, 1),
            (pyramid, 8236, 1),
            (pyramid, 8232, 2),
        ):
            invocation = EffectInvocation(
                -1,
                level,
                boss.id,
                target.id,
                target.position,
                native_retained_container={"present": False},
            )
            self.assertTrue(
                retention.apply_state_reference(
                    state_handler,
                    invocation,
                    reference,
                    level,
                    carrier_context=StateCarrierContext(
                        -1, 0, False, None, 100, False, False, False, 0, None
                    ),
                )
            )
        self.assertEqual(boss.state_ledger.entries[0].uid, 1)
        fight.native_effect_uid_next = 900
        f = resolver_fixture.NativeResolverTests()
        f.setUp()
        f.actors = list(fight.actors.values())
        f.native = {
            a.id: dict(
                bEe=True,
                is_amO=True,
                is_eGj=True,
                is_Qq=False,
                is_eHH=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
            )
            for a in f.actors
        }
        f.resolver.direct_target_policies = native["direct"]
        f.resolver.fresh_group_population = (
            lambda e, i: policy.permits_event_group_population(fight, e, i)
        )

        def conditions(invocation=None):
            caster = pc if invocation is None else fight.actors[invocation.caster_id]
            target = boss if invocation is None else fight.actors[invocation.target_id]
            aliases = {
                name: actor.state_ledger.condition_actor(
                    retained_effect_ids=frozenset(
                        row[0]
                        for row in native_retained_condition_effects(fight, actor.id)
                    )
                )
                for name, actor in (("caster", caster), ("target", target))
            }
            return ConditionContext(
                aliases,
                state_range_query=lambda maximum, role, state, level, in_play, owner: sum(
                    any(
                        s.reference == state and (level < 0 or s.level >= level)
                        for s in a.state_ledger.entries
                    )
                    for a in fight.actors.values()
                ),
            )

        stat = NativeStatHandler(
            fight,
            packets,
            {"effects": {"400": {"runner": "eXE"}}},
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda e, i: timing.stat(fight, {}, e, i),
        )
        retention.stat_handler = stat
        # Only this original fire listener and its marker branch are under test;
        # sibling WP/damage-modifier programs keep their source definitions but
        # are outside this unit's fixture authority.
        selected_refs = {378827, 379873, 379874}

        def resolve(effect, invocation):
            if invocation.reference not in selected_refs:
                return ()
            if invocation.reference == 378827:
                return (invocation,)
            return f.resolver(effect, invocation)

        dispatcher = EffectDispatcher(
            ImmutableCatalog(native["effects"]),
            {400: retention.wrap(stat)},
            resolve=resolve,
            condition_context=conditions,
            probability_accepts=lambda p, i: p == 100,
            group_cells=lambda *args: (),
            actor_position=lambda identity: fight.actors[identity].position,
            group_retention=retention,
        )
        replay = NativeEventReplay(dispatcher, retention)
        authority = NativeCloneAuthority(
            lambda e, i, s: fight.actors[i.target_id].hp > 0,
            lambda e, i, s: conditions(i),
        )
        dispatcher.execute(
            EffectInvocation(378827, 1, boss.id, boss.id, boss.position, state_uid=1)
        )
        original = deepcopy(
            next(iter(fight.native_owned_group_effects.values()))["invocation"]
        )
        source = NativeEventSource(
            800,
            149450,
            4037,
            pc.id,
            boss.id,
            boss.position,
            (0, 2, 5),
            2,
            boss.id,
            None,
            False,
            False,
            False,
            True,
        )
        replay(source, authority=authority)
        markers = list(fight.owned_stat_effects.values())
        self.assertEqual(len(markers), 1)
        self.assertEqual(
            (markers[0]["target_id"], markers[0]["caster_id"]), (pc.id, pc.id)
        )
        self.assertIn(
            379874, {row[0] for row in native_retained_condition_effects(fight, pc.id)}
        )
        self.assertNotIn(
            379874,
            {row[0] for row in native_retained_condition_effects(fight, boss.id)},
        )
        self.assertEqual(
            next(iter(fight.native_owned_group_effects.values()))["invocation"],
            original,
        )
