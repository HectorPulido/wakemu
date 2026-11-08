"""Synchronous recursive queries must not retain the preview after returning."""
import gc
import unittest
import weakref
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_event_replay import NativeCloneAuthority
from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
from wakfu_server.combat_npc_external_event_scope import qualified_npc_uids


def fight_fixture():
    actor = Actor(1, 0, (0, 0, 0), 10, 6, 3, 1, 1, owner_id=1, controlled=True)
    opponent = Actor(-1, 1, (1, 0, 0), 10, 6, 3, 1, 1)
    return Fight(
        77, [actor, opponent], {(0, 0, 0), (1, 0, 0)}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
    )


class RecursiveQueryLifetimeTests(unittest.TestCase):
    def test_npc_query_releases_preview_on_success_and_post_definition_errors(self):
        def run(failure):
            fight = fight_fixture()
            reference = weakref.ref(fight)
            retention = SimpleNamespace(
                fight=fight, view=lambda: SimpleNamespace(entries=())
            )
            # A minimal valid public qualification boundary: the empty retained
            # view needs no spell catalog or effect execution policy.
            events = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
            events.preview, events.retention = fight, retention
            events.replay = object()
            events.adapter = SimpleNamespace(
                actor_authority=OrdinaryActorAuthority(
                    characters={}, monsters={}, decks={}, excluded_decks={}, catalog={}
                )
            )
            dispatcher = SimpleNamespace(
                native_retention=retention,
                replay_event=events.replay,
                native_clone_authority=NativeCloneAuthority(
                    events.executable, events.conditions
                ),
            )
            if failure == "carriers":
                # This error occurs immediately after creating the recursive
                # helper, before qualification starts.
                fight.native_effect_areas[9] = {}
                fight.native_retired_area_managers[9] = {}
                with self.assertRaisesRegex(ValueError, "both active and retired"):
                    qualified_npc_uids(dispatcher)
            elif failure == "closure":
                calls = 0

                def fail_final(*args, **kwargs):
                    nonlocal calls
                    calls += 1
                    if calls == 1:
                        return frozenset()
                    raise ValueError("closure failure")

                # A plain callable does not retain Mock call arguments or a
                # preconstructed exception traceback containing the preview.
                with patch(
                    "wakfu_server.combat_npc_external_event_scope._source_closure",
                    new=fail_final,
                ):
                    with self.assertRaisesRegex(ValueError, "closure failure"):
                        qualified_npc_uids(dispatcher)
            else:
                self.assertEqual(qualified_npc_uids(dispatcher), frozenset())
            return reference

        enabled = gc.isenabled()
        gc.disable()
        try:
            for failure in (None, "carriers", "closure"):
                reference = run(failure)
                self.assertIsNone(reference(), failure)
        finally:
            if enabled:
                gc.enable()

    def test_pv_owner_releases_preview_after_recursion_shortcut_and_error(self):
        def run(kind):
            fight = fight_fixture()
            reference = weakref.ref(fight)
            adapter = NativeServerRuntimeAdapter.__new__(NativeServerRuntimeAdapter)
            adapter.actor_authority = lambda preview, actor: SimpleNamespace(
                targeting={"is_eGj": True, "dpu_id": actor.id}
            )
            fight.native_retired_area_managers[9] = {"owner_id": 1}
            invocation = SimpleNamespace(target_id=None, cell=(0, 0, 0), caster_id=9)
            if kind == "shortcut":
                invocation.target_id = 1
            elif kind == "cycle":
                fight.native_retired_area_managers[9]["owner_id"] = 9
            if kind == "cycle":
                with self.assertRaisesRegex(ValueError, "canonical PV owner"):
                    adapter._area_identity_query(fight, invocation, "IsOwnArea", False)
            else:
                self.assertFalse(
                    adapter._area_identity_query(fight, invocation, "IsOwnArea", False)
                )
                self.assertFalse(
                    adapter._area_identity_query(
                        fight, invocation, "IsOwnDeposit", False
                    )
                )
            return reference

        enabled = gc.isenabled()
        gc.disable()
        try:
            for kind in ("recursive", "shortcut", "cycle"):
                reference = run(kind)
                self.assertIsNone(reference(), kind)
        finally:
            if enabled:
                gc.enable()
