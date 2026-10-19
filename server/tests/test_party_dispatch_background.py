"""Party refresh defers a bad fight snapshot without hiding unrelated failures."""
from contextlib import contextmanager, nullcontext
import unittest
from unittest.mock import patch

from wakfu_server import party_dispatch


class Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def execute(self, *_args):
        return self

    def fetchall(self):
        return self.rows


class Store:
    @contextmanager
    def connection(self):
        yield Cursor([])


class World:
    def snapshot(self):
        return [dict(id=101), dict(id=202)]


class PartyRefreshBackgroundTests(unittest.TestCase):
    def parties(self):
        parties = object.__new__(party_dispatch.Parties)
        parties.store = Store()
        parties.world = World()
        return parties

    def test_typed_snapshot_deferral_is_bounded_and_does_not_stop_other_parties(self):
        parties = self.parties()
        rows = [dict(party_id=11, anchor=101), dict(party_id=22, anchor=202)]

        def publish(party_id):
            if party_id == 11:
                raise party_dispatch.PartySnapshotUnavailable(11, 303, 404)
            return True

        with patch.object(parties, "_guard", return_value=nullcontext()), patch.object(
            parties, "_publish", side_effect=publish
        ), patch.object(party_dispatch.player_parties, "expire") as expire:
            # The first query is the missing-roster query; the second returns
            # these party anchors. Expiration is deliberately side-effect free.
            calls = 0

            @contextmanager
            def connection():
                nonlocal calls
                calls += 1
                yield Cursor([] if calls == 1 else rows)

            parties.store.connection = connection
            result = parties.refresh_online()

        self.assertEqual(
            result,
            {
                "refreshed": 1,
                "deferred": [dict(party_id=11, character_id=303, fight_id=404)],
            },
        )
        expire.assert_called_once_with(parties.store)

    def test_unrelated_publication_error_propagates(self):
        parties = self.parties()

        calls = 0

        @contextmanager
        def connection():
            nonlocal calls
            calls += 1
            yield Cursor([] if calls == 1 else [dict(party_id=33, anchor=101)])

        parties.store.connection = connection
        with patch.object(parties, "_guard"), patch.object(
            parties, "_publish", side_effect=RuntimeError("storage unavailable")
        ), patch.object(party_dispatch.player_parties, "expire"):
            with self.assertRaisesRegex(RuntimeError, "storage unavailable"):
                parties.refresh_online()


if __name__ == "__main__":
    unittest.main()
