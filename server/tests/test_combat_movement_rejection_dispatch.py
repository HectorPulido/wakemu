"""Rejected native movement receives an owned authoritative position correction."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import random
import struct
import unittest
from collections import deque

import test_partial_tackle_paid_pipeline as fixtures
from wakfu_server.combat_actor import actual_actor_stats
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import snapshot


class MovementRejectionDispatchTests(unittest.TestCase):
    def test_actual_solo_rejected_partial_departure_corrects_position_before_valid_retry(
        self,
    ):
        fight, characters, decks = fixtures.PartialTacklePaidPipelineTests().fixture()
        runtime = RuntimeMessages(fight)
        origin = fight.current.position
        destination = (-8, -6, -1)
        occupied = {actor.position for actor in fight.actors.values()}
        second = next(
            cell
            for start, cell in sorted(fight.edges)
            if start == destination and cell not in occupied and cell != origin
        )
        rejected_path = (destination, second)
        from wakfu_server.combat_tackle_movement import movement_tackle_cost

        self.assertIn((origin, destination), fight.edges)
        self.assertEqual(fight.current.mp, 3)
        self.assertGreater(
            len(rejected_path)
            + movement_tackle_cost(fight, fight.current, rejected_path)[1],
            3,
        )
        self.assertEqual(
            1 + movement_tackle_cost(fight, fight.current, (destination,))[1], 3
        )
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test)
            == "opcode == 12161 and fight_messages is not None"
        )
        # Retain the original shared continue statement in its native loop;
        # the concrete test selects the solo branch and executes one request.
        loop = ast.For(
            target=ast.Name(id="_request", ctx=ast.Store()),
            iter=ast.Tuple(elts=[ast.Constant(None)], ctx=ast.Load()),
            body=deepcopy(branch.body),
            orelse=[],
        )
        dispatch = compile(
            ast.fix_missing_locations(ast.Module(body=[loop], type_ignores=[])),
            str(source),
            "exec",
        )
        sent, records = [], []

        def stats(actor, current):
            return actual_actor_stats(
                characters[actor.id],
                actor,
                current.id,
                fight=current,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
            )

        def provider(current, **boundary):
            return prepare_area_movement(
                characters[7],
                {},
                current,
                decks[7],
                player_characters=characters,
                deck_blobs=decks,
                rng=random.Random(17),
                **boundary
            )

        import os
        from psycopg import DatabaseError
        from psycopg_pool import PoolTimeout

        lease = SimpleNamespace(current=True, checks=[])

        def current_character_session(account_id, generation, character_id):
            lease.checks.append((account_id, generation, character_id))
            return lease.current and (account_id, generation, character_id) == (
                3,
                "fresh-3",
                7,
            )

        namespace = dict(
            combat_session=None,
            fight_messages=runtime,
            fight=fight,
            account_id=3,
            character=characters[7],
            connection=object(),
            service="world",
            os=os,
            STORE=SimpleNamespace(current_character_session=current_character_session),
            generation="fresh-3",
            DatabaseError=DatabaseError,
            PoolTimeout=PoolTimeout,
            body=struct.pack(">q", 7)
            + b"".join(struct.pack(">iih", *cell) for cell in rejected_path),
            current_combat_stats=lambda actor, current=None: stats(
                actor, runtime.fight if current is None else current
            ),
            area_movement_provider=provider,
            record=lambda **event: records.append(event),
            send=lambda connection, service, opcode, body: sent.append((opcode, body)),
        )
        before = snapshot(fight)
        turn = (fight.turn_id, fight.current.turn_count)
        exec(dispatch, namespace)
        self.assertEqual(records[-1]["event"], "combat_movement_rejected")
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(runtime.action_id, 0)
        self.assertEqual(
            sent,
            [(13887, struct.pack(">iqiih", fight.id, 7, *origin))],
            "Rejected12161 leaves the original native movement input locked without13887",
        )
        self.assertEqual(lease.checks, [(3, "fresh-3", 7)])
        lease.current = False
        sent.clear()
        exec(dispatch, namespace)
        self.assertEqual(records[-1]["event"], "combat_movement_rejected")
        self.assertFalse(sent)
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(runtime.action_id, 0)
        lease.current = True
        # Shorten the same requested route without altering any canonical
        # resource, facing, actor, turn or ACK. TurnBegin cannot rearm this retry.
        self.assertEqual((fight.current.ap, fight.current.mp), (6, 3))
        # This Python retry establishes server behavior only. The original
        # aVk.cbj -> fcK/fcJ callback is qualified separately by the JVM probe.
        namespace["body"] = struct.pack(">qiih", 7, *destination)
        sent.clear()
        exec(dispatch, namespace)
        self.assertEqual(records[-1]["event"], "combat_movement")
        self.assertEqual(
            (fight.current.position, fight.current.ap, fight.current.mp),
            (destination, 5, 0),
        )
        self.assertEqual((fight.turn_id, fight.current.turn_count), turn)
        self.assertIsNone(runtime.awaiting_ack)
        self.assertIn(13624, [opcode for opcode, _ in sent])
        self.assertNotIn(13337, [opcode for opcode, _ in sent])

    def test_shared_correction_is_private_ordered_and_fenced_without_game_mutation(
        self,
    ):
        from wakfu_server.combat_movement_rejection import (
            movement_rejection_packet,
            queue_shared_movement_rejection,
        )
        from wakfu_server.combat_shared import Registry, SharedFight, Session, Batch
        from wakfu_server.combat_reconnect_birth_stage import (
            BirthPresentation,
            PendingBirthPresentation,
        )

        fight, characters, decks = fixtures.PartialTacklePaidPipelineTests().fixture()
        runtime = RuntimeMessages(fight)
        sessions = {
            owner: Session(owner, uid, "fresh-" + str(owner), 1134, 0)
            for uid, owner in ((7, 3), (8, 4), (9, 5))
        }
        live = set(sessions.values())
        registry = Registry(lambda session: session in live)
        shared = SharedFight(fight, 1134, 0, runtime)
        shared.participants = dict(sessions)
        shared.connected = set(sessions)
        shared.outboxes = {owner: deque() for owner in sessions}
        registry.fights[fight.id] = shared
        request = struct.pack(">qiih", 7, -8, -6, -1)
        correction = (
            13887,
            struct.pack(">iqiih", fight.id, 7, *fight.current.position),
        )
        before = snapshot(fight)
        shared.sequence = 4
        shared.outboxes[3].append(Batch(4, (correction,), public_events=False))
        self.assertTrue(
            queue_shared_movement_rejection(registry, sessions[3], fight.id, request)
        )
        self.assertEqual(shared.sequence, 5)
        self.assertEqual([batch.sequence for batch in shared.outboxes[3]], [4, 5])
        self.assertEqual(shared.outboxes[3][-1].packets, (correction,))
        self.assertFalse(shared.outboxes[3][-1].public_events)
        self.assertFalse(shared.outboxes[4])
        self.assertFalse(shared.outboxes[5])
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(runtime.action_id, 0)
        registry.drain(fight.id, sessions[3])

        def rejected(session=sessions[3], body=request):
            sequence = shared.sequence
            self.assertFalse(
                queue_shared_movement_rejection(registry, session, fight.id, body)
            )
            self.assertEqual(shared.sequence, sequence)
            self.assertFalse(shared.outboxes[3])
            self.assertEqual(snapshot(fight), before)

        rejected(body=b"")
        rejected(body=struct.pack(">qiih", 8, -7, -6, -1))
        rejected(session=Session(3, 7, "old-generation", 1134, 0))
        live.remove(sessions[3])
        rejected()
        live.add(sessions[3])
        runtime.awaiting_ack = 17
        rejected()
        runtime.awaiting_ack = None
        runtime.fight = deepcopy(fight)
        rejected()
        runtime.fight = fight
        presentation = BirthPresentation(17, (8,), (), ())
        shared.reconnect_presentations[3] = PendingBirthPresentation.bind(
            sessions[3], presentation
        )
        rejected()
        shared.reconnect_presentations.clear()
        shared.pending_world_recoveries[3] = object()
        rejected()
        shared.pending_world_recoveries.clear()
        shared.pending_publication_recoveries[4] = object()
        rejected()
        shared.pending_publication_recoveries.clear()
        previous = shared.participants[3]
        shared.participants[3] = Session(3, 7, "replacement-generation", 1134, 0)
        rejected()
        shared.participants[3] = previous
        self.assertIsNone(movement_rejection_packet(runtime, 3, request))
        self.assertEqual(
            movement_rejection_packet(runtime, 3, request, session_is_current=True),
            correction,
        )
