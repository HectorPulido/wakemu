"""Server-owned order requests with explicitly synthetic reducer receipts."""

from copy import deepcopy
import json
from pathlib import Path
import struct
from types import SimpleNamespace as Namespace
import unittest
from unittest.mock import patch

from wakfu_server import native_order_trial_admission as admission
from wakfu_server import native_order_trial_checkpoint as checkpoint
from wakfu_server import native_order_trial_orders as requests
from wakfu_server import native_order_trial_selection as selection
from wakfu_server.achievements import native_order_trials as kernel
from test_native_order_trial_checkpoint import prepared_fixture, stage_fixture


INITIAL = (("blue", "tomato"), ("red", "cheese"), ("green", "pepper"))
NEXT = (("red", "tomato"), ("blue", "pepper"), ("green", "cheese"))
NATIVE = Path(__file__).with_name("fixtures").joinpath("pizzlarva-native-form.json")


def _proof(fight, document, mode):
    hard_proof, _, _ = checkpoint.validate(document, encounter_id=fight.id)
    if mode == "hard":
        return hard_proof
    native = json.loads(NATIVE.read_text())
    source = document["capability"]["sources"]["normal"]
    character = dict(
        id=hard_proof.owner_id,
        account_id=hard_proof.account_id,
        instance_id=99,
        map_id=source["map_id"],
        **dict(zip(("x", "y", "z"), source["approaches"][0])),
    )
    proof = admission.plan(
        document["capability"],
        character,
        struct.pack(">qHH", source["object_id"], 0, 0),
        native_source=native["mode_objects"][str(source["object_id"])],
    )
    from dataclasses import replace

    return replace(proof, generation="selected-test")


def _new_trial(mode="hard"):
    fight = prepared_fixture()
    document = deepcopy(fight.native_order_trial)
    proof = _proof(fight, document, mode)
    rules = checkpoint.validate(document, encounter_id=fight.id)[1]
    delattr(fight, checkpoint.FIELD)
    dispatcher = Namespace(
        native_state_handler=Namespace(fight=fight),
        native_retention=Namespace(fight=fight),
    )
    return fight, proof, rules, document, dispatcher


def _install(fight, proof, rules, document, orders):
    initial_state = kernel.start(
        owner_id=proof.owner_id,
        encounter_id=fight.id,
        hard_mode=proof.hard_mode,
        orders=orders,
    )
    checkpoint.install(
        fight,
        proof,
        initial_state,
        rules,
        capability=document["capability"],
        provenance=document["rules"]["provenance"],
    )


def _serve_batch(fight, proof, orders):
    """Synthetic event classifier fixture; this does not prove a live spell producer."""
    last_event = None
    for index, (color, ingredient) in enumerate(orders):
        target = -500 - index
        stage_fixture(fight, "spawn", target_id=target, color=color)
        stage_fixture(fight, "pickup", ingredient=ingredient)
        stage_fixture(fight, "tenderize", target_id=target)
        stage_fixture(fight, "garnish", target_id=target)
        if index != len(orders) - 1:
            stage_fixture(fight, "bake", target_id=target)
            continue
        # Model the typed event shape expected from the later verified producer.
        # It is a synthetic fixture event, not evidence that native120461 has
        # been wired to this arcade.
        last_event = fight._event(
            "kill_hp_minimum_update",
            generic_effect=120461,
            source_id=proof.owner_id,
        )
        checkpoint.observe(
            fight,
            last_event,
            classify=lambda candidate, event: {
                "action": "bake",
                "arguments": {"target_id": target},
                "source": "synthetic unit fixture for order-refill boundary",
            },
        )
    return last_event


class NativeOrderTrialOrdersTests(unittest.TestCase):
    def test_initial_draw_is_distinct_and_checkpoint_replay_does_not_redraw(self):
        fight, proof, rules, document, dispatcher = _new_trial()
        with patch.object(selection, "draw_initial", return_value=INITIAL) as draw:
            first = requests.initial(dispatcher, proof)
        self.assertEqual(first, INITIAL)
        self.assertEqual(len(set(first)), 3)
        self.assertEqual(fight.native_order_request_policy, requests.POLICY)
        _install(fight, proof, rules, document, first)

        with patch.object(
            selection, "draw_initial", side_effect=AssertionError("replay rerolled")
        ) as draw:
            replay = requests.initial(dispatcher, proof)
        self.assertEqual(replay, first)
        draw.assert_not_called()

    def test_hard_mode_refills_only_after_current_receipt_clears_batch_and_json_replays(
        self,
    ):
        fight, proof, rules, document, dispatcher = _new_trial("hard")
        with patch.object(selection, "draw_initial", return_value=INITIAL):
            initial = requests.initial(dispatcher, proof)
        _install(fight, proof, rules, document, initial)
        fight.native_order_request_policy = dict(requests.POLICY)
        event = _serve_batch(fight, proof, initial)
        _, _, before = checkpoint.validate(
            fight.native_order_trial, encounter_id=fight.id
        )
        self.assertEqual(before.orders, ())

        selection_events = [
            fight._event(
                "native_turn_boundary_completed",
                actor_id=proof.owner_id,
                event_id=1001,
                source="synthetic selected-native-lottery boundary",
            ),
            fight._event(
                "native_order_recipe_selected",
                actor_id=proof.owner_id,
                initialization=False,
                source="synthetic selected-native-lottery witness",
            ),
        ]
        batch = [event, *selection_events]

        def selected(candidate, events):
            self.assertIs(candidate, fight)
            self.assertIs(events, batch)
            has_turn = any(
                row.get("kind") == "native_turn_boundary_completed"
                and row.get("event_id") == 1001
                and row.get("actor_id") == proof.owner_id
                for row in events
            )
            has_selection = any(
                row.get("kind") == "native_order_recipe_selected" for row in events
            )
            return NEXT if has_turn and has_selection else None

        with patch.object(selection, "selected", side_effect=selected) as select:
            self.assertTrue(requests.advance(fight, events=batch))
        select.assert_called_once_with(fight, batch)
        proof2, rules2, state = checkpoint.validate(
            json.loads(json.dumps(fight.native_order_trial)), encounter_id=fight.id
        )
        self.assertEqual(proof2, proof)
        self.assertEqual(rules2, rules)
        self.assertEqual(state.orders, NEXT)
        self.assertFalse(state.finished)

        with patch.object(selection, "selected", return_value=NEXT) as replay:
            self.assertFalse(requests.advance(fight, events=batch))
        replay.assert_called_once_with(fight, batch)

        waiting = [event]
        before_wait = deepcopy(fight.native_order_trial)
        with patch.object(selection, "selected", return_value=None) as no_lottery:
            self.assertFalse(requests.advance(fight, events=waiting))
        no_lottery.assert_called_once_with(fight, waiting)
        self.assertEqual(fight.native_order_trial, before_wait)

    def test_normal_mode_finishes_after_last_receipt_and_fake_or_foreign_receipt_rejects(
        self,
    ):
        fight, proof, rules, document, dispatcher = _new_trial("normal")
        with patch.object(selection, "draw_initial", return_value=INITIAL):
            initial = requests.initial(dispatcher, proof)
        _install(fight, proof, rules, document, initial)
        fight.native_order_request_policy = dict(requests.POLICY)
        event = _serve_batch(fight, proof, initial)
        with patch.object(
            selection,
            "draw_initial",
            side_effect=AssertionError("normal mode must not reroll"),
        ) as draw:
            self.assertTrue(requests.advance(fight, events=[event]))
        draw.assert_not_called()
        _, _, state = checkpoint.validate(
            json.loads(json.dumps(fight.native_order_trial)), encounter_id=fight.id
        )
        self.assertEqual(state.orders, ())
        self.assertTrue(state.finished)

        replay = checkpoint.validate(fight.native_order_trial, encounter_id=fight.id)[2]
        self.assertTrue(replay.finished)
        self.assertFalse(requests.advance(fight, events=[event]))

        hard_fight, hard_proof, hard_rules, hard_doc, hard_dispatcher = _new_trial(
            "hard"
        )
        with patch.object(selection, "draw_initial", return_value=INITIAL):
            hard_initial = requests.initial(hard_dispatcher, hard_proof)
        _install(hard_fight, hard_proof, hard_rules, hard_doc, hard_initial)
        hard_fight.native_order_request_policy = dict(requests.POLICY)
        _serve_batch(hard_fight, hard_proof, hard_initial)
        foreign = hard_fight._event(
            "kill_hp_minimum_update",
            generic_effect=120461,
            source_id=hard_proof.owner_id + 1,
        )
        with patch.object(selection, "selected", return_value=None):
            self.assertFalse(requests.advance(hard_fight, events=[foreign]))
        wrong_effect = hard_fight._event(
            "kill_hp_minimum_update",
            generic_effect=120460,
            source_id=hard_proof.owner_id,
        )
        with patch.object(selection, "selected", return_value=None):
            self.assertFalse(requests.advance(hard_fight, events=[wrong_effect]))
        hard_fight.native_order_request_policy = {**requests.POLICY, "distinct": False}
        with self.assertRaisesRegex(ValueError, "frozen native policy"):
            requests.advance(hard_fight, events=[foreign])


if __name__ == "__main__":
    unittest.main()
