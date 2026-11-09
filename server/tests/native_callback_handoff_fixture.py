"""Focused proof renewal through the real native SDK producer methods."""
from types import SimpleNamespace
import unittest

from tests import native_oracle_fixture as native_fixtures
from wakfu_server.wakia_bridge.wakfu_ai.bridge.world_sources import bind_private_sources
from wakfu_server.wakia_bridge.wakfu_ai.native.native_oracle import NativeOracle
from wakfu_server.wakia_bridge.wakfu_ai.native.native_stats import NativeStats
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
