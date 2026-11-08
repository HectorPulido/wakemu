"""Fresh native carrier records match legacy checkpoint/source serialization."""
from dataclasses import asdict, dataclass, fields, replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server import fight_checkpoint_store as store
from wakfu_server.combat_state_ledger import RunningState, StateLedger
from wakfu_server.combat_state_timing import StateTimer
from wakfu_server.combat_geometry_snapshot import source_snapshot


def entry():
    return RunningState(
        19,
        3442,
        1,
        7,
        8,
        3,
        "caster",
        False,
        (123, 456),
        0,
        True,
        StateTimer(7, 3, "start"),
    )


class StatePlainProjectionTests(unittest.TestCase):
    def test_exact_fresh_shape_and_custom_fallback_preserve_source_guards(self):
        native = entry()
        legacy = store._plain(asdict(native))
        with patch.object(store, "asdict", wraps=asdict) as conversion:
            first = store._plain_state_entry(native)
            second = store._plain_state_entry(native)
            self.assertEqual(conversion.call_count, 0)
        self.assertEqual(first, legacy)
        self.assertEqual(list(first), [field.name for field in fields(native)])
        self.assertEqual(
            list(first["timer"]), ["actor_id", "expiration_round", "phase"]
        )
        first["effect_ids"].append(999)
        first["timer"]["expiration_round"] = 9
        self.assertEqual(second, legacy)
        self.assertEqual(native.effect_ids, (123, 456))
        self.assertEqual(native.timer.expiration_round, 3)

        @dataclass(frozen=True)
        class CustomState(RunningState):
            extra: int = 44

        @dataclass(frozen=True)
        class CustomTimer(StateTimer):
            extra: int = 55

        class CustomScalar:
            def __deepcopy__(self, memo):
                return 23

        extra = replace(native)
        object.__setattr__(extra, "extra", [])
        rows = (
            CustomState(**vars(native)),
            replace(native, timer=CustomTimer(7, 3, "start")),
            replace(native, level=CustomScalar()),
            replace(native, level=True),
            replace(native, effect_ids=[1, 2]),
            replace(native, timer=StateTimer(7, 3, 1.5)),
            extra,
        )
        for row in rows:
            with self.subTest(row=type(row).__name__):
                expected = store._plain(asdict(row))
                with patch.object(store, "asdict", wraps=asdict) as conversion:
                    self.assertEqual(store._plain_state_entry(row), expected)
                    self.assertEqual(conversion.call_count, 1)
        ledger = StateLedger(8)
        ledger._entries = (native,)
        fight = SimpleNamespace(id=11, actors={8: SimpleNamespace(state_ledger=ledger)})
        snapshot = store.snapshot(fight)
        source = source_snapshot(fight)
        self.assertEqual(snapshot["actors"]["8"]["state_ledger"]["entries"], [legacy])
        self.assertEqual(source, snapshot)
        ledger._entries = (replace(native, level=2),)
        self.assertNotEqual(source_snapshot(fight), source)
        self.assertEqual(source["actors"]["8"]["state_ledger"]["entries"], [legacy])
