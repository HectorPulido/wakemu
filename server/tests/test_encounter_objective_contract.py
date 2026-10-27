"""Objective admission/receipt contracts; native victory is qualified separately."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_server.combat_encounter_objective_policy import (
    objective_policy,
    require_admitted_policy,
    bound_objective_policy,
)
from wakfu_server.combat_encounter_objective import (
    SceneTerminalEventReceipt,
    install_objective_policy,
    observe_native_terminal,
    deliver_objective_boundary,
)
from wakfu_server.combat_encounter_objective_facts import (
    objective_result_payload,
    enqueue_objective_results,
)
from wakfu_server.objectives.engine import increment


class EncounterObjectiveContractTests(unittest.TestCase):
    def receipt(self):
        return SceneTerminalEventReceipt(
            schema="wakemu-scene-terminal-event-v1",
            policy="wakemu-ogrest-six-phases-v1",
            version=1,
            fight_id=17,
            map_id=1156,
            boss_actor_id=-1,
            boss_reference=4378,
            objective_key="ogrest-owned-native-exit",
            boundary_actor_id=40,
            boundary="owned_player_end",
            table=19,
            score=500,
            terminal_root=238861,
            terminal_kind="owned_native_exit",
            result="success",
            source="native-owned-exit",
            scene_contract_policy=None,
            admission_digest="a" * 64,
            catalog_revision=None,
        )

    def test_partial_or_unbound_policies_cannot_mutate_or_admit_an_encounter(self):
        for reference in (5516, 5612, 5595, 5848, 5888):
            with self.subTest(reference=reference):
                policy = objective_policy(reference)
                if reference == 5848:
                    # The recovered declaration is complete; its unbound record
                    # still cannot authorize a fight without actual admission.
                    self.assertTrue(policy.admitted)
                    self.assertIsNone(policy.map_id)
                else:
                    self.assertFalse(policy.admitted)
                fight = SimpleNamespace(phase="active", turn_id=1)
                before = deepcopy(vars(fight))
                with self.assertRaises(ValueError):
                    install_objective_policy(fight, policy.record())
                self.assertEqual(vars(fight), before)

    def test_spirit_binding_preserves_native_quota_and_requires_real_scene_admission(
        self,
    ):
        policy = bound_objective_policy(5848, 1134)
        self.assertTrue(policy.admitted)
        self.assertEqual(
            (policy.minimum_score, policy.first_table, policy.last_table),
            (200000, 13, 13),
        )
        self.assertEqual(policy.native_player_state, 9145)
        self.assertEqual(policy.success_root, 411013)
        self.assertEqual(require_admitted_policy(policy.record()), policy)
        for invalid in (None, True, 1134.0):
            with self.subTest(map_id=invalid), self.assertRaises(ValueError):
                bound_objective_policy(5848, invalid)
        fight = SimpleNamespace(phase="active", turn_id=1)
        with self.assertRaises(ValueError):
            install_objective_policy(fight, policy.record())
        self.assertFalse(hasattr(fight, "native_encounter_objective_policy"))

    def test_old_fights_are_noop_without_any_database_access(self):
        fight = SimpleNamespace(id=17)
        dispatcher = SimpleNamespace(native_retention=SimpleNamespace(fight=fight))
        before = deepcopy(vars(fight))
        self.assertIsNone(observe_native_terminal(fight))
        self.assertIsNone(
            deliver_objective_boundary(
                dispatcher, actor_id=40, boundary="owned_player_end"
            )
        )
        self.assertEqual(enqueue_objective_results(object(), fight), ())
        self.assertEqual(vars(fight), before)

    def test_only_exact_published_ogrest_record_is_admitted(self):
        record = objective_policy(4378).record()
        self.assertIs(require_admitted_policy(record), objective_policy(4378))
        for field, value in (
            ("minimum_score", 1),
            ("map_id", 1134),
            ("success_root", 1),
            ("version", True),
        ):
            changed = {**record, field: value}
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    require_admitted_policy(changed)
        with self.assertRaises(ValueError):
            require_admitted_policy({})

    def test_ogrest_policy_requires_real_constructor_and_scene_before_damage(self):
        fight = SimpleNamespace(phase="active", turn_id=1)
        with self.assertRaises(ValueError):
            install_objective_policy(fight, objective_policy(4378).record())
        self.assertFalse(hasattr(fight, "native_encounter_objective_policy"))

    def test_terminal_receipt_rejects_forgery_and_ambiguous_numeric_types(self):
        record = self.receipt().to_record()
        self.assertEqual(SceneTerminalEventReceipt.from_record(record), self.receipt())
        for field, value in (
            ("fight_id", True),
            ("score", -1),
            ("boss_reference", False),
            ("result", "failure"),
            ("admission_digest", "g" * 64),
            ("terminal_root", 0),
            ("terminal_kind", "invented"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ValueError):
                    SceneTerminalEventReceipt.from_record({**record, field: value})

    def test_exact_objective_fact_uses_existing_consumer_and_never_kill_credit(self):
        payload = objective_result_payload(self.receipt())
        rule = {
            "event": "scenario_objective_completed",
            "filters": {
                "objective_key": "ogrest-owned-native-exit",
                "outcome_policy": "wakemu-ogrest-six-phases-v1",
                "outcome_version": 1,
                "reference": 4378,
            },
            "target": 1,
        }
        self.assertEqual(increment(rule, payload), 1)
        for field, value in (
            ("objective_key", "other"),
            ("outcome_policy", "other"),
            ("outcome_version", 2),
            ("reference", 1988),
        ):
            with self.subTest(field=field):
                self.assertEqual(increment(rule, {**payload, field: value}), 0)
        self.assertEqual(
            increment(
                {"event": "original_monster_killed", "filters": {}, "target": 1},
                payload,
            ),
            0,
        )
        with self.assertRaises(ValueError):
            objective_result_payload(payload)
