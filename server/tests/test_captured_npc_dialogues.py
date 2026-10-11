"""Native capture ledger controls; no runtime database or client required."""
import base64
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "sniffer" / (name + ".py")
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


recover = module("export_captured_native_npcs").recover
qualify = module("qualify_captured_npc_dialogues").qualify


class CapturedNpcDialogueTests(unittest.TestCase):
    def frame(self, index, direction, opcode, body):
        return dict(
            frame_index=index,
            direction=direction,
            opcode=opcode,
            body_base64=base64.b64encode(body).decode(),
        )

    def spawn(self, identity, x):
        blob = b"\x0b" + struct.pack(">qBqH", identity, 1, -1, 0)
        blob += struct.pack(">hiihqB", 5458, x, 0, 2, 1387, 1)
        return b"\x00\x01" + struct.pack(">BqH", 1, identity, len(blob)) + blob

    def ledger(self):
        identity = -1706442035962340
        frames = [
            self.frame(1, "in", 12608, self.spawn(identity, -12)),
            self.frame(2, "out", 13222, struct.pack(">qq", identity, 1238)),
            self.frame(3, "in", 12969, struct.pack(">ibq", 5764, 2, identity)),
            self.frame(4, "in", 12608, self.spawn(identity, -16)),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frames.jsonl"
            path.write_text("\n".join(json.dumps(frame) for frame in frames))
            return recover(path)

    def native(self):
        return dict(
            speakers=[dict(ref=5458, actions=[dict(id=1238, criteria="")])],
            nodes=[dict(id=5764, criteria="", native_cmT="")],
        )

    def test_dialogue_attaches_to_preceding_spawn_not_future_movement(self):
        result = self.ledger()
        self.assertEqual(result["observed_interactions"][0]["spawn"]["x"], -12)
        first, second = result["actors"]
        self.assertEqual(len(first["observed_dialogue_opens"]), 1)
        self.assertEqual(second["observed_dialogue_opens"], [])
        self.assertEqual(first["frame_index"], 1)

    def test_native_unconditional_action_and_root_qualify_only_observed_scope(self):
        result = qualify(self.ledger(), self.native())
        self.assertEqual(len(result["accepted"]), 1)
        self.assertFalse(result["unconditional_world_activation"])

    def test_conditional_action_root_or_unmatched_speaker_stays_withheld(self):
        for field in ("action", "node", "speaker"):
            capture, native = self.ledger(), self.native()
            if field == "action":
                native["speakers"][0]["actions"][0]["criteria"] = "QuestFlag()"
            elif field == "node":
                native["nodes"][0]["criteria"] = "QuestFlag()"
            else:
                capture["observed_interactions"][0]["actor_matches"] = False
            self.assertEqual(qualify(capture, native)["accepted"], [])

    def test_multiple_observed_roots_for_same_action_fail_closed(self):
        capture = self.ledger()
        other = dict(
            capture["observed_interactions"][0],
            response=dict(node_id=999, speaker_type=2),
        )
        capture["observed_interactions"].append(other)
        self.assertEqual(qualify(capture, self.native())["accepted"], [])
