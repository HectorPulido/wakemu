import unittest
from build_conditional_state_producer_gaps import build


class ConditionalStateProducerGapTests(unittest.TestCase):
    def test_transitive_innate_and_extra_book_sources_are_not_missing_implementations(
        self,
    ):
        source = dict(
            effect=100,
            native_runner_class="eWu",
            criterion_raw="HasState(1)",
            class_spell_ancestors=[],
        )
        extra = dict(
            source,
            effect=200,
            class_spell_ancestors=[dict(spell=300, breeds=[6], depth=2)],
        )
        matrix = dict(
            state_source_index={
                "1": dict(native_state_apply_candidates=[source]),
                "2": dict(native_state_apply_candidates=[extra]),
                "3": dict(native_state_apply_candidates=[]),
            }
        )
        plan = dict(
            plans=[
                dict(
                    spell=500,
                    branch=0,
                    breeds=[6],
                    criterion_raw="HasState(1)",
                    preparation=[dict(state=state)],
                )
                for state in (1, 2, 3)
            ]
        )
        components = dict(
            classes=[
                dict(breed=6, innate_dependency_components=dict(effect=["effect:100"])),
                dict(
                    breed=11, innate_dependency_components=dict(effect=["effect:100"])
                ),
            ]
        )
        rows = build(matrix, plan, components, states=(1, 2, 3))
        self.assertEqual(
            rows[0]["classification"],
            "transitive_innate_producer_ownership_missing_from_current_planner",
        )
        self.assertEqual(
            rows[0]["state_apply_sources"][0]["innate_component_owner_breeds"], [6, 11]
        )
        self.assertEqual(rows[0]["transitive_innate_owner_breeds"], [6])
        self.assertEqual(
            rows[1]["classification"],
            "extra_owned_book_fixture_omission_requires_actual_permission",
        )
        self.assertEqual(
            rows[2]["classification"], "no_state_apply_edge_in_current_scoped_graph"
        )
        self.assertTrue(
            all(not row["actual_source_execution_verified"] for row in rows)
        )
