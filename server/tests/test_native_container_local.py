"""UID-local carrier resolution preserves live aliases, scopes and legacy errors."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace, asdict
import json
import sys
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_ledger import StateLedger, RunningState
from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server import combat_native_container as container
from wakfu_server import combat_native_container_query as query
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server.combat_summon_initialization import detached_summon_scope


def state(uid, target=1):
    return RunningState(uid, 1, 1, 1, target, -1, "target", False, (), 0, True, None)


@contextmanager
def no_global_queries():
    forbidden = {
        container.state_managers.__code__,
        container.owned_container_users.__code__,
    }
    calls = []
    previous = sys.getprofile()

    def profile(frame, event, arg):
        if event == "call" and frame.f_code in forbidden:
            calls.append(frame.f_code.co_name)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)
        if calls:
            raise AssertionError("Unexpected global query: " + repr(calls))


class NativeContainerLocalTests(unittest.TestCase):
    def fixture(self):
        actors = [Actor(i, i - 1, (i - 1, 0, 0), 10, 6, 3, 1, 1) for i in (1, 2)]
        return Fight(
            7, actors, {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )

    def assert_current(self, fight, uid):
        with patch.object(query, "live_state_container", return_value=(False, None)):
            expected = container.resolve_state_container(fight, uid)
        with no_global_queries():
            actual = container.resolve_state_container(fight, uid)
        self.assertIs(actual, expected)
        return actual

    def test_current_ledger_replacement_descriptor_refresh_and_scope_are_local(self):
        fight = self.fixture()
        original = state(71)
        actor = fight.actors[1]
        actor.state_ledger._entries = (original,)
        source = OwnedStateSourceRow(uid=80, state_uid=71)
        fight.owned_stat_effects[80] = source
        self.assertIs(self.assert_current(fight, 71), original)
        with no_global_queries():
            container.capture_owned_state_container(fight, 71)
        descriptor = fight.native_owned_state_containers[71]
        old = actor.state_ledger
        actor.state_ledger = StateLedger(1)
        updated = replace(original, level=3)
        actor.state_ledger._entries = (updated,)
        old._entries = (replace(original, uid=72),)
        self.assertIs(self.assert_current(fight, 71), updated)
        with no_global_queries():
            container.capture_owned_state_container(fight, 71)
        self.assertEqual(descriptor["level"], 1)
        self.assertEqual(fight.native_owned_state_containers[71]["level"], 3)
        with container.state_container_scope(fight, {71: updated}):
            actor.state_ledger._entries = ()
            with no_global_queries():
                self.assertIs(container.resolve_state_container(fight, 71), updated)
        with no_global_queries():
            self.assertEqual(
                asdict(container.resolve_state_container(fight, 71)), asdict(updated)
            )
            source["state_uid"] = 72
            self.assertFalse(query.has_owned_container_users(fight, 71))
            self.assertTrue(query.has_owned_container_users(fight, 72))
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            container.resolve_state_container(fight, 71)

    def test_actual_area_and_detached_namespaces_and_duplicate_errors(self):
        from test_detached_membership_scope import authority

        fight = self.fixture()
        row = OwnedAreaRow(
            uid=81,
            cell=(0, 0, 0),
            native_area_contract="faY",
            state_ledger=StateLedger(81),
        )
        row["state_ledger"]._entries = (state(90, 81),)
        fight.native_effect_areas[81] = row
        self.assert_current(fight, 90)
        fight.native_retired_area_managers[81] = fight.native_effect_areas.pop(81)
        self.assert_current(fight, 90)
        summon = Actor(3, 0, (0, 0, 0), 10, 6, 3, 1, 1)
        summon.team = -1
        summon.state_ledger._entries = (state(91, 3),)
        with detached_summon_scope(fight, summon, authority(3)):
            self.assert_current(fight, 91)
        self.assertEqual(query.live_state_container(fight, 91), (True, None))
        fight.actors[1].state_ledger._entries = (state(90),)
        with self.assertRaisesRegex(ValueError, "Missing unique"):
            container.resolve_state_container(fight, 90)
        with patch.object(query, "live_state_container", return_value=(False, None)):
            with self.assertRaisesRegex(ValueError, "Missing unique"):
                container.resolve_state_container(fight, 90)

    def test_clone_codec_and_custom_provider_fallback(self):
        fight = self.fixture()
        fight.actors[1].state_ledger._entries = (state(71),)
        for clone in (
            deepcopy(fight),
            decode_state(json.loads(json.dumps(encode_state(fight)))),
        ):
            self.assert_current(clone, 71)
            clone.actors[1].state_ledger._entries = (state(72),)
            self.assertEqual(query.live_state_container(clone, 71), (True, None))
            self.assert_current(clone, 72)
        calls = []
        actual_managers = container.state_managers

        def custom_managers(current):
            calls.append(current)
            return actual_managers(current)

        with patch.object(container, "state_managers", custom_managers):
            self.assertEqual(query.live_state_container(fight, 71), (False, None))
            self.assertIs(
                container.resolve_state_container(fight, 71),
                fight.actors[1].state_ledger.entries[0],
            )
        self.assertEqual(calls, [fight])


if __name__ == "__main__":
    unittest.main()
