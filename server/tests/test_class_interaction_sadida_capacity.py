"""Mixed Sadida capacity uses native team-source carriers, not raw roster size."""
from dataclasses import replace
import unittest
import re

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionCell,
    ConditionContext,
    evaluate_condition,
)
from wakfu_server.combat_range_conditions import (
    RangeFighter,
    own_team_state_carriers,
    range_count,
)


class SadidaMixedCapacityInteractionTests(unittest.TestCase):
    def test_seed_native_count_branch_preserves_permissive_alternate_cast_routes(self):
        rule = native_catalog.record(
            DATA_ROOT / "native-spell-casting.json", "spells", "8137"
        )
        # This is one original branch, not a global cast limit: the full
        # published rule also contains permissive8150/no8150 alternatives.
        branch = re.search(
            r'\(GetOwnTeamStateCountInRange\(-1, "caster", 8202\).*?\) < 6',
            rule["cast_criterion_raw"],
            re.DOTALL,
        )
        self.assertIsNotNone(branch)
        # Explicit range-authority fixture: native state-carrier facts are input,
        # not claimed paid summons. Count/filter/criterion are production code.
        caster = ConditionActor(
            actor_id=7,
            is_player=True,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
        )
        affiliations = {7: 0, 8: 0, -7: 1}
        base = tuple(
            RangeFighter(
                (index, 0, 0), 0, 0, True, False, False, states=((reference, 1, 7),)
            )
            for index, reference in enumerate((8202, 8200, 8200, 8200, 8217))
        )
        sixth = RangeFighter(
            (8, 0, 0), 0, 0, True, False, False, states=((8217, 1, 8),)
        )
        cases = (
            ("five_mixed", base, True),
            ("sixth_from_friendly_other_owner", base + (sixth,), False),
            (
                "hostile_source_not_counted",
                base + (replace(sixth, states=((8217, 1, -7),)),),
                True,
            ),
            (
                "retired_friendly_not_counted",
                base + (replace(sixth, in_play=False),),
                True,
            ),
            (
                "native3616_subtraction",
                base + (replace(sixth, states=((8217, 1, 8), (3616, 1, 8))),),
                True,
            ),
        )
        for label, population, expected in cases:
            with self.subTest(case=label):
                rows = tuple(
                    replace(
                        row,
                        states=own_team_state_carriers(
                            row.states,
                            0,
                            affiliations,
                        ),
                    )
                    for row in population
                )

                def count(maximum, selector, reference, level, in_play, owner):
                    self.assertEqual(owner, "")
                    return range_count(
                        rows,
                        affiliation=0,
                        center=(0, 0, 0),
                        minimum=0,
                        maximum=maximum,
                        relation="state",
                        in_play=in_play,
                        state_reference=reference,
                        state_level=level,
                    )

                context = ConditionContext(
                    actors={"caster": caster},
                    target_cell=ConditionCell(True, False),
                    effect_target_absent=True,
                    null_actor_aliases=frozenset({"target"}),
                    state_null_fallback_absent=True,
                    cell_specific_area_query=lambda *_: False,
                    own_team_state_range_query=count,
                )
                self.assertEqual(evaluate_condition(branch.group(0), context), expected)
                # Do not turn the isolated branch into an invented global
                # rejection. The ordinary no8150 alternate remains legal.
                self.assertTrue(evaluate_condition(rule["cast_criterion_raw"], context))
