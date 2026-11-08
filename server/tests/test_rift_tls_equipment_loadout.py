"""Ordinary QA equipment uses owned item UIDs and native command ordering."""
from pathlib import Path
from types import SimpleNamespace
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import rift_tls_party_e2e as runner


class EquipmentLoadoutTests(unittest.TestCase):
    def test_loadout_commands_verify_owned_sheet_and_reject_changed_uid(self):
        for wrong_uid in (False, True):
            with self.subTest(wrong_uid=wrong_uid):
                commands, waits, queries = [], [], []

                def send(opcode, body):
                    self.assertEqual(opcode, 12366)
                    size = struct.unpack_from(">H", body)[0]
                    self.assertEqual(size, len(body) - 2)
                    commands.append(body[2:].decode())
                    return len(commands)

                def observe(args, query):
                    queries.append(query)
                    self.assertEqual(
                        (query["account_id"], query["character_id"]), (7, 19)
                    )
                    uid = 9000 + query["slot"]
                    if query.get("require_equipped") and wrong_uid:
                        uid += 1
                    return dict(
                        uid=uid,
                        slot=query["slot"],
                        equipped=bool(query.get("require_equipped")),
                        hp=2500,
                        max_hp=4600,
                    )

                peer = SimpleNamespace(
                    send=send,
                    wait=lambda opcode, **kwargs: waits.append((opcode, kwargs)),
                )
                loadout = [
                    runner.equipment_reference(value)
                    for value in ("30291:0", "31545:5", "30304:13")
                ]
                with patch.object(runner, "observe", side_effect=observe):
                    if wrong_uid:
                        with self.assertRaisesRegex(ValueError, "verification failed"):
                            runner.equip_qa_loadout(
                                SimpleNamespace(wave=3),
                                peer,
                                dict(account_id=7, character=dict(id=19)),
                                loadout,
                            )
                    else:
                        result = runner.equip_qa_loadout(
                            SimpleNamespace(wave=3),
                            peer,
                            dict(account_id=7, character=dict(id=19)),
                            loadout,
                        )
                        self.assertEqual(
                            [row["reference"] for row in result], [30291, 31545, 30304]
                        )
                        self.assertEqual(
                            commands,
                            [
                                "!item 30291 1",
                                "!equip 9000 0",
                                "!item 31545 1",
                                "!equip 9005 5",
                                "!item 30304 1",
                                "!equip 9013 13",
                            ],
                        )
                self.assertEqual(len(waits), len(commands))
                self.assertTrue(
                    all(query["operation"] == "equipment" for query in queries)
                )
