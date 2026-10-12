"""Fresh-process imports must resolve the production spatial transaction module."""
from pathlib import Path
import subprocess
import sys
import unittest


class NativeSpatial937PackagingTests(unittest.TestCase):
    def test_actual_lifecycle_import_has_no_private_prototype_dependency(self):
        server = Path(__file__).resolve().parents[1]
        code = f"""
import sys
sys.path.insert(0, {str(server)!r})
from wakfu_server.combat_pointer_qi_lifecycle import retained_spatial_transaction
from wakfu_server.combat_pointer_qi_transaction import checkpoint, restore
assert checkpoint.__module__ == 'wakfu_server.combat_pointer_qi_transaction'
for name in ('pointer_checkpoint', 'actual_domain_bridge', 'qualified_trove'):
    assert name not in sys.modules, name
"""
        result = subprocess.run(
            [sys.executable, "-I", "-c", code], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
