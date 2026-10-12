"""Execute actual native selector/NPC preflight and scene consumers without engine."""
import ast, json, random, sys, types, unittest, copy, functools
from pathlib import Path
from unittest.mock import patch

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER / "tools"))
ZERO = {
    "2076": {
        "allow_self": False,
        "cast_criterion_native_present": False,
        "cast_criterion_raw": "",
        "categories": [],
        "conditional": [],
        "costs": [[0, 0, 0]],
        "diagonal": False,
        "forbid_QI_P": False,
        "free_cell": False,
        "levels": [[0, 0, [359771]]],
        "line_of_sight": False,
        "linear": False,
        "linear_path": False,
        "path_option": False,
        "range_modifiable": False,
    },
    "5043": {
        "allow_self": False,
        "cast_criterion_native_present": True,
        "cast_criterion_raw": 'not HasFightProperty("caster", 11) and not IsCarried("caster") and (IsTargetCellFree() or not HasFightProperty("target", 11))',
        "categories": [],
        "conditional": [],
        "costs": [[1, 0, 1]],
        "diagonal": False,
        "forbid_QI_P": False,
        "free_cell": False,
        "levels": [[2, 6, [416704, 417163]]],
        "line_of_sight": False,
        "linear": False,
        "linear_path": False,
        "path_option": False,
        "range_modifiable": True,
    },
}
POS = {
    "5043": {"maximum_level": 2, "levels": [[1, 1, [123]], [2, 2, [456]]]},
    "2076": {"maximum_level": 1, "levels": [[0, 0, [999]]]},
}
EFFECTS = {str(x): {"ref": x} for x in [123, 456, 359771, 416704, 417163]}


def function(path, name, scope):
    node = next(
        n
        for n in ast.parse(
            (
                (SERVER / "wakfu_server/combat" / path)
                if path.startswith("combat_")
                else (SERVER / "tools" / path)
            ).read_text()
        ).body
        if isinstance(n, ast.FunctionDef) and n.name == name
    )
    exec(
        compile(
            ast.Module(body=[node], type_ignores=[]),
            "<actual-canonical-" + name + ">",
            "exec",
        ),
        scope,
    )
    return scope[name]


class RuntimeReached(Exception):
    pass


class NativeZeroConsumers(unittest.TestCase):
    def setup_modules(self, zero):
        modules = {
            name: types.ModuleType(name)
            for name in [
                "wakfu_server.combat_native_spell_casting",
                "wakfu_server.combat_class_initialization",
                "wakfu_server.combat_server_spell",
                "wakfu_server.combat_npc_attack",
                "wakfu_server.combat_npc_activation",
                "wakfu_server.combat_cast",
            ]
        }
        modules[
            "wakfu_server.combat_class_initialization"
        ].level_zero_catalog = lambda: {"casting": zero}
        scope = {"__package__": "wakfu_server", "catalog": lambda: POS}
        table = function(
            "combat_native_spell_casting.py", "native_casting_table", scope
        )
        modules["wakfu_server.combat_native_spell_casting"].native_casting_table = table
        modules["wakfu_server.combat_native_spell_casting"].catalog = lambda: POS
        modules["wakfu_server.combat_native_spell_casting"].definition = lambda *a: None
        modules["wakfu_server.combat_server_spell"].server_runtime = lambda *a, **k: (
            _ for _ in ()
        ).throw(RuntimeReached())
        modules[
            "wakfu_server.combat_npc_attack"
        ].npc_runtime_catalog = lambda **k: types.SimpleNamespace(effects=EFFECTS)
        modules["wakfu_server.combat_npc_attack"].npc_spell_catalog = lambda: {
            "activation_policy": {}
        }
        modules["wakfu_server.combat_npc_activation"].imports_enabled = lambda *a: True
        modules["wakfu_server.combat_cast"]._validate_target = lambda *a: None
        return modules, table

    def test_selector_keeps_exact_zero_cost_range_roots(self):
        modules, table = self.setup_modules(ZERO)
        with patch.dict(sys.modules, modules):
            row, index = table(5043, 0)
            self.assertEqual(index, 0)
            self.assertEqual(row["costs"], [[1, 0, 1]])
            self.assertEqual(row["levels"], [[2, 6, [416704, 417163]]])
            self.assertEqual(table(5043, 2)[1], 1)

    def npc(self, level, zero, effects=EFFECTS):
        modules, _ = self.setup_modules(zero)
        modules[
            "wakfu_server.combat_npc_attack"
        ].npc_runtime_catalog = lambda **k: types.SimpleNamespace(effects=effects)
        scope = {
            "__package__": "wakfu_server",
            "random": random,
            "owned_spells": lambda *a: {5043: level},
        }
        call = function("combat_npc_spell.py", "prepare_npc_spell", scope)
        actor = types.SimpleNamespace(id=-200, effect_stats={4: 6}, effective_level=20)
        fight = types.SimpleNamespace(
            phase="active", current=actor, actors={-200: actor}
        )
        monsters = {-200: {"ref": 2879, "map_id": 1134}}
        action = {
            "type": "cast",
            "spellId": 5043,
            "level": level,
            "target": [-9, -7, -1],
        }
        with patch.dict(sys.modules, modules):
            return call(fight, action, {}, monsters, b"", action_id=1)

    def test_actual_npc_preflight_accepts_zero_and_positive_tables(self):
        for level in [0, 2]:
            with self.subTest(level=level), self.assertRaises(RuntimeReached):
                self.npc(level, ZERO)

    def test_actual_npc_preflight_missing_zero_rejects(self):
        with self.assertRaisesRegex(ValueError, "explicit zero"):
            self.npc(0, {})

    def test_actual_npc_preflight_retains_root_definition_guard(self):
        with self.assertRaisesRegex(ValueError, "Unsupported native NPC effect roots"):
            self.npc(0, ZERO, {})

    def test_both_scene_consumers_zero_and_positive(self):
        modules, _ = self.setup_modules(ZERO)
        modules[
            "wakfu_server.combat_npc_attack"
        ].npc_runtime_catalog = lambda: types.SimpleNamespace(effects=EFFECTS)
        enemy = function(
            "monster_pending_scenarios.py",
            "enemy_search_envelope",
            {"effect_search_envelope": lambda effects, roots, maximum: roots},
        )
        from ally_scene_roots import native_ally_scene_roots

        with patch.dict(sys.modules, modules):
            for level, roots in [(0, [416704, 417163]), (2, [456])]:
                self.assertEqual(enemy(5043, level, 6), roots)
                self.assertEqual(
                    native_ally_scene_roots(5043, level, POS, EFFECTS),
                    [EFFECTS[str(x)] for x in roots],
                )

    def test_both_scene_consumers_missing_zero_fail_closed(self):
        modules, _ = self.setup_modules({})
        enemy = function(
            "monster_pending_scenarios.py",
            "enemy_search_envelope",
            {"effect_search_envelope": lambda *a: None},
        )
        from ally_scene_roots import native_ally_scene_roots

        with patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(ValueError, "explicit zero"):
                enemy(5043, 0, 6)
            with self.assertRaisesRegex(ValueError, "explicit zero"):
                native_ally_scene_roots(5043, 0, POS, EFFECTS)

    def test_positive_array_not_accepted_as_explicit_zero(self):
        modules, table = self.setup_modules({})
        with patch.dict(sys.modules, modules), self.assertRaisesRegex(
            ValueError, "explicit zero"
        ):
            table(5043, 0, zero_casting={"5043": POS["5043"]})


from native_scene_casting import native_scene_casting_row


class CapabilityZero(unittest.TestCase):
    def describe(self, level, zero):
        modules, table = NativeZeroConsumers().setup_modules(zero)
        modules["wakfu_server.combat_static_catalogs"] = types.ModuleType(
            "wakfu_server.combat_static_catalogs"
        )
        modules[
            "wakfu_server.combat_static_catalogs"
        ].characteristic_registry = lambda: {"effects": {}}
        modules[
            "wakfu_server.combat_npc_attack"
        ].npc_runtime_catalog = lambda: types.SimpleNamespace(
            effects={}, source_states={}
        )
        scope = {
            "__package__": "wakfu_server",
            "lru_cache": functools.lru_cache,
            "classify_roots": lambda roots, *a, **k: {
                "tags": ["tested_roots:" + ",".join(map(str, roots))],
                "unknownDependencies": [],
                "conditional": False,
            },
        }
        describe = function("combat_ai_capabilities.py", "describe_spell", scope)
        with patch.dict(sys.modules, modules):
            return describe(5043, level)

    def test_actual_descriptor_uses_zero_range_and_roots(self):
        result = self.describe(0, ZERO)
        self.assertEqual((result["minimum"], result["maximum"]), (2, 6))
        self.assertEqual(result["tags"], ["tested_roots:416704,417163"])
        self.assertEqual(result["unknownDependencies"], [])

    def test_missing_zero_stays_unknown_instead_of_using_positive_table(self):
        result = self.describe(0, {})
        self.assertEqual(result["unknownDependencies"], ["missing_casting_table"])
        self.assertEqual((result["minimum"], result["maximum"]), (0, 0))

    def test_positive_descriptor_keeps_native_index(self):
        # Canonical positive casting table also carries its independent conditions.
        POS["5043"]["conditional"] = []
        self.assertEqual(self.describe(2, {})["tags"], ["tested_roots:456"])


class SceneMaximum(unittest.TestCase):
    def row(self, level, maximum):
        modules, _ = NativeZeroConsumers().setup_modules(ZERO)
        table = copy.deepcopy(POS)
        table["5043"]["maximum_level"] = maximum
        with patch.dict(sys.modules, modules):
            return native_scene_casting_row(5043, level, table)

    def test_invalid_maximum_fails_closed(self):
        for maximum in (None, True, False, 0, -1, 32768, "2", 2.0):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                self.row(1, maximum)

    def test_level_above_metadata_maximum_fails_closed(self):
        with self.assertRaises(ValueError):
            self.row(2, 1)

    def test_bool_level_fails_closed(self):
        with self.assertRaises(ValueError):
            self.row(True, 2)

    def test_valid_positive_and_explicit_zero_remain_exact(self):
        self.assertEqual(self.row(2, 2), [2, 2, [456]])
        self.assertEqual(self.row(0, None), ZERO["5043"]["levels"][0])


if __name__ == "__main__":
    unittest.main()
