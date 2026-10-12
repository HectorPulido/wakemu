"""Dynamic eWj1070 over actual installed characteristic metadata and setters."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server.combat_characteristic_transfer import (
    attach_transfer,
    detach_transfer,
    transfer_parameters,
)
from wakfu_server.combat_characteristic_transfer_handler import (
    NativeCharacteristicTransferHandler,
    remove_characteristic_transfer,
)
from wakfu_server.combat_character_copy_metadata import native_copy_characteristics
from wakfu_server.combat_stat_handler import StatExecutionContext, _write
from wakfu_server.combat_effect_dispatch import EffectInvocation


class NativeCharacteristicTransferHandlerTests(unittest.TestCase):
    def fixture(self):
        definitions = native_copy_characteristics()["fresh_characteristics"]
        actors = {}
        for identity in (7, 9):
            actors[identity] = SimpleNamespace(
                id=identity,
                initiative=50,
                hp=100,
                ap=6,
                mp=3,
                max_hp=100,
                max_ap=6,
                max_mp=3,
                effect_stats={35: 50, 8: 10, 52: 20},
                effect_minima={
                    s: definitions[str(s)]["hard_minimum"] for s in (35, 8, 52)
                },
                effect_maxima={
                    s: definitions[str(s)]["hard_maximum"] for s in (35, 8, 52)
                },
                effect_frozen=frozenset(),
            )
        fight = SimpleNamespace(
            id=1, actors=actors, phase="active", owned_stat_effects={}
        )
        packets = []
        uids = iter(range(101, 200))
        handler = NativeCharacteristicTransferHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: next(uids),
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
            rng=lambda: 0,
        )
        effect = dict(
            effect_class=1070,
            parameters=[35, 0, 8, 0, 1, 0, 1, 0, 100, 200],
            target_masks=[[] for _ in range(7)],
        )
        invocation = EffectInvocation(164418, 95, 7, 9, (0, 0, 0))
        return fight, handler, packets, effect, invocation

    def test_owned_native_effect_tracks_live_source_and_detaches(self):
        fight, handler, packets, effect, invocation = self.fixture()
        self.assertTrue(handler(effect, [], invocation))
        self.assertEqual(fight.actors[9].effect_stats[8], 60)
        _write(fight, 7, fight.actors[7], 35, 80)
        self.assertEqual(fight.actors[9].effect_stats[8], 90)
        self.assertEqual(fight.actors[7].initiative, 80)
        remove_characteristic_transfer(handler, 101)
        self.assertEqual(fight.actors[9].effect_stats[8], 10)
        self.assertEqual(fight.native_characteristic_transfers, [])
        _write(fight, 7, fight.actors[7], 35, 100)
        self.assertEqual(fight.actors[9].effect_stats[8], 10)
        self.assertEqual([p[0] for p in packets], [13497, 13560])
        with self.assertRaises(KeyError):
            remove_characteristic_transfer(handler, 101)
        self.assertEqual(fight.actors[9].effect_stats[8], 10)

    def test_same_actor_different_pc_supported_same_pc_cycle_rejected(self):
        fight, handler, _, effect, invocation = self.fixture()
        from dataclasses import replace

        self.assertTrue(handler(effect, [], replace(invocation, target_id=7)))
        self.assertEqual(fight.actors[7].effect_stats[8], 60)
        with self.assertRaisesRegex(ValueError, "cycle"):
            attach_transfer(
                fight,
                uid=102,
                source_id=7,
                destination_id=7,
                caster_id=7,
                specification=transfer_parameters([35, 0, 35, 0, 1, 0], 95),
            )
        self.assertEqual(len(fight.native_characteristic_transfers), 1)

    def test_chain_updates_in_native_registration_order_and_cycle_fails_closed(self):
        fight, handler, _, effect, invocation = self.fixture()
        handler(effect, [], invocation)
        attach_transfer(
            fight,
            uid=102,
            source_id=9,
            destination_id=7,
            caster_id=7,
            specification=transfer_parameters([8, 0, 52, 0, 1, 0], 95),
        )
        self.assertEqual(fight.actors[7].effect_stats[52], 80)
        _write(fight, 7, fight.actors[7], 35, 80)
        self.assertEqual(fight.actors[7].effect_stats[52], 110)
        with self.assertRaisesRegex(ValueError, "cycle"):
            attach_transfer(
                fight,
                uid=103,
                source_id=7,
                destination_id=7,
                caster_id=7,
                specification=transfer_parameters([52, 0, 35, 0, 1, 0], 95),
            )

    def test_mixed_existing_eWh_registration_rejected_without_mutation(self):
        fight, handler, packets, effect, invocation = self.fixture()
        fight.native_characteristic_links = {
            4: dict(source_id=7, destination_id=9, source_stat=35, destination_stat=8)
        }
        before = deepcopy(fight.actors)
        with self.assertRaisesRegex(ValueError, "Mixed eWh/eWj"):
            handler(effect, [], invocation)
        self.assertEqual(fight.actors, before)
        self.assertEqual(packets, [])

    def test_eWh_after_eWj_registration_rejected_without_mutation(self):
        from wakfu_server.combat_characteristic_link import (
            NativeCharacteristicLinkHandler,
        )

        fight, handler, packets, effect, invocation = self.fixture()
        handler(effect, [], invocation)
        before = deepcopy(fight)
        packet_count = len(packets)
        other = NativeCharacteristicLinkHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 102,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
        )
        with self.assertRaisesRegex(ValueError, "Mixed eWh/eWj"):
            other(
                dict(effect_class=1038, parameters=[35, 0, 52, 0, 1, 0]), [], invocation
            )
        self.assertEqual(fight, before)
        self.assertEqual(len(packets), packet_count)

    def test_injected_destination_write_failure_stays_on_unpublished_preview(self):
        fight, handler, _, effect, invocation = self.fixture()
        handler(effect, [], invocation)
        before = deepcopy(fight)
        preview = deepcopy(fight)
        original_write = _write

        def failure(f, source, actor, stat, value):
            if actor.id == 9 and stat == 8:
                raise RuntimeError("injected destination serializer boundary")
            return original_write(f, source, actor, stat, value)

        with patch("wakfu_server.combat_stat_handler._write", side_effect=failure):
            with self.assertRaises(RuntimeError):
                _write(preview, 7, preview.actors[7], 35, 80)
        self.assertEqual(fight, before)
        self.assertEqual(fight.native_characteristic_transfers[0]["actual"], 50)

    def test_force_copy_max_then_current_notifies_once_per_native_setter(self):
        from wakfu_server.combat_characteristic_transfer import (
            observed_fixed_assignment,
        )

        fight, handler, _, effect, invocation = self.fixture()
        handler(effect, [], invocation)
        source = fight.actors[7]
        source.effect_base_maxima = {35: source.effect_maxima[35]}
        with patch(
            "wakfu_server.combat_characteristic_transfer.update_transfer",
            wraps=__import__(
                "wakfu_server.combat_characteristic_transfer",
                fromlist=["update_transfer"],
            ).update_transfer,
        ) as refresh:
            observed_fixed_assignment(
                fight,
                source,
                35,
                source_id=7,
                requested=90,
                raw_maximum=200,
                maximum=200,
                maximum_step=True,
            )
        self.assertEqual(refresh.call_count, 2)
        self.assertEqual(fight.actors[9].effect_stats[8], 100)

    def test_nonchanging_current_setter_does_not_notify(self):
        fight, handler, _, effect, invocation = self.fixture()
        handler(effect, [], invocation)
        with patch(
            "wakfu_server.combat_characteristic_transfer.update_transfer"
        ) as refresh:
            _write(fight, 7, fight.actors[7], 35, 50)
        refresh.assert_not_called()


class NativeCharacteristicTransferCommitTests(unittest.TestCase):
    def test_actual_serializer_failure_rolls_back_listener_and_successful_commit_keeps_live_updates(
        self,
    ):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        fixture = SpellTransactionTests()
        fixture.setUp()
        definitions = native_copy_characteristics()["fresh_characteristics"]
        for actor in fixture.fight.actors.values():
            if actor.effect_minima is None:
                actor.effect_minima = {}
            for stat, current in ((35, 50), (8, 10)):
                actor.effect_stats[stat] = current
                actor.effect_minima[stat] = definitions[str(stat)]["hard_minimum"]
                actor.effect_maxima[stat] = definitions[str(stat)]["hard_maximum"]
        fixture.fight.owned_stat_effects = {}
        transaction = fixture.execute()
        preview = transaction.fight
        # Original fixture preparation initializes its optional modifier maps.
        # Capture the durable source preimage, avoiding identity-only geometry
        # authority objects that deepcopy intentionally recreates.
        from wakfu_server.fight_checkpoint_store import snapshot

        before = snapshot(fixture.fight)
        packets = []
        handler = NativeCharacteristicTransferHandler(
            preview,
            packets,
            action_id=1,
            allocate_uid=lambda: 101,
            context=lambda *args: StatExecutionContext(True, True, None, True, None),
            rng=lambda: 0,
        )
        effect = dict(
            effect_class=1070,
            parameters=[35, 0, 8, 0, 1, 0, 1, 0, 100, 200],
            target_masks=[[] for _ in range(7)],
        )
        handler(effect, [], EffectInvocation(164418, 95, 7, -7, (1, 0, 0)))
        _write(preview, 7, preview.actors[7], 35, 80)
        from dataclasses import replace

        transaction = replace(transaction, packets=(*transaction.packets, *packets))
        runtime = RuntimeMessages(fixture.fight)

        def fail(actor, fight):
            if actor.id == -7:
                raise RuntimeError("injected actual serializer failure")
            return b"owned-stats"

        with self.assertRaises(RuntimeError):
            commit_spell_transaction(runtime, transaction, stats_serializer=fail)
        self.assertIs(runtime.fight, fixture.fight)
        self.assertEqual(runtime.action_id, 0)
        self.assertEqual(snapshot(fixture.fight), before)
        commit_spell_transaction(
            runtime, transaction, stats_serializer=lambda *args: b"owned-stats"
        )
        self.assertEqual(runtime.fight.actors[-7].effect_stats[8], 90)
        _write(runtime.fight, 7, runtime.fight.actors[7], 35, 100)
        self.assertEqual(runtime.fight.actors[-7].effect_stats[8], 110)
        self.assertEqual(len(runtime.fight.native_characteristic_transfers), 1)
