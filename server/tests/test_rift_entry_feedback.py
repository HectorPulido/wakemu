"""Typed Rift denials preserve exact member details without raw exceptions."""
import unittest

from wakfu_server.player_action_feedback import failure_message
from wakfu_server.rift_entry_feedback import RiftEntryError


class RiftEntryFeedbackTests(unittest.TestCase):
    def test_member_failures_name_the_member_and_explain_recovery(self):
        cases = (
            ("proximity", "lejos", "portal"),
            ("location", "otro mapa", "grupo"),
            ("level", "mínimo 21", "nivel"),
            ("session", "sesión activa", "seleccione"),
        )
        for reason, cause, recovery in cases:
            with self.subTest(reason=reason):
                error = RiftEntryError(
                    reason,
                    "private implementation detail",
                    member={"id": 46, "name": "ELLECHERO"},
                    required_level=21,
                )
                text = failure_message("rift_entry", error)
                self.assertIn("ELLECHERO", text)
                self.assertIn(cause, text)
                self.assertIn(recovery, text)
                self.assertIn("No se ha realizado esta entrada", text)
                self.assertNotIn("private", text)
                self.assertEqual(str(error), "private implementation detail")
        for reason, expected in (
            ("leader", "líder"),
            ("party_changed", "grupo cambió"),
        ):
            self.assertIn(
                expected,
                failure_message("rift_entry", RiftEntryError(reason, "private")),
            )

    def test_unknown_or_wrong_action_does_not_expose_diagnostic_or_fake_attributes(
        self,
    ):
        errors = [
            RiftEntryError("unknown", "private-token"),
            ValueError("private-token"),
        ]
        errors[-1].reason = "proximity"
        errors[-1].member_name = "private-token"
        for error in errors:
            self.assertNotIn("private", failure_message("rift_entry", error))
        self.assertNotIn(
            "ELLECHERO",
            failure_message(
                "inventory_move",
                RiftEntryError(
                    "proximity", "private", member={"id": 46, "name": "ELLECHERO"}
                ),
            ),
        )
        name = "\nELLECHERO\r\x00" + "a" * 100
        error = RiftEntryError("proximity", "private", member={"id": 46, "name": name})
        self.assertEqual(len(error.member_name), 64)
        self.assertTrue(error.member_name.isprintable())
