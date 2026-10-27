"""Emergency cancellation sends public marker removal only to World observers."""
import ast
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
import struct
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server.combat_external_markers import _remove_body
from wakfu_server.combat_shared import Session
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.world import World


class EmergencyMarkerCleanupTests(unittest.TestCase):
    def test_actual_emergency_helpers_keep_marker_cleanup_out_of_participant_terminal(
        self,
    ):
        for helper in (
            "emergency_exit_current_combat",
            "abort_waiting_publication_cohort",
        ):
            with self.subTest(helper=helper):
                self.exercise_helper(helper)

    def exercise_helper(self, helper):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        nodes = [
            deepcopy(n)
            for n in ast.walk(tree)
            if isinstance(n, (ast.ClassDef, ast.FunctionDef))
            and n.name
            in (
                "AbortedNativeReturn",
                "emergency_exit_current_combat",
                "abort_waiting_publication_cohort",
            )
        ]
        self.assertEqual(len(nodes), 3)
        for node in nodes:
            if isinstance(node, ast.FunctionDef):
                for index, statement in enumerate(node.body):
                    if isinstance(statement, ast.Nonlocal):
                        node.body[index] = ast.Global(names=statement.names)
        owners = (Session(1, 105, "issuer", 527, 0), Session(2, 108, "peer", 527, 0))
        actors = [
            Actor(105, 0, (0, 0, 0), 41, 6, 3, 100, 30, 1, True),
            Actor(108, 0, (1, 0, 0), 41, 6, 3, 100, 30, 2, True),
            Actor(-200, 1, (2, 0, 0), 41, 6, 3, 100, 30),
        ]
        fight = Fight(
            346,
            actors,
            {a.position for a in actors},
            {0: {a.position for a in actors[:2]}, 1: {actors[2].position}},
        )
        fight.ready(1)
        fight.ready(2)
        runtime = RuntimeMessages(fight)
        shared = SimpleNamespace(
            fight=fight,
            runtime=runtime,
            map_id=527,
            instance_id=0,
            participants={o.account_id: o for o in owners},
            settlement_ready=False,
            group_lease=None,
        )
        delivered = defaultdict(list)
        world = World(
            lambda _: b"",
            lambda _: b"",
            lambda peer, opcode, body: delivered[peer].append((opcode, body)),
        )
        for owner in owners:
            world.join(
                owner.generation,
                owner.account_id,
                dict(id=owner.character_id, map_id=527, instance_id=0),
            )
        world.join("observer", 3, dict(id=999, map_id=527, instance_id=0))
        world.join("elsewhere", 4, dict(id=998, map_id=528, instance_id=0))
        delivered.clear()
        registry = SimpleNamespace(
            lock=threading.RLock(),
            lookup_character=lambda _: shared,
            abort_pending_publication_recovery=lambda *a, **kw: {"exits": {}},
        )
        ns = dict(
            account_id=1,
            generation="issuer",
            character={"id": 105},
            combat_session=None,
            COMBAT_SESSIONS=SimpleNamespace(
                registry=registry, lookup_character=lambda _: shared
            ),
            CHECKPOINT_WRITER=SimpleNamespace(flush_fight=lambda *a, **kw: True),
            EXTERNAL_FIGHT_MARKERS=SimpleNamespace(
                remove=lambda _: (12238, _remove_body(346))
            ),
            WORLD=world,
            STORE=object(),
            COMBAT_GROUPS=None,
            publication_recovery_shared=None,
            deferred_native_combat_attachment=lambda: shared,
            send=Mock(),
            information=lambda text: (674, text),
            connection=None,
            service="world",
        )
        exec(
            compile(
                ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                str(source),
                "exec",
            ),
            ns,
        )
        pending = ns["AbortedNativeReturn"](owners[0], shared)

        def normal_cleanup(*, bootstrap):
            self.assertFalse(bootstrap)
            delivered[1].extend(pending.packets())
            return True

        ns["recover_aborted_publication_cohort"] = normal_cleanup
        ns["continue_aborted_publication_recovery"] = lambda: normal_cleanup(
            bootstrap=False
        )
        # SQL cancellation is already committed at this boundary; it is not
        # reconstructed by this transport test. The helper/World/codec are real.
        with patch(
            "wakfu_server.combat_command_recovery.cancel",
            return_value={"shared": shared, "exits": {}},
        ):
            self.assertTrue(ns[helper]())
        self.assertEqual(delivered[3], [(12238, _remove_body(346))])
        self.assertFalse(delivered[4])
        self.assertFalse(delivered[2])
        terminal = [body for opcode, body in delivered[1] if opcode == 12238]
        self.assertEqual(len(terminal), 1)
        self.assertGreater(len(terminal[0]), 13)
        self.assertEqual(terminal[0][12], 0)
        self.assertNotIn((12238, _remove_body(346)), delivered[1])
        self.assertTrue(pending.callback_flag)
        with self.assertRaisesRegex(ValueError, "foreign native callback flag"):
            pending.acknowledge(struct.pack(">iB", 346, 0))
        pending.acknowledge(struct.pack(">iB", 346, 1))
        self.assertTrue(pending.acknowledged)


if __name__ == "__main__":
    unittest.main(defaultTest="EmergencyMarkerCleanupTests")
