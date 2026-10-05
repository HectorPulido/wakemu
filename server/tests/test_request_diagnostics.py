import unittest
from types import SimpleNamespace
from wakfu_server.request_diagnostics import (
    RequestTrace,
    current_request,
    request_context,
    redact,
    state_summary,
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
