"""Real Ready/cast/rebind/copy regression for native callback ownership."""
import gc
import unittest
import weakref
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from tests import test_weak_owner_native_handoff as handoff_fixtures
from native_combat_fixture import NativeOracleTests as native_fixtures
from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import (
    NativeOracle,
    native_boundary_owner,
)
from wakfu_server.wakia_bridge.wakfu_ai.bridge.world_sources import bind_private_sources
from wakfu_server.wakia_bridge.wakfu_ai.context.native_fingerprint import fingerprint
from wakfu_server.combat_retained_gc_authority import native_callbacks_known
from wakfu_server.combat_retained_gc_ephemeral import ephemeral_sources_known
from wakfu_server.combat_retained_gc_boundary import (
    _canonical_graph,
    prepare_retired_gc,
)


class CallbackOwnerCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handoff_fixtures.NativeCallbackHandoffTests.setUpClass()

    def prepared_private_clone(self):
        (
            fixture,
            runtime,
            decks,
        ) = handoff_fixtures.NativeCallbackHandoffTests().runtime_for()
        # The casting fixture readies placement but deliberately omits public
        # participant start delivery. Initialize through the production producer
        # before exercising actual start/end lifecycle callbacks.
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_area_boundary import adopt_fight

        initialized, initialization_packets = prepare_server_initialization(
            fixture.character,
            {fixture.monster["id"]: fixture.monster},
            runtime.fight,
            fixture.character["account_id"],
            decks[fixture.character["id"]],
            action_id=runtime.action_id + 1,
            fight_start=True,
            player_characters={fixture.character["id"]: fixture.character},
            deck_blobs=decks,
        )
        adopt_fight(runtime.fight, initialized)
        self.assertTrue(runtime.fight.native_start_event_delivered)
        del initialized, initialization_packets
        oracle = native_fixtures.oracle_for(
            runtime, fixture.character, fixture.monster, decks[fixture.character["id"]]
        )
        original_runtime = weakref.ref(runtime)
        del runtime
        self.assertIsNotNone(original_runtime(), "Planning oracle must own its runtime")
        runtime = oracle.runtime
        # Unknown provider extensions retain their existing strong-owner contract.
        oracle.outcome_features_provider = lambda value: None
        self.assertIs(native_boundary_owner(oracle, runtime), oracle)
        oracle.outcome_features_provider = None
        oracle.commit(
            dict(
                type="cast",
                spellId=7962,
                level=1,
                targetId=fixture.pc.id,
                target=list(fixture.pc.position),
            ),
            stats_serializer=runtime.stats_serializer,
        )
        self.assertTrue(native_callbacks_known(runtime))
        self.assertIsNone(runtime.turn_start_provider.__self__.runtime)
        # Preserve the committed callback-only owner in the private clone.
        clone = deepcopy(runtime)
        self.assertTrue(native_callbacks_known(clone))
        # Ordinary fights intentionally switch back to OwnedExpirationFactory.
        bind_private_sources(
            runtime,
            SimpleNamespace(
                account_id=fixture.character["account_id"],
                character_id=fixture.character["id"],
            ),
        )
        self.assertTrue(native_callbacks_known(runtime))
        self.assertIs(
            runtime.turn_start_provider.__self__, runtime.expiration_runtime_factory
        )
        refs = {
            "runtime": original_runtime,
            "fight": weakref.ref(runtime.fight),
            "oracle": weakref.ref(oracle),
        }
        return clone, refs

    def assert_existing_rift_callback_rebind(self):
        case = handoff_fixtures.NativeCallbackHandoffTests()
        fixture, runtime, decks = case.runtime_for()
        provider = runtime.expiration_runtime_factory
        runtime.fight.rift_monsters = dict(provider.monsters)
        planning = NativeOracle(
            runtime,
            characters=provider.characters,
            monsters=fixture.fight.rift_monsters,
            decks=provider.decks,
            excluded_decks={key: frozenset() for key in provider.decks},
            viewer_id=fixture.character["id"],
            flags={},
        )
        boundary = native_boundary_owner(planning, runtime)
        self.assertIsNone(boundary.runtime)
        runtime.turn_start_provider = boundary.live_start_boundary
        runtime.turn_end_provider = boundary.live_end_boundary
        for callback in (runtime.turn_start_provider, runtime.turn_end_provider):
            self.assertIsNone(callback.__self__.runtime)
            self.assertEqual(
                callback.__self__._native_boundary_fight_id, fixture.fight.id
            )
        self.assertEqual(
            set(provider.monsters),
            set(fixture.fight.rift_monsters),
        )

    def test_real_callback_owner_releases_runtime_and_survives_private_copy(self):
        self.assert_existing_rift_callback_rebind()
        gc.collect()
        previous = gc.isenabled()
        gc.disable()
        try:
            clone, original = self.prepared_private_clone()
            self.assertEqual(
                {name: ref() is not None for name, ref in original.items()},
                {"runtime": False, "fight": False, "oracle": False},
            )
            self.assertTrue(native_callbacks_known(clone))
            source = fingerprint(clone.fight)
            for provider in (clone.turn_start_provider, clone.turn_end_provider):
                result, packets = provider(
                    clone.fight,
                    actor_id=clone.fight.current.id,
                    action_id=clone.action_id + 1,
                )
                self.assertIsNot(result, clone.fight)
                self.assertIsInstance(packets, tuple)
                self.assertEqual(fingerprint(clone.fight), source)
                del result, packets
            del provider
            self.assertTrue(native_callbacks_known(clone))
            probe = deepcopy(clone)
            self.assertTrue(ephemeral_sources_known(probe.fight))
            details = []
            self.assertTrue(_canonical_graph(probe.fight, diagnostic=details), details)
            reasons = []

            def notice(_fight, event, **fields):
                if event == "guard_rejected":
                    reasons.append(fields.get("reason"))

            with patch(
                "wakfu_server.combat_retained_gc_boundary._gc_diagnostic", new=notice
            ):
                prepare_retired_gc(deepcopy(probe.fight), probe.fight, probe, ())
            self.assertEqual(reasons, ["no_ordinary_qi_retirements"])
            # Guard compatibility uses a separate private probe.
            del probe
            refs = {
                "runtime": weakref.ref(clone),
                "fight": weakref.ref(clone.fight),
                "callback_owner": weakref.ref(clone.turn_start_provider.__self__),
            }
            del clone
            self.assertEqual(
                {name: ref() is not None for name, ref in refs.items()},
                {"runtime": False, "fight": False, "callback_owner": False},
            )
        finally:
            gc.collect()
            if previous:
                gc.enable()


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromName(
        "CallbackOwnerCycleTests.test_real_callback_owner_releases_runtime_and_survives_private_copy",
        module=sys.modules[__name__],
    )
    raise SystemExit(
        not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful()
    )
