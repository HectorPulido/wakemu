"""Scoped calendar publisher contracts; table eight is a component premise."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

import psycopg
from postgres_case import PostgresCase


class NoxPostStartTableListenerTests(PostgresCase):
    def fixture(self):
        from wakfu_server import combat_encounter_table_listeners as listeners
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        listeners._version.cache_clear()
        self.addCleanup(listeners._version.cache_clear)
        self.enterContext(patch.object(listeners, "_database", return_value=self.store))
        frozen = listeners.freeze_table_listener_policy(1435, (5664,))
        self.assertEqual(len(frozen["callbacks"]), 1)
        callback = frozen["callbacks"][0]
        self.assertEqual(
            (
                callback["effect_reference"],
                callback["owner_state"],
                callback["forbidden_state"],
                callback["event_id"],
                callback["channel"],
            ),
            (401544, 8978, 8979, 1005, 60),
        )
        effect = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", 401544
        )
        metadata = native_catalog.record(
            DATA_ROOT / "native-retained-effect-metadata.json", "effects", 401544
        )
        boss = SimpleNamespace(
            id=-200,
            controlled=False,
            hp=100,
            state_ledger=SimpleNamespace(
                entries=(
                    SimpleNamespace(
                        uid=10, reference=8978, caster_id=-200, target_id=-200
                    ),
                )
            ),
        )
        # An explicit post-1001 component premise, not an earned-calendar claim.
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
            native_turn_event_deliveries={
                "17:-200:start": dict(
                    actor_id=-200, turn_id=17, phase="start", event_id=1001
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
        entries = [
            SimpleNamespace(uid=11, manager_id=-200, generic_effect=401544),
            SimpleNamespace(uid=12, manager_id=7, generic_effect=401544),
        ]
        calls = []

        def replay(source, **kwargs):
            calls.append((source, kwargs))
            # Simulate birth inside replay: it must not hear this publication.
            entries.append(
                SimpleNamespace(uid=13, manager_id=-200, generic_effect=401749)
            )
            return (True,)

        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(
                fight=fight,
                metadata={"effects": {"401544": metadata}},
                view=lambda: SimpleNamespace(entries=tuple(entries)),
            ),
            effects={"401544": effect},
            native_clone_authority=object(),
            replay_event=replay,
        )
        return listeners, frozen, fight, dispatcher, calls

    def test_database_authority_immutable_inventory_and_explicit_absence_pin(self):
        listeners, frozen, fight, dispatcher, calls = self.fixture()
        roles = SimpleNamespace(map_id=1435, monster_references=(5664,))
        with self.store.connection() as db:
            with self.assertRaises(psycopg.Error):
                with db.transaction():
                    db.execute(
                        "UPDATE encounter_table_listener_callbacks SET event_id=1002 "
                        "WHERE policy=%s",
                        (frozen["policy"],),
                    )
            db.execute("DELETE FROM encounter_table_listener_active WHERE map_id=1435")
        self.assertEqual(
            listeners.freeze_encounter_table_listener_policy(fight, roles=roles), frozen
        )
        absent = SimpleNamespace()
        self.assertIsNone(
            listeners.freeze_encounter_table_listener_policy(absent, roles=roles)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_table_listener_active(map_id,monster_references,policy) "
                "VALUES (1435,ARRAY[5664],%s)",
                (frozen["policy"],),
            )
        self.assertIsNone(
            listeners.freeze_encounter_table_listener_policy(absent, roles=roles)
        )
        frozen["callbacks"][0]["event_id"] = 1002
        with self.assertRaisesRegex(ValueError, "policy changed"):
            listeners.frozen_table_listener_policy(fight)
        # Existing Ombrage policy has no additional-content serialization delta.
        ordinary = listeners.freeze_table_listener_policy(1229, (4770,))
        self.assertNotIn("callbacks", ordinary)

    def test_post_start_owned_snapshot_once_checkpoint_and_failed_preview(self):
        listeners, frozen, fight, dispatcher, calls = self.fixture()
        original = deepcopy(fight)
        preview = deepcopy(fight)
        dispatcher.native_retention.fight = preview

        def failure(*args, **kwargs):
            raise ValueError("native callback failure")

        with patch.object(dispatcher, "replay_event", side_effect=failure):
            with self.assertRaisesRegex(ValueError, "native callback failure"):
                listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=-200)
        self.assertFalse(hasattr(preview, "native_encounter_post_start_deliveries"))
        self.assertEqual(vars(fight), vars(original))
        dispatcher.native_retention.fight = fight
        self.assertEqual(
            listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=-200),
            (True,),
        )
        source, arguments = calls[0]
        self.assertEqual(
            (source.manager_actor_id, source.event_ids, source.channel),
            (-200, (1005,), 60),
        )
        self.assertEqual(arguments["eligible_uids"], frozenset({11}))
        self.assertIsNone(source.uid)
        self.assertIsNone(source.movement_boundary_context)
        fight.native_encounter_post_start_deliveries = json.loads(
            json.dumps(fight.native_encounter_post_start_deliveries)
        )
        self.assertEqual(
            listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=-200), ()
        )
        self.assertEqual(len(calls), 1)
        for mutate in (
            lambda f: f.native_turn_event_deliveries.clear(),
            lambda f: f.native_owned_group_effects[11]["invocation"].update(
                caster_id=7
            ),
        ):
            bad = deepcopy(original)
            mutate(bad)
            dispatcher.native_retention.fight = bad
            with self.assertRaises(ValueError):
                listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=-200)
            self.assertFalse(hasattr(bad, "native_encounter_post_start_deliveries"))


class NoxPostStartProductionCallerTests(__import__("unittest").TestCase):
    def test_actual_turn_start_publishes_after_1001_and_keeps_original_preview_private(
        self,
    ):
        from test_combat_turn_events import OwnedTurnEndTests
        from wakfu_server import combat_server_spell as server
        from wakfu_server import combat_turn_events as turns
        from wakfu_server import combat_encounter_table_listeners as listeners
        from wakfu_server import combat_npc_phase_controller as phases
        from wakfu_server import combat_ogrest_phase_controller as ogrest
        from wakfu_server import combat_periodic_aptitude as aptitude

        fight, _, _ = OwnedTurnEndTests().fixture()
        actor_id = fight.current.id
        before = (
            deepcopy(fight.native_turn_event_deliveries)
            if hasattr(fight, "native_turn_event_deliveries")
            else None
        )
        order = []

        def factory(preview, plan):
            return SimpleNamespace(native_retention=SimpleNamespace(fight=preview)), []

        def start(dispatcher, *, actor_id):
            order.append("1001")
            dispatcher.native_retention.fight.native_turn_event_deliveries = {
                "proof": dict(actor_id=actor_id, event_id=1001)
            }

        def post(dispatcher, *, actor_id):
            order.append("post_start")
            self.assertEqual(
                dispatcher.native_retention.fight.native_turn_event_deliveries["proof"][
                    "event_id"
                ],
                1001,
            )

        with patch.object(
            server, "server_runtime", return_value=(factory, None)
        ), patch.object(turns, "deliver_turn_start", side_effect=start), patch.object(
            phases, "deliver_npc_score_result"
        ), patch.object(
            phases, "deliver_npc_table_phase"
        ), patch.object(
            ogrest, "deliver_ogrest_post_turn_start"
        ), patch.object(
            aptitude, "renew_periodic_aptitudes"
        ), patch.object(
            listeners, "deliver_owned_post_start_listeners", side_effect=post
        ):
            preview, packets = server.prepare_server_turn_start(
                None, {}, fight, b"", actor_id=actor_id, action_id=1
            )
        self.assertEqual(order, ["1001", "post_start"])
        self.assertIsNot(preview, fight)
        self.assertEqual(getattr(fight, "native_turn_event_deliveries", None), before)
        self.assertEqual(packets, ())


class NoxPostStartNativeConsumerTests(PostgresCase):
    def test_original_calendar_branch_creates_fatality_and_its_terminal_subscription(
        self,
    ):
        """Premise: table eight and constructor carrier; exercise one native branch."""
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
            for ref in (8978, 8979)
        }
        refs = {401544, 401546, 401563}
        for state in states.values():
            refs.update(state["effect_ids"])
        effects = {
            str(ref): record("combat-state-definitions.json", "effects", ref)
            for ref in refs
        }
        # Dispatcher validates each direct child definition before resolver scope.
        for ref in effects["401544"]["children"]:
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
                    for ref in (8978, 8979)
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
            8978,
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

        # This component qualifies the original fatality carrier branch only.
        # Sibling damage/geometry and removal programs retain their definitions
        # but are outside this small fixture's authority.
        selected = {401544, 401546, 401563}
        dispatcher = EffectDispatcher(
            effects,
            {304: retention.wrap(state, state=True)},
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
                401544,
                1,
                boss.id,
                boss.id,
                boss.position,
                state_uid=carrier_uid,
                native_retained_container={"present": False},
            )
        )
        old_uids = {
            entry.uid
            for entry in retention.view().entries
            if entry.generic_effect == 401544
        }
        self.assertTrue(old_uids)
        fight.native_table_turn = 7
        fight.native_turn_event_deliveries = {
            f"{fight.turn_id}:{boss.id}:start": dict(
                actor_id=boss.id, turn_id=fight.turn_id, phase="start", event_id=1001
            )
        }
        listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=boss.id)
        self.assertNotIn(8979, {entry.reference for entry in boss.state_ledger.entries})
        fight.native_table_turn = (
            8  # Explicit component premise; no paid-calendar claim.
        )
        listeners.deliver_owned_post_start_listeners(dispatcher, actor_id=boss.id)
        fatality = next(
            entry for entry in boss.state_ledger.entries if entry.reference == 8979
        )
        self.assertEqual((fatality.caster_id, fatality.target_id), (boss.id, boss.id))
        terminal = [
            entry
            for entry in retention.view().entries
            if entry.generic_effect == 401563
        ]
        self.assertTrue(terminal)
        for entry in terminal:
            self.assertEqual(
                fight.native_owned_group_effects[entry.uid]["invocation"]["state_uid"],
                fatality.uid,
            )
        journal = fight.native_encounter_post_start_deliveries[
            f"{frozen['policy']}:{boss.id}:8"
        ]
        self.assertEqual(set(journal["callbacks"][0]["eligible_uids"]), old_uids)
