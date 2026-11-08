"""Immutable carrier values are shared; native ledger transactions stay isolated."""
from copy import deepcopy
from dataclasses import replace
import unittest

from wakfu_server.combat_state_ledger import RunningState, StateLedger
from wakfu_server.combat_state_timing import StateTimer


class ImmutableStateCloneTests(unittest.TestCase):
    def test_native_replacement_isolation_aliases_and_custom_fallback(self):
        entry = RunningState(
            19, 3442, 1, 7, 8, 3, "caster", False, (123, 456), 0, True, None
        )
        timer = StateTimer(7, 3, "start")
        timed = replace(entry, timer=timer)
        ledger = StateLedger(8)
        ledger._entries = (entry,)
        clone, alias, timer_copy, timed_copy = deepcopy((ledger, entry, timer, timed))
        self.assertIsNot(clone, ledger)
        self.assertIs(clone.entries[0], entry)
        self.assertIs(alias, entry)
        self.assertIs(timer_copy, timer)
        self.assertIs(timed_copy, timed)
        clone.bind_registered_timer(entry, timed)
        self.assertIs(ledger.entries[0], entry)
        self.assertIs(clone.entries[0], timed)
        clone.remove(19)
        self.assertEqual(clone.entries, ())
        self.assertEqual(ledger.entries, (entry,))
        # Actual realtime publication also replaces instead of mutating values.
        realtime = replace(entry, realtime_duration=100)
        ledger._entries = (realtime,)
        clone = deepcopy(ledger)
        updated = clone.install_realtime_clock(19, deadline_ms=123456, in_combat=True)
        self.assertIsNot(updated, realtime)
        self.assertIsNone(ledger.entries[0].realtime_deadline_ms)
        self.assertEqual(clone.entries[0].realtime_deadline_ms, 123456)
        # Honor a caller's existing memo mapping for a nested immutable timer.
        alternate = replace(timer, expiration_round=4)
        remapped = deepcopy(timed, {id(timer): alternate})
        self.assertIsNot(remapped, timed)
        self.assertIs(remapped.timer, alternate)
        for original in (
            replace(entry, effect_ids=[123]),
            replace(entry, timer=StateTimer(7, 3, ["start"])),
        ):
            copied = deepcopy(original)
            self.assertIsNot(copied, original)
            self.assertEqual(copied, original)

        class CustomState(RunningState):
            pass

        class CustomTimer(StateTimer):
            pass

        for original in (CustomState(**vars(entry)), CustomTimer(7, 3, "start")):
            copied = deepcopy(original)
            self.assertIs(type(copied), type(original))
            self.assertIsNot(copied, original)
        # Extra attributes and cycles are still ordinary deepcopy graphs.
        for original in (replace(entry), StateTimer(7, 3, "start")):
            object.__setattr__(original, "extra", [original])
            copied, alias = deepcopy((original, original))
            self.assertIsNot(copied, original)
            self.assertIs(copied, alias)
            self.assertIs(copied.extra[0], copied)
            self.assertIsNot(copied.extra, original.extra)
