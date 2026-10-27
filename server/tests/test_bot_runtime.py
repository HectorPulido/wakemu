"""Run bot actions through the headless World runtime with lightweight boundaries."""

import unittest
from contextlib import contextmanager

from wakfu_server.bots.runtime import BotsRuntime
from wakfu_server.bots.bridge import BotConflict


class FakeRepository:
    def __init__(self):
        self.rows = {}

    def create(self, bot_id, args):
        row = {
            "bot_id": bot_id,
            "account_id": 51,
            "character_id": 91,
            "capabilities": args.get("capabilities", []),
        }
        self.rows[bot_id] = row
        return row

    def get(self, bot_id):
        return self.rows[bot_id]

    def list(self):
        return list(self.rows.values())


class FakeStore:
    def __init__(self):
        self.generation = 0
        self.current = None

    @contextmanager
    def connection(self):
        class DB:
            def execute(self, *_args):
                class Result:
                    def fetchall(self):
                        return []

                return Result()

        yield DB()

    def character(self, account_id, character_id):
        return {"id": character_id, "name": "Headless", "breed": 15, "level": 1}

    def begin_session(self, account_id):
        self.generation += 1
        self.current = (account_id, self.generation, 91)
        return self.generation

    def select_character(self, account_id, generation, character_id):
        return {"id": character_id, "name": "Headless", "map_id": 1}

    def current_character_session(self, account_id, generation, character_id):
        return self.current == (account_id, generation, character_id)

    def clear_character(self, account_id, generation):
        pass

    def end_session(self, account_id, generation):
        self.current = None

    def heartbeat(self, account_id, generation):
        return True

    def account_kamas(self, account_id):
        return 900


class FakeWorld:
    def __init__(self):
        self.joins = []
        self.leaves = []
        self.deactivated_ecology = []

    def join(self, generation, peer, character):
        self.joins.append((generation, peer, character))

    def live_identity(self, character_id):
        return self.joins[-1][0], {"id": character_id, "name": "Headless"}

    def deactivate_ecology(self, character_id, generation):
        self.deactivated_ecology.append((character_id, generation))

    def leave(self, character_id, generation):
        self.leaves.append((character_id, generation))


class FakePositions:
    def __init__(self):
        self.attached, self.released, self.flushed = [], [], []

    def attach(self, account_id, generation, character):
        self.attached.append((account_id, generation, character["id"]))

    def release(self, account_id, generation, character_id, **kwargs):
        self.released.append((account_id, generation, character_id, kwargs))

    def flush(self, **kwargs):
        self.flushed.append(kwargs)


class FakeExchanges:
    def __init__(self):
        self.calls = []

    def bot_command(self, action, args, account_id, generation, character_id):
        self.calls.append((action, args, account_id, generation, character_id))
        return {"id": args["exchange_id"], "state": "active", "revision": 4}


class BotRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.store, self.world, self.positions, self.exchanges = (
            FakeStore(),
            FakeWorld(),
            FakePositions(),
            FakeExchanges(),
        )
        self.spoken, self.events = [], []
        self.runtime = BotsRuntime(
            self.store,
            self.world,
            self.exchanges,
            self.positions,
            say=lambda generation, character, text: self.spoken.append(
                (generation, character, text)
            ),
            emit=lambda bot_id, kind, payload: self.events.append(
                (bot_id, kind, payload)
            ),
            repository=FakeRepository(),
            clock=lambda: 100,
        )

    def create(self, capabilities=("chat", "exchange")):
        self.runtime.execute(
            "bot_1",
            "create",
            {
                "name": "Headless",
                "breed": 15,
                "sex": 0,
                "capabilities": list(capabilities),
            },
        )

    def test_headless_chat_exchange_and_deactivation_share_world_lifecycle(self):
        self.create()
        self.runtime.execute("bot_1", "activate", {})
        self.assertEqual(len(self.world.joins), 1)
        self.assertEqual(self.world.deactivated_ecology, [(91, 1)])
        self.assertEqual(
            self.runtime.execute("bot_1", "say", {"text": " hello "}), {"spoken": True}
        )
        self.assertEqual(self.spoken, [(1, {"id": 91, "name": "Headless"}, "hello")])
        result = self.runtime.execute(
            "bot_1",
            "exchange.offer_kamas",
            {"exchange_id": "ex-2", "amount": 10, "revision": 3},
        )
        self.assertEqual(result, {"id": "ex-2", "state": "active", "revision": 4})
        self.assertEqual(self.exchanges.calls[0][1]["revision"], 3)
        self.runtime.execute("bot_1", "deactivate", {})
        self.assertEqual(self.world.leaves, [(91, 1)])
        self.assertEqual(len(self.positions.flushed), 1)
        with self.assertRaises(ValueError):
            self.runtime.execute("bot_1", "say", {"text": "too late"})

    def test_capabilities_and_chat_validation_fail_closed(self):
        self.create(capabilities=("chat",))
        self.runtime.execute("bot_1", "activate", {})
        with self.assertRaises(PermissionError):
            self.runtime.execute("bot_1", "exchange.cancel", {"exchange_id": "ex-1"})
        for text in ("!item 1", "\x00bad", " "):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.runtime.execute("bot_1", "say", {"text": text})

    def test_exchange_outbox_events_are_projected_only_for_current_bot_lease(self):
        self.create()
        self.runtime.execute("bot_1", "activate", {})
        row = {
            "id": 22,
            "exchange_id": "ex-3",
            "revision": 7,
            "character_id": 91,
            "generation": 1,
            "payload": {
                "state": "active",
                "inviter_id": 91,
                "invitee_id": 92,
                "members": [{"character_id": 91, "offered_kamas": 0}],
                "items": [
                    {
                        "character_id": 92,
                        "uid": 99,
                        "unit": {"reference": 4},
                        "quantity": 2,
                    }
                ],
            },
        }
        self.assertTrue(self.runtime.handle_exchange(row))
        self.assertEqual(self.events[0][1], "exchange.updated")
        self.assertEqual(self.events[0][2]["items"][0]["reference"], 4)
        self.assertEqual(self.events[0][2]["bot_kamas"], 900)
        self.assertFalse(self.runtime.handle_exchange({**row, "generation": 999}))

    def test_stale_exchange_revision_is_rejected_without_rewriting_the_offer(self):
        class StaleExchanges(FakeExchanges):
            def bot_command(self, action, args, account_id, generation, character_id):
                raise BotConflict("stale_revision")

        self.runtime.exchanges = StaleExchanges()
        self.create()
        self.runtime.execute("bot_1", "activate", {})
        with self.assertRaisesRegex(BotConflict, "stale_revision"):
            self.runtime.execute(
                "bot_1", "exchange.ready", {"exchange_id": "ex-old", "revision": 2}
            )


if __name__ == "__main__":
    unittest.main()
