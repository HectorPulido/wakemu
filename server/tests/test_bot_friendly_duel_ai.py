"""Friendly bot opt-in reaches the same combat control authority as WakIA."""
import sys
import unittest
import threading
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

BOT_SERVICE_ROOT = Path(__file__).resolve().parents[1] / "bot-service"
if str(BOT_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(BOT_SERVICE_ROOT))

from wakfu_bots.behaviors import BehaviorRegistry
from wakfu_bots.config import validate_profile
from wakfu_server.friendly_duel_runtime import enable_friendly_bot_ai
from wakfu_server.combat_effective_control import (
    effective_input_owner,
    effective_server_controlled,
    require_effective_owner,
)
from wakfu_server.combat_state import Actor
from wakfu_server.combat_controller_registry import (
    initialize_controller_registry,
    register_native_controller,
)
from wakfu_server.bots.friendly_duel import accept
from wakfu_server.friendly_duel_bot_ack import acknowledge_delivered, return_settled


class BotFriendlyDuelAITests(unittest.TestCase):
    def setUp(self):
        self.human = Actor(7, 0, (0, 0, 0), 100, 6, 3, 1, 68)
        self.bot = Actor(8, 1, (2, 0, 0), 100, 6, 3, 1, 68)
        self.fight = SimpleNamespace(actors={7: self.human, 8: self.bot})
        initialize_controller_registry(self.fight)
        register_native_controller(self.fight, 7, team=0, controller_id=7)
        register_native_controller(self.fight, 8, team=1, controller_id=8)
        self.human.controlled = self.bot.controlled = True
        self.human.owner_id, self.bot.owner_id = 101, 202
        self.human.native_controlled_by_ai = self.bot.native_controlled_by_ai = False
        self.participants = (self.human.id, self.bot.id)

    def test_opted_in_duelist_is_server_controlled_without_transferring_human(self):
        enable_friendly_bot_ai(self.fight, self.participants, self.bot.id)
        self.assertTrue(effective_server_controlled(self.fight, self.bot))
        self.assertIsNone(effective_input_owner(self.fight, self.bot))
        with self.assertRaises(ValueError):
            require_effective_owner(self.fight, self.bot, 202)
        self.assertFalse(effective_server_controlled(self.fight, self.human))
        self.assertEqual(effective_input_owner(self.fight, self.human), 101)
        self.assertEqual(self.bot.owner_id, 202)

    def test_other_duels_and_invalid_identities_never_gain_ai_control(self):
        enable_friendly_bot_ai(self.fight, self.participants, None)
        for bad in (999999, True, "2"):
            with self.subTest(bot_id=bad), self.assertRaises(ValueError):
                enable_friendly_bot_ai(self.fight, self.participants, bad)
        self.assertFalse(self.human.native_controlled_by_ai)
        self.assertFalse(self.bot.native_controlled_by_ai)
        self.bot.controlled = False
        with self.assertRaises(ValueError):
            enable_friendly_bot_ai(self.fight, self.participants, self.bot.id)
        self.assertFalse(self.bot.native_controlled_by_ai)

    def test_profile_requires_explicit_friendly_duel_behavior(self):
        base = {
            "bot_id": "tester",
            "character": {"name": "Tester", "breed": 15, "sex": 0},
            "enabled": True,
            "capabilities": [],
            "behaviors": {"announcer": {"text": "hello", "interval_seconds": 60}},
        }
        registry = BehaviorRegistry()
        self.assertNotIn("duel", registry.world_capabilities(validate_profile(base)))
        enabled = dict(base, behaviors={"friendly_duel": {}})
        self.assertEqual(
            registry.world_capabilities(validate_profile(enabled)), ["duel"]
        )
        with self.assertRaises(ValueError):
            validate_profile(
                dict(base, behaviors={"friendly_duel": {"unexpected": True}})
            )

    def test_acceptance_requires_live_lease_and_forwards_native_duel_preparation(self):
        lease = dict(
            bot_id="bot",
            character_id=8,
            account_id=202,
            generation="gen",
            capabilities=["duel"],
        )
        runtime = SimpleNamespace(
            lock=threading.RLock(),
            active={"bot": lease},
            store=object(),
            _lease=lambda _: lease,
        )
        target = SimpleNamespace(character_id=8, account_id=202, generation="gen")
        captured = {}

        def answer(store, session, body, *, prepare_duel, prewarm_duel):
            captured["body"] = body
            return prepare_duel(None, 42, {"auto_lock": False}, {"id": 7}, {"id": 8})

        def prepare(*args, **kwargs):
            captured["kwargs"] = kwargs
            return {"fight": self.fight, "rollback": lambda: None}

        with patch(
            "wakfu_server.friendly_duels.flush_answer_positions"
        ) as flush, patch(
            "wakfu_server.friendly_duels.answer_challenge", side_effect=answer
        ), patch(
            "wakfu_server.friendly_duel_runtime.prepare_and_register",
            side_effect=prepare,
        ):
            result, rollback = accept(runtime, object(), target, 7, lambda **_: None)
            self.assertEqual(result["fight"], self.fight)
            self.assertTrue(callable(rollback))
            self.assertEqual(captured["kwargs"]["ai_bot_character_id"], 8)
            self.assertEqual(
                captured["body"], __import__("struct").pack(">qBB", 7, 1, 0)
            )
            flush.assert_called_once()
            lease["capabilities"] = []
            with self.assertRaisesRegex(ValueError, "not enabled"):
                accept(runtime, object(), target, 7, lambda **_: None)
            lease["capabilities"] = ["duel"]
            target.generation = "stale"
            with self.assertRaisesRegex(ValueError, "not enabled"):
                accept(runtime, object(), target, 7, lambda **_: None)

    def test_only_duel_bot_acknowledges_and_returns_after_settlement(self):
        bot = SimpleNamespace(character_id=8, account_id=202, generation="gen")
        human = SimpleNamespace(character_id=7, account_id=101, generation="human")
        ack = SimpleNamespace(
            turn=3, expected={101: "human", 202: "gen"}, received=set()
        )
        shared = SimpleNamespace(
            is_duel=True,
            join_context={"ai_bot_character_id": 8},
            participants={101: human, 202: bot},
            returned=set(),
            ack=ack,
            fight=SimpleNamespace(id=42),
            lock=threading.RLock(),
            settlement_ready=False,
        )

        class Adapter:
            def acknowledge(self, session, fight_id, body, callback):
                ack.received.add(session.account_id)
                return True

            def mark_returned(self, session, fight_id):
                shared.returned.add(session.account_id)
                return True

        adapter = Adapter()
        self.assertTrue(acknowledge_delivered(adapter, shared))
        self.assertEqual(ack.received, {202})
        self.assertFalse(acknowledge_delivered(adapter, shared))
        self.assertFalse(return_settled(adapter, shared))
        shared.settlement_ready = True
        self.assertTrue(return_settled(adapter, shared))
        self.assertEqual(shared.returned, {202})
        shared.is_duel = False
        self.assertFalse(acknowledge_delivered(adapter, shared))
        self.assertFalse(return_settled(adapter, shared))

    def test_ack_uses_real_registry_and_waits_for_human(self):
        import struct
        from test_combat_shared import SharedCombatTests
        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        fixture = SharedCombatTests()
        fixture.setUp()
        fixture.join()
        shared, registry = fixture.shared, fixture.registry
        shared.is_duel = True
        shared.join_context["ai_bot_character_id"] = fixture.two.character_id
        registry.drain(99, fixture.one)
        registry.drain(99, fixture.two)
        registry.arm_ack(99, 7)
        adapter = object.__new__(CombatSessionAdapter)
        adapter.registry = registry
        self.assertFalse(acknowledge_delivered(adapter, shared))
        self.assertEqual(shared.ack.received, {fixture.two.account_id})
        released = []

        def release(fight, runtime, body):
            released.append(body)
            return [(13482, b"next-turn")]

        self.assertTrue(
            registry.acknowledge(99, fixture.one, struct.pack(">i", 7), release)
        )
        self.assertEqual(released, [struct.pack(">i", 7)])
        self.assertEqual(
            registry.drain(99, fixture.one)[0].packets, ((13482, b"next-turn"),)
        )

    def test_real_duel_registry_ready_and_server_turn_with_scope_fence(self):
        from test_friendly_duels import FriendlyDuelRegistryTests

        fixture = FriendlyDuelRegistryTests()
        fixture.setUp()
        fight, registry = fixture.fight, fixture.registry
        for actor in fight.actors.values():
            actor.native_controlled_by_ai = False
        initialize_controller_registry(fight)
        for actor in fight.actors.values():
            register_native_controller(
                fight, actor.id, team=actor.team, controller_id=actor.id
            )
        shared = registry.register_duel(
            fight,
            (fixture.first, fixture.second),
            join_context={"ai_bot_character_id": fixture.second.character_id},
            initial_packets={1: (), 2: ()},
        )

        def bot_ready(candidate, runtime):
            enable_friendly_bot_ai(candidate, (11, 22), 22)
            candidate.ready(2, True)
            return []

        registry.execute(99, fixture.second, 22, bot_ready, require_turn=False)
        self.assertTrue(shared.fight.actors[22].native_controlled_by_ai)
        self.assertEqual(shared.fight.ready_owners, {2})
        # A bot cannot use the normal player action route once AI was enabled.
        with self.assertRaisesRegex(ValueError, "Foreign/dead"):
            registry.execute(
                99, fixture.second, 22, lambda f, r: [], require_turn=False
            )
        # The other real owner can still ready normally.
        registry.ready(99, fixture.first, True, lambda f, r: [])
        self.assertEqual(shared.fight.phase, "active")
        shared.fight.turn_index = shared.fight.order.index(22)

        def ai_action(candidate, runtime):
            candidate.actors[11].hp -= 1
            return [(12873, b"bot-action")]

        shared.is_duel = False
        with self.assertRaisesRegex(ValueError, "Not current server-controlled"):
            registry.execute_server(
                99, 22, ai_action, expected_sequence=shared.sequence
            )
        shared.is_duel = True
        registry.execute_server(99, 22, ai_action, expected_sequence=shared.sequence)
        self.assertEqual(shared.fight.actors[11].hp, 59)
        self.assertEqual(
            registry.drain(99, fixture.first)[-1].packets, ((12873, b"bot-action"),)
        )


if __name__ == "__main__":
    unittest.main()
