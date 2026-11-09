"""Compact enemy books remain bounded advisory evidence."""
from types import SimpleNamespace
import unittest

from wakfu_server.wakia_bridge.wakfu_ai.bridge.rival_threat_summary import project


def actor(identity, team=0, *, hp=10, modifiers=None):
    return SimpleNamespace(
        id=identity,
        team=team,
        hp=hp,
        spell_ap_cost_modifiers={} if modifiers is None else modifiers,
    )


def casting(spell, level):
    return SimpleNamespace(
        baseline=(3, 1, 0, 1, 5, True, False, False, False),
        rules=(),
        cost_categories=(17,),
    )


def describe(spell, level):
    return dict(tags=["damage"], conditional=False, unknownDependencies=[])


class Oracle:
    def __init__(self, books):
        self.books = books

    def owned_spells(self, fight, identity):
        value = self.books[identity]
        if isinstance(value, Exception):
            raise value
        return value


class RivalSummaryTests(unittest.TestCase):
    def run_projection(self, books, actors, **kwargs):
        fight = SimpleNamespace(sequence=13)
        return project(
            Oracle(books),
            fight,
            actor(-1, 1),
            actors,
            deadline=100,
            clock=lambda: 1,
            affiliation=lambda fight, who: who.team,
            describe=describe,
            casting=casting,
            **kwargs
        )

    def test_current_owned_rows_and_native_modifiers_without_fake_damage(self):
        result = self.run_projection({1: {100: 2}}, [actor(1, modifiers={17: -1})])
        record = result["actors"][0]
        self.assertTrue(record["complete"])
        self.assertEqual(
            record["abilities"],
            [
                dict(
                    spellId=100,
                    level=2,
                    minimum=1,
                    maximum=5,
                    ap=2,
                    mp=1,
                    wp=0,
                    needsLos=True,
                    inLine=False,
                    rangeModifiable=False,
                    conditional=False,
                )
            ],
        )
        self.assertEqual(result["sourceRevision"], 13)

    def test_round_robin_leaves_later_books_explicitly_partial(self):
        result = self.run_projection(
            {1: {1: 1, 2: 1}, 2: {3: 1, 4: 1}}, [actor(1), actor(2)], max_operations=4
        )
        one, two = result["actors"]
        self.assertEqual([a["spellId"] for a in one["abilities"]], [1])
        self.assertEqual([a["spellId"] for a in two["abilities"]], [3])
        self.assertEqual(one["unknown"], ["budget_exhausted"])
        self.assertEqual(two["unknown"], ["budget_exhausted"])
        self.assertFalse(one["complete"] or two["complete"])

    def test_unknown_books_and_summons_never_mean_zero_risk(self):
        def classify(spell, level):
            return dict(tags=["summon"], conditional=False, unknownDependencies=[])

        result = project(
            Oracle({1: ValueError("not available"), 2: {8: 1}}),
            SimpleNamespace(sequence=1),
            actor(-1, 1),
            [actor(1), actor(2), actor(3, 1), actor(4, hp=0)],
            deadline=100,
            clock=lambda: 1,
            affiliation=lambda fight, who: who.team,
            describe=classify,
            casting=casting,
        )
        self.assertEqual(len(result["actors"]), 2)
        self.assertEqual(
            result["actors"][0]["unknown"], ["owned_spell_metadata_unavailable"]
        )
        self.assertEqual(
            result["actors"][1]["unknown"], ["non_direct_damage_potential"]
        )
        self.assertTrue(all(not row["complete"] for row in result["actors"]))

    def test_conditional_and_modifiable_ranges_are_not_complete(self):
        def conditional(spell, level):
            return SimpleNamespace(
                baseline=(3, 0, 0, 1, 2, True, False, False, True),
                rules=(("condition", ()),),
                cost_categories=(),
            )

        result = project(
            Oracle({1: {1: 1}}),
            SimpleNamespace(sequence=1),
            actor(-1, 1),
            [actor(1)],
            deadline=100,
            clock=lambda: 1,
            affiliation=lambda fight, who: who.team,
            describe=describe,
            casting=conditional,
        )
        record = result["actors"][0]
        self.assertFalse(record["complete"])
        self.assertEqual(record["unknown"], ["conditional_or_modifiable_range"])
        self.assertTrue(record["abilities"][0]["rangeModifiable"])

    def test_provider_io_failure_remains_advisory_unknown(self):
        def unavailable(spell, level):
            raise OSError("catalog unavailable")

        result = project(
            Oracle({1: {1: 1}}),
            SimpleNamespace(sequence=1),
            actor(-1, 1),
            [actor(1)],
            deadline=100,
            clock=lambda: 1,
            affiliation=lambda fight, who: who.team,
            describe=unavailable,
            casting=casting,
        )
        self.assertEqual(result["actors"][0]["unknown"], ["spell_metadata_unavailable"])
        self.assertFalse(result["actors"][0]["complete"])

    def test_exhausted_deadline_and_truncated_book_are_marked_unknown(self):
        fight = SimpleNamespace(sequence=1)
        result = project(
            Oracle({1: {1: 1}}),
            fight,
            actor(-1, 1),
            [actor(1)],
            deadline=1,
            clock=lambda: 1,
            affiliation=lambda fight, who: who.team,
            describe=describe,
            casting=casting,
        )
        self.assertEqual(result["actors"][0]["unknown"], ["budget_exhausted"])
        limited = self.run_projection(
            {1: {1: 1, 2: 1}}, [actor(1)], max_spells_per_actor=1
        )
        self.assertEqual(limited["actors"][0]["unknown"], ["book_limit"])
        self.assertFalse(limited["actors"][0]["complete"])

    def test_slow_provider_never_reports_a_complete_book(self):
        for slow_stage in ("ownership", "classification", "casting"):
            with self.subTest(stage=slow_stage):
                now = [0]
                calls = []

                class SlowOracle:
                    def owned_spells(self, fight, identity):
                        calls.append("ownership")
                        if slow_stage == "ownership":
                            now[0] = 10
                        return {10: 1}

                def classified(spell, level):
                    calls.append("classification")
                    if slow_stage == "classification":
                        now[0] = 10
                    return describe(spell, level)

                def cast_metadata(spell, level):
                    calls.append("casting")
                    if slow_stage == "casting":
                        now[0] = 10
                    return casting(spell, level)

                result = project(
                    SlowOracle(),
                    SimpleNamespace(sequence=1),
                    actor(-1, 1),
                    [actor(1)],
                    deadline=10,
                    clock=lambda: now[0],
                    affiliation=lambda fight, who: who.team,
                    describe=classified,
                    casting=cast_metadata,
                )
                record = result["actors"][0]
                self.assertFalse(record["complete"])
                self.assertEqual(record["unknown"], ["budget_exhausted"])
                self.assertEqual(record["abilities"], [])
                if slow_stage == "ownership":
                    self.assertEqual(calls, ["ownership"])
                if slow_stage == "classification":
                    self.assertEqual(calls, ["ownership", "classification"])


if __name__ == "__main__":
    unittest.main()
