"""Advisory ordering and warm hints obey the native owner's deadline."""
import unittest
from unittest.mock import patch

from wakfu_ai.native.native_deadline import bounded
from wakfu_ai.planning import attack_opportunities as attack
from wakfu_ai.planning.query_search import _warm_start_actions
from test_attack_opportunities import actor, spell


class AdvisoryDeadlineTests(unittest.TestCase):
    def test_route_ranking_checks_deadline_without_scanning_every_route(self):
        actors = {1: actor(1, 1, (0, 0, 0)), 2: actor(2, 0, (10000, 0, 0))}
        routes = [((i, 0, 0),) for i in range(1, 5001)]
        now, calls = [0], [0]

        def priority(route):
            calls[0] += 1
            now[0] = 2
            return (0, len(route), route)

        with bounded(1, clock=lambda: now[0]):
            with self.assertRaises(TimeoutError):
                attack.attack_opportunity_routes(
                    routes,
                    actors,
                    1,
                    [spell()],
                    range_hints=lambda value: value["ranges"],
                    route_priority=priority,
                )
        self.assertLessEqual(calls[0], 256)
        self.assertEqual(len(routes), 5000)

    def test_already_reachable_recipients_do_not_skip_deadline_checks(self):
        actors = {
            identity: actor(
                identity, 1 if identity == 1 else 0, (identity % 16, identity // 16, 0)
            )
            for identity in range(1, 129)
        }
        spells = [spell(ranges=((0, 100 + i),)) for i in range(32)]
        now, calls = [0], [0]
        original = attack._matches

        def matches(*args):
            calls[0] += 1
            now[0] = 2
            return original(*args)

        with patch.object(attack, "_matches", matches), bounded(
            1, clock=lambda: now[0]
        ):
            with self.assertRaises(TimeoutError):
                attack.attack_opportunity_routes(
                    [((1, 0, 0),)],
                    actors,
                    1,
                    spells,
                    range_hints=lambda value: value["ranges"],
                    route_priority=lambda route: (0, len(route), route),
                )
        self.assertLessEqual(calls[0], 256)

    def test_warm_path_validation_stops_after_owner_deadline(self):
        for length in (8, 256, 4096, 32767):
            with self.subTest(length=length):
                now, traversals = [0], [0]

                class Cell(list):
                    def __iter__(self):
                        now[0] = 2
                        traversals[0] += 1
                        return super().__iter__()

                payload = dict(
                    schema="verified-turn-continuation-v1",
                    actions=[
                        dict(type="move", path=[Cell([i, 0, 0]) for i in range(length)])
                    ],
                )
                with bounded(1, clock=lambda: now[0]):
                    with self.assertRaises(TimeoutError):
                        _warm_start_actions(payload)
                # Validation and the independent public copy each traverse a cell.
                self.assertLessEqual(traversals[0], 512)

    def test_already_expired_owner_rejects_even_small_warm_cast(self):
        now = [0]
        with bounded(1, clock=lambda: now[0]):
            now[0] = 2
            with self.assertRaises(TimeoutError):
                _warm_start_actions(
                    dict(
                        schema="verified-turn-continuation-v1",
                        actions=[
                            dict(type="cast", spellId=1, level=1, target=[1, 0, 0])
                        ],
                    )
                )


if __name__ == "__main__":
    unittest.main()
