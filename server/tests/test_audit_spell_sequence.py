import unittest, random, copy, sys
from pathlib import Path
from types import SimpleNamespace as N

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_spell_sequence import audit_sequence, blocking_verdict


class SequenceAuditTests(unittest.TestCase):
    def test_accepted_first_cast_does_not_hide_later_block_or_missing_effect(self):
        row = dict(status="actor_state_changed", cast_elapsed_seconds=0.01)
        for status in ("REJECTED", "LIFECYCLE_FAILED"):
            row["sequence"] = dict(steps=[dict(status=status)])
            self.assertEqual(blocking_verdict(row, 2), "sequence_blocked")
        row["sequence"] = dict(steps=[dict(status="NO_EFFECT_OBSERVED")])
        self.assertEqual(blocking_verdict(row, 2), "no_effect_requires_review")
        row["sequence"] = dict(steps=[dict(status="PRECONDITION_CHANGED")])
        self.assertEqual(blocking_verdict(row, 2), "client_validation_required")

    def fixture(self, ap=4, hp=10):
        caster = N(id=7, hp=20, ap=ap, mp=3, owner_id=3, controlled=True, turn_count=1)
        target = N(id=-7, hp=hp, position=(1, 0, 0))

        class Fight:
            def end_turn(self, owner, actor, turn):
                self.phase = "ended"
                self.events.append({"kind": "ended"})

        fight = Fight()
        fight.actors = {7: caster, -7: target}
        fight.current = caster
        fight.phase = "active"
        fight.events = []
        fight.turn_id = 1
        return N(fight=fight), random.Random(0)

    def snap(self, f):
        return (f.phase, f.actors[7].ap, f.actors[-7].hp, list(f.events))

    def execute(self, first, rng, preflight=lambda f: None, cast=None, end=None):
        def default_cast(f):
            p = copy.deepcopy(f)
            p.actors[7].ap -= 2
            p.actors[-7].hp -= 1
            return N(fight=p, plan={"costs": {"ap": 2}}, events=(), packets=())

        def default_end(f):
            return copy.deepcopy(f), ()

        return audit_sequence(
            first,
            actor_id=7,
            owner_id=3,
            preflight=preflight,
            cast=cast or default_cast,
            turn_end=end or default_end,
            rng=rng,
            snapshot=self.snap,
            target_id=-7,
            target_cell=(1, 0, 0),
        )

    def test_second_uses_remaining_resources_and_end_turn_runs_on_its_preview(self):
        first, rng = self.fixture()
        r = self.execute(first, rng)
        self.assertEqual([s["status"] for s in r["steps"]], ["EXECUTED", "EXECUTED"])
        self.assertEqual(r["final_resources"]["ap"], 2)
        self.assertEqual(first.fight.actors[7].ap, 4)
        self.assertTrue(r["first_result_preserved"])

    def test_dead_target_is_changed_precondition_but_end_turn_still_checked(self):
        first, rng = self.fixture(hp=0)
        r = self.execute(first, rng)
        self.assertEqual(
            [s["status"] for s in r["steps"]], ["PRECONDITION_CHANGED", "EXECUTED"]
        )

    def test_native_insufficient_ap_does_not_fabricate_resources_or_advance_rng(self):
        first, rng = self.fixture(ap=1)
        state = rng.getstate()

        def preflight(f):
            rng.random()
            raise ValueError("Insufficient authoritative spell resources")

        r = self.execute(first, rng, preflight=preflight)
        self.assertEqual(r["steps"][0]["status"], "PRECONDITION_CHANGED")
        self.assertEqual(r["final_resources"]["ap"], 1)
        self.assertEqual(rng.getstate(), state)

    def test_second_rejection_and_lifecycle_failure_are_distinct_and_rollback_rng(self):
        first, rng = self.fixture()
        state = rng.getstate()

        def reject(f):
            rng.random()
            raise RuntimeError("Missing native family")

        def fail_end(f):
            rng.random()
            raise ValueError("Missing native turn criterion")

        r = self.execute(first, rng, cast=reject, end=fail_end)
        self.assertEqual(
            [s["status"] for s in r["steps"]], ["REJECTED", "LIFECYCLE_FAILED"]
        )
        self.assertEqual(rng.getstate(), state)
        self.assertTrue(r["first_result_preserved"])

    def test_preflight_rng_is_replayed_once_by_successful_cast(self):
        first, rng = self.fixture()
        seen = []

        def preflight(f):
            seen.append(rng.random())

        def cast(f):
            seen.append(rng.random())
            return N(fight=copy.deepcopy(f), plan={"costs": {}}, events=(), packets=())

        self.execute(first, rng, preflight=preflight, cast=cast)
        self.assertEqual(seen[0], seen[1])
        check = random.Random(0)
        check.random()
        self.assertEqual(rng.getstate(), check.getstate())

    def test_missing_native_preflight_authority_is_rejected_not_changed_precondition(
        self,
    ):
        first, rng = self.fixture()

        def unknown(f):
            raise ValueError("Missing native spell category metadata")

        report = self.execute(first, rng, preflight=unknown)
        self.assertEqual(report["steps"][0]["status"], "REJECTED")

    def test_cost_only_second_cast_is_reported_without_claiming_effect_execution(self):
        first, rng = self.fixture()

        def cast(f):
            preview = copy.deepcopy(f)
            preview.actors[7].ap -= 2
            return N(fight=preview, plan={"costs": {"ap": 2}}, events=(), packets=())

        report = audit_sequence(
            first,
            actor_id=7,
            owner_id=3,
            preflight=lambda f: None,
            cast=cast,
            turn_end=lambda f: (copy.deepcopy(f), ()),
            rng=rng,
            snapshot=self.snap,
            target_id=-7,
            target_cell=(1, 0, 0),
            observe=lambda f, r: "no_effect_observed",
        )
        self.assertEqual(report["steps"][0]["status"], "NO_EFFECT_OBSERVED")
        self.assertEqual(report["final_resources"]["ap"], 2)
        self.assertTrue(report["first_result_preserved"])

    def test_moved_target_does_not_silently_retarget_second_cast(self):
        first, rng = self.fixture()
        first.fight.actors[-7].position = (2, 0, 0)
        report = self.execute(first, rng)
        self.assertEqual(report["steps"][0]["status"], "PRECONDITION_CHANGED")
        self.assertIn("moved", report["steps"][0]["reason"])
        self.assertEqual(report["final_resources"]["ap"], 4)

    def test_end_turn_uses_actual_fsm_actor_and_personal_turn_signature(self):
        from wakfu_server.combat_state import Actor, Fight

        caster = Actor(7, 0, (0, 0, 0), 60, 6, 3, 100, 1, 3, True)
        target = Actor(-7, 1, (1, 0, 0), 20, 4, 2, 20, 1)
        fight = Fight(
            78,
            [caster, target],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(3)
        snapshot = lambda f: (
            f.phase,
            f.current.id,
            f.current.turn_count,
            tuple(str(e) for e in f.events),
        )
        report = audit_sequence(
            N(fight=fight),
            actor_id=7,
            owner_id=3,
            preflight=lambda f: None,
            cast=lambda f: N(
                fight=copy.deepcopy(f), plan={"costs": {}}, events=(), packets=()
            ),
            turn_end=lambda f: (copy.deepcopy(f), ()),
            rng=random.Random(0),
            snapshot=snapshot,
        )
        self.assertEqual(report["steps"][1]["status"], "EXECUTED")
        self.assertTrue(report["first_result_preserved"])
        self.assertEqual(fight.current.id, 7)
