"""Producer recovery preserves actual grants and native eligibility boundaries."""
from copy import deepcopy
import random
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.combat_artifact_assignment import (
    artifact_assignment_eligible,
    assign_artifact,
)
from wakfu_server.rift_artifact_recovery import reconcile_artifact_group
from wakfu_server.rift_native_gameplay import (
    apply_artifact_collection,
    artifact_contact_eligible,
    distribute_unclaimed_artifacts,
)


class RiftArtifactRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.rows = {
            uid: dict(
                uid=uid,
                reference=1500 + uid,
                native_area_contract="faM",
                level=100,
                owner_id=7,
            )
            for uid in (101, 102, 103, 104)
        }
        self.group = dict(
            wave=1,
            original={str(uid): row["reference"] for uid, row in self.rows.items()},
            remaining=list(self.rows),
            assignments=[],
            choices_allowed=2,
            choices_made=0,
        )
        self.fight = SimpleNamespace(
            actors={
                7: SimpleNamespace(id=7, team=0, controlled=True),
                -200: SimpleNamespace(id=-200, team=1),
            },
            native_effect_areas=deepcopy(self.rows),
            native_artifact_activation_receipts={},
            rift_wave_state=dict(native_artifact_groups={"1": self.group}),
            _in_play=lambda actor: True,
        )
        self.assigned = []
        self.eligible = lambda uid, recipient: uid in self.fight.native_effect_areas

        def activate(uid, recipient):
            if not self.eligible(uid, recipient):
                return False
            self.fight.native_effect_areas.pop(uid)
            self.assigned.append((uid, recipient))
            return True

        self.events = SimpleNamespace(
            artifact_assignment_eligible=lambda uid, recipient: self.eligible(
                uid, recipient
            ),
            assign_artifact=activate,
        )
        self.dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=self.fight),
            native_area_events=self.events,
            rift_artifact_rng=random.Random(10),
        )
        self.policy = patch(
            "wakfu_server.rift_native_gameplay.policy",
            return_value={"artifacts": {"enabled": True}},
        )
        self.roles = patch(
            "wakfu_server.combat_encounter_roles.assigned_roles",
            return_value=SimpleNamespace(player_team=0, npc_team=1),
        )
        self.policy.start()
        self.roles.start()
        self.addCleanup(self.policy.stop)
        self.addCleanup(self.roles.stop)

    def test_absent_native_area_is_ineligible_without_effects_or_grants(self):
        runtime = SimpleNamespace(fight=self.fight, _definition=Mock())
        for uid in (101, 102):
            self.fight.native_effect_areas.pop(uid)
            self.assertFalse(artifact_assignment_eligible(runtime, uid, 7))
            self.assertFalse(assign_artifact(runtime, uid, 7))
        runtime._definition.assert_not_called()
        with self.assertRaises(ValueError):
            artifact_assignment_eligible(runtime, True, 7)

    def test_retired_references_repair_once_and_remaining_native_pair_is_assigned(self):
        self.fight.native_effect_areas.pop(101)
        self.fight.native_effect_areas.pop(102)
        self.assertTrue(distribute_unclaimed_artifacts(self.dispatcher, before_wave=2))
        self.assertEqual(set(self.group["retired"]), {"101", "102"})
        self.assertEqual({uid for uid, _ in self.assigned}, {103, 104})
        self.assertEqual(self.group["remaining"], [])
        self.assertEqual(len(self.group["assignments"]), 1)
        snapshot, rng = (
            deepcopy(self.group),
            self.dispatcher.rift_artifact_rng.getstate(),
        )
        self.assertFalse(distribute_unclaimed_artifacts(self.dispatcher, before_wave=2))
        self.assertEqual(self.group, snapshot)
        self.assertEqual(self.dispatcher.rift_artifact_rng.getstate(), rng)
        self.assertEqual(len(self.assigned), 2)

    def test_odd_native_remainder_does_not_block_a_wave_or_invent_a_pair(self):
        for uid in (101, 102, 103):
            self.fight.native_effect_areas.pop(uid)
        self.assertTrue(distribute_unclaimed_artifacts(self.dispatcher, before_wave=2))
        self.assertEqual(self.group["remaining"], [104])
        self.assertEqual(self.assigned, [])
        self.assertFalse(distribute_unclaimed_artifacts(self.dispatcher, before_wave=3))

    def test_no_eligible_recipient_preserves_live_areas_and_rng_for_later(self):
        self.eligible = lambda uid, recipient: False
        before = deepcopy(self.group)
        rng = self.dispatcher.rift_artifact_rng.getstate()
        self.assertFalse(distribute_unclaimed_artifacts(self.dispatcher, before_wave=2))
        self.assertEqual(self.group, before)
        self.assertEqual(self.dispatcher.rift_artifact_rng.getstate(), rng)
        self.assertEqual(self.assigned, [])

    def test_contact_commits_and_missing_opponent_is_assigned_on_later_wave(self):
        row = self.fight.native_effect_areas.pop(101)
        self.fight.native_artifact_activation_receipts["101"] = dict(
            origin="contact",
            complete=False,
            source_kind="observed_original_artifact_activation",
            area_uid=101,
            area_level=row["level"],
            actor_id=7,
            reference=row["reference"],
            owner_id=row["owner_id"],
        )
        self.fight.actors.pop(-200)
        self.assertTrue(
            apply_artifact_collection(
                self.dispatcher,
                area_row=row,
                actor_id=7,
            )
        )
        self.assertEqual(self.group["choices_made"], 1)
        self.assertEqual(len(self.group["pending_pairs"]), 1)
        self.assertEqual(self.assigned, [])
        self.assertFalse(
            apply_artifact_collection(
                self.dispatcher,
                area_row=row,
                actor_id=7,
            )
        )
        self.fight.actors[-201] = SimpleNamespace(id=-201, team=1)
        self.assertTrue(distribute_unclaimed_artifacts(self.dispatcher, before_wave=2))
        self.assertNotIn("pending_pairs", self.group)
        self.assertEqual(self.group["assignments"][0]["kind"], "contact_pair")
        self.assertEqual(self.group["assignments"][0]["before_wave"], 2)
        self.assertEqual(self.group["assignments"][0]["recipient"], -201)
        self.assertEqual(len(self.assigned), 3)

    def test_retirement_inside_first_assignment_cannot_block_next_wave(self):
        activate = self.events.assign_artifact

        def retire_other_areas(uid, recipient):
            applied = activate(uid, recipient)
            if recipient == 7:
                self.fight.native_effect_areas.clear()
            return applied

        self.events.assign_artifact = retire_other_areas
        self.assertTrue(distribute_unclaimed_artifacts(self.dispatcher, before_wave=2))
        self.assertEqual(len(self.assigned), 1)
        self.assertEqual(self.group["remaining"], [])
        self.assertEqual(len(self.group["pending_pairs"]), 1)
        self.assertEqual(self.group["assignments"], [])
        self.assertFalse(distribute_unclaimed_artifacts(self.dispatcher, before_wave=3))

    def test_recovery_does_not_borrow_another_live_area_or_rewrite_history(self):
        history = dict(kind="contact_pair", opponent=90, recipient=-200)
        self.group["assignments"].append(history)
        self.fight.native_effect_areas[101]["reference"] += 1
        with self.assertRaisesRegex(ValueError, "live identity changed"):
            reconcile_artifact_group(self.fight, self.group)
        self.assertEqual(self.group["assignments"], [history])

    def test_contact_reserves_only_live_remaining_choices_for_pending_opponent(self):
        self.group["remaining"] = [101, 102]
        self.group["pending_pairs"] = [
            dict(kind="contact_pair", collected=103, collector=7)
        ]
        self.fight.native_effect_areas.pop(101)
        before = deepcopy(self.group)
        with patch(
            "wakfu_server.combat_carrying.carrying_relations",
            return_value={"is_carried": False},
        ):
            self.assertFalse(
                artifact_contact_eligible(
                    self.fight,
                    area_row=self.rows[102],
                    actor_id=7,
                )
            )
        self.assertEqual(self.group, before)
