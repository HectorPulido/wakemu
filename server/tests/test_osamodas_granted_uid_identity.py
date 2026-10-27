"""Invocation's raw object UID cannot alias another owned class spell."""
from copy import deepcopy
import struct
import unittest

import test_combat_spell_transaction as transaction_fixtures
from wakfu_server.combat_cast import decode_cast, resolve_owned_spell_action
from wakfu_server.combat_cast_delivery_source import connected_action_source
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_reconnect_grants import ReconnectGrantProjection
from wakfu_server.combat_remote_effects import (
    RemoteRunningEffect,
    encode_remote_effects,
)
from wakfu_server.combat_spell_grant import NativeSpellGrantHandler, remove_spell_grant
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.spells import encode_deck


class OsamodasGrantedUIDIdentityTests(unittest.TestCase):
    def test_live_removed_replayed_grant_keeps_exact_uid_across_hero_context(self):
        (
            source,
            _,
            fight,
        ) = transaction_fixtures.SpellTransactionTests().native_server_fixture(
            2, 42, full_health=True, native_qi=True, variation_seed=17
        )
        deck = encode_deck([7317])
        # Two selected-main contexts for the same owning account. The cast
        # remains on the actual active Osamodas; its build is never borrowed.
        other = dict(source, id=64, breed=16)
        characters = {7: source, 64: other}
        decks = {7: deck, 64: encode_deck([6907])}
        packets = []
        counter = iter(range(900, 920))
        handler = NativeSpellGrantHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: next(counter),
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
        )

        def grant(reference):
            before = set(getattr(fight, "owned_stat_effects", {}))
            handler(
                dict(
                    effect_class=649,
                    parameters=[2.0, 0.0, 0.0, 0.0, float(reference), 0.0, -1.0, 0.0],
                ),
                [],
                EffectInvocation(326447, 42, 7, 7, fight.actors[7].position),
            )
            added = set(fight.owned_stat_effects) - before
            self.assertEqual(len(added), 1)
            return added.pop(), packets[-1]

        grant_uid, carrier = grant(7348)
        grant(7349)
        grant(7350)

        def resolve(uid, *, main=7, actor_id=7, current=fight):
            request = decode_cast(
                struct.pack(">qqiih", actor_id, uid, *fight.actors[7].position)
            )
            actual, actual_deck = connected_action_source(
                current, characters, decks, main, 3, actor_id
            )
            return resolve_owned_spell_action(request, actual, current, 3, actual_deck)

        for main in (7, 64, 7):
            self.assertEqual(resolve(7348, main=main)[1:], (7348, 42))
            self.assertEqual(resolve((7 << 32) | 7317, main=main)[1:], (7317, 42))
            self.assertEqual(resolve(7349, main=main)[1:], (7349, 42))
            self.assertEqual(resolve(7350, main=main)[1:], (7350, 42))
            for foreign_or_inactive in (
                7317,
                6907,
                (64 << 32) | 6907,
                (64 << 32) | 7317,
                (64 << 32) | 7348,
            ):
                with self.subTest(main=main, uid=foreign_or_inactive):
                    with self.assertRaises(ValueError):
                        resolve(foreign_or_inactive, main=main)
        with self.assertRaises(ValueError):
            resolve(7348, actor_id=-7)
        # Actual reconnect projection consumes the retained649 carrier only
        # for presentation. It cannot replace the authoritative grant identity.
        before = deepcopy(fight.native_spell_grants)
        retained = RemoteRunningEffect(
            649, bytes.fromhex(fight.owned_stat_effects[grant_uid]["payload"]), 42
        )
        encoded = encode_remote_effects((retained,))
        projection = ReconnectGrantProjection([carrier])
        projection.effects(7, encoded)
        projection.verify_complete()
        projection.effects(7, encoded, final=True)
        projection.verify_complete(final=True)
        self.assertEqual(fight.native_spell_grants, before)
        self.assertEqual(resolve(7348, main=64)[1:], (7348, 42))
        self.assertEqual(
            resolve(7348, main=64, current=deepcopy(fight))[1:], (7348, 42)
        )
        remove_spell_grant(handler, grant_uid)
        for main in (7, 64):
            with self.assertRaisesRegex(ValueError, "expired grant"):
                resolve(7348, main=main)
            self.assertEqual(resolve((7 << 32) | 7317, main=main)[1:], (7317, 42))
        grant(7348)
        self.assertEqual(resolve(7348, main=64)[1:], (7348, 42))
        # Corrupted UID/reference aliases must fail rather than silently map
        # an unrelated active spell object into Invocation.
        fight.native_spell_grants[7][7348]["reference"] = 7317
        with self.assertRaisesRegex(ValueError, "temporary spell record"):
            resolve(7348)
