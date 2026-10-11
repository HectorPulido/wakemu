"""Actual native border marker controls on paid sequential movement."""
import unittest


class BorderMultistepTests(unittest.TestCase):
    def fixture(self, budget=6):
        from dataclasses import replace
        from types import SimpleNamespace

        from test_combat_effect_runtime import NativeRuntimeFactoryTests
        from wakfu_server.combat_battleground_border import (
            POLICY,
            install_battleground_border,
        )
        from wakfu_server.combat_conditions import ConditionActor, ConditionContext
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
        from wakfu_server.combat_effect_area_catalog import area_effect_catalog
        from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
        from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )
        from wakfu_server.combat_static_catalogs import characteristic_registry
        from wakfu_server.combat_summon import RegisteredSummonAuthority
        from wakfu_server.spell_audit import states_catalog

        fixture = NativeRuntimeFactoryTests()
        NativeRuntimeFactoryTests.setUpClass()
        fixture.setUp()
        from wakfu_server.combat_state import Fight
        from wakfu_server.combat_qi_fight import move_registered_actor

        actor = fixture.fight.actors[7]
        enemy = fixture.fight.actors[-7]
        # Fresh two-team constructor, preserving actual actor/stat sources.
        # No initialized QI or timeline roster is edited after registration.
        move_registered_actor(fixture.fight, enemy, (4, 0, 0))
        cells = {(x, 0, 0) for x in range(5)}
        fight = Fight(
            77, [actor, enemy], cells, {0: {actor.position}, 1: {enemy.position}}
        )
        fight.ready(3)
        self.assertEqual(fight.current.id, actor.id)
        actor.mp = budget
        actor.effect_stats[3] = budget
        actor.max_mp = 6
        actor.effect_maxima[3] = 6
        actor.effect_stats[86] = 0
        actor.effect_minima[86] = 0
        actor.effect_maxima[86] = 1000
        actor.effect_stats[8] = 100
        from test_combat_tackle_movement import Authority as MovementAuthority

        fight.native_rail_movement_authority = MovementAuthority()
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=5, height=1, cell_masks=[0, 128, 128, 128, 0]
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        install_battleground_border(
            fight,
            dict(
                native_border_policy=POLICY,
                native_border_cells={(1, 0, 0), (2, 0, 0), (3, 0, 0)},
                min_z=0,
            ),
            reference=46,
            identity=-100,
        )

        states = states_catalog()
        timing = NativeEffectTimingProvider(states)

        def condition(preview, plan, effect, invocation):
            retained = native_retained_condition_effects(preview, invocation.target_id)
            target = preview.actors[invocation.target_id]
            return ConditionContext(
                {
                    "caster": ConditionActor(actor_id=-100, is_native_fighter=False),
                    "target": ConditionActor(
                        actor_id=target.id,
                        characteristics={"WILLPOWER": target.effect_stats[86]},
                        retained_effect_ids=frozenset(row[0] for row in retained),
                    ),
                }
            )

        actor_authority = OrdinaryActorAuthority(
            characters={7: dict(id=7, breed=15, level=1)},
            # Same ordinary Wonejo source contract as
            # test_combat_ordinary_events.OrdinaryHealingEventTests.
            monsters={-7: dict(id=-7, ref=5525)},
            decks={7: []},
            excluded_decks={7: []},
        )
        # Static roster/source qualification before invoking any native runner.
        self.assertEqual(
            set(fight.actors),
            set(actor_authority.characters) | set(actor_authority.monsters),
        )
        self.assertEqual(
            {uid for uid, row in fight.actors.items() if row.controlled},
            set(actor_authority.characters),
        )
        adapter = SimpleNamespace(actor_authority=actor_authority)

        def healing_events(preview, plan, replay, retention):
            return OrdinaryHealingEvents(
                adapter=adapter,
                preview=preview,
                plan=plan,
                replay=replay,
                retention=retention,
            )

        contexts = replace(
            fixture.contexts,
            condition=condition,
            stat=timing.stat,
            healing_events=healing_events,
        )

        class TestSummonAuthority(RegisteredSummonAuthority):
            def __init__(self):
                super().__init__(object())

            def properties(self, preview, target):
                return frozenset()

        factory = NativeEffectRuntimeFactory(
            effects=dict(area_effect_catalog()["effects"]),
            state_catalog=states,
            characteristic_registry=characteristic_registry(),
            action_id=1,
            contexts=contexts,
            summon_authority=TestSummonAuthority(),
        )
        dispatcher, _ = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        area_events = dispatcher.native_area_events
        from wakfu_server.combat_resource_pa_notifications import set_resource_current

        if getattr(actor, "effect_resource_raw_currents", None) is not None:
            set_resource_current(fight, actor, 3, budget)
        self.native_factory = factory
        return fight, actor, area_events

    def move(self, fight, actor, events, path):
        observations = []

        def step(current, mover, before, cell):
            paid = mover.mp
            with current.effect_resolution():
                outcomes = events.movement(mover.id, from_cell=before, to_cell=cell)
            observations.append((before, cell, paid, mover.mp, outcomes))

        event = fight.move(3, actor.id, path, step_callback=step)
        return event, observations

    def test_consecutive_border_cells_charge_movement_but_marker_blocks_repeat_loss(
        self,
    ):
        fight, actor, events = self.fixture()
        event, observed = self.move(
            fight, actor, events, [(1, 0, 0), (2, 0, 0), (3, 0, 0)]
        )
        self.assertEqual(event["cost"], 3)
        self.assertEqual(actor.mp, 2)
        self.assertEqual(
            [(row[2], row[3]) for row in observed], [(5, 4), (3, 3), (2, 2)]
        )
        self.assertEqual(event["path"], [(1, 0, 0), (2, 0, 0), (3, 0, 0)])

    def test_exit_reentry_same_turn_keeps_native_once_marker(self):
        fight, actor, events = self.fixture()
        event, observed = self.move(
            fight, actor, events, [(1, 0, 0), (0, 0, 0), (1, 0, 0)]
        )
        self.assertEqual(event["cost"], 3)
        self.assertEqual(actor.mp, 2)
        self.assertEqual(
            [(row[2], row[3]) for row in observed], [(5, 4), (3, 3), (2, 2)]
        )

    def test_effect_loss_halts_route_after_affordable_paid_entry(self):
        fight, actor, events = self.fixture(budget=2)
        event, observed = self.move(fight, actor, events, [(1, 0, 0), (2, 0, 0)])
        self.assertEqual(event["path"], [(1, 0, 0)])
        self.assertEqual(event["cost"], 1)
        self.assertEqual((actor.position, actor.mp), ((1, 0, 0), 0))
        self.assertEqual(len(observed), 1)

    def test_paired_route_without_border_callbacks_pays_only_movement(self):
        fight, actor, events = self.fixture()
        event = fight.move(
            3,
            actor.id,
            [(1, 0, 0), (2, 0, 0), (3, 0, 0)],
            step_callback=lambda *args: None,
        )
        self.assertEqual(event["cost"], 3)
        self.assertEqual(actor.mp, 3)
        self.assertEqual(actor.position, (3, 0, 0))

    def test_live_client_wrapper_stops_after_border_consumes_remaining_mp(self):
        import struct
        from unittest.mock import patch
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement

        fight, actor, events = self.fixture(budget=2)
        actor.direction = 1
        runtime = RuntimeMessages(fight)
        path = [(1, 0, 0), (2, 0, 0)]
        body = struct.pack(">q", actor.id) + b"".join(
            struct.pack(">iih", *cell) for cell in path
        )
        observed = []

        def provider(current, *, actor_id, action_id, path, origin):
            observed.append((tuple(path), origin))
            return prepare_area_movement(
                {},
                {},
                current,
                [],
                actor_id=actor_id,
                action_id=action_id,
                path=path,
                origin=origin,
            )

        # Use the existing source-backed isolated native factory while retaining
        # the production client wrapper, area transaction and border handlers.
        with patch(
            "wakfu_server.combat_server_spell.server_runtime",
            return_value=(self.native_factory, None),
        ):
            packets, event = apply_client(
                runtime, 3, body, lambda actor: b"owned", area_provider=provider
            )
        self.assertEqual(event["path"], [(1, 0, 0)])
        self.assertEqual(event["cost"], 1)
        self.assertEqual(
            (runtime.fight.actors[7].position, runtime.fight.actors[7].mp),
            ((1, 0, 0), 0),
        )
        self.assertTrue(observed)
        self.assertTrue(packets)

    def test_native_marker_due_clock_removal_reenables_entry(self):
        from wakfu_server.combat_timed_expiration import expire_timed_effects
        from wakfu_server.combat_resource_pa_notifications import set_resource_current
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )

        fight, actor, events = self.fixture()
        self.move(fight, actor, events, [(1, 0, 0), (0, 0, 0)])
        records = [
            row
            for row in fight.native_retained_records.values()
            if row.get("generic_effect") == 152028
        ]
        self.assertEqual(len(records), 1, fight.native_retained_records)
        uid = records[0]["uid"]
        owned = fight.owned_stat_effects.get(
            uid, fight.native_owned_group_effects.get(uid)
        )
        self.assertIsNotNone(owned, (uid, fight.owned_stat_effects))
        timer = owned.get("timer")
        self.assertIsNotNone(timer, owned)
        self.assertEqual(timer["actor_id"], actor.id)

        def expiration_factory(*, action_id):
            from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory

            source = self.native_factory
            return NativeEffectRuntimeFactory(
                effects=source.effects,
                state_catalog=source.state_catalog,
                characteristic_registry=source.characteristic_registry,
                action_id=action_id,
                contexts=source.contexts,
                summon_authority=source.summon_authority,
            )

        expire_timed_effects(
            fight,
            actor_id=timer["actor_id"],
            round_number=timer["expiration_round"],
            phase=timer["phase"],
            action_id=20,
            runtime_factory=expiration_factory,
        )
        self.assertNotIn(
            152028,
            {row[0] for row in native_retained_condition_effects(fight, actor.id)},
        )
        self.assertEqual(
            actor.mp, 3
        )  # Genuine budget left after two paid steps and one loss.
        self.move(fight, actor, events, [(1, 0, 0)])
        self.assertEqual(actor.mp, 1)
