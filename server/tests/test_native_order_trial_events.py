"""Order outcomes require successful, owner-bound native handlers."""

from copy import deepcopy
import unittest
from types import SimpleNamespace

from wakfu_server import native_order_trial_checkpoint as checkpoint
from wakfu_server import native_order_trial_events as outcomes
from wakfu_server.achievements import native_order_trials as kernel
from wakfu_server.combat_area_boundary import adopt_fight
from wakfu_server.combat_active_spell import active_spell_scope
from wakfu_server.combat_effect_dispatch import (
    EffectInvocation,
    UnsupportedEffectExecution,
)
from wakfu_server.combat_state_handler import NativeStateHandler, StateCarrierContext
from wakfu_server.combat_state_ledger import StateChange
from wakfu_server.spell_audit import states_catalog

from test_native_order_trial_checkpoint import prepared_fixture


class NativeOrderTrialEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = states_catalog()

    def handler(self, fight, runner_uid, *, state_random=None):
        if fight.native_effect_uid_next is None:
            # The checkpoint fixture supplies admission and frozen form, but
            # not the live server's per-fight UID allocator initialization.
            fight.native_effect_uid_next = 10000
        return NativeStateHandler(
            fight,
            [],
            self.catalog,
            action_id=101,
            allocate_uid=fight.allocate_effect_uid,
            context=lambda *_args: StateCarrierContext(
                -1, 0, False, None, runner_uid, False, False, False, 0, None
            ),
            execute_child=lambda _invocation: None,
            state_random=state_random,
        )

    def pickup(self, fight, runner_uid, *, spell=4538, root=118980):
        actor = fight.actors[7]
        invocation = EffectInvocation(
            root,
            1,
            actor.id,
            actor.id,
            actor.position,
            native_running_uid=runner_uid,
        )
        state_changes = []
        original_apply_state = fight.apply_state

        def capture_state_change(*args, **kwargs):
            change = original_apply_state(*args, **kwargs)
            state_changes.append(change)
            return change

        fight.apply_state = capture_state_change
        with active_spell_scope(fight, spell, level=1):
            result = self.handler(fight, runner_uid).apply_reference(
                {"effect_class": 304}, invocation, 3046, 2
            )
        self.assertTrue(result)
        self.assertEqual(len(state_changes), 1)
        return state_changes[0], invocation

    def emit_pickup(self, fight, runner_uid):
        if fight.native_effect_uid_next is None:
            fight.native_effect_uid_next = 10000
        actor = fight.actors[7]
        invocation = EffectInvocation(
            118980,
            1,
            actor.id,
            actor.id,
            actor.position,
            native_running_uid=runner_uid,
        )
        with active_spell_scope(fight, 4538, level=1):
            self.assertTrue(
                self.handler(fight, runner_uid).apply_reference(
                    {"effect_class": 304}, invocation, 3046, 2
                )
            )
        return next(
            event
            for event in reversed(fight.events)
            if event.get("kind") == "native_order_state_applied"
        )

    def test_actual304_pickups_use_real_statechange_and_runner_to_additive_charges(
        self,
    ):
        fight = prepared_fixture()
        for index, expected_level in enumerate((2, 4), start=1):
            runner_uid = 9100 + index
            before = len(fight.events)
            change, _invocation = self.pickup(fight, runner_uid)
            self.assertIs(type(change), StateChange)
            self.assertIsNotNone(change.applied)
            self.assertEqual(change.applied.reference, 3046)
            self.assertEqual(change.applied.level, expected_level)
            batch = fight.events[before:]
            witness = next(
                event
                for event in batch
                if event.get("kind") == "native_order_state_applied"
            )
            self.assertEqual(
                (
                    witness["effect_reference"],
                    witness["spell_id"],
                    witness["runner_uid"],
                ),
                (118980, 4538, runner_uid),
            )
            self.assertEqual(witness["carrier_uid"], change.applied.uid)
            self.assertEqual(witness["after_level"], expected_level)
            self.assertEqual(outcomes.observe_pending(fight, events=(witness,)), 1)
            _, _, state = checkpoint.validate(
                fight.native_order_trial, encounter_id=fight.id, replay=False
            )
            self.assertEqual(
                (state.ingredient, state.charges), ("tomato", expected_level)
            )

    def test_failed304_and_ordinary_fight_emit_no_order_observation(self):
        fight = prepared_fixture()
        actor = fight.actors[7]
        handler = self.handler(fight, 9201, state_random=lambda _limit: 1)
        invocation = EffectInvocation(
            118980, 1, actor.id, actor.id, actor.position, native_running_uid=9201
        )
        before = len(fight.events)
        with active_spell_scope(fight, 4538, level=1):
            with self.assertRaisesRegex(
                UnsupportedEffectExecution, "native caster and target characteristics"
            ):
                handler(
                    {"effect_class": 304, "parameters": [3046, 2, 0]},
                    {"parameters": [3046, 2, 0]},
                    invocation,
                )
        self.assertEqual(fight.events[before:], [])
        self.assertEqual(fight.actors[7].state_ledger.entries, ())

        ordinary = prepared_fixture()
        del ordinary.native_order_trial
        actor = ordinary.actors[7]
        change, _ = self.pickup(ordinary, 9202)
        self.assertIs(type(change), StateChange)
        self.assertFalse(
            any(
                event.get("kind") == "native_order_state_applied"
                for event in ordinary.events
            )
        )

    def test_forged_runner_root_and_foreign_owner_are_rejected(self):
        fight = prepared_fixture()
        _change, _invocation = self.pickup(fight, 9301)
        witness = next(
            event
            for event in fight.events
            if event.get("kind") == "native_order_state_applied"
        )
        witness["runner_uid"] += 1
        with self.assertRaisesRegex(ValueError, "forged, changed or foreign"):
            outcomes.classify(fight, witness)

        wrong_root = prepared_fixture()
        before = len(wrong_root.events)
        with self.assertRaisesRegex(ValueError, "actual native carrier/action"):
            self.pickup(wrong_root, 9302, spell=4535)
        self.assertFalse(
            any(
                event.get("kind") == "native_order_state_applied"
                for event in wrong_root.events[before:]
            )
        )

        foreign = prepared_fixture()
        foreign.actors[7].owner_id += 1
        before = len(foreign.events)
        with self.assertRaisesRegex(ValueError, "original controlled owner"):
            self.pickup(foreign, 9303)
        self.assertFalse(
            any(
                event.get("kind") == "native_order_state_applied"
                for event in foreign.events[before:]
            )
        )

    def test_borrowed_plain_outcome_event_and_score_events_do_not_classify(self):
        fight = prepared_fixture()
        plain = fight._event(
            "native_order_state_applied",
            effect_reference=118980,
            spell_id=4538,
            runner_uid=9401,
            carrier_uid=9402,
            caster_id=7,
            target_id=7,
            state_reference=3046,
            before_level=0,
            after_level=2,
            carrier_sha256="0" * 64,
            ingredient="tomato",
        )
        with self.assertRaisesRegex(ValueError, "forged, changed or foreign"):
            outcomes.classify(fight, plain)
        for kind in ("finished", "client_score", "death", "score"):
            event = fight._event(kind, actor_id=7, score=999)
            self.assertIsNone(outcomes.classify(fight, event))

    def test_real_area_adoption_rebinds_only_fresh_candidate_witnesses(self):
        destination = prepared_fixture()
        destination.native_effect_uid_next = 10000
        old = self.emit_pickup(destination, 9501)
        self.assertEqual(outcomes.observe_pending(destination, events=(old,)), 1)
        previous_receipt = destination.native_order_trial["events"][0]["receipt"]

        candidate = deepcopy(destination)
        fresh = self.emit_pickup(candidate, 9502)
        previous_sequence = destination.sequence
        adopt_fight(destination, candidate)
        self.assertEqual(outcomes.classify(destination, fresh)["action"], "pickup")
        self.assertEqual(outcomes.observe_pending(destination, events=(fresh,)), 1)
        self.assertEqual(
            destination.native_order_trial["events"][0]["receipt"], previous_receipt
        )
        _, _, state = checkpoint.validate(
            destination.native_order_trial, encounter_id=destination.id, replay=False
        )
        self.assertEqual(state.charges, 4)
        self.assertIs(destination.events, candidate.events)
        self.assertGreater(fresh["sequence"], previous_sequence)

        plain_candidate = prepared_fixture()
        plain_sequence = plain_candidate.sequence
        plain_candidate._event("native_order_state_applied", runner_uid=9601)
        plain_destination = SimpleNamespace(
            id=plain_candidate.id,
            events=plain_candidate.events,
            native_order_trial=plain_candidate.native_order_trial,
        )
        with self.assertRaisesRegex(ValueError, "Fresh order witness changed"):
            outcomes.adopt_witnesses(
                plain_destination, plain_candidate, previous_sequence=plain_sequence
            )

        foreign_candidate = prepared_fixture()
        foreign_sequence = foreign_candidate.sequence
        foreign_source = prepared_fixture()
        foreign_candidate.native_effect_uid_next = 10000
        foreign_event = self.emit_pickup(foreign_source, 9602)
        foreign_candidate.events.append(foreign_event)
        foreign_candidate.sequence = foreign_event["sequence"]
        foreign_destination = SimpleNamespace(
            id=foreign_candidate.id,
            events=foreign_candidate.events,
            native_order_trial=foreign_candidate.native_order_trial,
        )
        with self.assertRaisesRegex(ValueError, "Fresh order witness changed"):
            outcomes.adopt_witnesses(
                foreign_destination,
                foreign_candidate,
                previous_sequence=foreign_sequence,
            )

        damaged_candidate = prepared_fixture()
        damaged_candidate.native_effect_uid_next = 10000
        damaged_sequence = damaged_candidate.sequence
        damaged = self.emit_pickup(damaged_candidate, 9603)
        damaged["runner_uid"] += 1
        damaged_destination = SimpleNamespace(
            id=damaged_candidate.id,
            events=damaged_candidate.events,
            native_order_trial=damaged_candidate.native_order_trial,
        )
        with self.assertRaisesRegex(ValueError, "Fresh order witness changed"):
            outcomes.adopt_witnesses(
                damaged_destination,
                damaged_candidate,
                previous_sequence=damaged_sequence,
            )

    def test_kernel_only_tenderize_repeat_and_destroy_transition(self):
        """Reducer semantics only; this does not prove a combat producer."""
        orders = (("blue", "tomato"), ("red", "cheese"), ("green", "pepper"))
        rules = kernel.OrderRules(
            tuple((recipe, 5) for recipe in sorted(kernel.RECIPES))
        )
        state = kernel.start(owner_id=7, encounter_id=77, hard_mode=True, orders=orders)

        def apply(state, receipt, action, **kwargs):
            return kernel.apply(
                state,
                rules,
                owner_id=7,
                encounter_id=77,
                receipt=receipt,
                action=action,
                **kwargs,
            )

        state = apply(state, "spawn", "spawn", target_id=-201, color="blue")
        state = apply(state, "tenderize-first", "tenderize", target_id=-201)
        state = apply(state, "tenderize-again", "tenderize", target_id=-201)
        self.assertEqual(len(state.larvae), 1)
        self.assertTrue(state.larvae[0].tenderized)
        state = apply(state, "second-hit-death", "destroy_tenderized", target_id=-201)
        self.assertEqual(state.larvae, ())

        state = apply(state, "spawn-plain", "spawn", target_id=-202, color="red")
        with self.assertRaisesRegex(ValueError, "lacks its first tenderize"):
            apply(state, "plain-death", "destroy_tenderized", target_id=-202)


if __name__ == "__main__":
    unittest.main()
