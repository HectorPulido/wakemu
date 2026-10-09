from copy import deepcopy
import unittest
from wakfu_ai.context.native_context import encode, NativeGraph
from wakfu_ai.planning.query_search import candidates


class CandidateTargetMaskTests(unittest.TestCase):
    def collect(self, envelope, *, spells=None, cells=None):
        cells = cells or {(x, 0, 0) for x in range(-4, 5)} | {(2, 0, 99)}
        graph = NativeGraph(
            encode({"runtime": {"fight": {"walkable": cells, "edges": set()}}})
        )
        state = {
            "actors": [dict(id=-7, team=1, position=[0, 0, 0], hp=20, max_hp=20, mp=0)]
        }
        repertoire = dict(
            actorId=-7,
            spells=spells or [dict(spellId=10, level=1)],
            nativeTargetEnvelope=envelope,
        )
        return [
            a for a in candidates(graph, state, repertoire, -7) if a["type"] == "cast"
        ]

    def envelope(self):
        return dict(
            version="native-target-envelope-v1",
            actorId=-7,
            origin=[0, 0, 0],
            metric="xy-manhattan",
            complete=True,
            maximum=2,
            basis="native-casting-range-upper-bound",
            unrestrictedSpellIds=[],
            unknownSpellIds=[],
            spells=[
                dict(
                    spellId=10,
                    level=1,
                    minimum=0,
                    maximum=2,
                    source="baseline+all-conditional-branches",
                )
            ],
        )

    def test_certified_mask_keeps_empty_cells_self_and_all_heights(self):
        actions = self.collect(self.envelope())
        targets = {tuple(a["target"]) for a in actions}
        self.assertEqual(targets, {(x, 0, 0) for x in range(-2, 3)} | {(2, 0, 99)})

    def test_unknown_ability_preserves_full_targets_with_known_ability_masked(self):
        envelope = self.envelope()
        envelope.update(complete=False, maximum=None, unknownSpellIds=[11])
        actions = self.collect(
            envelope, spells=[dict(spellId=10, level=1), dict(spellId=11, level=1)]
        )
        self.assertEqual(sum(a["spellId"] == 10 for a in actions), 6)
        self.assertEqual(sum(a["spellId"] == 11 for a in actions), 10)

    def test_override_spell_retains_every_target(self):
        envelope = self.envelope()
        envelope.update(complete=False, maximum=None, unrestrictedSpellIds=[10])
        self.assertEqual(len(self.collect(envelope)), 10)

    def test_stale_origin_and_future_schema_disable_mask(self):
        for change in (
            {"origin": [1, 0, 0]},
            {"actorId": -8},
            {"version": "future"},
            {"futureField": True},
        ):
            envelope = self.envelope()
            envelope.update(change)
            self.assertEqual(len(self.collect(envelope)), 10)

    def test_integer_wraparound_targets_are_never_filtered(self):
        cells = {(0, 0, 0), (-(1 << 31), 0, 0), ((1 << 31), 0, 0)}
        self.assertEqual(len(self.collect(self.envelope(), cells=cells)), 3)

    def test_mask_does_not_change_complete_graph_or_metadata(self):
        envelope = self.envelope()
        before = deepcopy(envelope)
        self.collect(envelope)
        self.assertEqual(envelope, before)
