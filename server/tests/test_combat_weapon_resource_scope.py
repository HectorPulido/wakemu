"""First unarmed requests resolve WP without a prior placement-only branch."""
import ast
import dis
from pathlib import Path
import symtable
from types import CodeType
import unittest


SOURCE = Path(__file__).parents[1] / "local_game_server.py"


class WeaponResourceScopeTests(unittest.TestCase):
    def test_first_shared_weapon_uses_module_wp_reader_not_uninitialized_session_cell(
        self,
    ):
        source = SOURCE.read_text()
        symbols = symtable.symtable(source, str(SOURCE), "exec")
        self.assertTrue(symbols.lookup("live_wp").is_imported())
        session = next(
            child for child in symbols.get_children() if child.get_name() == "session"
        )
        wp = session.lookup("live_wp")
        self.assertTrue(wp.is_global())
        self.assertFalse(wp.is_local())
        self.assertFalse(wp.is_imported())
        weapon = next(
            child
            for child in session.get_children()
            if child.get_name() == "shared_weapon"
        )
        self.assertTrue(weapon.lookup("live_wp").is_global())
        self.assertFalse(weapon.lookup("live_wp").is_free())

        # Compile the actual closure without executing World startup. A local
        # conditional import would emit LOAD_DEREF and make the first request
        # depend on whether an unrelated placement branch had run earlier.
        tree = ast.parse(source)
        session_node = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "session"
        )
        module = compile(
            ast.Module(body=[session_node], type_ignores=[]), str(SOURCE), "exec"
        )
        session_code = next(
            code for code in module.co_consts if isinstance(code, CodeType)
        )
        weapon_code = next(
            code
            for code in session_code.co_consts
            if isinstance(code, CodeType) and code.co_name == "shared_weapon"
        )
        loads = [
            instruction.opname
            for instruction in dis.get_instructions(weapon_code)
            if instruction.argval == "live_wp"
        ]
        self.assertTrue(loads)
        self.assertTrue(all(name.startswith("LOAD_GLOBAL") for name in loads), loads)
        self.assertNotIn("live_wp", session_code.co_cellvars)
