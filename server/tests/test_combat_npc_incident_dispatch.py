"""Common incident dispatch keeps chosen NPC replay summaries payload-free."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wakfu_server.combat_incident_replay import (
    NPC_SCHEMA,
    NPC_RECIPE,
    NPC_PUBLICATION_SCHEMA,
    NPC_PUBLICATION_RECIPE,
    IncidentReplayError,
    read_incident,
    replay_runtime_incident,
    write_incident,
)


class NPCIncidentDispatchTests(unittest.TestCase):
    def receipt(self):
        server = Path(__file__).resolve().parents[1]
        return {
            "schema": NPC_SCHEMA,
            "incident_id": "chosen-npc",
            "before": {"private": "before"},
            "after": {"private": "after"},
            "error": None,
            "identity": {
                "dispatcher_sha256": hashlib.sha256(
                    (server / "local_game_server.py").read_bytes()
                ).hexdigest()
            },
        }

    def test_private_roundtrip_accepts_npc_schema(self):
        receipt = self.receipt()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "incident.json"
            write_incident(path, receipt)
            self.assertEqual(read_incident(path), receipt)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_summary_compares_state_and_error_without_serializing_packets(self):
        receipt = self.receipt()
        outcome = {
            "after": receipt["after"],
            "error": None,
            "packets": ((13420, b"private-packet"),),
            "boundary": "chosen-commit",
        }
        with patch(
            "wakfu_server.combat_npc_reproduction.replay_npc_receipt",
            return_value=outcome,
        ) as replay:
            summary = replay_runtime_incident(receipt, provider_recipe=NPC_RECIPE)
            self.assertTrue(summary["operation_matches"])
            self.assertFalse(summary["shared_delivery_qualified"])
            self.assertNotIn("private", json.dumps(summary))
            replay.assert_called_once_with(receipt)
            outcome["error"] = {"type": "builtins.ValueError", "message": "changed"}
            mismatch = replay_runtime_incident(receipt, provider_recipe=NPC_RECIPE)
            self.assertFalse(mismatch["operation_matches"])

    def test_recipe_drift_and_dispatcher_guards_precede_sdk_execution(self):
        receipt = self.receipt()
        with patch("wakfu_server.combat_npc_reproduction.replay_npc_receipt") as replay:
            for options in (
                {"provider_recipe": "unknown"},
                {"provider_recipe": NPC_RECIPE, "allow_source_drift": True},
            ):
                with self.assertRaises(IncidentReplayError):
                    replay_runtime_incident(receipt, **options)
            receipt["identity"]["dispatcher_sha256"] = "changed"
            with self.assertRaises(IncidentReplayError):
                replay_runtime_incident(receipt, provider_recipe=NPC_RECIPE)
            replay.assert_not_called()

    def test_common_summary_preserves_domain_aliases_and_packet_values(self):
        from wakfu_server.combat_reproduction_state import encode_state

        scalar = "runtime scalar key " * 5
        equal_scalar = "".join((scalar, ""))
        self.assertEqual(scalar, equal_scalar)
        self.assertIsNot(scalar, equal_scalar)
        domain = [b"native-packet"]
        expected = encode_state([scalar, scalar, domain, domain], preserve_scalars=True)
        actual = encode_state(
            [scalar, equal_scalar, domain, domain], preserve_scalars=True
        )
        self.assertNotEqual(expected, actual)
        receipt = self.receipt()
        receipt["after"] = expected
        outcome = {"after": actual, "error": None, "boundary": "chosen-commit"}
        with patch(
            "wakfu_server.combat_npc_reproduction.replay_npc_receipt",
            return_value=outcome,
        ):
            result = replay_runtime_incident(receipt, provider_recipe=NPC_RECIPE)
            self.assertTrue(result["operation_matches"])
            self.assertEqual(result["expected_sha256"], result["actual_sha256"])
            self.assertEqual(
                result["state_comparison"],
                "exact-domain-graph-with-immutable-scalar-values-v1",
            )
            for corrupted in (
                [scalar, equal_scalar, domain, list(domain)],
                [scalar, equal_scalar, [b"changed-packet"], domain],
            ):
                outcome["after"] = encode_state(corrupted, preserve_scalars=True)
                self.assertFalse(
                    replay_runtime_incident(receipt, provider_recipe=NPC_RECIPE)[
                        "operation_matches"
                    ]
                )

    def test_publication_summary_compares_typed_return_and_private_transition(self):
        receipt = self.receipt()
        receipt.update(
            schema=NPC_PUBLICATION_SCHEMA,
            return_value=1,
            return_recorded=True,
            transition={"private": "transition"},
        )
        outcome = {
            "after": receipt["after"],
            "error": None,
            "return_value": 1,
            "transition": receipt["transition"],
            "boundary": "server-mailboxes",
        }
        with patch(
            "wakfu_server.combat_npc_publication.replay_npc_publication",
            return_value=outcome,
        ):
            result = replay_runtime_incident(
                receipt, provider_recipe=NPC_PUBLICATION_RECIPE
            )
            self.assertTrue(result["operation_matches"])
            self.assertTrue(result["mailbox_matches"])
            self.assertFalse(result["shared_delivery_qualified"])
            self.assertNotIn("private", json.dumps(result))
            receipt["return_value"] = True  # bool must not compare equal to integer 1.
            result = replay_runtime_incident(
                receipt, provider_recipe=NPC_PUBLICATION_RECIPE
            )
            self.assertFalse(result["operation_matches"])

    def test_publication_recipe_and_delivery_boundaries_are_explicit(self):
        receipt = self.receipt()
        receipt["schema"] = NPC_PUBLICATION_SCHEMA
        with patch(
            "wakfu_server.combat_npc_publication.replay_npc_publication"
        ) as replay:
            for options in (
                {"provider_recipe": NPC_RECIPE},
                {"provider_recipe": NPC_PUBLICATION_RECIPE, "allow_source_drift": True},
                {
                    "provider_recipe": NPC_PUBLICATION_RECIPE,
                    "evidence_sink": lambda state: None,
                },
            ):
                with self.assertRaises(IncidentReplayError):
                    replay_runtime_incident(receipt, **options)
            replay.assert_not_called()


if __name__ == "__main__":
    unittest.main()
