"""Focused completed-history consumers; import candidate in public namespace."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_server import combat_materialized_event_history as helper
from wakfu_ai.planning.turn_memory import attacked_this_turn, damaged_targets_this_turn


class PlainGraph:
    @staticmethod
    def field(value, name):
        return getattr(value, name)

    @staticmethod
    def plain(value):
        return value


def fight_from(rows):
    events = [dict(row, sequence=i + 1) for i, row in enumerate(rows)]
    return SimpleNamespace(
        events=events, turn_id=9, sequence=len(events), _resolution_depth=0
    )


class CompletedEventHistoryTests(unittest.TestCase):
    def test_exact_deletions_and_current_tail_causal_and_unknown_protection(self):
        rows = [dict(kind="turn_started", turn_id=8)]
        removed_indices = []
        for kind in (
            "state_removed",
            "turn_ended",
            "npc_cast",
            "movement",
            "orientation",
        ):
            removed_indices.append(len(rows))
            rows.append(dict(kind=kind, turn_id=8))
            # Even an invalid causal predecessor must remain invalid, not be
            # replaced by an older plausible damage event after compaction.
            rows.extend(
                [
                    dict(kind="damage", source_id=1, target_id=-1, hp=0),
                    dict(kind=kind, turn_id=8),
                    dict(kind="death", actor_id=-1),
                ]
            )
        for kind in ("turn_ended", "npc_cast"):
            for value in (None, True, 9, 10):
                rows.append(dict(kind=kind, turn_id=value))
        rows.append(dict(kind="unknown_future_kind"))
        rows.extend(dict(kind="unknown_padding_diagnostic") for _ in range(280))
        # Tail rows precede the new-turn anchor and therefore independently
        # prove the last256 guard, rather than only the current-turn guard.
        rows.extend(
            dict(kind=kind, turn_id=8)
            for kind in (
                "state_removed",
                "turn_ended",
                "npc_cast",
                "movement",
                "orientation",
            )
        )
        rows.append(dict(kind="turn_started", turn_id=9))
        rows.extend(
            dict(kind=kind, turn_id=9)
            for kind in (
                "state_removed",
                "turn_ended",
                "npc_cast",
                "movement",
                "orientation",
            )
        )
        fight = fight_from(rows)
        before = deepcopy(fight.events)
        expected = [row for i, row in enumerate(before) if i not in removed_indices]
        self.assertEqual(helper.prune_materialized_events(fight), 5)
        self.assertEqual(fight.events, expected)
        self.assertEqual(fight.events[-256:], before[-256:])
        self.assertEqual(fight.sequence, len(before))
        self.assertEqual(helper.prune_materialized_events(fight), 0)

    def test_real_ai_turn_memory_is_equal_before_after_and_after_current_end(self):
        rows = [dict(kind="turn_started", turn_id=8)]
        rows.extend(
            [
                dict(kind="damage", source_id=1, target_id=-7, amount=12),
                dict(kind="npc_cast", actor_id=1, turn_id=8),
                dict(kind="turn_ended", turn_id=8),
            ]
        )
        rows.extend(dict(kind="state_removed", uid=i) for i in range(300))
        rows.extend(
            [
                dict(kind="turn_started", turn_id=9),
                dict(kind="damage", source_id=1, target_id=-8, amount=10),
                dict(kind="npc_cast", actor_id=1, turn_id=9),
            ]
        )
        for ended in (False, True):
            with self.subTest(ended=ended):
                fight = fight_from(
                    rows + ([dict(kind="turn_ended", turn_id=9)] if ended else [])
                )
                graph = PlainGraph()
                before = (
                    attacked_this_turn(graph, fight, 1),
                    damaged_targets_this_turn(graph, fight, 1),
                )
                self.assertEqual(
                    before, (False, frozenset()) if ended else (True, frozenset({-8}))
                )
                self.assertGreater(helper.prune_materialized_events(fight), 0)
                after = (
                    attacked_this_turn(graph, fight, 1),
                    damaged_targets_this_turn(graph, fight, 1),
                )
                self.assertEqual(after, before)

    def test_real_ai_facing_uses_identical_recent_damage_and_materialized_positions(
        self,
    ):
        from wakfu_server.combat_ai_facing import choose

        rows = [dict(kind="turn_started", turn_id=8)]
        rows.extend(
            dict(kind=("movement", "orientation")[i % 2], actor_id=1)
            for i in range(300)
        )
        rows.append(dict(kind="turn_started", turn_id=9))
        rows.extend(
            [
                dict(kind="damage", source_id=2, target_id=1, amount=5),
                dict(kind="damage", source_id=3, target_id=1, amount=20),
                dict(kind="movement", actor_id=1, path=[(0, 0, 0)]),
                dict(kind="orientation", actor_id=1, direction=2),
            ]
        )
        fight = fight_from(rows)

        def actor(identity, team, position):
            return SimpleNamespace(
                id=identity,
                team=team,
                position=position,
                hp=100,
                controlled=False,
                effect_stats={},
            )

        fight.actors = {
            1: actor(1, 0, (0, 0, 0)),
            2: actor(2, 1, (1, 0, 0)),
            3: actor(3, 1, (-1, 0, 0)),
        }
        fight._in_play = lambda actor: actor.hp > 0
        before = choose(fight, fight.actors[1])
        self.assertEqual(before["targetId"], 3)
        self.assertEqual(before["observedIncoming"], 20)
        positions = {key: actor.position for key, actor in fight.actors.items()}
        self.assertGreater(helper.prune_materialized_events(fight), 0)
        self.assertEqual(choose(fight, fight.actors[1]), before)
        self.assertEqual(
            {key: actor.position for key, actor in fight.actors.items()}, positions
        )
