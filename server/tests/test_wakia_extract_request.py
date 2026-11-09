import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[1] / "tools/wakia_extract_request.py"


class WakIARequestExtractionTests(unittest.TestCase):
    def test_extracts_without_modifying_request_and_refuses_overwrite(self):
        request = {
            "protocol": 1,
            "requestId": "private",
            "source": {"actorId": 987},
            "board": {
                "actors": [{"id": 987}],
                "nativeSupport": {"increaseTo": {"987": 2}},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            source, target = (
                Path(directory) / "source.json",
                Path(directory) / "target.json",
            )
            source.write_text(json.dumps([{"request": request}]))
            command = [
                "python3",
                str(TOOL),
                "--input",
                str(source),
                "--output",
                str(target),
            ]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(target.read_text()), request)
            self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o600)
            self.assertNotEqual(
                subprocess.run(command, capture_output=True).returncode, 0
            )
            self.assertEqual(json.loads(target.read_text()), request)

    def test_invalid_request_never_creates_output(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = (
                Path(directory) / "source.json",
                Path(directory) / "target.json",
            )
            source.write_text('{"request": {"private": "secret"}}')
            result = subprocess.run(
                ["python3", str(TOOL), "--input", str(source), "--output", str(target)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn("secret", result.stderr)
            self.assertFalse(target.exists())

    def test_rejects_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            source, target = (
                Path(directory) / "source.json",
                Path(directory) / "target.json",
            )
            source.write_text(
                '{"protocol":1,"protocol":1,"requestId":"x","source":{},"board":{}}'
            )
            result = subprocess.run(
                ["python3", str(TOOL), "--input", str(source), "--output", str(target)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(target.exists())

    def test_protocol_requires_integer(self):
        for value in (True, 1.0):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                source, target = (
                    Path(directory) / "source.json",
                    Path(directory) / "target.json",
                )
                source.write_text(
                    json.dumps(
                        {"protocol": value, "requestId": "x", "source": {}, "board": {}}
                    )
                )
                result = subprocess.run(
                    [
                        "python3",
                        str(TOOL),
                        "--input",
                        str(source),
                        "--output",
                        str(target),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(target.exists())

    def test_json_pointer_extracts_nested_request_without_leaking_content(self):
        request = {
            "protocol": 1,
            "requestId": "secret-request",
            "source": {"actorId": 987},
            "board": {"actors": [{"id": 987}]},
        }
        with tempfile.TemporaryDirectory() as directory:
            source, target = (
                Path(directory) / "source.json",
                Path(directory) / "target.json",
            )
            source.write_text(
                json.dumps({"result/x": {"~first": [{"request": request}]}})
            )
            base = [
                "python3",
                str(TOOL),
                "--input",
                str(source),
                "--output",
                str(target),
            ]
            result = subprocess.run(
                base + ["--path", "/result~1x/~0first/0"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(target.read_text()), request)
            self.assertEqual(stat.S_IMODE(os.stat(target).st_mode), 0o600)
            target.unlink()
            for pointer in (
                "result",
                "/result~2x",
                "/result~1x/~0first/01",
                "/result~1x/missing",
            ):
                with self.subTest(pointer=pointer):
                    result = subprocess.run(
                        base + ["--path", pointer], capture_output=True, text=True
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("secret-request", result.stdout + result.stderr)
                    self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
