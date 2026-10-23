import unittest

from wakfu_ai.planning.attack_opportunities import attack_opportunity_routes


def actor(identity, team, position, hp=10):
    return dict(id=identity, team=team, position=position, hp=hp, max_hp=10)


def spell(*, ranges=((1, 3),), tags=("damage",), linear=False, diagonal=False):
    return dict(
        spellId=10,
        level=1,
        ranges=ranges,
        casting=dict(linear=linear, diagonal=diagonal, conditional=[]),
        advisoryCapabilities=dict(spellId=10, level=1, tags=list(tags)),
    )


def opportunities(routes, actors, spells, priority=None, evidence=None):
    return attack_opportunity_routes(
        routes,
        actors,
        1,
        spells,
        range_hints=lambda value: value.get("ranges"),
        capability_evidence=evidence,
        route_priority=priority or (lambda route: (0, len(route), route)),
    )


class AttackOpportunityTests(unittest.TestCase):
    def test_promotes_complete_route_enabling_linear_cast_instead_of_merely_closing(
        self,
    ):
        actors = {1: actor(1, 1, (0, 0, 0)), 2: actor(2, 0, (3, 2, 0))}
        closer = ((1, 0, 0),)
        aligned = ((0, 1, 0), (0, 2, 0))
        routes = [closer, aligned]
        self.assertEqual(
            opportunities(routes, actors, [spell(linear=True)]), (aligned,)
        )
        self.assertEqual(routes, [closer, aligned])

    def test_known_linear_hint_works_with_legacy_metadata_without_diagonal_flag(self):
        actors = {1: actor(1, 1, (0, 0, 0)), 2: actor(2, 0, (3, 2, 0))}
        aligned = ((0, 1, 0), (0, 2, 0))
        known = spell(linear=True)
        del known["casting"]["diagonal"]
        del known["casting"]["conditional"]
        self.assertEqual(
            opportunities([((1, 0, 0),), aligned], actors, [known]), (aligned,)
        )

    def test_minimum_range_can_favor_sideways_movement_without_closing(self):
        actors = {1: actor(1, 1, (0, 0, 0)), 2: actor(2, 0, (1, 0, 0))}
        too_close, in_range = ((0, 1, 0),), ((0, 1, 0), (0, 2, 0))
        self.assertEqual(
            opportunities([too_close, in_range], actors, [spell(ranges=((3, 4),))]),
            (in_range,),
        )

    def test_diagonal_and_conditional_alignment_are_advisory_alternatives(self):
        actors = {1: actor(1, 1, (0, 0, 0)), 2: actor(2, 0, (3, 2, 1))}
        diagonal = ((1, 0, 0),)
        wrong = ((0, 1, 0),)
        self.assertEqual(
            opportunities(
                [wrong, diagonal], actors, [spell(ranges=((1, 5),), diagonal=True)]
            ),
            (diagonal,),
        )
        alternative = spell(ranges=((1, 3), (1, 5)), linear=True)
        alternative["casting"]["conditional"] = [dict(linear=False, diagonal=True)]
        self.assertEqual(opportunities([diagonal], actors, [alternative]), (diagonal,))

    def test_healing_uses_wounded_allies_and_damage_uses_enemies(self):
        actors = {
            1: actor(1, 1, (0, 0, 0)),
            2: actor(2, 1, (3, 0, 0), hp=5),
            3: actor(3, 0, (-3, 0, 0)),
        }
        east, west = ((1, 0, 0),), ((-1, 0, 0),)
        self.assertEqual(
            opportunities(
                [west, east], actors, [spell(ranges=((1, 2),), tags=("healing",))]
            ),
            (east,),
        )
        actors[2]["hp"] = 10
        self.assertEqual(
            opportunities([east], actors, [spell(ranges=((1, 2),), tags=("healing",))]),
            (),
        )
        self.assertEqual(
            opportunities([east, west], actors, [spell(ranges=((1, 2),))]), (west,)
        )

    def test_native_heal_and_armor_tags_match_observed_capability_names(self):
        actors = {1: actor(1, 1, (0, 0, 0)), 2: actor(2, 1, (3, 0, 0), hp=5)}
        route = ((1, 0, 0),)
        for tag in ("heal", "armor"):
            self.assertEqual(
                opportunities([route], actors, [spell(ranges=((1, 2),), tags=(tag,))]),
                (route,),
            )

    def test_preserves_hazard_preference_even_when_dangerous_route_opens_cast(self):
        actors = {1: actor(1, 1, (0, 0, 0)), 2: actor(2, 0, (3, 0, 0))}
        safe, dangerous = ((0, 1, 0),), ((1, 0, 0),)
        self.assertEqual(
            opportunities(
                [safe, dangerous],
                actors,
                [spell(ranges=((1, 2),))],
                priority=lambda route: (route == dangerous, route),
            ),
            (),
        )

    def test_unknown_metadata_and_already_reachable_target_add_no_bias(self):
        actors = {1: actor(1, 1, (0, 0, 0)), 2: actor(2, 0, (2, 0, 0))}
        routes = [((1, 0, 0),)]
        self.assertEqual(opportunities(routes, actors, [spell()]), ())
        unknown = spell(ranges=None)
        self.assertEqual(opportunities(routes, actors, [unknown]), ())
        mismatched = spell(ranges=((1, 1),))
        mismatched["advisoryCapabilities"]["spellId"] = 999
        self.assertEqual(opportunities(routes, actors, [mismatched]), ())
        self.assertEqual(
            opportunities(routes, actors, [mismatched], evidence={(10, 1): {"damage"}}),
            (routes[0],),
        )

    def test_comparison_budget_keeps_original_routes_available(self):
        actors = {1: actor(1, 1, (0, 0, 0)), 2: actor(2, 0, (10000, 0, 0))}
        routes = [((x, 0, 0),) for x in range(1, 5001)]
        original = list(routes)
        self.assertEqual(opportunities(routes, actors, [spell(ranges=((1, 1),))]), ())
        self.assertEqual(routes, original)


if __name__ == "__main__":
    unittest.main()
