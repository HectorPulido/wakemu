"""KO cast identity never creates living movement occupancy."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_ai.planning.query_search import _cast_recipient_ids


class RetainedCastRecipientTests(unittest.TestCase):
    def actor(self, identity, hp, cell=(1, 0, 0)):
        return dict(id=identity, hp=hp, position=cell)

    def test_retained_ko_fighter_has_explicit_cast_identity(self):
        actors = {1: self.actor(1, 0)}
        self.assertEqual(_cast_recipient_ids(actors), {(1, 0, 0): [1]})
        self.assertFalse(
            {tuple(a["position"]): a["id"] for a in actors.values() if a["hp"] > 0}
        )

    def test_living_recipient_wins_shared_cell(self):
        actors = {1: self.actor(1, 0), 2: self.actor(2, 10)}
        self.assertEqual(_cast_recipient_ids(actors), {(1, 0, 0): [2]})

    def test_all_retained_identities_are_offered_deterministically(self):
        actors = {4: self.actor(4, 0), 1: self.actor(1, 0)}
        self.assertEqual(_cast_recipient_ids(actors), {(1, 0, 0): [1, 4]})


if __name__ == "__main__":
    unittest.main()
