"""Real criterion/session boundary regressions for earned scene admission."""
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_quest_scene_authority import authenticated_quest_fact
from wakfu_server.combat_abomination_scene import (
    ACTIVATION,
    authorize_admission,
    apply_start,
)


class Database:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.queries = []

    def execute(self, query, args):
        self.queries.append((query, args))
        return self

    def fetchone(self):
        return (
            None if self.snapshot is None else dict(snapshot=self.snapshot, revision=9)
        )


class QuestSceneAuthorityTests(unittest.TestCase):
    def fact(self, snapshot, *, date=(2026, 2, 20), required=()):
        db = Database(snapshot)
        now = datetime(*date, tzinfo=timezone.utc)
        store = SimpleNamespace(now=lambda: now, clock=lambda: now.timestamp())
        with patch("wakfu_server.inventory_owner.lock_inventory_character") as fence:
            fact = authenticated_quest_fact(
                store,
                db,
                account_id=7,
                generation="session-A",
                character_id=19,
                quest_id=1714,
                objective_id=3248,
                required_completed_objectives=required,
                activation_criterion=ACTIVATION,
            )
            fence.assert_called_once_with(store, db, 7, "session-A", 19)
        self.assertTrue(
            any("FOR UPDATE" in q and "achievement" in q for q, _ in db.queries)
        )
        return fact

    def test_existing_quest_ledger_and_native_season_are_required(self):
        snapshot = dict(running=[1714], completed=[], objectives=[])
        fact = self.fact(snapshot)
        self.assertEqual(
            (fact.quest_id, fact.objective_id, fact.authority_revision), (1714, 3248, 9)
        )
        self.assertEqual(fact.record()["generation"], "session-A")
        self.assertEqual(len(fact.snapshot_digest), 64)
        self.assertIsNone(self.fact(snapshot, date=(2026, 10, 25)))
        self.assertIsNone(self.fact(snapshot, date=(2026, 2, 17)))
        self.assertIsNone(self.fact(None))

    def test_completed_or_unstarted_objective_cannot_mint_grant(self):
        for snapshot in (
            dict(running=[], completed=[], objectives=[]),
            dict(running=[1714], completed=[], objectives=[3248]),
            dict(running=[], completed=[1714], objectives=[3248]),
        ):
            self.assertIsNone(self.fact(snapshot))

    def test_prior_objective_uses_authoritative_completion(self):
        self.assertIsNone(
            self.fact(
                dict(running=[1714], completed=[], objectives=[]),
                required=(3247,),
            )
        )
        self.assertIsNotNone(
            self.fact(
                dict(running=[1714], completed=[], objectives=[3247]),
                required=(3247,),
            )
        )

    def test_session_fence_failure_is_not_treated_as_absent_optional_quest(self):
        with patch(
            "wakfu_server.inventory_owner.lock_inventory_character",
            side_effect=ValueError("expired session"),
        ):
            with self.assertRaisesRegex(ValueError, "expired"):
                authenticated_quest_fact(
                    SimpleNamespace(),
                    Database(None),
                    account_id=7,
                    generation="expired",
                    character_id=19,
                    quest_id=1714,
                    objective_id=3248,
                )

    def test_other_monsters_and_unearned_fights_have_no_grant_path(self):
        fight = SimpleNamespace(phase="active", id=1, actors={})
        self.assertIsNone(
            authorize_admission(
                None,
                None,
                fight,
                account_id=7,
                generation="A",
                character_id=19,
                monster_references=(2880, 2880),
            )
        )
        self.assertFalse(apply_start(fight, None, []))
        self.assertFalse(hasattr(fight, "native_abomination_quest_grant"))


class SceneOutcomeTests(unittest.TestCase):
    def test_scene_interest_filters_both_source_variants_by_departing_owner(self):
        from wakfu_server.combat_scene_outcome import active_scene_grants

        fight = SimpleNamespace(
            native_abomination_quest_grant=dict(
                status="granted", source=dict(participant_id=10)
            ),
            native_spirit_scene_admission=dict(
                status="granted", carrier_uids={"10": 41, "20": 42}
            ),
        )
        self.assertEqual(active_scene_grants(fight), ("abomination", "spirit"))
        self.assertEqual(
            active_scene_grants(fight, actor_ids={10}), ("abomination", "spirit")
        )
        self.assertEqual(active_scene_grants(fight, actor_ids={20}), ("spirit",))
        self.assertEqual(active_scene_grants(fight, actor_ids={30}), ())
        fight.native_spirit_scene_admission["cleaned_actor_ids"] = [10]
        self.assertEqual(active_scene_grants(fight, actor_ids={10}), ("abomination",))
        self.assertEqual(active_scene_grants(fight, actor_ids={20}), ("spirit",))

    def test_partial_cleanup_passes_exact_departing_actor_filter_to_spirit(self):
        from wakfu_server.combat_scene_outcome import cleanup_scene_grants

        fight = SimpleNamespace(
            native_spirit_scene_admission=dict(
                status="granted",
                carrier_uids={"10": 41, "20": 42},
            )
        )
        with patch(
            "wakfu_server.combat_encounter_objective_spirit.cleanup_spirit_scene"
        ) as clean:
            self.assertTrue(
                cleanup_scene_grants(fight, "actual-runtime", [], actor_ids={10})
            )
            clean.assert_called_once_with(fight, "actual-runtime", [], actor_ids={10})
        self.assertEqual(
            fight.native_spirit_scene_admission["carrier_uids"], {"10": 41, "20": 42}
        )

    def test_ordinary_outcome_keeps_original_identity_and_runtime_noop(self):
        from wakfu_server.combat_scene_outcome import prepare_outcome

        fight = SimpleNamespace(phase="finished")
        with patch(
            "wakfu_server.combat_consumable_lifecycle.prepare_outcome",
            return_value=(fight, ()),
        ) as original:
            self.assertEqual(prepare_outcome(fight, None, action_id=17), (fight, ()))
            original.assert_called_once_with(fight, None, action_id=17)

    def test_scene_cleanup_is_private_and_preserves_original_action_and_packets(self):
        from contextlib import nullcontext
        from wakfu_server.combat_scene_outcome import prepare_outcome

        fight = SimpleNamespace(
            phase="finished",
            native_abomination_quest_grant={"status": "granted"},
            effect_resolution=nullcontext,
        )
        factories = []

        def factory(*, action_id):
            factories.append(action_id)
            return "same-action-runtime"

        def clean(candidate, runtime, packets):
            self.assertIsNot(candidate, fight)
            self.assertEqual(runtime, "same-action-runtime")
            candidate.native_abomination_quest_grant["status"] = "cleaned"
            packets.append((13560, b"native-owned-removal"))

        with patch(
            "wakfu_server.combat_consumable_lifecycle.prepare_outcome",
            return_value=(fight, ((1, b"consumable"),)),
        ), patch("wakfu_server.combat_abomination_scene.cleanup", side_effect=clean):
            result, packets = prepare_outcome(fight, factory, action_id=17)
        self.assertEqual(factories, [17])
        self.assertEqual(fight.native_abomination_quest_grant["status"], "granted")
        self.assertEqual(result.native_abomination_quest_grant["status"], "cleaned")
        self.assertEqual(
            packets, ((1, b"consumable"), (13560, b"native-owned-removal"))
        )


if __name__ == "__main__":
    unittest.main()
