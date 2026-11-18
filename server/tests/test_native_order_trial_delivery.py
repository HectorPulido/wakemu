"""Focused producer and teardown delivery tests for native order trials."""

import struct
from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from psycopg.pq import TransactionStatus

from wakfu_server.achievements import combat_adapter
from wakfu_server.achievements import native_order_trial_settlement as settlement
from wakfu_server import combat_abandon
from wakfu_server.combat_progression_delivery import after_return
from test_native_order_trial_checkpoint import prepared_fixture, stage_fixture
from wakfu_server import native_order_trial_checkpoint as checkpoint
from wakfu_server import native_order_trial_admission as admission
from wakfu_server.achievements import native_order_trials as kernel
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight


class _DB:
    """Only the terminal-checkpoint/participant reads made by stage()."""

    def __init__(self, fight, owner_id, account_id):
        self.fight = fight
        self.owner_id = owner_id
        self.account_id = account_id

    def execute(self, query, _params=()):
        self.query = query
        return self

    def fetchone(self):
        if "FROM combat_fights f JOIN fight_checkpoints" in self.query:
            return {
                "fight_status": "finished",
                "checkpoint_status": "ended",
                "snapshot": {
                    "phase": "finished",
                    checkpoint.FIELD: deepcopy(self.fight.native_order_trial),
                },
            }
        if "FROM combat_fight_participants" in self.query:
            return {"account_id": self.account_id}
        raise AssertionError(self.query)


class _Store:
    def __init__(self, character):
        self.value = character

    def character(self, account_id, character_id, _db=None):
        if (account_id, character_id) != (self.value["account_id"], self.value["id"]):
            return None
        return dict(self.value)

    def lock_character(self, _db, account_id, _generation, character_id):
        if (account_id, character_id) != (self.value["account_id"], self.value["id"]):
            raise ValueError("fixture owner mismatch")

    def now(self):
        return datetime.now(timezone.utc)


class _PersistDB:
    """Small isolated transaction cursor for the real withdraw-store hook."""

    def __init__(self, original, candidate, owner):
        self.original = original
        self.candidate = candidate
        self.owner = owner
        self.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
        self.query = ""
        self.params = ()
        self.rowcount = 0
        self.queries = []

    def execute(self, query, params=()):
        self.query, self.params = query, params
        self.queries.append(query)
        self.rowcount = 1 if "INSERT INTO combat_pve_withdrawals" in query else 0
        return self

    def fetchone(self):
        if "SELECT status FROM combat_fights" in self.query:
            return {"status": "active"}
        if "SELECT session_generation FROM combat_fight_participants" in self.query:
            return {"session_generation": self.owner.generation}
        if "FROM combat_fights f JOIN fight_checkpoints" in self.query:
            return {
                "fight_status": "active",
                "checkpoint_status": "active",
                "snapshot": {
                    "phase": "active",
                    checkpoint.FIELD: deepcopy(self.candidate.native_order_trial),
                },
                "account_id": self.owner.account_id,
                "session_generation": self.owner.generation,
            }
        if "FROM combat_fight_participants" in self.query:
            return {"account_id": self.owner.account_id}
        raise AssertionError(self.query)

    def __iter__(self):
        if "ORDER BY character_id FOR UPDATE" in self.query:
            return iter(
                (
                    {
                        "character_id": self.owner.character_id,
                        "session_generation": self.owner.generation,
                    },
                )
            )
        raise AssertionError(self.query)


def _actual_withdraw_store_persist(original, candidate, owner, store, character):
    """Call the real hook with external persistence mechanics tightly stubbed."""
    from wakfu_server import combat_pve_withdraw_store

    db = _PersistDB(original, candidate, owner)
    with (
        patch(
            "wakfu_server.combat_health.persist",
            return_value={"character": character, "applied": True},
        ),
        patch(
            "wakfu_server.combat_terminal_metadata.registered_summon_actor_ids",
            return_value=set(),
        ),
        patch(
            "wakfu_server.combat_companions.registered_companion_ids",
            return_value=set(),
        ),
        patch("wakfu_server.combat_companions.validate_durable_roster"),
        patch("wakfu_server.rift_withdrawal_rewards.settle", return_value={}),
        patch("wakfu_server.characters.companions.settle_owner_exit"),
        patch(
            "wakfu_server.combat_captured_roster_checkpoint.persist_captured_roster_updates"
        ),
    ):
        result = combat_pve_withdraw_store.persist(
            store,
            owner,
            character,
            original,
            db=db,
            captured_departure_fight=candidate,
        )
    return result, db


def _score_trial(fight, generation):
    """Use the existing reducer fixture on the real PvE withdrawal fight."""
    prepared_fixture(fight, generation=generation)
    proof, _fixture_rules, initial = checkpoint.validate(
        fight.native_order_trial, encounter_id=fight.id
    )
    rules = kernel.OrderRules(
        tuple((recipe, 150) for recipe in sorted(kernel.RECIPES)),
        score_threshold=400,
    )
    capability = admission.document()
    capability["enabled"] = True
    delattr(fight, checkpoint.FIELD)
    checkpoint.install(
        fight,
        proof,
        initial,
        rules,
        capability=capability,
        provenance=dict(
            kind="reviewed_reconstruction",
            evidence="Focused delivery test's accepted hard-mode score fixture",
        ),
    )
    state = initial
    for index, (color, ingredient) in enumerate(
        (("blue", "tomato"), ("red", "cheese"), ("green", "pepper")),
        start=1,
    ):
        target = -600 - index
        for action, kwargs in (
            ("spawn", {"target_id": target, "color": color}),
            ("pickup", {"ingredient": ingredient}),
            ("tenderize", {"target_id": target}),
            ("garnish", {"target_id": target}),
            ("bake", {"target_id": target}),
        ):
            stage_fixture(fight, action, **kwargs)
    proof, rules, state = checkpoint.validate(
        fight.native_order_trial, encounter_id=fight.id
    )
    if not state.hard_mode or state.score < rules.score_threshold:
        raise AssertionError("The actual withdrawal fixture did not earn hard score")
    rule = settlement.load_rule()
    if rule.admission_id != proof.profile_id or (
        rule.event_reference,
        rule.minimum_score,
    ) != (14412, 400):
        raise AssertionError("Default producer rule differs from native 2149 contract")
    return proof, rule


def _withdrawal_fixture():
    """Small real Fight/Registry setup matching test_combat_pve_withdraw."""
    owner = Session(1, 10, "owner", 885, 99)
    other = Session(2, 20, "other", 885, 99)
    fight = Fight(
        77,
        [
            Actor(10, 0, (0, 0, 0), 45, 6, 3, 100, 1, 1, True),
            Actor(20, 0, (1, 0, 0), 55, 6, 3, 90, 1, 2, True),
            Actor(-200, 1, (2, 0, 0), 25, 4, 2, 1, 1),
        ],
        {(x, 0, 0) for x in range(3)},
        {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0)}},
    )
    fight.ready(1)
    fight.ready(2)
    runtime = RuntimeMessages(fight)
    registry = Registry(lambda session: session in (owner, other))
    teammate_actor = fight.actors.pop(20)
    shared = registry.register(fight, owner, runtime=runtime)
    fight.actors[20] = teammate_actor
    shared.participants[2] = other
    shared.connected.add(2)
    from collections import deque

    shared.outboxes[2] = deque()
    registry.by_actor[20] = registry.by_character[20] = fight.id
    return owner, other, fight, runtime, registry, shared


class NativeOrderTrialProducerTests(unittest.TestCase):
    def test_finished_defeat_uses_actual_default_score_rule_but_ordinary_fight_does_not(
        self,
    ):
        from test_native_order_trial_settlement import _DB as TerminalDB
        from test_native_order_trial_settlement import _finished_fight

        fight, proof, _fixture_rule = _finished_fight()
        character = {
            "id": proof.owner_id,
            "account_id": proof.account_id,
            "map_id": 885,
        }
        store = _Store(character)
        db = TerminalDB(fight, participant_account=proof.account_id)
        packet = (13832, b"score objective")
        with (
            patch(
                "wakfu_server.achievements.mission_toolkit.settle",
                return_value=[packet],
            ) as settle,
            patch("wakfu_server.owned_story_terminal_returns.stage", return_value={}),
        ):
            delivery = combat_adapter.settle_participants(db, store, fight, [], [])

        self.assertEqual(delivery["packets_by_owner"], {proof.account_id: [packet]})
        self.assertEqual(settle.call_count, 1)
        self.assertTrue(settle.call_args.args[3].startswith("native-order-trial:"))
        self.assertEqual(settle.call_args.args[4:], ("scenario_completed", 14412))
        rule = settlement.load_rule()
        self.assertEqual(
            (rule.admission_id, rule.event_reference, rule.minimum_score),
            (proof.profile_id, 14412, 400),
        )
        self.assertEqual(
            fight.winner, 1
        )  # A qualifying server score is not victory-gated.

        ordinary = deepcopy(fight)
        del ordinary.native_order_trial
        ordinary_db = TerminalDB(fight, participant_account=proof.account_id)
        with (
            patch.object(settlement, "stage") as stage,
            patch("wakfu_server.owned_story_terminal_returns.stage", return_value={}),
        ):
            result = combat_adapter.settle_participants(
                ordinary_db, store, ordinary, [], []
            )
        stage.assert_not_called()
        self.assertEqual(result["packets_by_owner"], {})

    def test_pve_withdrawal_stages_only_after_persist_and_delivers_after_native_return_once(
        self,
    ):
        owner, _other, original, runtime, registry, shared = _withdrawal_fixture()
        proof, rule = _score_trial(original, owner.generation)
        self.assertEqual(
            (proof.owner_id, proof.account_id), (owner.character_id, owner.account_id)
        )
        character = {
            "id": owner.character_id,
            "account_id": owner.account_id,
            "hp": 45,
            "max_hp": 100,
        }
        store = _Store(character)
        injected_packets = ((13832, b"score objective"), (13422, b"completed 2149"))
        captured = {}

        def teardown(candidate):
            captured["candidate"] = candidate

        def persist(persisted_original):
            self.assertIs(persisted_original, original)
            candidate = captured["candidate"]
            self.assertTrue(candidate.actors[owner.character_id].pve_withdrawn)
            self.assertFalse(
                getattr(original.actors[owner.character_id], "pve_withdrawn", False)
            )
            with patch(
                "wakfu_server.achievements.mission_toolkit.settle",
                return_value=list(injected_packets),
            ) as settle:
                staged, persist_db = _actual_withdraw_store_persist(
                    original, candidate, owner, store, character
                )
            settle.assert_called_once()
            self.assertEqual(settle.call_args.args[4:], ("scenario_completed", 14412))
            withdrawal_insert = next(
                i
                for i, query in enumerate(persist_db.queries)
                if "INSERT INTO combat_pve_withdrawals" in query
            )
            score_check = next(
                i
                for i, query in enumerate(persist_db.queries)
                if "FROM combat_fights f JOIN fight_checkpoints" in query
            )
            self.assertLess(withdrawal_insert, score_check)
            return {
                "character": character,
                "order_trial_progression": staged["order_trial_progression"],
            }

        receipt = registry.withdraw_pve(owner, persist=persist, owned_teardown=teardown)
        private_runtime = receipt["withdrawal"].private_runtime
        self.assertEqual(
            after_return(
                private_runtime.fight,
                owner.account_id,
                owner.generation,
                owner.character_id,
            ),
            injected_packets,
        )
        self.assertEqual(
            after_return(
                private_runtime.fight,
                owner.account_id,
                owner.generation + "-stale",
                owner.character_id,
            ),
            (),
        )

        class ReturnDB:
            def execute(self, query, _params=()):
                self.query = query
                return self

            def fetchone(self):
                if "SELECT id FROM combat_fights" in self.query:
                    return {"id": original.id}
                if "FROM combat_pve_withdrawals" in self.query:
                    return {"character_id": owner.character_id}
                raise AssertionError(self.query)

        db = ReturnDB()
        return_store = SimpleNamespace(connection=lambda: nullcontext(db))
        with (
            patch(
                "wakfu_server.combat_results.continuation",
                side_effect=lambda fight_id, body: self.assertEqual(
                    body, struct.pack(">iB", fight_id, 1)
                ),
            ),
            patch(
                "wakfu_server.combat_health.persist_owned",
                return_value={
                    "character": character,
                    "applied": True,
                    "coefficient": 1.0,
                },
            ),
            patch(
                "wakfu_server.combat_results.outside_fight_updates",
                return_value=[(12925, b"native cleanup")],
            ),
            patch(
                "wakfu_server.combat_abandon.outside_progression",
                return_value=(13052, b"world"),
            ),
            patch("wakfu_server.combat_abandon.health.packet", return_value=b"health"),
            patch(
                "wakfu_server.rift_withdrawal_rewards.return_packets", return_value=[]
            ),
        ):
            returned = combat_abandon.return_to_world(
                return_store,
                owner.account_id,
                owner.generation,
                character,
                private_runtime,
                struct.pack(">iB", original.id, 1),
                wp=6,
            )
            self.assertEqual(returned["packets"][0], (12925, b"native cleanup"))
            self.assertEqual(tuple(returned["packets"][1:3]), injected_packets)
            repeated = combat_abandon.return_to_world(
                return_store,
                owner.account_id,
                owner.generation,
                character,
                private_runtime,
                struct.pack(">iB", original.id, 1),
                wp=6,
            )
        self.assertTrue(returned["applied"])
        self.assertTrue(private_runtime.abandon_returned)
        self.assertEqual(repeated["packets"], [])

    def test_failed_persist_does_not_adopt_withdrawal_or_deferred_packets(self):
        owner, other, fight, _runtime, registry, shared = _withdrawal_fixture()
        proof, _rule = _score_trial(fight, owner.generation)
        original_shared_fight = shared.fight
        captured = {}

        def teardown(candidate):
            captured["candidate"] = candidate

        def fail(_original):
            candidate = captured["candidate"]
            self.assertTrue(candidate.actors[proof.owner_id].pve_withdrawn)
            with patch(
                "wakfu_server.achievements.native_order_trial_settlement.stage_withdrawal",
                side_effect=RuntimeError("withdrawal receipt persistence failed"),
            ):
                _actual_withdraw_store_persist(
                    _original,
                    candidate,
                    owner,
                    _Store(
                        {
                            "id": owner.character_id,
                            "account_id": owner.account_id,
                            "hp": 45,
                        }
                    ),
                    {
                        "id": owner.character_id,
                        "account_id": owner.account_id,
                        "hp": 45,
                    },
                )

        with self.assertRaisesRegex(RuntimeError, "receipt persistence"):
            registry.withdraw_pve(owner, persist=fail, owned_teardown=teardown)
        self.assertIs(shared.fight, original_shared_fight)
        self.assertEqual(shared.connected, {owner.account_id, other.account_id})
        self.assertEqual(shared.withdrawals, {})
        self.assertFalse(getattr(captured["candidate"], "post_combat_progression", {}))
        self.assertFalse(getattr(fight.actors[proof.owner_id], "pve_withdrawn", False))


class _WithdrawalReceiptDB:
    """Receipt/checkpoint witness emitted by the fixture's persist callback."""

    def __init__(self, candidate, proof):
        self.candidate = candidate
        self.proof = proof
        self.query = ""

    def execute(self, query, _params=()):
        self.query = query
        return self

    def fetchone(self):
        if "FROM combat_fights f JOIN fight_checkpoints" in self.query:
            return {
                "fight_status": "active",
                "checkpoint_status": "active",
                "snapshot": {
                    "phase": "active",
                    checkpoint.FIELD: deepcopy(self.candidate.native_order_trial),
                },
                "account_id": self.proof.account_id,
                "session_generation": self.proof.generation,
            }
        if "FROM combat_fight_participants" in self.query:
            return {"account_id": self.proof.account_id}
        raise AssertionError(self.query)


if __name__ == "__main__":
    unittest.main()
