"""Scoped Faille descendant recipient contracts, without a score/victory claim."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
import json
import psycopg
from postgres_case import PostgresCase


class NoxFailleOriginalBossRecipientTests(PostgresCase):
    def policies(self):
        from wakfu_server import combat_encounter_effect_recipient as recipient
        from wakfu_server import combat_encounter_owned_start_binding as binding
        from wakfu_server import combat_encounter_roles as roles

        for module in (recipient, binding, roles):
            module._version.cache_clear()
            self.addCleanup(module._version.cache_clear)
            self.enterContext(
                patch.object(module, "_database", return_value=self.store)
            )
        assignment = roles.role_assignment(1435, (5664,))
        return recipient, binding, assignment

    def scene(self):
        from test_nox_owned_start_binding import NoxOwnedStartBindingTests
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_event_replay import NativeExternalEvent
        from wakfu_server.combat_turn_events import TURN_BOUNDARY_POLICY
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT

        recipient, binding, assignment = self.policies()
        _, _, fight, start_source, args = NoxOwnedStartBindingTests.fixture(self)
        fight.actors[1].position = (0, 0, 0)
        fight.actors[-200].position = (1, 0, 0)
        fight.actors[-200].hp = 100
        fight.phase = "placement"
        recipient.freeze_effect_recipient_policy(fight, roles=assignment)
        fight.phase = "active"
        with owned_turn_recipient_scope(fight, start_source.turn_boundary_context):
            self.assertEqual(binding.owned_start_caster(fight, start_source, **args), 1)
        rule = fight.native_encounter_effect_recipient_policy["rules"][1]
        context = dict(
            policy=TURN_BOUNDARY_POLICY,
            actor_id=1,
            turn_id=fight.turn_id,
            phase="regeneration",
            event_id=1037,
        )
        source = NativeExternalEvent(1, (1037,), 60, turn_boundary_context=context)
        parent = EffectInvocation(
            402211,
            1,
            1,
            1,
            (0, 0, 0),
            base_uid=81,
            state_uid=55,
            native_turn_boundary_context=context,
        )
        invocation = replace(parent, reference=402212, native_explicit_target=True)
        fight.native_owned_group_effects[81] = dict(
            invocation=dict(reference=402211, state_uid=55, caster_id=1, target_id=1)
        )
        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=fight),
            _active_activation=(parent, source, None, None),
        )
        effect = native_catalog.record(
            DATA_ROOT / "combat-state-definitions.json", "effects", 402212
        )
        return recipient, assignment, fight, dispatcher, effect, invocation, context

    def test_immutable_policy_checkpoint_absence_and_scope_do_not_follow_pointer(self):
        (
            recipient,
            assignment,
            fight,
            dispatcher,
            effect,
            invocation,
            context,
        ) = self.scene()
        frozen = deepcopy(fight.native_encounter_effect_recipient_policy)
        self.assertEqual(
            [r["effect_reference"] for r in frozen["rules"]], [402195, 402212]
        )
        with self.store.connection() as db:
            db.execute("DELETE FROM encounter_effect_recipient_active")
        fight.phase = "placement"
        self.assertEqual(
            recipient.freeze_effect_recipient_policy(fight, roles=assignment), frozen
        )
        absent = SimpleNamespace(phase="placement")
        self.assertIsNone(
            recipient.freeze_effect_recipient_policy(absent, roles=assignment)
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_effect_recipient_active VALUES(1435,ARRAY[5664],%s)",
                (frozen["policy"],),
            )
        self.assertIsNone(
            recipient.freeze_effect_recipient_policy(absent, roles=assignment)
        )
        for table in (
            "encounter_effect_recipient_versions",
            "encounter_effect_recipient_rules",
        ):
            with self.assertRaises(psycopg.Error), self.store.connection() as db:
                db.execute("DELETE FROM " + table)
        fight.native_encounter_effect_recipient_policy = json.loads(json.dumps(frozen))
        self.assertEqual(recipient._frozen(fight), frozen)
        fight.native_encounter_effect_recipient_policy["rules"][0]["native_parameters"][
            0
        ] = 9028.0
        with self.assertRaisesRegex(ValueError, "policy changed"):
            recipient._frozen(fight)
        fight.native_encounter_effect_recipient_policy = frozen
        with self.assertRaisesRegex(ValueError, "admission"):
            recipient.freeze_effect_recipient_policy(
                fight, roles=SimpleNamespace(map_id=1, monster_references=(5664,))
            )

    def test_actual_start_lineage_exact_carrier_tamper_once_and_private_rollback(self):
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )

        (
            recipient,
            assignment,
            fight,
            dispatcher,
            effect,
            invocation,
            context,
        ) = self.scene()
        canonical = deepcopy(vars(fight))
        with owned_turn_recipient_scope(fight, context):
            chosen = recipient.rebind_original_boss_recipient(
                dispatcher, effect, invocation, (402211,)
            )
            self.assertEqual(
                (chosen.caster_id, chosen.target_id, chosen.cell), (1, -200, (1, 0, 0))
            )
            self.assertEqual((invocation.caster_id, invocation.target_id), (1, 1))
            with self.assertRaisesRegex(ValueError, "already consumed"):
                recipient.rebind_original_boss_recipient(
                    dispatcher, effect, invocation, (402211,)
                )
        # A later failed native child must discard the candidate journal too.
        committed = deepcopy(vars(fight))
        candidate = deepcopy(fight)
        candidate.native_encounter_effect_recipient_deliveries = {}
        dispatcher.native_retention.fight = candidate
        with self.assertRaisesRegex(RuntimeError, "later native child"):
            with owned_turn_recipient_scope(candidate, context):
                recipient.rebind_original_boss_recipient(
                    dispatcher, effect, invocation, (402211,)
                )
                raise RuntimeError("later native child failure")
        self.assertTrue(candidate.native_encounter_effect_recipient_deliveries)
        self.assertEqual(vars(fight), committed)
        for mutate in (
            lambda f: f.native_owned_start_caster_deliveries.clear(),
            lambda f: f.native_owned_group_effects[81]["invocation"].update(
                state_uid=999
            ),
            lambda f: setattr(f.actors[-200], "team", assignment.player_team),
        ):
            preview = deepcopy(fight)
            preview.native_encounter_effect_recipient_deliveries = {}
            mutate(preview)
            dispatcher.native_retention.fight = preview
            with owned_turn_recipient_scope(preview, context), self.assertRaises(
                ValueError
            ):
                recipient.rebind_original_boss_recipient(
                    dispatcher, effect, invocation, (402211,)
                )
            self.assertEqual(preview.native_encounter_effect_recipient_deliveries, {})
        dispatcher.native_retention.fight = fight
        with owned_turn_recipient_scope(fight, context), self.assertRaisesRegex(
            ValueError, "escaped"
        ):
            recipient.rebind_original_boss_recipient(
                dispatcher, dict(effect, criteria="True"), invocation, (402211,)
            )
        self.assertEqual(
            fight.native_owned_group_effects, canonical["native_owned_group_effects"]
        )
        fight.native_encounter_effect_recipient_policy = None
        self.assertIs(
            recipient.rebind_original_boss_recipient(
                dispatcher, effect, invocation, (402211,)
            ),
            invocation,
        )

    def test_real_replay_decays_then_gains_original_boss_counter_and_keeps_marker_on_player(
        self,
    ):
        """Constructor/counter premises, real native owned replay and state handlers."""
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT
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
        from wakfu_server.combat_state_decurse import NativeStateDecurseHandler
        from wakfu_server.combat_event_replay import (
            NativeEventReplay,
            NativeCloneAuthority,
            NativeExternalEvent,
        )
        from wakfu_server.combat_conditions import ConditionContext
        from wakfu_server.combat_qi_fight import (
            install_fresh_actor_slots,
            prepare_fresh_actor_slots,
        )
        from wakfu_server.combat_turn_events import TURN_BOUNDARY_POLICY
        from wakfu_server.combat_external_turn_recipient import (
            owned_turn_recipient_scope,
        )

        recipient, binding, assignment = self.policies()

        def record(path, collection, reference):
            return native_catalog.record(DATA_ROOT / path, collection, reference)

        states = {
            str(ref): record("combat-state-definitions.json", "states", ref)
            for ref in (8969, 9027, 9028, 9029)
        }
        references = {402183, 402194, 402195, 402211, 402212, 402213}
        for state in states.values():
            references.update(state["effect_ids"])
        effects = {
            str(ref): record("combat-state-definitions.json", "effects", ref)
            for ref in references
        }
        metadata = {
            str(ref): record("native-retained-effect-metadata.json", "effects", ref)
            for ref in references
        }
        native = dict(states=states, effects=effects)
        pc = Actor(7, assignment.player_team, (0, 0, 0), 100, 6, 3, 10, 1, 3, True)
        boss = Actor(-7, assignment.npc_team, (1, 0, 0), 100, 6, 3, 5, 1)
        fight = Fight(
            77,
            [pc, boss],
            {pc.position, boss.position},
            {pc.team: {pc.position}, boss.team: {boss.position}},
        )
        fight.native_encounter_roles = assignment.record()
        binding.freeze_owned_start_binding(fight, roles=assignment)
        recipient.freeze_effect_recipient_policy(fight, roles=assignment)
        fight.native_qi_snapshot = dict(x=0, y=0, width=2, height=1, cell_masks=[0, 0])
        install_fresh_actor_slots(
            fight, prepare_fresh_actor_slots(fight, physical_radii={7: 0, -7: 0})
        )
        fight.ready(3)
        fight.native_effect_uid_next = 1
        fight.native_npc_initialization_receipts = {
            -7: dict(ref=5664, initialized=True, resolved_states=[dict(state_id=8969)])
        }
        packets = []
        retention = NativeRetainedRuntime(
            fight,
            packets,
            plan=dict(spell_id=6266, evaluation_level=1),
            state_catalog=native,
            action_id=1,
            timing=NativeEffectTimingProvider(native),
            metadata=dict(
                effects=metadata,
                states={
                    ref: record(
                        "native-retained-effect-metadata.json", "states", int(ref)
                    )
                    for ref in states
                },
            ),
        )
        carrier_context = StateCarrierContext(
            -1, 0, False, None, 100, False, False, False, 0, None
        )
        # Unrelated constructor and bonus-stat children are outside this small
        # counter-recipient component; every definition remains original.
        state = NativeStateHandler(
            fight,
            packets,
            native,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *args: carrier_context,
            execute_child=lambda inv: False,
            applied_state_scope=retention.applied_state_scope,
        )
        for target, reference, level in (
            (boss, 8969, 1),
            (boss, 9027, 3),
            (pc, 9028, 1),
        ):
            self.assertTrue(
                retention.apply_state_reference(
                    state,
                    EffectInvocation(
                        -1,
                        level,
                        boss.id,
                        target.id,
                        target.position,
                        native_retained_container={"present": False},
                    ),
                    reference,
                    level,
                    carrier_context=carrier_context,
                )
            )
        carrier = next(
            entry for entry in pc.state_ledger.entries if entry.reference == 9028
        )

        def conditions(invocation=None):
            caster = pc if invocation is None else fight.actors[invocation.caster_id]
            target = pc if invocation is None else fight.actors[invocation.target_id]
            actors = {
                name: actor.state_ledger.condition_actor(
                    retained_effect_ids=frozenset(
                        row[0]
                        for row in native_retained_condition_effects(fight, actor.id)
                    )
                )
                for name, actor in (("caster", caster), ("target", target))
            }
            return ConditionContext(
                actors,
                state_range_query=lambda maximum, role, ref, level, in_play, owner: sum(
                    any(s.reference == ref for s in a.state_ledger.entries)
                    for a in fight.actors.values()
                ),
            )

        def reapply(effect, reference, level, invocation):
            return retention.apply_state_reference(
                state, invocation, reference, level, carrier_context=carrier_context
            )

        decurse = NativeStateDecurseHandler(
            fight,
            packets,
            native,
            action_id=1,
            state_handler=state,
            reapply_state=reapply,
            allocate_uid=fight.allocate_effect_uid,
        )
        dispatcher = EffectDispatcher(
            effects,
            {
                304: retention.wrap(state, state=True),
                321: retention.wrap(decurse, state=True),
            },
            resolve=lambda effect, inv: (inv,),
            condition_context=conditions,
            probability_accepts=lambda probability, inv: probability == 100,
            group_cells=lambda *args: (),
            actor_position=lambda identity: fight.actors[identity].position,
            group_retention=retention,
            invocation_reconstruction=lambda effect, inv, ancestors: recipient.rebind_original_boss_recipient(
                dispatcher, effect, inv, ancestors
            ),
        )
        dispatcher.native_retention = retention
        dispatcher.native_clone_authority = NativeCloneAuthority(
            lambda e, i, s: True, lambda e, i, s: conditions(i)
        )
        replay = NativeEventReplay(dispatcher, retention)
        # Qualified259 START is invoked with the original subscribed descriptor,
        # carrier and retained UID. Its lineage journal is produced by the real
        # authority function, not inserted by this fixture.
        dispatcher.execute(
            EffectInvocation(
                402183,
                1,
                boss.id,
                pc.id,
                pc.position,
                state_uid=carrier.uid,
                native_retained_container={"present": False},
            )
        )
        start_entry = next(
            entry
            for entry in retention.view().entries
            if entry.generic_effect == 402183
        )
        original = EffectInvocation(
            **fight.native_owned_group_effects[start_entry.uid]["invocation"]
        )
        start_context = dict(
            policy=TURN_BOUNDARY_POLICY,
            actor_id=pc.id,
            turn_id=fight.turn_id,
            phase="start",
            event_id=1001,
        )
        start_source = NativeExternalEvent(
            pc.id, (1001,), 60, turn_boundary_context=start_context
        )
        with owned_turn_recipient_scope(fight, start_context):
            self.assertEqual(
                binding.owned_start_caster(
                    fight,
                    start_source,
                    entry=start_entry,
                    original=original,
                    definition=metadata["402183"],
                    effect=effects["402183"],
                ),
                pc.id,
            )
        # These original retained descendants are component premises after that
        # qualified START; no full Faille acquisition or encounter is claimed.
        for ref in (402194, 402211):
            dispatcher.execute(
                EffectInvocation(
                    ref,
                    1,
                    pc.id,
                    pc.id,
                    pc.position,
                    state_uid=carrier.uid,
                    native_retained_container={"present": False},
                )
            )
        original_rows = deepcopy(
            {
                uid: row["invocation"]
                for uid, row in fight.native_owned_group_effects.items()
            }
        )
        for phase, event, ref, expected in (
            ("end", 1002, 402194, 2),
            ("regeneration", 1037, 402211, 4),
        ):
            context = dict(
                policy=TURN_BOUNDARY_POLICY,
                actor_id=pc.id,
                turn_id=fight.turn_id,
                phase=phase,
                event_id=event,
            )
            source = NativeExternalEvent(
                pc.id, (event,), 60, turn_boundary_context=context
            )
            selected = frozenset(
                entry.uid
                for entry in retention.view().entries
                if entry.generic_effect == ref
            )
            self.assertTrue(selected)
            with owned_turn_recipient_scope(fight, context):
                replay(
                    source,
                    authority=dispatcher.native_clone_authority,
                    eligible_uids=selected,
                )
            self.assertEqual(
                next(
                    entry.level
                    for entry in boss.state_ledger.entries
                    if entry.reference == 9027
                ),
                expected,
            )
            self.assertNotIn(
                9027, {entry.reference for entry in pc.state_ledger.entries}
            )
        self.assertIn(9029, {entry.reference for entry in pc.state_ledger.entries})
        self.assertNotIn(9029, {entry.reference for entry in boss.state_ledger.entries})
        journal = fight.native_encounter_effect_recipient_deliveries
        self.assertEqual(
            {row["effect_reference"] for row in journal.values()}, {402195, 402212}
        )
        self.assertTrue(
            all(row["reconstructed_target"] == boss.id for row in journal.values())
        )
        for uid, original_row in original_rows.items():
            if uid in fight.native_owned_group_effects:
                self.assertEqual(
                    fight.native_owned_group_effects[uid]["invocation"], original_row
                )
