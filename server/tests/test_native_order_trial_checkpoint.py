"""Optional checkpoint acceptance; synthetic action classification is not gameplay."""

from copy import deepcopy
from dataclasses import replace
from itertools import count
import json
from pathlib import Path
import struct
from threading import RLock
from types import SimpleNamespace as N
import unittest
from unittest.mock import patch

from wakfu_server import native_order_trial_admission as admission
from wakfu_server import native_order_trial_checkpoint as sidecar
from wakfu_server.achievements import native_order_trials as kernel
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_morph_handler import NativeMorphHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot, recovery_snapshot
from wakfu_server.checkpoint_worker import _detach_active_projection


def prepared_fixture(fight=None, *, generation="selected-test"):
    native = json.loads(
        Path(__file__)
        .with_name("fixtures")
        .joinpath("pizzlarva-native-form.json")
        .read_text()
    )
    if fight is None:
        fight = Fight(
            77,
            [
                Actor(7, 0, (0, 0, 0), 100, 6, 3, 20, 50, 3, True),
                Actor(-200, 1, (1, 0, 0), 100, 0, 2, 0, 1),
            ],
            [(0, 0, 0), (1, 0, 0)],
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
    fight.phase = "active"
    actor = next(row for row in fight.actors.values() if row.controlled)
    value = admission.document()
    value["enabled"] = True
    source = value["sources"]["hard"]
    character = dict(
        id=actor.id,
        account_id=actor.owner_id,
        instance_id=99,
        map_id=885,
        **dict(zip(("x", "y", "z"), source["approaches"][0]))
    )
    proof = admission.plan(
        value,
        character,
        struct.pack(">qHH", source["object_id"], 0, 0),
        native_source=native["mode_objects"][str(source["object_id"])],
    )
    proof = replace(proof, generation=generation)
    ids, packets = count(501), []
    handler = NativeMorphHandler(
        fight,
        packets,
        action_id=1,
        allocate_uid=lambda: next(ids),
        context=lambda *args: StatExecutionContext(True, True, None, True, None),
        rng=lambda: 0.5,
        profiles=native["morph_document"]["profiles"],
    )
    assert handler(
        native["morph_effect"],
        {},
        EffectInvocation(118992, 1, actor.id, actor.id, actor.position),
    )
    # Explicit test-only matrix verifies persistence; it is never published.
    rules = kernel.OrderRules(tuple((recipe, 5) for recipe in sorted(kernel.RECIPES)))
    trial = admission.start_trial(
        proof,
        encounter_id=fight.id,
        orders=(("blue", "tomato"), ("red", "cheese"), ("green", "pepper")),
    )
    sidecar.install(
        fight,
        proof,
        trial,
        rules,
        capability=value,
        provenance=dict(
            kind="reviewed_reconstruction",
            evidence="Synthetic test matrix; not native scoring or gameplay",
        ),
    )
    return fight


def stage_fixture(fight, action, **arguments):
    event = fight._event("test_only_order_observation", action=action)
    classification = dict(
        action=action,
        arguments=arguments,
        source="Test-only classifier on actual candidate event; no production producer",
    )
    return sidecar.observe(
        fight, event, classify=lambda candidate, observed: classification
    )


class NativeOrderTrialCheckpointTests(unittest.TestCase):
    def test_third_escape_finishes_once_and_ignores_later_native_batch_outcomes(self):
        fight = prepared_fixture()
        for index in range(3):
            identity = -700 - index
            self.assertTrue(
                stage_fixture(fight, "spawn", target_id=identity, color="blue")
            )
            self.assertTrue(stage_fixture(fight, "escape", target_id=identity))
            _proof, _rules, state = sidecar.validate(
                fight.native_order_trial, encounter_id=fight.id, replay=True
            )
            self.assertEqual(state.strikes, index + 1)
            self.assertEqual(state.finished, index == 2)
        terminal = deepcopy(fight.native_order_trial)
        for action, arguments in (
            ("spawn", dict(target_id=-799, color="red", population_limit=2)),
            ("turn_end", {}),
            ("finish", {}),
        ):
            self.assertFalse(stage_fixture(fight, action, **arguments))
            self.assertEqual(fight.native_order_trial, terminal)
        _proof, _rules, recovered = sidecar.validate(
            fight.native_order_trial, encounter_id=fight.id, replay=True
        )
        self.assertTrue(recovered.finished)
        self.assertEqual(recovered.strikes, 3)
        self.assertEqual(len(recovered.receipts), len(terminal["events"]))

    def test_native_additive_pickup_capacity_and_actual_level_survive_recovery(self):
        fight = prepared_fixture()
        for actual in (2, 4, 6, 8, 10, 10):
            self.assertTrue(
                stage_fixture(
                    fight, "pickup", ingredient="tomato", charges_after=actual
                )
            )
        _, rules, trial = sidecar.validate(
            fight.native_order_trial, encounter_id=fight.id
        )
        self.assertEqual((rules.ingredient_capacity, trial.charges), (10, 10))
        before = deepcopy(fight.native_order_trial)
        with self.assertRaises(ValueError):
            stage_fixture(fight, "pickup", ingredient="tomato", charges_after=9)
        self.assertEqual(fight.native_order_trial, before)
        self.assertTrue(
            stage_fixture(fight, "pickup", ingredient="cheese", charges_after=2)
        )
        restored = Checkpoints._read_snapshot(
            json.loads(json.dumps(recovery_snapshot(fight)))
        )
        _, _, trial = sidecar.validate(restored[sidecar.FIELD], encounter_id=fight.id)
        self.assertEqual((trial.ingredient, trial.charges), ("cheese", 2))

    def test_incremental_observation_replays_history_only_on_durable_read(self):
        fight = prepared_fixture()
        original_apply = kernel.apply
        with patch.object(kernel, "apply", wraps=original_apply) as apply:
            for _ in range(8):
                self.assertTrue(stage_fixture(fight, "turn_end"))
            self.assertEqual(apply.call_count, 8)
            state = recovery_snapshot(fight)
            snapshot(fight)
            self.assertEqual(apply.call_count, 8)
            Checkpoints._read_snapshot(json.loads(json.dumps(state)))
            self.assertEqual(apply.call_count, 16)
        damaged = deepcopy(state)
        damaged[sidecar.FIELD]["events"][0]["native_event"]["kind"] = "tampered"
        with self.assertRaises(ValueError):
            Checkpoints._read_snapshot(damaged)

    def test_absent_sidecar_has_no_observer_or_checkpoint_effect(self):
        fight = N(id=1, actors={}, events=[])
        self.assertFalse(
            sidecar.observe(
                fight,
                object(),
                classify=lambda *args: self.fail("ordinary fight observer"),
            )
        )
        self.assertEqual(snapshot(fight), dict(id=1, actors={}, events=[]))
        sidecar.validate_checkpoint(dict(id=1, actors={}))

    def test_actual_form_candidate_clone_recovery_and_dedup_preserve_mode(self):
        fight = prepared_fixture()
        candidate = deepcopy(fight)
        before = deepcopy(fight.native_order_trial)
        self.assertTrue(
            stage_fixture(
                candidate, "spawn", target_id=-301, color="blue", population_limit=2
            )
        )
        self.assertEqual(fight.native_order_trial, before)
        event = candidate.events[-1]
        self.assertFalse(
            sidecar.observe(
                candidate,
                event,
                classify=lambda *args: self.fail("duplicate classified twice"),
            )
        )
        state = recovery_snapshot(candidate)
        self.assertEqual(state[sidecar.FIELD], candidate.native_order_trial)
        restored = Checkpoints._read_snapshot(json.loads(json.dumps(state)))
        self.assertEqual(restored[sidecar.FIELD]["admission"]["mode"], "hard")
        proof, rules, trial = sidecar.validate(
            restored[sidecar.FIELD], encounter_id=candidate.id
        )
        self.assertEqual([row.actor_id for row in trial.larvae], [-301])
        detached, _, _ = _detach_active_projection(
            N(lock=RLock(), fight=candidate, runtime=None, checkpoint_revision=1)
        )
        self.assertEqual(detached.native_order_trial, candidate.native_order_trial)
        self.assertIsNot(detached.native_order_trial, candidate.native_order_trial)
        detached.native_order_trial["events"].clear()
        self.assertEqual(len(candidate.native_order_trial["events"]), 1)

    def test_score_event_rules_and_owner_tampering_fail_before_storage(self):
        fight = prepared_fixture()
        self.assertTrue(stage_fixture(fight, "spawn", target_id=-301, color="blue"))
        for mutate in (
            lambda d: d["state"].update(score=400),
            lambda d: d["admission"].update(mode="normal"),
            lambda d: d["rules"]["weights"][0].__setitem__(2, 100),
            lambda d: d["events"][0]["native_event"].update(sequence=999),
            lambda d: d["state"]["receipts"].clear(),
        ):
            damaged = deepcopy(fight.native_order_trial)
            mutate(damaged)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                sidecar.validate(damaged, encounter_id=fight.id)
        with self.assertRaisesRegex(ValueError, "actual candidate"):
            sidecar.observe(
                fight, deepcopy(fight.events[-1]), classify=lambda *args: None
            )
        state = recovery_snapshot(fight)
        state["actors"]["7"]["owner_id"] = 8
        with self.assertRaisesRegex(ValueError, "durable combat owner"):
            Checkpoints._read_snapshot(state)

    def test_disabled_install_and_missing_form_are_rejected(self):
        fight = prepared_fixture()
        doc = deepcopy(fight.native_order_trial)
        proof, rules, trial = sidecar.validate(doc, encounter_id=fight.id)
        del fight.native_order_trial
        with self.assertRaisesRegex(ValueError, "disabled"):
            sidecar.install(
                fight, proof, trial, rules, provenance=doc["rules"]["provenance"]
            )
        fight.native_morph_spellbooks.clear()
        with self.assertRaisesRegex(ValueError, "actual native form"):
            sidecar.install(
                fight,
                proof,
                trial,
                rules,
                capability=doc["capability"],
                provenance=doc["rules"]["provenance"],
            )
