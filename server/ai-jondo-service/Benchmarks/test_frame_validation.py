"""Check that the benchmark invokes the actual host frame-key validator."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "WakIABenchmarks.csproj"
DLL = ROOT / "bin/Release/net8.0/WakIABenchmarks.dll"


class FrameValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run(
            ["dotnet", "build", str(PROJECT), "-c", "Release", "--nologo"],
            check=True,
            capture_output=True,
            text=True,
        )

    def check_frame(self, contents):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "frame.json"
            path.write_text(contents)
            return subprocess.run(
                ["dotnet", str(DLL), "--check-frame", str(path)],
                capture_output=True,
                text=True,
            )

    def test_valid_frame_passes(self):
        result = self.check_frame('{"id":1,"endpoint":"/health","payload":{}}')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_duplicate_key_inside_array_is_rejected(self):
        result = self.check_frame(
            '{"id":1,"endpoint":"/wakia/decide",'
            '"payload":{"board":{"actors":[{"id":7,"id":8}]}}}'
        )
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("Duplicate JSON key", result.stderr)


if __name__ == "__main__":
    unittest.main()
