"""Year-round native public entry keeps its level and item payment gates."""
import struct
import unittest
from datetime import datetime, timezone

from wakfu_server import generic_transports
from wakfu_server.maps import seasonal_transport


class SeasonalTransportTests(unittest.TestCase):
    def setUp(self):
        self.body = struct.pack(">qiBi", 18012, 4810, 0, 2)
        self.actor = dict(map_id=235, instance_id=0, level=51)
        self.now_ms = int(datetime(2030, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

    def criterion(self, expression, actor, destination):
        return seasonal_transport.evaluate(
            expression, actor, destination, now_ms=self.now_ms
        )

    def test_reviewed_public_event_opens_off_calendar_and_preserves_native_price(self):
        result = generic_transports.resolve(
            self.actor,
            self.body,
            source_allowed=lambda *_: True,
            criterion_evaluator=self.criterion,
            allow_item_payment=True,
        )
        self.assertEqual(result["destination"]["map_id"], 146)
        self.assertEqual(result["item_payment"], dict(reference=33075, quantity=1))
        self.assertIn("GetRealLevel()", result["criterion"])

    def test_default_resolver_still_requires_authoritative_criterion_callback(self):
        with self.assertRaisesRegex(ValueError, "access criterion"):
            generic_transports.resolve(
                self.actor, self.body, source_allowed=lambda *_: True
            )

    def test_low_level_cannot_use_year_round_event(self):
        self.actor["level"] = 50
        with self.assertRaisesRegex(ValueError, "criterion is not met"):
            generic_transports.resolve(
                self.actor,
                self.body,
                source_allowed=lambda *_: True,
                criterion_evaluator=self.criterion,
                allow_item_payment=True,
            )

    def test_calendar_opening_does_not_waive_required_payment_or_source(self):
        with self.assertRaisesRegex(ValueError, "item transaction"):
            generic_transports.resolve(
                self.actor,
                self.body,
                source_allowed=lambda *_: True,
                criterion_evaluator=self.criterion,
            )
        with self.assertRaisesRegex(ValueError, "interaction not allowed"):
            generic_transports.resolve(
                self.actor,
                self.body,
                source_allowed=lambda *_: False,
                criterion_evaluator=self.criterion,
                allow_item_payment=True,
            )
