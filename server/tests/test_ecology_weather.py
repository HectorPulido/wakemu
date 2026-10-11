import contextlib
import json
import unittest
from unittest.mock import patch

from wakfu_server import ecology_weather as domain


class Store:
    def __init__(self, row):
        self.row = row
        self.inside = False
        self.queries = []

    @contextlib.contextmanager
    def connection(self):
        self.inside = True
        try:
            yield self
        finally:
            self.inside = False

    def execute(self, query, params):
        self.queries.append((query, params))
        return self

    def fetchone(self):
        return self.row


class EcologyWeatherTests(unittest.TestCase):
    def setUp(self):
        self.event = dict(map_id=1134, instance_id=0, region_id=79201, revision=2)
        self.proposal = dict(
            domain="weather",
            operation="publish",
            event=self.event,
            world_epoch="test-epoch",
        )

    def test_prepare_total_bound_and_json_safe(self):
        event = dict(self.event, weather="STORM", native_payload=b"native")
        with patch.object(domain.weather, "advance_due") as advance, patch.object(
            domain.weather, "pending_publications", return_value=[event]
        ), patch.object(domain.forecast, "pending_publications") as forecasts:
            proposals = domain.prepare(object(), {"world_epoch": "test-epoch"}, limit=1)
        advance.assert_called_once()
        forecasts.assert_not_called()
        self.assertEqual(json.loads(json.dumps(proposals)), [self.proposal])

    def test_stale_authority_never_publishes_or_acknowledges(self):
        store = Store(None)
        with patch.object(domain.weather, "publish_to_world") as publish, patch.object(
            domain.weather, "acknowledge_publication"
        ) as acknowledge:
            self.assertEqual(
                domain.apply(store, object(), self.proposal)["status"], "stale"
            )
        publish.assert_not_called()
        acknowledge.assert_not_called()
        self.assertIn("o.revision=w.revision", store.queries[0][0])

    def test_publish_outside_transaction_and_cas_supersession(self):
        store = Store(dict(self.event, weather="STORM", native_payload=b"native"))

        def publish(world, event):
            self.assertFalse(store.inside)

        with patch.object(
            domain.weather, "publish_to_world", side_effect=publish
        ), patch.object(domain.weather, "acknowledge_publication", return_value=False):
            self.assertEqual(
                domain.apply(store, object(), self.proposal),
                dict(status="stale", published=0),
            )

    def test_failed_send_leaves_outbox_unacknowledged(self):
        store = Store(dict(self.event, weather="STORM", native_payload=b"native"))
        with patch.object(
            domain.weather, "publish_to_world", side_effect=OSError("send")
        ), patch.object(domain.weather, "acknowledge_publication") as acknowledge:
            with self.assertRaises(OSError):
                domain.apply(store, object(), self.proposal)
        acknowledge.assert_not_called()

    def test_forecast_service_encodes_world_uses_prepared_payload(self):
        event = {key: value for key, value in self.event.items() if key != "revision"}
        event["policy_version"] = 3
        with patch.object(domain.weather, "advance_due"), patch.object(
            domain.weather, "pending_publications", return_value=[]
        ), patch.object(
            domain.forecast, "pending_publications", return_value=[event]
        ), patch.object(
            domain.forecast, "packet_for_territory", return_value=b"forecast"
        ):
            proposals = domain.prepare(object(), {"epoch": "fallback-epoch"}, 1)
        self.assertEqual(proposals[0]["world_epoch"], "fallback-epoch")
        store = Store(event)
        with patch.object(domain.forecast, "publish_to_world") as publish, patch.object(
            domain.forecast, "acknowledge_publication", return_value=True
        ), patch.object(domain.forecast, "packet_for_territory") as encode:
            self.assertEqual(
                domain.apply(store, object(), proposals[0])["published"], 1
            )
        encode.assert_not_called()
        publish.assert_called_once_with(
            store, unittest.mock.ANY, event, prepared_payload=b"forecast"
        )

    def test_malformed_prepared_forecast_never_publishes_or_acknowledges(self):
        event = {key: value for key, value in self.event.items() if key != "revision"}
        event["policy_version"] = 3
        proposal = {
            "domain": "weather",
            "operation": "forecast_publish",
            "event": event,
            "payload_hex": "not-hex",
        }
        store = Store(event)
        with patch.object(domain.forecast, "publish_to_world") as publish, patch.object(
            domain.forecast, "acknowledge_publication"
        ) as acknowledge:
            with self.assertRaisesRegex(
                ValueError, "Invalid prepared forecast payload"
            ):
                domain.apply(store, object(), proposal)
        self.assertFalse(store.inside)
        publish.assert_not_called()
        acknowledge.assert_not_called()


if __name__ == "__main__":
    unittest.main()
