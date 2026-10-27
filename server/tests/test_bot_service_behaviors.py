"""Exercise bot configuration and behavior decisions without live services."""

import sys
import tempfile
from pathlib import Path
import unittest

SERVICE_ROOT = Path(__file__).resolve().parents[1] / "bot-service"
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from wakfu_bots.behaviors import BehaviorRegistry
from wakfu_bots.config import Profiles, validate_profile
from wakfu_bots.runtime import Worker


def profile(*, capabilities=("shop",), behaviors=None, enabled=True):
    return {
        "bot_id": "merchant_1",
        "character": {"name": "Merchant", "breed": 15, "sex": 0},
        "enabled": enabled,
        "capabilities": list(capabilities),
        "behaviors": behaviors or {"buyer": {"purchase_percent": 80}},
    }


class BotServiceBehaviorTests(unittest.TestCase):
    def test_profile_schema_requires_explicit_integration_capabilities(self):
        valid = validate_profile(profile())
        self.assertEqual(valid["bot_id"], "merchant_1")
        for invalid in (
            profile(capabilities=()),
            profile(behaviors={"llm": {"personality": "helpful"}}),
            profile(behaviors={"buyer": {"purchase_percent": 101}}),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_profile(invalid)
        with tempfile.TemporaryDirectory() as directory:
            profiles = Profiles(Path(directory) / "profiles.json")
            with self.assertRaises(ValueError):
                profiles.validate(profile(behaviors={"unknown": {}}))

    def test_buyer_prices_exchange_and_cancels_unpriced_offer_without_llm(self):
        class Shop:
            def __init__(self):
                self.calls = []

            def quote(self, items, percent):
                self.calls.append((items, percent))
                return 80

        shop = Shop()
        registry = BehaviorRegistry()
        buyer = profile()["behaviors"]
        buyer_profile = profile()
        event = {
            "id": 5,
            "bot_id": "merchant_1",
            "type": "exchange.updated",
            "payload": {
                "state": "active",
                "exchange_id": "ex-9",
                "revision": 3,
                "bot_character_id": 90,
                "bot_kamas": 100,
                "items": [{"character_id": 91, "reference": 22, "quantity": 1}],
                "members": [
                    {"character_id": 90, "offered_kamas": 0},
                    {"character_id": 91, "offered_kamas": 0},
                ],
            },
        }
        self.assertEqual(
            registry.decide(buyer_profile, event, shop=shop, llm=None),
            [
                (
                    "exchange.offer_kamas",
                    {"exchange_id": "ex-9", "revision": 3, "amount": 80},
                )
            ],
        )
        self.assertEqual(shop.calls[0][1], 80)
        self.assertEqual(
            registry.decide(
                buyer_profile,
                event,
                shop=type("ExpensiveShop", (), {"quote": lambda *_: 101})(),
                llm=None,
            ),
            [("exchange.cancel", {"exchange_id": "ex-9"})],
        )
        self.assertEqual(
            registry.decide(
                buyer_profile,
                {
                    **event,
                    "payload": {
                        **event["payload"],
                        "items": [
                            {"character_id": 91, "reference": 999, "quantity": 1}
                        ],
                    },
                },
                shop=type("UnknownShop", (), {"quote": lambda *_: None})(),
                llm=None,
            ),
            [("exchange.cancel", {"exchange_id": "ex-9"})],
        )

    def test_worker_replays_exchange_once_and_does_not_call_llm_for_buyer(self):
        with tempfile.TemporaryDirectory() as directory:
            profiles = Profiles(Path(directory) / "profiles.json")
            profiles.put("merchant_1", profile())

            class World:
                def __init__(self):
                    self.calls = []
                    self.pages = 0

                def snapshot(self):
                    return {
                        "world_epoch": "epoch-a",
                        "cursor": 0,
                        "pending_events": [],
                        "bots": [{"bot_id": "merchant_1", "active": True}],
                    }

                def events(self, after):
                    self.pages += 1
                    if after:
                        return {"world_epoch": "epoch-a", "events": [], "cursor": after}
                    return {
                        "world_epoch": "epoch-a",
                        "cursor": 1,
                        "events": [
                            {
                                "id": 1,
                                "bot_id": "merchant_1",
                                "type": "exchange.updated",
                                "payload": {
                                    "state": "active",
                                    "exchange_id": "ex-1",
                                    "revision": 2,
                                    "bot_character_id": 90,
                                    "bot_kamas": 100,
                                    "items": [
                                        {
                                            "character_id": 91,
                                            "reference": 4,
                                            "quantity": 1,
                                        }
                                    ],
                                    "members": [
                                        {"character_id": 90, "offered_kamas": 0},
                                        {"character_id": 91, "offered_kamas": 0},
                                    ],
                                },
                            }
                        ],
                    }

                def command(self, bot_id, action, args, request_id, *, issued_at=None):
                    self.calls.append((bot_id, action, args, request_id))

            class Shop:
                def quote(self, items, percent):
                    return 25

            class ForbiddenLlm:
                def reply(self, *_args):
                    raise AssertionError("buyer must not invoke the LLM")

            world = World()
            worker = Worker(
                profiles,
                world,
                shop=Shop(),
                llm=ForbiddenLlm(),
                state_path=Path(directory) / "state.json",
            )
            worker.tick()
            worker.tick()

        self.assertEqual(len(world.calls), 1)
        self.assertEqual(
            world.calls[0][1:3],
            (
                "exchange.offer_kamas",
                {"exchange_id": "ex-1", "revision": 2, "amount": 25},
            ),
        )
        self.assertEqual(worker.state["cursor"], 1)

    def test_llm_failure_stays_queued_without_blocking_buyer_for_other_bot(self):
        with tempfile.TemporaryDirectory() as directory:
            profiles = Profiles(Path(directory) / "profiles.json")
            profiles.put("merchant_1", profile())
            profiles.put(
                "chat_bot",
                profile(
                    capabilities=("llm",),
                    behaviors={"llm": {"personality": "friendly"}},
                )
                | {"bot_id": "chat_bot"},
            )

            class World:
                def __init__(self):
                    self.calls = []

                def snapshot(self):
                    return {
                        "world_epoch": "epoch-isolated",
                        "cursor": 0,
                        "pending_events": [],
                        "bots": [
                            {"bot_id": "merchant_1", "active": True},
                            {"bot_id": "chat_bot", "active": True},
                        ],
                    }

                def events(self, after):
                    events = (
                        []
                        if after
                        else [
                            {
                                "id": 1,
                                "bot_id": "merchant_1",
                                "type": "exchange.updated",
                                "payload": {
                                    "state": "active",
                                    "exchange_id": "ex-5",
                                    "revision": 4,
                                    "bot_character_id": 90,
                                    "bot_kamas": 100,
                                    "items": [
                                        {
                                            "character_id": 91,
                                            "reference": 4,
                                            "quantity": 1,
                                        }
                                    ],
                                    "members": [
                                        {"character_id": 90, "offered_kamas": 0},
                                        {"character_id": 91, "offered_kamas": 0},
                                    ],
                                },
                            },
                            {
                                "id": 2,
                                "bot_id": "chat_bot",
                                "type": "chat.message",
                                "payload": {
                                    "addressed": True,
                                    "text": "hello",
                                    "channel": "local",
                                },
                            },
                        ]
                    )
                    return {
                        "world_epoch": "epoch-isolated",
                        "events": events,
                        "cursor": 2 if not after else after,
                    }

                def command(self, bot_id, action, args, request_id, *, issued_at=None):
                    self.calls.append((bot_id, action, args))

            class Shop:
                def quote(self, items, percent):
                    return 30

            class FailingLlm:
                def reply(self, *_args):
                    raise ConnectionError("optional provider unavailable")

            world = World()
            worker = Worker(
                profiles,
                world,
                shop=Shop(),
                llm=FailingLlm(),
                state_path=Path(directory) / "state.json",
            )
            worker.tick()

        self.assertEqual(
            [
                (
                    "merchant_1",
                    "exchange.offer_kamas",
                    {"exchange_id": "ex-5", "revision": 4, "amount": 30},
                )
            ],
            world.calls,
        )
        self.assertEqual(2, worker.state["cursor"])
        self.assertEqual(
            ["chat_bot"], [item["event"]["bot_id"] for item in worker.state["pending"]]
        )
        self.assertEqual("ConnectionError", worker.state["pending"][0]["error"])


if __name__ == "__main__":
    unittest.main()
