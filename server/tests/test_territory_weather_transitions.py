import struct
import unittest
from datetime import datetime, timedelta, timezone

from postgres_case import PostgresCase
from wakfu_server.territory_weather import (
    pending_publications,
    publish_pending,
    save,
    schedule_transition,
)


class TerritoryWeatherTransitionTests(PostgresCase):
    map_id = 1134
    instance_id = 17
    region_id = 79201

    @staticmethod
    def payload(weather_id):
        return struct.pack(
            ">qb6fi", 123456789, -7, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, weather_id
        )

    def add_current(self, *, instance_id=None, region_id=None, weather_id=1):
        return save(
            self.store,
            map_id=self.map_id,
            instance_id=self.instance_id if instance_id is None else instance_id,
            region_id=self.region_id if region_id is None else region_id,
            payload=self.payload(weather_id),
        )

    def schedule(self, at, target, *, instance_id=None, region_id=None):
        return schedule_transition(
            self.store,
            map_id=self.map_id,
            instance_id=self.instance_id if instance_id is None else instance_id,
            region_id=self.region_id if region_id is None else region_id,
            transition_at=at,
            target_weather=target,
        )

    def test_admin_schedule_is_durable_idempotent_and_rejects_conflicting_target(self):
        self.add_current()
        at = datetime.now(timezone.utc) + timedelta(minutes=1)
        self.assertTrue(self.schedule(at, "STORM"))
        self.assertFalse(self.schedule(at, "STORM"))
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            self.schedule(at, "ABSENT")
        with self.reopen().connection() as db:
            row = db.execute(
                "SELECT target_weather,transition_at FROM territory_weather_transitions "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s",
                (self.map_id, self.instance_id, self.region_id),
            ).fetchone()
        self.assertEqual(row["target_weather"], "STORM")
        self.assertEqual(row["transition_at"], at)

    def test_unknown_zone_and_bad_clock_or_enum_fail_closed(self):
        at = datetime.now(timezone.utc) + timedelta(minutes=1)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.schedule(at, "LIGHT", instance_id=991)
        self.add_current()
        with self.assertRaisesRegex(ValueError, "Unknown scheduled weather"):
            self.schedule(at, "SUNNY")
        with self.assertRaisesRegex(ValueError, "aware timestamp"):
            self.schedule(datetime.now(), "STORM")
        with self.assertRaisesRegex(ValueError, "future"):
            self.schedule(datetime.now(timezone.utc) - timedelta(seconds=1), "STORM")

    def test_old_outbox_snapshot_is_superseded_by_new_authority(self):
        self.add_current(weather_id=1)
        newer = self.payload(3)
        saved = save(
            self.store,
            map_id=self.map_id,
            instance_id=self.instance_id,
            region_id=self.region_id,
            payload=newer,
        )
        pending = pending_publications(self.store)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["revision"], saved["revision"])
        self.assertEqual(pending[0]["native_payload"], newer)
        with self.store.connection() as db:
            stale = db.execute(
                "SELECT published_at,superseded_at FROM territory_weather_outbox "
                "WHERE map_id=%s AND instance_id=%s AND region_id=%s AND revision=1",
                (self.map_id, self.instance_id, self.region_id),
            ).fetchone()
        self.assertIsNone(stale["published_at"])
        self.assertIsNotNone(stale["superseded_at"])

    def test_publication_failure_retries_exact_snapshot_and_ack_is_conditional(self):
        self.add_current()
        # Explicit World/admin write; autonomous transitions are tested through Rust.
        self.add_current(weather_id=2)
        expected = pending_publications(self.store)[0]
        sent = []

        def fail(event):
            sent.append(event)
            raise OSError("simulated publisher failure")

        with self.assertRaisesRegex(OSError, "simulated"):
            publish_pending(self.store, fail)
        self.assertEqual(pending_publications(self.store), [expected])

        self.assertEqual(publish_pending(self.store, sent.append), 1)
        self.assertEqual(sent, [expected, expected])
        self.assertEqual(pending_publications(self.store), [])
        self.assertEqual(publish_pending(self.store, sent.append), 0)

    def test_weather_updates_are_scoped_to_exact_instance(self):
        self.add_current(instance_id=17)
        self.add_current(instance_id=18)
        self.add_current(instance_id=17, weather_id=3)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT instance_id,weather,revision FROM territory_weather "
                "WHERE map_id=%s AND region_id=%s ORDER BY instance_id",
                (self.map_id, self.region_id),
            ).fetchall()
        self.assertEqual(
            [(row["instance_id"], row["weather"], row["revision"]) for row in rows],
            [(17, "STORM", 2), (18, "LIGHT", 1)],
        )


if __name__ == "__main__":
    unittest.main()
