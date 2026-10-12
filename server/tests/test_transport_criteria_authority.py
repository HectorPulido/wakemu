"""Installed conditional boats consume only their source actor's durable ledger."""
import struct
import unittest
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server.maps import transport_criteria
from wakfu_server.achievements import storage
import test_native_boat_dispatch as dispatch_fixtures


class TransportCriteriaAuthorityTests(PostgresCase):
    def test_actual_owner_snapshot_is_lazy_immutable_and_never_uses_other_character(
        self,
    ):
        account = self.store.register("criteria-owner", "local-password")["id"]
        own = self.store.create_character(account, "Criteria Owner")
        other = self.store.create_character(account, "Criteria Other")
        with self.store.connection() as db:
            state = storage.load_locked(db, other["id"])
            state["completed"] = [2192]
            storage.store(db, other["id"], state)
        allowed = transport_criteria.evaluator(self.store, own)
        self.assertFalse(allowed("IsAchievementComplete(2192)", own))
        with self.store.connection() as db:
            state = storage.load_locked(db, own["id"])
            state["completed"] = [2192]
            storage.store(db, own["id"], state)
        self.assertFalse(allowed("IsAchievementComplete(2192)", own))
        self.assertTrue(
            transport_criteria.evaluator(self.store, own)(
                "IsAchievementComplete(2192)", own
            )
        )
        with self.assertRaises(ValueError):
            allowed("IsAchievementComplete(2192)", other)

    def test_missing_native_authority_rejects_even_when_other_character_completed(self):
        account = self.store.register("criteria-missing", "local-password")["id"]
        own = self.store.create_character(account, "Criteria Missing")
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM character_achievement_authority WHERE character_id=%s",
                (own["id"],),
            )
        allowed = transport_criteria.evaluator(self.store, own)
        self.assertTrue(allowed("GetRealLevel() >= 1", own))
        with self.assertRaisesRegex(ValueError, "authority"):
            allowed("IsAchievementComplete(2192)", own)


class ConditionalBoatDispatcherTests(unittest.TestCase):
    def fixture(self):
        fixture = dispatch_fixtures.NativeBoatDispatchTests(
            "test_boat_requires_authority_then_fenced_commit_and_normal_bootstrap"
        )
        fixture.setUp()
        fixture.character.update(map_id=323, x=-2, y=10, z=6)
        fixture.namespace["body"] = struct.pack(">qq", 13976, 20236)
        fixture.terrain.map_geometry.return_value = {
            "edges": [((94, 5, 6), (94, 6, 6))]
        }
        fixture.store.transition_map.return_value = dict(
            fixture.character, map_id=527, x=94, y=5, z=6
        )
        return fixture

    def test_actual_dispatcher_evaluates_native_achievement_after_source_authority(
        self,
    ):
        fixture = self.fixture()
        order = []

        def admit(*args, **kwargs):
            order.append("source-authority")
            return True

        def queries(store, owner):
            self.assertIs(store, fixture.store)
            self.assertEqual(owner, 7)
            order.append("owned-achievement")
            return {"IsAchievementComplete": lambda identity: identity == 2192}

        with patch.object(
            dispatch_fixtures.native_boats, "admit_source", side_effect=admit
        ), patch(
            "wakfu_server.maps.dungeon_achievement_authority.queries",
            side_effect=queries,
        ):
            fixture.run_dispatch()
        self.assertEqual(order, ["source-authority", "owned-achievement"])
        fixture.store.transition_map.assert_called_once()
        fixture.namespace["join_world"].assert_called_once()

    def test_actual_dispatcher_missing_achievement_denies_without_transition(self):
        fixture = self.fixture()
        with patch.object(
            dispatch_fixtures.native_boats, "admit_source", return_value=True
        ), patch(
            "wakfu_server.maps.dungeon_achievement_authority.queries",
            side_effect=ValueError("Missing achievement authority"),
        ):
            fixture.run_dispatch()
        fixture.store.transition_map.assert_not_called()
        fixture.namespace["join_world"].assert_not_called()
        self.assertEqual(
            fixture.namespace["record"].call_args.kwargs["event"],
            "native_transport_rejected",
        )
