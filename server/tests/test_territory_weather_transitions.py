import struct
import unittest
from datetime import datetime, timedelta, timezone

from postgres_case import PostgresCase
from wakfu_server.territory_weather import (
    advance_due,
    decode,
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

    def test_scheduled_transition_updates_only_enum_and_writes_outbox_once(self):
        self.add_current()
        first_at = datetime.now(timezone.utc) + timedelta(seconds=2)
        latest_at = first_at + timedelta(seconds=1)
        self.assertTrue(self.schedule(first_at, "HEAVY"))
        self.assertTrue(self.schedule(latest_at, "STORM"))

        # Repeating the same configured occurrence is idempotent; a conflicting
        # target at the same instant is rejected rather than silently replacing it.
        self.assertFalse(self.schedule(latest_at, "STORM"))
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            self.schedule(latest_at, "ABSENT")

        later = self.reopen()
        result = advance_due(later, now=latest_at + timedelta(milliseconds=1))
        self.assertEqual(len(result), 1)
        event = result[0]
        self.assertEqual(
            (event["map_id"], event["instance_id"], event["region_id"]),
            (self.map_id, self.instance_id, self.region_id),
        )
        self.assertEqual((event["weather"], event["revision"]), ("STORM", 2))
        original = self.payload(1)
        self.assertEqual(event["native_payload"], original[:-4] + struct.pack(">i", 3))
        self.assertEqual(
            decode(event["native_payload"])["native_values"],
            decode(original)["native_values"],
        )
        self.assertEqual(
            advance_due(self.store, now=latest_at + timedelta(seconds=5)), []
        )
        pending = pending_publications(self.store)
        self.assertEqual(pending, [event])
        with self.store.connection() as db:
            remaining = db.execute(
                "SELECT count(*) FROM territory_weather_transitions WHERE map_id=%s "
                "AND instance_id=%s AND region_id=%s",
                (self.map_id, self.instance_id, self.region_id),
            ).fetchone()["count"]
        self.assertEqual(remaining, 0)

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
        with self.assertRaisesRegex(ValueError, "batch size"):
            advance_due(self.store, limit=True)
        with self.assertRaisesRegex(ValueError, "aware timestamp"):
            advance_due(self.store, now=datetime.now())

    def test_noop_transition_does_not_create_revision_or_publication(self):
        self.add_current(weather_id=1)
        at = datetime.now(timezone.utc) + timedelta(seconds=2)
        self.schedule(at, "LIGHT")
        self.assertEqual(advance_due(self.store, now=at + timedelta(seconds=1)), [])
        pending = pending_publications(self.store)
        # The initial save has one durable publication. The no-op scheduled
        # transition must not add a second revision/event.
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["revision"], 1)
        with self.store.connection() as db:
            row = db.execute(
                "SELECT weather,revision FROM territory_weather WHERE map_id=%s "
                "AND instance_id=%s AND region_id=%s",
                (self.map_id, self.instance_id, self.region_id),
            ).fetchone()
        self.assertEqual((row["weather"], row["revision"]), ("LIGHT", 1))

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
        at = datetime.now(timezone.utc) + timedelta(seconds=2)
        self.schedule(at, "HEAVY")
        advance_due(self.store, now=at + timedelta(seconds=1))
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
        at = datetime.now(timezone.utc) + timedelta(seconds=2)
        self.schedule(at, "STORM", instance_id=17)
        changed = advance_due(self.store, now=at + timedelta(seconds=1))
        self.assertEqual(len(changed), 1)
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

    def test_locked_latest_due_transition_never_falls_back_to_older_due_state(self):
        self.add_current(weather_id=1)
        first_at = datetime.now(timezone.utc) + timedelta(seconds=2)
        latest_at = first_at + timedelta(seconds=1)
        self.schedule(first_at, "HEAVY")
        self.schedule(latest_at, "STORM")

        # Simulate another worker holding the latest due row while this worker
        # executes its SKIP LOCKED query. It must not select the older due row.
        with self.store.connection() as locker:
            locker.execute(
                "SELECT 1 FROM territory_weather_transitions WHERE map_id=%s "
                "AND instance_id=%s AND region_id=%s AND transition_at=%s FOR UPDATE",
                (self.map_id, self.instance_id, self.region_id, latest_at),
            ).fetchone()
            self.assertEqual(
                advance_due(self.store, now=latest_at + timedelta(seconds=1)), []
            )

        applied = advance_due(self.store, now=latest_at + timedelta(seconds=1))
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["weather"], "STORM")
        self.assertEqual(applied[0]["revision"], 2)


if __name__ == "__main__":
    unittest.main()
