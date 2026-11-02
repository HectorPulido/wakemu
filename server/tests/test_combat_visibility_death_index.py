"""Candidate-only event indexing retains the single original corpse validator."""
from types import SimpleNamespace
import unittest

from wakfu_server.combat_global_pv_read_view import NativeGlobalPVReadView
from wakfu_server.combat_ordinary_death import _registered_death_event


def result(call):
    try:
        return ("value", call())
    except Exception as error:
        return ("error", type(error), str(error))


class VisibilityDeathIndexTests(unittest.TestCase):
    def fight(self, events):
        return SimpleNamespace(events=events, actors={7: object(), 8: object()})

    def assert_indexed_matches_original(self, fight, actor=8, sequence=None):
        view = NativeGlobalPVReadView(fight)
        indices = view.death_indices(fight, actor)
        plain = result(lambda: _registered_death_event(fight, actor, sequence=sequence))
        indexed = result(
            lambda: _registered_death_event(
                fight, actor, sequence=sequence, event_indices=indices
            )
        )
        self.assertEqual(plain, indexed)
        return indexed

    def death(self, sequence, actor=8, cause="damage"):
        previous = dict(
            kind=cause,
            source_id=7,
            target_id=actor,
            hp=0,
            hp_before=30,
            sequence=sequence - 1,
        )
        if cause == "percentage_hp_update":
            previous.update(effect_class=986, uid=900, maximum=30)
        if cause == "kill_hp_minimum_update":
            previous.update(effect_class=28, uid=901, minimum=0)
        if cause == "hp_minimum_update":
            previous.update(effect_class=830, uid=902, minimum=0)
        if cause == "summon_recall_hp_minimum_update":
            previous.update(effect_class=859, uid=903, minimum=0)
        return [previous, dict(kind="death", actor_id=actor, sequence=sequence)]

    def test_multiple_causes_revived_actor_and_exact_sequence_preserve_original_validation(
        self,
    ):
        for cause in (
            "damage",
            "percentage_hp_update",
            "kill_hp_minimum_update",
            "hp_minimum_update",
            "summon_recall_hp_minimum_update",
        ):
            with self.subTest(cause=cause):
                fight = self.fight(
                    self.death(2)
                    + [dict(kind="revive", actor_id=8, sequence=3)]
                    + self.death(5, cause=cause)
                )
                self.assertEqual(
                    self.assert_indexed_matches_original(fight), ("value", True)
                )
                self.assertEqual(
                    self.assert_indexed_matches_original(fight, sequence=2),
                    ("value", True),
                )
                self.assertEqual(
                    self.assert_indexed_matches_original(fight, sequence=5),
                    ("value", True),
                )
                self.assertEqual(
                    self.assert_indexed_matches_original(fight, sequence=999)[0],
                    "error",
                )

    def test_malformed_events_preserve_reverse_error_order_and_do_not_prevalidate_unvisited_history(
        self,
    ):
        for events in (
            [None] + self.death(3),  # Older malformed entry is never reached.
            self.death(2) + [None],  # Newer malformed entry must still raise.
            self.death(2) + [dict(kind="death", actor_id=[], sequence=4)],
            [dict(kind="death", actor_id=8, sequence=1)],
            [dict(kind="state", actor_id=8, sequence=1)],
            self.death(2) + [dict(kind="death", actor_id=7, sequence=3)],
        ):
            with self.subTest(events=events):
                self.assert_indexed_matches_original(self.fight(events))
        for events in (None, {}, "bad"):
            fight = self.fight(events)
            indexed = result(
                lambda: NativeGlobalPVReadView(fight).death_indices(fight, 8)
            )
            original = result(lambda: _registered_death_event(fight, 8))
            self.assertEqual(indexed, original)

    def test_each_operation_rebuilds_candidates_and_selected_cause_is_always_revalidated(
        self,
    ):
        fight = self.fight(self.death(2))
        view = NativeGlobalPVReadView(fight)
        indices = view.death_indices(fight, 8)
        self.assertEqual(indices, (1,))
        fight.events[0]["hp"] = 1
        self.assertEqual(
            result(lambda: _registered_death_event(fight, 8, event_indices=indices)),
            result(lambda: _registered_death_event(fight, 8)),
        )
        self.assertEqual(self.assert_indexed_matches_original(fight)[0], "error")
        fight.events.extend(self.death(4))
        self.assertEqual(view.death_indices(fight, 8), (3, 1))
        self.assertEqual(self.assert_indexed_matches_original(fight), ("value", True))
