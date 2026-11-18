"""Terminal settlement boundary for the dormant native order-trial sidecar."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import struct
from unittest import TestCase
from unittest.mock import patch

from wakfu_server import native_order_trial_admission as admission
from wakfu_server import native_order_trial_checkpoint as sidecar
from wakfu_server.achievements import native_order_trials as kernel
from wakfu_server.achievements.native_order_trial_settlement import (
    CompletionRule,
    stage,
    stage_withdrawal,
)
from wakfu_server.combat_pve_withdraw import plan as plan_withdrawal
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Session
from wakfu_server.combat_state import Actor
from test_native_order_trial_checkpoint import prepared_fixture, stage_fixture


ORDERS = (("blue", "tomato"), ("red", "cheese"), ("green", "pepper"))
WEIGHTS = tuple((recipe, 150) for recipe in sorted(kernel.RECIPES))
NATIVE = Path(__file__).with_name("fixtures").joinpath("pizzlarva-native-form.json")


class _DB:
    def __init__(
        self,
        fight,
        *,
        fight_status="finished",
        checkpoint_status="ended",
        checkpoint=None,
        participant_account=3,
    ):
        self.fight = fight
        self.fight_status = fight_status
        self.checkpoint_status = checkpoint_status
        self.checkpoint = checkpoint
        self.participant_account = participant_account

    def execute(self, query, params=()):
        self.query = query
        self.params = params
        return self

    def fetchone(self):
        if "FROM combat_fights f JOIN fight_checkpoints" in self.query:
            snapshot = self.checkpoint
            if snapshot is None:
                snapshot = {
                    "phase": "finished",
                    sidecar.FIELD: deepcopy(self.fight.native_order_trial),
                }
            return {
                "fight_status": self.fight_status,
                "checkpoint_status": self.checkpoint_status,
                "snapshot": snapshot,
            }
        if "FROM combat_fight_participants" in self.query:
            return {"account_id": self.participant_account}
        raise AssertionError(self.query)


class _Store:
    def __init__(self):
        self.character_calls = []

    def character(self, account_id, character_id, db):
        self.character_calls.append((account_id, character_id, db))
        return {"id": character_id, "account_id": account_id}


def _finished_fight(*, threshold=400, mode="hard", terminal="strikes"):
    """Build an actual valid sidecar; score weights are explicitly synthetic."""
    fight = prepared_fixture()
    document = deepcopy(fight.native_order_trial)
    hard_proof, _, _ = sidecar.validate(document, encounter_id=fight.id)
    capability = document["capability"]
    if mode == "hard":
        proof = hard_proof
        initial = kernel.start(
            owner_id=proof.owner_id,
            encounter_id=fight.id,
            hard_mode=True,
            orders=ORDERS,
        )
    else:
        native = json.loads(NATIVE.read_text())
        source = capability["sources"]["normal"]
        character = dict(
            id=hard_proof.owner_id,
            account_id=hard_proof.account_id,
            instance_id=99,
            map_id=source["map_id"],
            **dict(zip(("x", "y", "z"), source["approaches"][0])),
        )
        proof = admission.plan(
            capability,
            character,
            struct.pack(">qHH", source["object_id"], 0, 0),
            native_source=native["mode_objects"][str(source["object_id"])],
        )
        proof = replace(proof, generation="selected-test")
        initial = kernel.start(
            owner_id=proof.owner_id,
            encounter_id=fight.id,
            hard_mode=False,
            orders=ORDERS,
        )

    rules = kernel.OrderRules(WEIGHTS, score_threshold=threshold)
    delattr(fight, sidecar.FIELD)
    sidecar.install(
        fight,
        proof,
        initial,
        rules,
        capability=capability,
        provenance=document["rules"]["provenance"],
    )
    for index, (color, ingredient) in enumerate(ORDERS, start=1):
        target = -300 - index
        stage_fixture(fight, "spawn", target_id=target, color=color)
        stage_fixture(fight, "pickup", ingredient=ingredient)
        stage_fixture(fight, "tenderize", target_id=target)
        stage_fixture(fight, "garnish", target_id=target)
        stage_fixture(fight, "bake", target_id=target)
    if terminal == "strikes":
        # Three authentic reducer escape observations finish as a defeat
        # without requiring team victory or a synthetic client score.
        for index in range(3):
            target = -400 - index
            stage_fixture(fight, "spawn", target_id=target, color="blue")
            stage_fixture(fight, "escape", target_id=target)
        fight.phase = "finished"
        fight.winner = 1
    proof, rules, state = sidecar.validate(
        fight.native_order_trial, encounter_id=fight.id
    )
    assert state.hard_mode is (mode == "hard")
    if terminal == "strikes":
        assert state.finished and state.strikes == 3
    else:
        assert not state.finished
    return (
        fight,
        proof,
        CompletionRule(
            proof.profile_id,
            event_reference=4261,
            minimum_score=rules.score_threshold,
            evidence="focused settlement boundary test",
        ),
    )


class _WithdrawalDB:
    def __init__(
        self,
        fight,
        proof,
        *,
        generation=None,
        participant_generation=None,
        account_id=None,
        checkpoint=None,
        fight_status="active",
        checkpoint_status="active",
    ):
        self.fight = fight
        self.proof = proof
        self.generation = proof.generation if generation is None else generation
        self.participant_generation = (
            proof.generation
            if participant_generation is None
            else participant_generation
        )
        self.account_id = proof.account_id if account_id is None else account_id
        self.checkpoint = checkpoint
        self.fight_status = fight_status
        self.checkpoint_status = checkpoint_status

    def execute(self, _query, _params=()):
        return self

    def fetchone(self):
        snapshot = self.checkpoint
        if snapshot is None:
            snapshot = {
                "phase": "active",
                sidecar.FIELD: deepcopy(self.fight.native_order_trial),
            }
        return {
            "fight_status": self.fight_status,
            "checkpoint_status": self.checkpoint_status,
            "snapshot": snapshot,
            "account_id": self.account_id,
            "session_generation": self.generation,
            "participant_generation": self.participant_generation,
        }


def _withdrawal_candidate(*, threshold=400, mode="hard"):
    fight, proof, rule = _finished_fight(
        threshold=threshold, mode=mode, terminal="withdrawal"
    )
    # Re-open the fixture's active phase through the real two-owner Ready
    # transition so the withdrawal candidate comes from combat_pve_withdraw.
    fight.phase = "placement"
    fight.order = []
    fight.turn_index = 0
    fight.turn_id = 0
    fight.ready_owners.clear()
    teammate = Actor(8, 0, (3, 0, 0), 100, 6, 3, 10, 50, 4, True)
    fight.walkable.add(teammate.position)
    fight.placement[0].add(teammate.position)
    fight.actors[teammate.id] = teammate
    fight.ready(proof.account_id)
    fight.ready(teammate.owner_id)
    runtime = RuntimeMessages(fight)
    session = Session(proof.account_id, proof.owner_id, proof.generation, 885, 99)
    withdrawal = plan_withdrawal(session, fight, runtime)
    return fight, proof, rule, withdrawal.fight


class NativeOrderTrialSettlementTests(TestCase):
    def test_three_strike_defeat_delegates_once_without_victory(self):
        fight, proof, rule = _finished_fight()
        db, store = _DB(fight, participant_account=proof.account_id), _Store()
        responses = iter([["objective-packet"], []])
        with patch(
            "wakfu_server.achievements.mission_toolkit.settle",
            side_effect=lambda *args: next(responses),
        ) as settle:
            first = stage(db, store, fight, rule)
            replay = stage(db, store, fight, rule)

        self.assertEqual(first, {proof.account_id: ["objective-packet"]})
        self.assertEqual(replay, {})
        self.assertEqual(settle.call_count, 2)
        first_args = settle.call_args_list[0].args
        replay_args = settle.call_args_list[1].args
        self.assertEqual(first_args[1], store)
        self.assertEqual(first_args[2]["id"], proof.owner_id)
        self.assertEqual(first_args[3], replay_args[3])
        self.assertTrue(first_args[3].startswith(f"native-order-trial:{fight.id}:"))
        self.assertEqual(first_args[4:], ("scenario_completed", 4261))
        self.assertEqual(
            store.character_calls[0][:2], (proof.account_id, proof.owner_id)
        )

    def test_terminal_checkpoint_and_original_owner_are_required(self):
        fight, proof, rule = _finished_fight()
        store = _Store()
        cases = (
            ("aborted fight", _DB(fight, fight_status="aborted")),
            ("aborted checkpoint", _DB(fight, checkpoint_status="aborted")),
            (
                "foreign participant",
                _DB(fight, participant_account=proof.account_id + 1),
            ),
            (
                "mismatched sidecar",
                _DB(
                    fight,
                    checkpoint={"phase": "finished", sidecar.FIELD: {"tampered": True}},
                ),
            ),
            (
                "nonterminal snapshot",
                _DB(
                    fight,
                    checkpoint={
                        "phase": "active",
                        sidecar.FIELD: deepcopy(fight.native_order_trial),
                    },
                ),
            ),
        )
        for label, db in cases:
            with self.subTest(label=label), patch(
                "wakfu_server.achievements.mission_toolkit.settle"
            ) as settle:
                with self.assertRaises(ValueError):
                    stage(db, store, fight, rule)
                settle.assert_not_called()

    def test_normal_below_threshold_aborted_and_ordinary_fights_do_not_settle(self):
        normal, _proof, normal_rule = _finished_fight(mode="normal")
        below, _proof, below_rule = _finished_fight(threshold=500)
        aborted, _proof, aborted_rule = _finished_fight()
        aborted.phase = "aborted"
        ordinary, _proof, ordinary_rule = _finished_fight()
        delattr(ordinary, sidecar.FIELD)
        cases = (
            ("normal mode", normal, normal_rule),
            ("below threshold", below, below_rule),
            ("aborted", aborted, aborted_rule),
            ("no sidecar", ordinary, ordinary_rule),
            ("not finished", _unfinished_copy(normal), normal_rule),
        )
        for label, fight, rule in cases:
            with self.subTest(label=label), patch(
                "wakfu_server.achievements.mission_toolkit.settle"
            ) as settle:
                self.assertEqual(stage(_DB(fight), _Store(), fight, rule), {})
                settle.assert_not_called()

    def test_shared_toolkit_retains_explicit_quest_admission(self):
        fight, proof, rule = _finished_fight()
        with patch(
            "wakfu_server.achievements.mission_toolkit.settle", return_value=[]
        ) as settle:
            result = stage(
                _DB(fight, participant_account=proof.account_id), _Store(), fight, rule
            )
        self.assertEqual(result, {})
        self.assertEqual(settle.call_args.args[4:], ("scenario_completed", 4261))

    def test_actual_individual_withdrawal_candidate_uses_active_score_checkpoint(self):
        fight, proof, rule, candidate = _withdrawal_candidate()
        self.assertEqual(candidate.phase, "active")
        self.assertTrue(candidate.actors[proof.owner_id].pve_withdrawn)
        self.assertTrue(
            any(
                event.get("kind") == "withdrawn"
                and event.get("actor_id") == proof.owner_id
                and event.get("owner_id") == proof.account_id
                for event in candidate.events
            )
        )
        self.assertFalse(getattr(fight.actors[proof.owner_id], "pve_withdrawn", False))
        self.assertEqual(fight.actors[proof.owner_id].hp, 100)
        proof2, rules2, state2 = sidecar.validate(
            candidate.native_order_trial, encounter_id=candidate.id
        )
        self.assertEqual((proof2, rules2.score_threshold), (proof, rule.minimum_score))
        self.assertFalse(state2.finished)

        store = _Store()
        with patch(
            "wakfu_server.achievements.mission_toolkit.settle",
            return_value=["withdrawal-objective"],
        ) as settle:
            result = stage_withdrawal(
                _WithdrawalDB(candidate, proof), store, candidate, rule
            )
        self.assertEqual(result, {proof.account_id: ["withdrawal-objective"]})
        self.assertEqual(settle.call_args.args[4:], ("scenario_completed", 4261))
        self.assertTrue(
            settle.call_args.args[3].startswith(f"native-order-trial:{candidate.id}:")
        )

    def test_withdrawal_needs_matching_receipt_checkpoint_and_generation(self):
        fight, proof, rule, candidate = _withdrawal_candidate()
        wrong_snapshot = {"phase": "active", sidecar.FIELD: {"tampered": True}}
        cases = (
            (
                "foreign generation",
                _WithdrawalDB(candidate, proof, generation="other-generation"),
            ),
            ("aborted fight", _WithdrawalDB(candidate, proof, fight_status="aborted")),
            (
                "aborted checkpoint",
                _WithdrawalDB(candidate, proof, checkpoint_status="aborted"),
            ),
            (
                "mismatched accepted sidecar",
                _WithdrawalDB(candidate, proof, checkpoint=wrong_snapshot),
            ),
            (
                "finished checkpoint",
                _WithdrawalDB(
                    candidate,
                    proof,
                    checkpoint={
                        "phase": "finished",
                        sidecar.FIELD: deepcopy(candidate.native_order_trial),
                    },
                ),
            ),
        )
        for label, db in cases:
            with self.subTest(label=label), patch(
                "wakfu_server.achievements.mission_toolkit.settle"
            ) as settle:
                with self.assertRaises(ValueError):
                    stage_withdrawal(db, _Store(), candidate, rule)
                settle.assert_not_called()

        missing_receipt = deepcopy(candidate)
        missing_receipt.events = [
            event
            for event in missing_receipt.events
            if event.get("kind") != "withdrawn"
        ]
        with patch("wakfu_server.achievements.mission_toolkit.settle") as settle:
            with self.assertRaisesRegex(ValueError, "native departure candidate"):
                stage_withdrawal(
                    _WithdrawalDB(missing_receipt, proof),
                    _Store(),
                    missing_receipt,
                    rule,
                )
            settle.assert_not_called()

    def test_warm_withdrawal_uses_current_durable_lease_without_mutating_admission_proof(
        self,
    ):
        fight, proof, rule, candidate = _withdrawal_candidate()
        original_proof, _rules, _state = sidecar.validate(
            candidate.native_order_trial, encounter_id=candidate.id
        )
        new_generation = "warm-reconnect-generation"
        store = _Store()
        with patch(
            "wakfu_server.achievements.mission_toolkit.settle",
            return_value=["withdrawal-objective"],
        ) as settle:
            result = stage_withdrawal(
                _WithdrawalDB(
                    candidate,
                    proof,
                    generation=new_generation,
                    participant_generation=new_generation,
                ),
                store,
                candidate,
                rule,
            )
        self.assertEqual(result, {proof.account_id: ["withdrawal-objective"]})
        settle.assert_called_once()
        retained_proof, _rules, _state = sidecar.validate(
            candidate.native_order_trial, encounter_id=candidate.id
        )
        self.assertEqual(retained_proof, original_proof)
        self.assertEqual(retained_proof.generation, proof.generation)

        rejected = (
            _WithdrawalDB(
                candidate,
                proof,
                generation=proof.generation,
                participant_generation=new_generation,
            ),
            _WithdrawalDB(
                candidate,
                proof,
                generation=new_generation,
                participant_generation=new_generation,
                account_id=proof.account_id + 1,
            ),
            _WithdrawalDB(
                candidate,
                proof,
                generation=new_generation,
                participant_generation=new_generation,
                checkpoint_status="aborted",
            ),
        )
        for db in rejected:
            with self.subTest(db=db), patch(
                "wakfu_server.achievements.mission_toolkit.settle"
            ) as denied:
                with self.assertRaises(ValueError):
                    stage_withdrawal(db, _Store(), candidate, rule)
                denied.assert_not_called()

    def test_withdrawal_requires_hard_score_at_or_above_threshold(self):
        cases = (
            ("normal mode", _withdrawal_candidate(mode="normal")),
            ("below threshold", _withdrawal_candidate(threshold=500)),
        )
        for label, (_fight, proof, rule, candidate) in cases:
            with self.subTest(label=label), patch(
                "wakfu_server.achievements.mission_toolkit.settle"
            ) as settle:
                self.assertEqual(
                    stage_withdrawal(
                        _WithdrawalDB(candidate, proof), _Store(), candidate, rule
                    ),
                    {},
                )
                settle.assert_not_called()


def _unfinished_copy(fight):
    candidate = deepcopy(fight)
    candidate.phase = "active"
    return candidate
