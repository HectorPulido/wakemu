"""The production native oracle executes real class books after eWD transfer."""
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
for path in (ROOT / "server", ROOT / "server/tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import test_combat_spell_transaction as transaction_fixtures
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_server.combat_controller_registry import (
    initialize_controller_registry,
    register_native_controller,
)
from wakfu_server.combat_controller_transfer import (
    NativeControllerTransferHandler,
    remove_controller_runner,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_native_spell_casting import catalog as casting_catalog
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_class_ai_spell import require_class_ai_producer
from wakfu_server.spells import encode_deck


class NativeControllerClassAi207Tests(unittest.TestCase):
    def fixture(self):
        native = transaction_fixtures.SpellTransactionTests()
        character, monster, fight = native.native_server_fixture(
            7, 20, native_qi=True, target_distance=1
        )
        initialize_controller_registry(fight)
        for actor in fight.actors.values():
            register_native_controller(
                fight, actor.id, team=actor.team, controller_id=actor.id
            )
            actor.native_controlled_by_ai = not actor.controlled
        deck = encode_deck([638])
        runtime = RuntimeMessages(fight)
        oracle = NativeOracle(
            runtime,
            characters={7: character},
            monsters={-7: monster},
            decks={7: deck},
            excluded_decks={7: frozenset()},
            viewer_id=7,
            flags={"native_area_callbacks": False, "native_start_events": False},
        )
        factory, adapter = oracle.factory(fight, 1, random.Random(1))
        return runtime, oracle, factory, adapter, character, deck

    def transfer(self, runtime, factory):
        fight = runtime.fight
        # Use the real factory handler, timing and retained/event registration;
        # manually inserting an owned row is not an authoritative application.
        dispatcher, packets = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        handler = dispatcher.handlers[207]
        reference, effect = next(
            (int(ref), effect)
            for ref, effect in factory.effects.items()
            if effect["effect_class"] == 207
            and effect["minimum_level"] <= 20 <= effect["maximum_level"]
        )
        invocation = EffectInvocation(
            reference,
            20,
            -7,
            7,
            fight.actors[7].position,
            native_context_hex="0800100020ffffffffffffffffff0128013000380040004800",
            native_retained_container={"present": False},
        )
        handler(effect, {}, invocation)
        return dispatcher.native_retention, packets

    def test_actual_ordinary_producer_and_npc207_class_cast_then_restore(self):
        runtime, oracle, factory, adapter, character, deck = self.fixture()
        fight = runtime.fight
        actor = fight.actors[7]
        self.assertEqual(
            require_class_ai_producer(fight, actor, factory.displacement_authority),
            (character, deck),
        )
        original = (actor.owner_id, actor.controlled, actor.team)
        handler, packets = self.transfer(runtime, factory)
        self.assertTrue(actor.native_controlled_by_ai)
        self.assertEqual((actor.owner_id, actor.controlled, actor.team), original)
        self.assertEqual(packets[0][0], 12613)
        self.assertEqual(oracle.owned_spells(fight), {638: 20})
        action = dict(
            type="cast",
            spellId=638,
            level=20,
            targetId=-7,
            target=list(fight.actors[-7].position),
        )
        before_ap = actor.ap
        transaction = oracle.cast(runtime, action)
        self.assertEqual(transaction.plan["spell_uid"], (7 << 32) | 638)
        self.assertLess(transaction.fight.actors[7].ap, before_ap)
        self.assertEqual(actor.ap, before_ap)
        # Controller publication is part of the exact transaction source. A
        # changed running UID must reject commit even if player stats match.
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        row = fight.native_controller_action_books[7]
        original_uid = row["running_uid"]
        row["running_uid"] = original_uid + 1
        with self.assertRaisesRegex(ValueError, "Combat changed after preparing"):
            commit_spell_transaction(
                runtime, transaction, stats_serializer=lambda *args: b""
            )
        self.assertEqual(actor.ap, before_ap)
        row["running_uid"] = original_uid
        handler.stat_handler.remove(original_uid)
        handler.synchronize()
        self.assertFalse(actor.native_controlled_by_ai)
        self.assertEqual((actor.owner_id, actor.controlled, actor.team), original)

    def test_production_bridge_accepts_native_ai_player_and_skips_ordinary_player(self):
        from wakfu_ai.bridge.world_host import execute

        runtime, oracle, factory, adapter, character, deck = self.fixture()
        calls = []

        def runner(*args, **kwargs):
            calls.append(args[0].fight.current.id)
            return iter(())

        bindings = {
            "STORE": None,
            "character": character,
            "TEST_MONSTERS_BY_ID": {-7: oracle.monsters[-7]},
        }
        context = {"globals": bindings, "scopes": []}
        list(execute(runtime, context, runner))
        self.assertEqual(calls, [])
        self.transfer(runtime, factory)
        list(execute(runtime, context, runner))
        self.assertEqual(calls, [7])
        self.assertTrue(runtime.fight.current.controlled)

    def test_native_oracle_uses_server_movement_and_server_turn_for_ai_player(self):
        runtime, oracle, factory, adapter, character, deck = self.fixture()
        self.transfer(runtime, factory)
        with patch.object(
            type(runtime.fight),
            "move",
            side_effect=AssertionError("human movement path"),
        ):
            occupied = {a.position for a in runtime.fight.actors.values() if a.hp > 0}
            destination = next(
                dst
                for src, dst in sorted(runtime.fight.edges)
                if src == runtime.fight.current.position and dst not in occupied
            )
            private, packets, _ = oracle.preview(
                runtime, {"type": "move", "path": [list(destination)]}
            )
        self.assertEqual(private.fight.actors[7].position, destination)
        self.assertLess(private.fight.actors[7].mp, runtime.fight.actors[7].mp)
        self.assertTrue(private.fight.actors[7].controlled)
        with patch.object(
            type(runtime), "end_turn", side_effect=AssertionError("human end-turn path")
        ):
            private, packets, _ = oracle.preview(runtime, {"type": "end_turn"})
        self.assertNotEqual(private.fight.current.id, 7)
        self.assertEqual(runtime.fight.current.id, 7)

    def test_owner_thread_turn_commits_actual_class_cast_and_native_end_turn(self):
        from wakfu_ai.native.native_turn import run_turn
        from wakfu_ai.context.native_fingerprint import fingerprint

        runtime, oracle, factory, adapter, character, deck = self.fixture()
        self.transfer(runtime, factory)
        action = dict(
            type="cast",
            spellId=638,
            level=20,
            targetId=-7,
            target=list(runtime.fight.actors[-7].position),
        )
        actions = iter([action, {"type": "end_turn"}])

        class ScriptedPlannerSession:
            # Only external policy selection is scripted; ownership, source
            # guards, native effects, packet staging and adoption remain real.
            def __init__(self, actual_oracle, *args, **kwargs):
                self.oracle = actual_oracle
                self.source = fingerprint(actual_oracle.runtime)
                self.catalog = {}

            def decide(self, **kwargs):
                return {
                    "action": next(actions),
                    "reason": "scripted-policy-for-native-regression",
                }

            def guard(self):
                if fingerprint(self.oracle.runtime) != self.source:
                    raise ValueError("actual native source changed")

        before_ap = runtime.fight.actors[7].ap
        with patch("wakfu_ai.native.native_turn.NativeSession", ScriptedPlannerSession):
            driver = run_turn(
                runtime,
                characters=oracle.characters,
                monsters=oracle.monsters,
                decks=oracle.decks,
                excluded_decks=oracle.excluded_decks,
                viewer_id=7,
                flags=oracle.flags,
                transport=None,
                exporter=None,
                policy={},
                policy_version="regression",
                stats_serializer=lambda *args: b"",
                max_actions=2,
                budget_seconds=60,
            )
            cast_delivery = next(driver)
            self.assertEqual(cast_delivery[1]["action"]["type"], "cast")
            self.assertLess(runtime.fight.actors[7].ap, before_ap)
            end_delivery = next(driver)
            self.assertEqual(end_delivery[1]["action"]["type"], "end_turn")
            with self.assertRaises(StopIteration):
                next(driver)
        self.assertTrue(any(opcode == 12678 for opcode, _ in cast_delivery[0]))
        self.assertNotEqual(runtime.fight.current.id, 7)
        self.assertTrue(runtime.fight.actors[7].controlled)
        self.assertEqual(runtime.fight.actors[7].owner_id, 3)


if __name__ == "__main__":
    unittest.main()
