"""Lazy module bindings preserve real faW guards and cyclic import orders."""
import itertools
import importlib
import ast
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_fake_fighter as faw
from wakfu_server import combat_fake_fighter_resources as resources
from wakfu_server import combat_fake_fighter_owner_copy as owner_copy
from test_combat_faw_local_parameters import fixture


class DependencyModuleBindingTests(unittest.TestCase):
    def test_repeated_verification_binds_modules_once_but_rechecks_mutable_pa(self):
        row, definition = fixture("hp")
        faw._dependency_module.cache_clear()
        resources._dependency_module.cache_clear()
        with patch.object(
            faw, "import_module", wraps=faw.import_module
        ) as first, patch.object(
            resources, "import_module", wraps=resources.import_module
        ) as second:
            self.assertEqual(
                faw.verified_fake_fighter(row, definition),
                row["native_faw_constructor"],
            )
            calls = first.call_count, second.call_count
            self.assertEqual(calls, (2, 2))
            for _ in range(10):
                faw.verified_fake_fighter(row, definition)
            self.assertEqual((first.call_count, second.call_count), calls)
            row["native_faw_hp_current"] = True
            with self.assertRaisesRegex(ValueError, "HP PA authority"):
                faw.verified_fake_fighter(row, definition)
            self.assertEqual((first.call_count, second.call_count), calls)

    def test_bound_module_reads_current_guard_function_after_each_replacement(self):
        row, definition = fixture("hp")
        faw.verified_fake_fighter(row, definition)
        with patch.object(
            owner_copy,
            "_damage_only_mask_from_parameters",
            side_effect=ValueError("current mask guard"),
        ):
            with self.assertRaisesRegex(ValueError, "current mask guard"):
                faw.verified_fake_fighter(row, definition)
        with patch.object(
            resources,
            "_characteristics_from_plan",
            side_effect=ValueError("current PA guard"),
        ):
            with self.assertRaisesRegex(ValueError, "current PA guard"):
                faw.verified_fake_fighter(row, definition)
        self.assertEqual(
            faw.verified_fake_fighter(row, definition), row["native_faw_constructor"]
        )

    def test_all_canonical_faw_import_orders_remain_cycle_safe_without_catalog(self):
        names = (
            "combat_fake_fighter",
            "combat_fake_fighter_resources",
            "combat_fake_fighter_owner_copy",
        )
        environment = dict(os.environ)
        server = str(Path(__file__).resolve().parents[1])
        environment["PYTHONPATH"] = os.pathsep.join(
            filter(None, (server, environment.get("PYTHONPATH")))
        )
        script = (
            "import importlib,sys; "
            '[importlib.import_module("wakfu_server."+name) for name in sys.argv[1:]]; '
            'assert "wakfu_server.monsters" not in sys.modules; '
            'assert "wakfu_server.combat_actor_snapshot" not in sys.modules'
        )
        for order in itertools.permutations(names):
            with self.subTest(order=order):
                result = subprocess.run(
                    [sys.executable, "-c", script, *order],
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_area_manager_bindings_preserve_current_constructor_and_geometry_guards(
        self,
    ):
        # Use real manager/ledger/constructor code, with only the prototype
        # provider replaced by the existing lightweight faW fixture definition.
        from wakfu_server import native_catalog

        with patch.object(
            native_catalog,
            "load",
            side_effect=AssertionError("No catalog load allowed"),
        ):
            managers = importlib.import_module("wakfu_server.combat_state_managers")
            geometry = importlib.import_module(
                "wakfu_server.combat_effect_area_geometry"
            )
            areas = ModuleType("wakfu_server.combat_effect_area")
            properties = ModuleType("wakfu_server.combat_area_property")
            path = (
                Path(__file__).resolve().parents[1]
                / "wakfu_server/combat/combat_area_property.py"
            )
            function = next(
                node
                for node in ast.parse(path.read_text()).body
                if isinstance(node, ast.FunctionDef) and node.name == "area_properties"
            )
            exec(
                compile(
                    ast.Module(body=[function], type_ignores=[]), str(path), "exec"
                ),
                vars(properties),
            )
            row, definition = fixture("hp")
            definition.update(native_area_properties=[], entry_masks=[])
            row.update(
                uid=901,
                reference=1439,
                cell=(1, 1, 0),
                state_ledger=managers.StateLedger(901),
                native_running_effect_manager=True,
            )
            fight = SimpleNamespace(actors={}, native_effect_areas={901: row})
            areas.native_effect_areas = lambda: {"1439": definition}
            managers._dependency_module.cache_clear()
            self.addCleanup(managers._dependency_module.cache_clear)
            with patch.dict(
                sys.modules, {areas.__name__: areas, properties.__name__: properties}
            ):
                self.assertEqual(
                    managers.registered_area_pv(fight, 901).position, (1, 1, 0)
                )
                row["cell"] = (2, 1, 0)
                self.assertEqual(
                    managers.registered_area_pv(fight, 901).position, (2, 1, 0)
                )
                with patch.object(
                    geometry,
                    "refresh_area_geometry",
                    side_effect=ValueError("current geometry guard"),
                ):
                    with self.assertRaisesRegex(ValueError, "current geometry guard"):
                        managers.registered_area_pv(fight, 901)
                row["native_faw_hp_current"] = True
                with self.assertRaisesRegex(ValueError, "HP PA authority"):
                    managers.registered_area_pv(fight, 901)
