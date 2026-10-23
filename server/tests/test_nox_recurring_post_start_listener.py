"""Recurring original Auspice listener; no earned calendar or damage claim."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from postgres_case import PostgresCase


class NoxRecurringPostStartTests(PostgresCase):
    def policy(self):
        from wakfu_server import combat_encounter_table_listeners as listeners

        listeners._version.cache_clear()
        self.addCleanup(listeners._version.cache_clear)
        self.enterContext(patch.object(listeners, "_database", return_value=self.store))
        frozen = listeners.freeze_table_listener_policy(1435, (5664,))
        self.assertEqual(frozen["policy"], "wakemu-nox-owned-boundaries-v4")
        self.assertEqual(
            [row["effect_reference"] for row in frozen["callbacks"]], [401544, 401749]
        )
        return listeners, frozen

    def test_version_transition_preserves_committed_266_and_absence_without_following_pointer(
        self,
    ):
        listeners, frozen = self.policy()
        old = deepcopy(listeners._version("wakemu-nox-owned-boundaries-v3"))
        self.assertEqual([r["effect_reference"] for r in old["callbacks"]], [401544])
        old_fight = SimpleNamespace(native_encounter_table_listener_policy=old)
        self.assertEqual(listeners.frozen_table_listener_policy(old_fight), old)
        roles = SimpleNamespace(map_id=1435, monster_references=(5664,))
        self.assertEqual(
            listeners.freeze_encounter_table_listener_policy(old_fight, roles=roles),
            old,
        )
        with self.store.connection() as db:
            db.execute("DELETE FROM encounter_table_listener_active WHERE map_id=1435")
        absent = SimpleNamespace()
        self.assertIsNone(
            listeners.freeze_encounter_table_listener_policy(absent, roles=roles)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_table_listener_active VALUES(1435,ARRAY[5664],%s)",
                (frozen["policy"],),
            )
        self.assertIsNone(
            listeners.freeze_encounter_table_listener_policy(absent, roles=roles)
        )
        self.assertEqual(listeners.frozen_table_listener_policy(old_fight), old)
        for sql in (
            "UPDATE encounter_table_listener_callbacks SET execution_count=1 WHERE effect_reference=401749",
            "DELETE FROM encounter_table_listener_versions WHERE policy='wakemu-nox-owned-boundaries-v4'",
        ):
            with self.assertRaises(psycopg.Error), self.store.connection() as db:
                db.execute(sql)
        forged = SimpleNamespace(
            native_encounter_table_listener_policy=deepcopy(frozen)
        )
        forged.native_encounter_table_listener_policy["callbacks"][1][
            "execution_count"
        ] = 1
        with self.assertRaisesRegex(ValueError, "policy changed"):
            listeners.frozen_table_listener_policy(forged)

    def test_preexisting_uid_snapshot_excludes_birth_until_next_owned_start_and_success_stops_it(
        self,
    ):
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        listeners, frozen = self.policy()
        callbacks = frozen["callbacks"]
        boss = SimpleNamespace(
            id=-200,
            controlled=False,
            hp=100,
            state_ledger=SimpleNamespace(
                entries=[
                    SimpleNamespace(
                        uid=10, reference=8978, caster_id=-200, target_id=-200
                    )
                ]
            ),
        )
        fight = SimpleNamespace(
            phase="active",
            current=boss,
            actors={-200: boss},
            turn_id=17,
            native_table_turn=8,
            native_encounter_table_listener_policy=frozen,
            native_npc_initialization_receipts={
                -200: dict(
                    ref=5664, initialized=True, resolved_states=[dict(state_id=8969)]
                )
            },
            native_owned_group_effects={
                11: dict(
                    invocation=dict(
                        reference=401544, state_uid=10, caster_id=-200, target_id=-200
                    )
                )
            },
        )
        entries = [SimpleNamespace(uid=11, manager_id=-200, generic_effect=401544)]
        calls = []

        def replay(source, **kwargs):
            calls.append(kwargs["eligible_uids"])
            if kwargs["eligible_uids"] == frozenset({11}):
                boss.state_ledger.entries.append(
                    SimpleNamespace(
                        uid=20, reference=8979, caster_id=-200, target_id=-200
                    )
                )
                entries.append(
                    SimpleNamespace(uid=21, manager_id=-200, generic_effect=401749)
                )
                fight.native_owned_group_effects[21] = dict(
                    invocation=dict(
                        reference=401749, state_uid=20, caster_id=-200, target_id=-200
                    )
                )
            return (True,)

        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(
                fight=fight,
                metadata={
                    "effects": {
                        str(c["effect_reference"]): native_catalog.record(
                            DATA_ROOT / "native-retained-effect-metadata.json",
                            "effects",
                            c["effect_reference"],
                        )
                        for c in callbacks
                    }
                },
                view=lambda: SimpleNamespace(entries=tuple(entries)),
            ),
            effects={
                str(c["effect_reference"]): native_catalog.record(
                    DATA_ROOT / "combat-state-definitions.json",
                    "effects",
                    c["effect_reference"],
                )
                for c in callbacks
            },
            native_clone_authority=object(),
            replay_event=replay,
        )

        def boundary(table):
            fight.native_table_turn = table
            fight.turn_id += 1
            fight.native_turn_event_deliveries = {
                f"{fight.turn_id}:-200:start": dict(
                    actor_id=-200, turn_id=fight.turn_id, phase="start", event_id=1001
                )
            }

        boundary(8)
        listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=-200)
        self.assertEqual(calls, [frozenset({11})])
        listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=-200)
        self.assertEqual(len(calls), 1)
        boundary(9)
        listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=-200)
        self.assertEqual(calls[-1], frozenset({21}))
        fight.native_encounter_post_start_deliveries = json.loads(
            json.dumps(fight.native_encounter_post_start_deliveries)
        )
        boundary(10)
        listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=-200)
        self.assertEqual(calls, [frozenset({11}), frozenset({21}), frozenset({21})])
        boss.state_ledger.entries.append(SimpleNamespace(uid=30, reference=9031))
        boundary(11)
        listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=-200)
        self.assertEqual(len(calls), 3)

    def test_original_recurring_listener_reaches_native_8472_request_each_next_start(
        self,
    ):
        """Premise: fatality carrier already exists at an owned START."""
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server import combat_encounter_table_listeners as listeners
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_effect_dispatch import (
            EffectDispatcher,
            EffectInvocation,
        )
        from wakfu_server.combat_retained_runtime import (
            NativeRetainedRuntime,
            native_retained_condition_effects,
        )
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_state_handler import (
            NativeStateHandler,
            StateCarrierContext,
        )
        from wakfu_server.combat_event_replay import (
            NativeEventReplay,
            NativeCloneAuthority,
        )
        from wakfu_server.combat_conditions import ConditionContext
        from wakfu_server.combat_qi_fight import (
            install_fresh_actor_slots,
            prepare_fresh_actor_slots,
        )

        listeners._version.cache_clear()
        self.addCleanup(listeners._version.cache_clear)
        self.enterContext(patch.object(listeners, "_database", return_value=self.store))
        frozen = listeners.freeze_table_listener_policy(1435, (5664,))

        def record(path, collection, reference):
            return native_catalog.record(DATA_ROOT / path, collection, reference)

        states = {
            str(ref): record("combat-state-definitions.json", "states", ref)
            for ref in (8979,)
        }
        refs = {401544, 401749, 401750}
        for state in states.values():
            refs.update(state["effect_ids"])
        effects = {
            str(ref): record("combat-state-definitions.json", "effects", ref)
            for ref in refs
        }
        # Dispatcher validates each direct child definition before resolver scope.
        for ref in effects["401749"]["children"]:
            effects.setdefault(
                str(ref), record("combat-state-definitions.json", "effects", ref)
            )
        refs.update(int(ref) for ref in effects)
        metadata = {
            str(ref): record("native-retained-effect-metadata.json", "effects", ref)
            for ref in refs
        }
        native = dict(states=states, effects=effects)
        pc = Actor(7, 1, (0, 0, 0), 100, 6, 3, 5, 1, 3, True)
        boss = Actor(-7, 0, (1, 0, 0), 100, 6, 3, 10, 1)
        fight = Fight(
            77,
            [pc, boss],
            {pc.position, boss.position},
            {1: {pc.position}, 0: {boss.position}},
        )
        fight.native_qi_snapshot = dict(x=0, y=0, width=2, height=1, cell_masks=[0, 0])
        install_fresh_actor_slots(
            fight, prepare_fresh_actor_slots(fight, physical_radii={7: 0, -7: 0})
        )
        fight.ready(3)
        fight.native_effect_uid_next = 1  # Fresh component runner namespace.
        self.assertEqual(fight.current.id, boss.id)
        fight.native_encounter_table_listener_policy = frozen
        fight.native_npc_initialization_receipts = {
            boss.id: dict(
                ref=5664, initialized=True, resolved_states=[dict(state_id=8969)]
            )
        }
        packets = []
        timing = NativeEffectTimingProvider(native)
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan=dict(spell_id=6266, evaluation_level=1),
            state_catalog=native,
            action_id=1,
            timing=timing,
            metadata=dict(
                effects=metadata,
                states={
                    str(ref): record(
                        "native-retained-effect-metadata.json", "states", ref
                    )
                    for ref in (8979,)
                },
            ),
        )
        carrier = StateCarrierContext(
            -1, 0, False, None, 100, False, False, False, 0, None
        )
        state = NativeStateHandler(
            fight,
            packets,
            native,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *args: carrier,
            execute_child=lambda inv: False,
            applied_state_scope=retention.applied_state_scope,
        )
        retention.apply_state_reference(
            state,
            EffectInvocation(
                -1,
                1,
                boss.id,
                boss.id,
                boss.position,
                native_retained_container={"present": False},
            ),
            8979,
            1,
            carrier_context=carrier,
        )
        carrier_uid = boss.state_ledger.entries[0].uid

        def conditions(invocation=None):
            actor = boss.state_ledger.condition_actor(
                retained_effect_ids=frozenset(
                    row[0] for row in native_retained_condition_effects(fight, boss.id)
                )
            )
            return ConditionContext(
                {"caster": actor, "target": actor},
                fight_current_table_turn=fight.native_table_turn,
            )

        # Exercise the real native eYZ request boundary. The request executor
        # is observed; this component does not claim spell8472 damage or RNG.
        from random import Random
        from wakfu_server.combat_triggered_spell_handler import (
            NativeTriggeredSpellHandler,
        )
        from wakfu_server.combat_stat_handler import StatExecutionContext

        requests = []
        trigger = NativeTriggeredSpellHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *args: StatExecutionContext(True, True, None, False, None),
            authority=lambda *args: SimpleNamespace(targeting={"is_eGj": True}),
            rng=Random(1).random,
            executor=lambda request, effect, inv: requests.append((request, inv)),
        )
        selected = {401749, 401750}
        dispatcher = EffectDispatcher(
            effects,
            {426: retention.wrap(trigger)},
            resolve=lambda effect, inv: (inv,) if inv.reference in selected else (),
            condition_context=conditions,
            probability_accepts=lambda p, inv: p == 100,
            group_cells=lambda *args: (),
            actor_position=lambda identity: fight.actors[identity].position,
            group_retention=retention,
        )
        execute = dispatcher.execute
        # Original point children are preselected and bypass resolve(). Keep
        # the component branch boundary explicit before native execution.
        dispatcher.execute = (
            lambda inv, **kwargs: execute(inv, **kwargs)
            if inv.reference in selected
            else False
        )
        state.execute_child = dispatcher.execute
        state.register_subscription = dispatcher.execute
        dispatcher.native_retention = retention
        dispatcher.native_clone_authority = NativeCloneAuthority(
            lambda e, i, s: True, lambda e, i, s: conditions(i)
        )
        dispatcher.replay_event = NativeEventReplay(dispatcher, retention)
        dispatcher.execute(
            EffectInvocation(
                401749,
                1,
                boss.id,
                boss.id,
                boss.position,
                state_uid=carrier_uid,
                native_retained_container={"present": False},
            )
        )
        listener_uids = {
            entry.uid
            for entry in retention.view().entries
            if entry.generic_effect == 401749
        }
        self.assertTrue(listener_uids)
        for table in (9, 10):
            fight.native_table_turn = (
                table  # Explicit owned-calendar component premise.
            )
            fight.turn_id += 1
            fight.native_turn_event_deliveries = {
                f"{fight.turn_id}:{boss.id}:start": dict(
                    actor_id=boss.id,
                    turn_id=fight.turn_id,
                    phase="start",
                    event_id=1001,
                )
            }
            listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=boss.id)
            self.assertEqual(len(requests), table - 8)
            request, invocation = requests[-1]
            self.assertEqual(
                (request.spell_id, request.caster_id, request.cell),
                (8472, boss.id, boss.position),
            )
            self.assertEqual(
                (invocation.reference, invocation.caster_id, invocation.target_id),
                (401750, boss.id, boss.id),
            )
            row = fight.native_encounter_post_start_deliveries[
                f"{frozen['policy']}:{boss.id}:{table}"
            ]
            self.assertEqual(set(row["callbacks"][1]["eligible_uids"]), listener_uids)
            listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=boss.id)
            self.assertEqual(len(requests), table - 8)
