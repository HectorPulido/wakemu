import unittest
from types import SimpleNamespace
from wakfu_server.request_diagnostics import (
    RequestTrace,
    current_request,
    request_context,
    redact,
    state_summary,
    movement_summary,
)


class RequestDiagnosticsTests(unittest.TestCase):
    def test_correlation_batches_and_closes_once(self):
        batches = []

        def sink(**fields):
            current_request().append(redact({**request_context(), **fields}))

        trace = RequestTrace(
            sink=sink,
            opcode=13260,
            service="game",
            connection_id="diagnostic-only",
            snapshot=lambda: {"hp": 12},
            flush=batches.append,
        )
        sink(event="combat_effect", reference=42)
        trace.rejection("cast_rejected", "token=private")
        self.assertEqual(batches, [])
        trace.finish()
        trace.finish()
        self.assertEqual(len(batches), 1)
        self.assertEqual(len(batches[0]), 3)
        self.assertEqual({row["request_id"] for row in batches[0]}, {trace.id})
        self.assertEqual(batches[0][-1]["status"], "rejected")
        self.assertNotIn("private", str(batches))
        self.assertEqual(request_context(), {})

    def test_invalid_metadata_does_not_interrupt_request(self):
        rows = []

        def broken():
            raise ValueError("password=do-not-log")

        trace = RequestTrace(
            sink=lambda **fields: rows.append(fields),
            opcode=1,
            service="game",
            connection_id="c",
            snapshot=broken,
        )
        trace.finish()
        self.assertEqual(
            rows[-1]["state_after"], {"diagnostic_snapshot_error": "ValueError"}
        )
        self.assertNotIn("do-not-log", str(rows))

    def test_redacts_wire_and_credentials_recursively(self):
        result = redact(
            {
                "generation": "auth",
                "body": b"private",
                "nested": {"access_token": "private"},
                "reason": "authorization=Bearer abc.def password=hunter2",
                "packet": b"secret",
            }
        )
        self.assertNotIn("abc.def", str(result))
        self.assertNotIn("hunter2", str(result))
        self.assertNotIn("private", str(result))
        self.assertEqual(result["packet"]["bytes"], 6)

    def test_large_rift_summary_prioritizes_current_players_and_live_monsters(self):
        def actor(identity, *, controlled=False, hp=0):
            return SimpleNamespace(
                id=identity,
                team=1 if controlled else 0,
                controlled=controlled,
                position=(identity, 1, 0),
                hp=hp,
                ap=6,
                mp=3,
                effect_stats=None,
                state_ledger=SimpleNamespace(entries=[]),
            )

        actors = {identity: actor(identity) for identity in range(-126, 0)}
        actors[-1].hp = 20
        players = set(range(190, 196))
        actors.update(
            {identity: actor(identity, controlled=True, hp=100) for identity in players}
        )
        fight = SimpleNamespace(
            id=397, phase="active", turn_id=309, current=actors[195], actors=actors
        )
        summary = state_summary(None, fight)["fight"]
        retained = [row["id"] for row in summary["actors"]]
        self.assertEqual(
            (132, 68, 64),
            (summary["actor_total"], summary["actors_omitted"], len(retained)),
        )
        self.assertEqual(195, retained[0])
        self.assertEqual(players, set(retained[:6]))
        self.assertEqual(-1, retained[6])
        self.assertEqual([195, 1, 0], summary["actors"][0]["position"])
        self.assertEqual(132, len(fight.actors))
        # A non-player current actor also stays ahead of all controlled actors.
        fight.current = actors[-125]
        retained = [row["id"] for row in state_summary(None, fight)["fight"]["actors"]]
        self.assertEqual(-125, retained[0])
        self.assertTrue(players.issubset(retained))

    def test_movement_summary_bounds_inputs_without_replaying_or_aliasing(self):
        path = [[i, 1, 0] for i in range(100)]
        actor = SimpleNamespace(position=[3, 4, 0], mp=6)
        summary = movement_summary(190, path, actor)
        self.assertEqual(
            (100, 36, 64),
            (
                summary["requested_path_total"],
                summary["requested_path_omitted"],
                len(summary["requested_path"]),
            ),
        )
        self.assertEqual(190, summary["movement_actor_id"])
        self.assertEqual("before_apply", summary["movement_state_stage"])
        self.assertEqual(6, summary["actor_mp"])
        path[0][0] = 999
        actor.position[0] = 999
        self.assertEqual([0, 1, 0], summary["requested_path"][0])
        self.assertEqual([3, 4, 0], summary["actor_position"])
        self.assertNotIn("actor_position", movement_summary(190, []))

    def test_shared_malformed_decoder_rejection_has_no_stale_movement_fields(self):
        import ast
        from copy import deepcopy
        from pathlib import Path
        from unittest.mock import Mock

        source = (
            Path(__file__).resolve().parents[1] / "local_game_server.py"
        ).read_text()
        tree = ast.parse(source)
        branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Try)
            and any(
                isinstance(child, ast.Assign)
                and ast.unparse(child.targets[0])
                == "(movement_actor_id, movement_path)"
                for child in node.body
            )
        )
        branch = deepcopy(branch)
        # Exercise the real decoder failure and rejection logging; transport
        # correction follows unchanged and has separate protocol coverage.
        branch.handlers[0].body = branch.handlers[0].body[:1]
        branch.orelse = []
        branch.finalbody = []
        setup = ast.parse("movement_result = {}").body
        records = []
        namespace = dict(
            decode_request=Mock(
                side_effect=ValueError("Malformed combat movement request")
            ),
            body=b"bad",
            movement_summary=movement_summary,
            combat_session=SimpleNamespace(character_id=190),
            record=lambda **fields: records.append(fields),
        )
        exec(
            compile(
                ast.fix_missing_locations(
                    ast.Module(body=setup + [branch], type_ignores=[])
                ),
                "<movement rejection diagnostics>",
                "exec",
            ),
            namespace,
        )
        self.assertEqual(
            [
                dict(
                    event="combat_movement_rejected",
                    actor_id=190,
                    reason="Malformed combat movement request",
                )
            ],
            records,
        )
        namespace["decode_request"].assert_called_once_with(b"bad")

    def test_actor_state_summary_reports_omissions(self):
        states = [SimpleNamespace(uid=i, reference=42, level=1) for i in range(150)]
        actors = {
            i: SimpleNamespace(
                id=i,
                team=1,
                controlled=True,
                position=(0, 0, 0),
                hp=10,
                ap=6,
                mp=3,
                effect_stats={4: 6},
                state_ledger=SimpleNamespace(entries=states),
            )
            for i in range(80)
        }
        fight = SimpleNamespace(
            id=1, phase="ACTIVE", turn_id=2, current=actors[0], actors=actors
        )
        result = state_summary(None, fight)["fight"]
        self.assertEqual(len(result["actors"]), 64)
        self.assertEqual(result["actors_omitted"], 16)
        self.assertEqual(len(result["actors"][0]["states"]), 128)
        self.assertEqual(result["actors"][0]["states_omitted"], 22)


if __name__ == "__main__":
    unittest.main()
