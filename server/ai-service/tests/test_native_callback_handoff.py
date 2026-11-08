"""Focused proof renewal through the real native SDK producer methods."""
from types import SimpleNamespace
import unittest

import test_native_oracle as native_fixtures
from wakfu_ai.bridge.world_sources import bind_private_sources
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_ai.native.native_stats import NativeStats
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
from wakfu_server.combat_retained_gc_authority import (
    certify_ready_runtime,
    native_callbacks_known,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.spells import default_deck


class NativeCallbackHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native_fixtures.NativeOracleTests.setUpClass()

    def runtime_for(self, *, custom_before_bind=False):
        fixture = native_fixtures.NativeOracleTests.wonejo_fixture()
        characters = {fixture.character["id"]: fixture.character}
        monsters = {fixture.monster["id"]: fixture.monster}
        decks = {fixture.character["id"]: default_deck(fixture.character)}
        provider = OwnedExpirationFactory(
            characters=characters,
            monsters=monsters,
            decks=decks,
            actor_id=fixture.character["id"],
            fight_start=True,
            area_callbacks=False,
        )
        serializer = NativeStats(
            characters=characters,
            monsters=monsters,
            fight_id=fixture.fight.id,
            registrations=getattr(fixture.fight, "native_summon_registrations", {}),
        )
        runtime = RuntimeMessages(
            fixture.fight,
            stats_serializer=serializer,
            runtime_stats_serializer=serializer,
            turn_start_provider=provider.turn_start,
            turn_end_provider=provider.turn_end,
            expiration_runtime_factory=provider,
        )
        adapter = CombatSessionAdapter.__new__(CombatSessionAdapter)
        certify_ready_runtime(adapter, runtime, serializer, provider)
        self.assertTrue(native_callbacks_known(runtime), "Ready proof was not issued")
        if custom_before_bind:
            runtime.turn_end_provider = lambda *_args, **_kwargs: ()
            self.assertFalse(native_callbacks_known(runtime))
        session = SimpleNamespace(
            account_id=fixture.character["account_id"],
            character_id=fixture.character["id"],
        )
        bind_private_sources(runtime, session)
        return fixture, runtime, decks

    def test_ready_bind_and_native_commit_keep_only_attested_callback_handoffs(self):
        fixture, runtime, decks = self.runtime_for()
        self.assertTrue(
            native_callbacks_known(runtime), "private source bind lost proof"
        )

        oracle = native_fixtures.NativeOracleTests.oracle_for(
            runtime,
            fixture.character,
            fixture.monster,
            decks[fixture.character["id"]],
        )
        action = dict(
            type="cast",
            spellId=7962,
            level=1,
            targetId=fixture.pc.id,
            target=list(fixture.pc.position),
        )
        oracle.commit(action, stats_serializer=runtime.stats_serializer)
        self.assertTrue(
            native_callbacks_known(runtime), "native commit did not renew proof"
        )

        runtime.turn_start_provider = lambda *_args, **_kwargs: ()
        self.assertFalse(
            native_callbacks_known(runtime), "custom callback retained proof"
        )

    def test_custom_callback_before_private_bind_cannot_be_recaptured_as_native(self):
        _, runtime, _ = self.runtime_for(custom_before_bind=True)
        self.assertFalse(native_callbacks_known(runtime))

        # A later SDK-looking serializer or lifecycle method cannot restore a
        # Ready certificate that was revoked before bind_private_sources.
        runtime.runtime_stats_serializer = runtime.stats_serializer
        self.assertFalse(native_callbacks_known(runtime))


if __name__ == "__main__":
    unittest.main()
