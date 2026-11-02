"""The exact birth occupied-scan block preserves native lifecycle membership."""
import ast
import inspect
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import rift_npc_creation
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
    unregister_global_fighter,
)
from wakfu_server.combat_trove_long_map import NativeTroveLongMap
from wakfu_server.combat_state import Actor, Fight


def actual_occupied_operation():
    tree = ast.parse(inspect.getsource(rift_npc_creation))
    install = next(
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name == "install_native_wave"
    )
    block = next(
        n
        for n in install.body
        if isinstance(n, ast.If)
        and any(
            isinstance(a, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "occupied" for t in a.targets)
            for a in ast.walk(n)
        )
    )
    function = ast.FunctionDef(
        name="occupied",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="fight")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=[
            *[
                n
                for n in install.body
                if isinstance(n, ast.ImportFrom) and n.module == "combat_state"
            ],
            block,
            ast.Return(ast.Name(id="occupied", ctx=ast.Load())),
        ],
        decorator_list=[],
    )
    namespace = dict(vars(rift_npc_creation))
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
            "<actual-install-native-wave-occupied-block>",
            "exec",
        ),
        namespace,
    )
    return namespace["occupied"]


class RiftOccupiedReadViewTests(unittest.TestCase):
    def fixture(self, quantity):
        player = Actor(7, 0, (0, 0, 0), 100, 6, 6, 10, 10, owner_id=1, controlled=True)
        npcs = [
            Actor(-100 - index, 1, (index + 1, 0, 0), 30, 0, 0, 1, 10)
            for index in range(quantity)
        ]
        cells = {(x, 0, 0) for x in range(quantity + 2)}
        fight = Fight(
            99,
            [player, *npcs],
            cells,
            {0: {player.position}, 1: {a.position for a in npcs}},
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        return fight, player, npcs

    def test_exact_birth_scan_preserves_in_off_out_and_unregistered_history(self):
        occupied = actual_occupied_operation()
        fight, player, npcs = self.fixture(3)
        set_global_fighter_status(fight, npcs[0].id, "OFF_PLAY")
        set_global_fighter_status(fight, npcs[1].id, "OUT_OF_PLAY")
        unregister_global_fighter(fight, npcs[2].id)
        identities = tuple(fight.actors)
        self.assertEqual(occupied(fight), {player.position})
        self.assertEqual(tuple(fight.actors), identities)
        # An original source-status transition can make a corpse active again.
        set_global_fighter_status(fight, npcs[0].id, "IN_PLAY")
        self.assertEqual(occupied(fight), {player.position, npcs[0].position})

    def test_exact_scan_validates_native_map_once_for_two_or_eight_historical_entries(
        self,
    ):
        occupied = actual_occupied_operation()
        counts = []
        original = NativeTroveLongMap.__init__
        for quantity in (2, 8):
            fight, player, npcs = self.fixture(quantity)
            for actor in npcs:
                set_global_fighter_status(fight, actor.id, "OUT_OF_PLAY")
            calls = []

            def counted(instance, *args, **kwargs):
                calls.append(1)
                original(instance, *args, **kwargs)

            with patch.object(NativeTroveLongMap, "__init__", counted):
                self.assertEqual(occupied(fight), {player.position})
            counts.append(len(calls))
        self.assertEqual(counts, [1, 1])

    def test_exact_scan_preserves_corrupt_guard_errors_and_legacy_callback(self):
        occupied = actual_occupied_operation()
        fight, _, _ = self.fixture(2)
        fight.native_global_pv_collections["fighters"]["states"][0] = "bad"
        with self.assertRaisesRegex(
            ValueError, "Invalid persisted native Trove topology"
        ):
            occupied(fight)
        fight, _, _ = self.fixture(2)
        fight.native_global_pv_collections["fighter_status"]["7"] = True
        with self.assertRaisesRegex(ValueError, "Missing actual native fighter status"):
            occupied(fight)
        called = []
        actors = {
            1: SimpleNamespace(id=1, position=(1, 0, 0)),
            2: SimpleNamespace(id=2, position=(2, 0, 0)),
        }

        def legacy(actor):
            called.append(actor.id)
            return actor.id == 2

        self.assertEqual(
            occupied(SimpleNamespace(actors=actors, _in_play=legacy)), {(2, 0, 0)}
        )
        self.assertEqual(called, [1, 2])
        custom, _, _ = self.fixture(2)
        custom.native_global_pv_collections["fighters"]["states"][0] = "bad"
        called.clear()
        custom._in_play = lambda actor: called.append(actor.id) or actor.id == -101
        self.assertEqual(occupied(custom), {custom.actors[-101].position})
        self.assertEqual(called, list(custom.actors))

        class CustomFight(Fight):
            def _in_play(self, actor):
                called.append(actor.id)
                return actor.id == -100

        subclass = object.__new__(CustomFight)
        subclass.__dict__.update(custom.__dict__)
        del subclass.__dict__["_in_play"]
        called.clear()
        self.assertEqual(occupied(subclass), {subclass.actors[-100].position})
        self.assertEqual(called, list(subclass.actors))
