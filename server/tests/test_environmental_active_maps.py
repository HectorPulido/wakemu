"""No vacant-map environmental SQL, progress, tick or historical simulation."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from psycopg.pq import TransactionStatus
from wakfu_server.world import World
from wakfu_server.objectives import environmental_presence as presence
from wakfu_server.objectives import environmental_storage as storage
from wakfu_server.objectives import environmental_service as service
from wakfu_server.objectives import environmental_gameplay as gameplay
from wakfu_server.objectives.environmental_world import SelectedEnvironmentalEvents
from test_environmental_durable_lifecycle import EnvironmentalDurableLifecycleTests
from test_environmental_ranking import EnvironmentalRankingPostgresTests


def player(identity=1, instance=0):
    return dict(
        id=identity,
        account_id=identity,
        map_id=527,
        instance_id=instance,
        x=0,
        y=0,
        z=0,
    )


def fact():
    return gameplay.GameplayFact(
        "resource_collected",
        "real:1",
        1,
        1,
        527,
        0,
        "resource",
        1,
        1337,
        100,
        region_id=17,
        action_id=3,
        before_step=1,
        after_step=0,
    )


class EnvironmentalActiveMapTests(unittest.TestCase):
    def setUp(self):
        self.world = World(lambda _: b"", lambda _: b"", lambda *_: None)
        live = patch.object(presence, "_world", self.world)
        live.start()
        self.addCleanup(live.stop)
        self.db = Mock()
        self.db.info.transaction_status = TransactionStatus.INTRANS

    def test_empty_map_performs_no_sql_in_service_facts_or_connection_poll(self):
        store = SimpleNamespace(
            connection=Mock(side_effect=AssertionError("Vacant scope queried SQL")),
            current_character_session=Mock(
                side_effect=AssertionError("Vacant scope checked lease")
            ),
        )
        location = dict(map_id=527, instance_id=0, region_id=17)
        self.assertTrue(
            service.refresh(store, 1, "lease", 1, location=location, now_ms=100)[
                "inactive_scope"
            ]
        )
        self.assertEqual(storage.contribute(self.db, fact()), ())
        self.assertTrue(
            storage.refresh(
                self.db, account_id=1, character_id=1, location=location, now_ms=100
            )["inactive_scope"]
        )
        self.assertEqual(
            gameplay.settled_fight(
                self.db, account_id=1, character_id=1, fight_id=1, source_scene=location
            ),
            (),
        )
        self.assertEqual(
            gameplay.committed_resource(
                self.db, account_id=1, character_id=1, token="token", resource=location
            ),
            (),
        )
        self.assertEqual(
            gameplay.committed_planting(
                self.db,
                account_id=1,
                character_id=1,
                operation_id="op",
                source_scene=location,
            ),
            (),
        )
        checkpoint = Mock(side_effect=AssertionError("Vacant scope flushed position"))
        self.assertFalse(
            SelectedEnvironmentalEvents().refresh(
                store,
                self.world,
                1,
                "lease",
                1,
                location=location,
                ready=True,
                checkpoint=checkpoint,
            )
        )
        self.db.execute.assert_not_called()
        store.connection.assert_not_called()

    def test_exact_instance_last_departure_and_replacement_control_presence(self):
        self.world.join("a", object(), player())
        self.world.join("b", object(), player(2))
        self.world.join("instance", object(), player(3, 99))
        token = presence.capture(527, 0)
        self.assertIsNotNone(token)
        self.world.leave(1, "a")
        self.assertTrue(presence.current(token, 527, 0))
        self.world.deactivate_ecology(2, "b")
        self.assertIsNone(presence.capture(527, 0))
        self.assertIsNotNone(presence.capture(527, 99))
        self.world.join("replacement", object(), player(2))
        self.assertFalse(presence.current(token, 527, 0))
        self.assertFalse(self.world.deactivate_ecology(2, "b"))
        self.assertIsNotNone(presence.capture(527, 0))

    def test_departure_or_new_presence_episode_while_waiting_for_sql_cannot_count(self):
        self.world.join("a", object(), player())

        def replace_episode(*args):
            self.world.leave(1, "a")
            self.world.join("new", object(), player())

        with patch.object(storage, "_scope_lock", side_effect=replace_episode):
            self.assertEqual(storage.contribute(self.db, fact()), ())
        self.db.execute.assert_not_called()


class EnvironmentalActiveMapPostgresTests(EnvironmentalDurableLifecycleTests):
    ranked_profile = EnvironmentalRankingPostgresTests.ranked_profile

    def test_vacancy_freezes_counting_and_return_skips_all_missed_cycles(self):
        self.profile(mode="collaborative", required=2)
        first = self.admit()["instances"][0]["instance_id"]
        self.roster(first, [501, 502])
        self.consume(self.fact(501))
        # A durable live session/character row is deliberately left behind.
        # Only genuine socket/world membership authorizes the environmental map.
        self.presence_world.leave(self.character["id"], self.generation)
        with patch.object(
            self.store,
            "connection",
            side_effect=AssertionError("Vacant scope opened SQL"),
        ):
            self.assertTrue(self.admit(now_ms=self.now_ms + 500000)["inactive_scope"])
        self.assertEqual(self.consume(self.fact(502)), ())
        with self.store.connection() as db:
            self.assertFalse(
                storage.cancel(
                    db, first, reason="vacant callback", now_ms=self.now_ms + 500000
                )
            )
            self.assertFalse(
                storage.register_memberships(
                    db,
                    first,
                    [
                        dict(
                            entity_kind="resource",
                            entity_id=599,
                            reference=1337,
                            source_key="vacant callback",
                        )
                    ],
                )
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_memberships"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT state FROM environmental_event_instances"
                ).fetchone()["state"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT sum(quantity) AS n FROM environmental_progress"
                ).fetchone()["n"],
                1,
            )
        self.presence_world.join(self.generation, object(), self.character)
        resumed = self.admit(now_ms=self.now_ms + 500000)
        current = resumed["instances"][0]["instance_id"]
        self.assertNotEqual(current, first)
        self.assertEqual(resumed["rewards"]["delivered"], [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_instances"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
        # No retroactive credit from either the vacancy or the old scene.
        self.assertEqual(self.consume(self.fact(502)), ())
        self.roster(current, [503, 504])
        self.consume(replace(self.fact(503), occurred_at_ms=self.now_ms + 500001))
        self.consume(replace(self.fact(504), occurred_at_ms=self.now_ms + 500002))
        self.assertEqual(
            len(self.admit(now_ms=self.now_ms + 500003)["rewards"]["delivered"]), 1
        )

    def test_offline_competition_finalizes_only_real_prior_score_once_on_return(self):
        self.ranked_profile("competitive")
        event = self.admit()["instances"][0]["instance_id"]
        self.roster(event, [601, 602])
        self.consume(replace(self.fact(601), quantity=4))
        self.presence_world.leave(self.character["id"], self.generation)
        self.assertEqual(self.consume(replace(self.fact(602), quantity=99)), ())
        self.assertTrue(self.admit(now_ms=self.now_ms + 60000)["inactive_scope"])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_event_rankings"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_reward_entitlements"
                ).fetchone()["n"],
                0,
            )
        self.presence_world.join(self.generation, object(), self.character)
        self.assertEqual(
            len(self.admit(now_ms=self.now_ms + 60001)["rewards"]["delivered"]), 1
        )
        self.assertEqual(
            self.admit(now_ms=self.now_ms + 60002)["rewards"]["delivered"], []
        )
        with self.store.connection() as db:
            row = db.execute(
                "SELECT score,finalized_at_ms FROM environmental_event_rankings"
            ).fetchone()
            self.assertEqual(
                (row["score"], row["finalized_at_ms"]), (4, self.now_ms + 60001)
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM environmental_claim_receipts"
                ).fetchone()["n"],
                1,
            )
