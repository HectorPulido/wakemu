"""Real NativeOracle commits remain qualified Rift background lifecycle owners."""
import ast
from copy import deepcopy
from pathlib import Path
import socket
import struct
import threading
from types import SimpleNamespace
import unittest

from test_native_oracle import NativeOracleTests
from wakfu_ai.bridge.world_background import BackgroundTurn, admission
from wakfu_ai.bridge.world_sources import bind_private_sources
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_ai.native.native_stats import NativeStats
from wakfu_server.combat_background_work import BackgroundDiagnostics
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_shared import Registry, Session


def retained_outcome_features(runtime):
    return {"fixture_turn": runtime.fight.turn_id}


class RealOracleRiftBackgroundTests(unittest.TestCase):
    def test_real_commit_callbacks_survive_cast_end_ack_and_next_background_prepare(
        self,
    ):
        from wakfu_server.spells import default_deck

        fixture = NativeOracleTests.wonejo_fixture()
        fixture.character["instance_id"] = 77
        fixture.monster["instance_id"] = 77
        fight = fixture.fight
        fight.order, fight.turn_index, fight.turn_id = (
            [fixture.pc.id, fixture.npc.id],
            0,
            1,
        )
        fight.native_start_event_delivered = True
        fixture.pc.turn_count, fixture.npc.turn_count = 1, 0
        fight.rift_monsters = {fixture.npc.id: deepcopy(fixture.monster)}
        fight.rift_wave_state = dict(
            instance_id=77,
            wave=1,
            turn_budget=40,
            wave_actor_ids=[fixture.npc.id],
            current_actor_ids=[fixture.npc.id],
            pending_wave=None,
            staged_receipts=[],
        )
        runtime = RuntimeMessages(fight)
        deck = default_deck(fixture.character)
        provider = OwnedExpirationFactory(
            characters={fixture.pc.id: fixture.character},
            monsters=fight.rift_monsters,
            decks={fixture.pc.id: deck},
            actor_id=fixture.pc.id,
        )
        runtime.expiration_runtime_factory = provider
        runtime.turn_start_provider, runtime.turn_end_provider = (
            provider.turn_start,
            provider.turn_end,
        )
        flags = {
            "native_start_events": True,
            "native_area_callbacks": False,
            "retained_flag_probe": True,
        }
        oracle = NativeOracle(
            runtime,
            characters={fixture.pc.id: fixture.character},
            monsters={fixture.npc.id: fixture.monster},
            decks={fixture.pc.id: deck},
            excluded_decks={fixture.pc.id: frozenset()},
            viewer_id=fixture.pc.id,
            flags=flags,
            outcome_features=retained_outcome_features,
        )
        serializer = NativeStats(
            characters=oracle.characters,
            monsters=oracle.monsters,
            fight_id=fight.id,
            map_id=fixture.character["map_id"],
        )
        first = oracle.commit({"type": "end_turn"}, stats_serializer=serializer)
        self.assertTrue(first)
        self.assertEqual(runtime.awaiting_ack, 1)
        self.assertIs(
            runtime.turn_start_provider.__func__, NativeOracle.live_start_boundary
        )
        self.assertIs(
            runtime.turn_end_provider.__func__, NativeOracle.live_end_boundary
        )
        self.assertTrue(runtime.acknowledge_turn(struct.pack(">i", 1)))
        self.assertIsNone(runtime.awaiting_ack)
        self.assertEqual(runtime.fight.current.id, fixture.npc.id)
        session = Session(
            fixture.character["account_id"],
            fixture.pc.id,
            "real-oracle",
            fixture.character["map_id"],
            77,
        )
        import wakfu_server

        source = (
            Path(wakfu_server.__file__).resolve().parents[1] / "local_game_server.py"
        )
        callback = next(
            node
            for node in ast.walk(ast.parse(source.read_text()))
            if isinstance(node, ast.FunctionDef)
            and node.name == "checkpoint_accepted_rift"
        )
        namespace = {}
        exec(
            compile(ast.Module(body=[callback], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        checkpoint_callback = namespace["checkpoint_accepted_rift"]
        current = deepcopy(runtime)
        original_hp = runtime.fight.actors[fixture.pc.id].hp
        original_ap = runtime.fight.actors[fixture.npc.id].ap
        bind_private_sources(current, session)
        callback_owner = current.turn_start_provider.__self__
        self.assertIs(type(callback_owner), NativeOracle)
        self.assertIs(callback_owner.runtime, current)
        self.assertIs(runtime.turn_start_provider.__self__.runtime, runtime)
        self.assertIs(
            current.turn_start_provider.__self__, current.turn_end_provider.__self__
        )
        self.assertIs(
            callback_owner.outcome_features_provider, retained_outcome_features
        )
        self.assertEqual(callback_owner.flags, flags)
        self.assertEqual(callback_owner.monsters, current.fight.rift_monsters)
        self.assertIsNot(callback_owner, runtime.turn_start_provider.__self__)
        cast_oracle = NativeOracle(
            current,
            characters=callback_owner.characters,
            monsters=callback_owner.monsters,
            decks=callback_owner.decks,
            excluded_decks=callback_owner.excluded_decks,
            viewer_id=callback_owner.viewer_id,
            flags=callback_owner.flags,
            outcome_features=callback_owner.outcome_features_provider,
        )
        packets = cast_oracle.commit(
            dict(
                type="cast",
                spellId=7962,
                level=1,
                targetId=fixture.pc.id,
                target=list(current.fight.actors[fixture.pc.id].position),
            ),
            stats_serializer=current.stats_serializer,
        )
        self.assertTrue(packets)
        self.assertLess(current.fight.actors[fixture.pc.id].hp, original_hp)
        self.assertGreater(current.fight.sequence, runtime.fight.sequence)
        self.assertEqual(runtime.fight.actors[fixture.pc.id].hp, original_hp)
        self.assertEqual(runtime.fight.actors[fixture.npc.id].ap, original_ap)
        bind_private_sources(current, session)
        next_owner = current.turn_end_provider.__self__
        self.assertIs(type(next_owner), NativeOracle)
        self.assertIs(next_owner.runtime, current)
        self.assertEqual(next_owner.flags, flags)
        self.assertEqual(next_owner.monsters, current.fight.rift_monsters)
        end_oracle = NativeOracle(
            current,
            characters=next_owner.characters,
            monsters=next_owner.monsters,
            decks=next_owner.decks,
            excluded_decks=next_owner.excluded_decks,
            viewer_id=next_owner.viewer_id,
            flags=next_owner.flags,
            outcome_features=next_owner.outcome_features_provider,
        )
        ending_turn = current.fight.turn_id
        self.assertTrue(
            end_oracle.commit(
                {"type": "end_turn"}, stats_serializer=current.stats_serializer
            )
        )
        self.assertEqual(current.awaiting_ack, ending_turn)
        self.assertTrue(current.acknowledge_turn(struct.pack(">i", ending_turn)))
        bind_private_sources(current, session)
        self.assertEqual(current.fight.current.id, fixture.pc.id)
        next_owner = current.turn_end_provider.__self__
        player_oracle = NativeOracle(
            current,
            characters=next_owner.characters,
            monsters=next_owner.monsters,
            decks=next_owner.decks,
            excluded_decks=next_owner.excluded_decks,
            viewer_id=next_owner.viewer_id,
            flags=next_owner.flags,
            outcome_features=next_owner.outcome_features_provider,
        )
        ending_turn = current.fight.turn_id
        self.assertTrue(
            player_oracle.commit(
                {"type": "end_turn"}, stats_serializer=current.stats_serializer
            )
        )
        current.acknowledge_turn(struct.pack(">i", ending_turn))
        registry = Registry(lambda member: member is session)
        shared = registry.register(
            current.fight,
            session,
            runtime=current,
            join_context={"rift_accepted_action": checkpoint_callback},
        )
        self.assertIsNone(admission(shared))
        before_hp = shared.fight.actors[fixture.pc.id].hp
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        seen = []

        def blocked_real_candidate(candidate, **kwargs):
            owner = candidate.turn_start_provider.__self__
            seen.append((type(owner), owner.runtime is candidate, dict(owner.flags)))
            entered.set()
            self.assertTrue(release.wait(3))
            if False:
                yield [], {}

        job = BackgroundTurn(
            shared,
            SimpleNamespace(registry=registry),
            session,
            blocked_real_candidate,
            object(),
            fixture.character,
            current.fight.rift_monsters,
            BackgroundDiagnostics(),
        )
        worker = threading.Thread(target=job)
        worker.start()
        self.assertTrue(entered.wait(3))
        left, right = socket.socketpair()
        try:
            right.sendall(b"chat")
            self.assertEqual(left.recv(4), b"chat")
        finally:
            left.close()
            right.close()
        job.cancel()
        release.set()
        worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(seen, [(NativeOracle, True, flags)])
        self.assertEqual(shared.sequence, 0)
        self.assertEqual(shared.fight.actors[fixture.pc.id].hp, before_hp)
        self.assertFalse(getattr(shared, "native_ai_turn_claim", None))
