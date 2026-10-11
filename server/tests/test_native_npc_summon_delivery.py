"""NPC forecasts admit registered native births and keep commit atomic."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_geometry_snapshot import source_snapshot
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_spell_transaction import SpellTransaction
from wakfu_server.combat_summon import SummonSpecification
from wakfu_server.combat_summon_codec import summon_application
from wakfu_server.combat_summon_stats import registered_summon_stats
from wakfu_server.combat_tactical_ai import NativeProvider, _validate_added_summons


class NativeNpcSummonDeliveryTests(unittest.TestCase):
    def fixture(self):
        caster = Actor(-200, 1, (0, 0, 0), 40, 6, 3, 10, 1)
        enemy = Actor(7, 0, (1, 0, 0), 60, 6, 3, 20, 1)
        fight = Fight(
            77,
            [caster, enemy],
            {(0, 0, 0), (1, 0, 0), (0, 1, 0)},
            {0: {(1, 0, 0)}, 1: {(0, 0, 0)}},
        )
        candidate = deepcopy(fight)
        actor = Actor(901, 1, (0, 1, 0), 20, 4, 2, 10, 1)
        actor.native_summon_source = dict(
            ref=2612,
            level=1,
            caster_id=-200,
            controller_id=-200,
            native_relation_source="big.new_bje.fdt_initial_registration",
        )
        actor.native_controller_id = -200
        actor.direction = 1
        actor.native_obstacle_id = 5
        actor.native_controlled_by_ai = True
        actor.native_fight_property_counts = {}
        candidate.actors[actor.id] = actor
        candidate.native_summon_registrations = {
            901: dict(
                actor_id=901,
                caster_id=-200,
                controller_id=-200,
                authority=dict(
                    is_summon=True,
                    is_player=False,
                    breed_id=2612,
                    native_real_level=1,
                    native_controller_id=-200,
                ),
            )
        }
        specification = SummonSpecification(2612, 1, False, 1, 1, "caster", 0)
        packet = summon_application(
            77,
            1,
            uid=900,
            base_uid=900,
            effect_reference=96363,
            caster_id=-200,
            cell=actor.position,
            specification=specification,
            actor_id=901,
            obstacle_index=5,
            properties=(),
            timing_payload=b"",
            container_type=1,
            container_id=3799,
        )
        candidate.native_summon_creation_deliveries = {
            901: dict(opcode=packet[0], payload_hex=packet[1].hex())
        }
        candidate.actors[-200].ap -= 3
        transaction = SpellTransaction(
            candidate,
            dict(actor_id=-200),
            0,
            (True,),
            (packet,),
            (),
            source_snapshot(fight),
            1,
        )
        provider = NativeProvider(dict(id=7, map_id=1134), {}, b"")
        action = dict(
            type="cast", spellId=3799, level=1, target=[0, 1, 0], targetId=None
        )
        return fight, transaction, provider, action

    def test_forecast_accepts_native_creation_without_mutating_source(self):
        fight, transaction, provider, action = self.fixture()
        before = source_snapshot(fight)
        with patch(
            "wakfu_server.combat_summon_stats.snapshot_characteristics",
            return_value=b"\x00\x00",
        ), patch(
            "wakfu_server.combat_npc_spell.prepare_npc_spell", return_value=transaction
        ):
            preview = provider.preview(fight, action, 1, forecast=True)
        self.assertIs(preview.fight.actors[901], transaction.fight.actors[901])
        self.assertEqual(source_snapshot(fight), before)
        self.assertNotIn(901, fight.actors)

    def test_commit_preserves_old_actor_identity_and_adopts_native_new_actor(self):
        fight, transaction, provider, action = self.fixture()
        old = dict(fight.actors)
        runtime = RuntimeMessages(fight)
        observed = []

        def serialize(actor, current):
            self.assertIs(current.actors[actor.id], actor)
            observed.append(actor.id)
            return (
                registered_summon_stats(actor, current, 1134)
                if actor.id == 901
                else b"\x00\x00"
            )

        with patch(
            "wakfu_server.combat_summon_stats.snapshot_characteristics",
            return_value=b"\x00\x00",
        ), patch(
            "wakfu_server.combat_npc_spell.prepare_npc_spell", return_value=transaction
        ):
            packets = provider.commit(runtime, action, serialize)
        self.assertIs(runtime.fight, fight)
        for identity, actor in old.items():
            self.assertIs(fight.actors[identity], actor)
        self.assertIs(fight.actors[901], transaction.fight.actors[901])
        self.assertEqual(observed, [-200, 7, 901])
        self.assertIn(transaction.packets[0], packets)
        self.assertEqual(runtime.action_id, 1)

    def test_new_actor_serializer_failure_rolls_back_entire_commit(self):
        fight, transaction, provider, action = self.fixture()
        runtime = RuntimeMessages(fight)
        before = source_snapshot(fight)
        old = dict(fight.actors)

        def serialize(actor, current):
            if actor.id == 901:
                raise ValueError("injected new summon serializer failure")
            return b"\x00\x00"

        with patch(
            "wakfu_server.combat_summon_stats.snapshot_characteristics",
            return_value=b"\x00\x00",
        ), patch(
            "wakfu_server.combat_npc_spell.prepare_npc_spell", return_value=transaction
        ):
            with self.assertRaisesRegex(ValueError, "injected new summon"):
                provider.commit(runtime, action, serialize)
        self.assertEqual(source_snapshot(fight), before)
        self.assertEqual(runtime.action_id, 0)
        self.assertEqual(runtime.pending, [])
        self.assertIsNone(runtime.awaiting_ack)
        for identity, actor in old.items():
            self.assertIs(fight.actors[identity], actor)

    def test_unknown_or_unregistered_added_actor_remains_rejected(self):
        fight, transaction, _, _ = self.fixture()
        transaction.fight.native_summon_registrations.clear()
        with self.assertRaisesRegex(ValueError, "registered native summon"):
            _validate_added_summons(fight, transaction, 1134)

    def test_missing_or_foreign_creation_delivery_remains_rejected(self):
        for change in ("missing", "foreign", "malformed"):
            fight, transaction, _, _ = self.fixture()
            if change == "missing":
                transaction.fight.native_summon_creation_deliveries.clear()
            elif change == "foreign":
                transaction = replace(transaction, packets=())
            else:
                transaction.fight.native_summon_creation_deliveries[901][
                    "payload_hex"
                ] = "invalid"
            with self.subTest(change=change), patch(
                "wakfu_server.combat_summon_stats.snapshot_characteristics",
                return_value=b"\x00\x00",
            ):
                with self.assertRaisesRegex(ValueError, "creation delivery"):
                    _validate_added_summons(fight, transaction, 1134)

    def test_removing_existing_actor_is_still_rejected(self):
        fight, transaction, _, _ = self.fixture()
        del transaction.fight.actors[7]
        with self.assertRaisesRegex(ValueError, "remove existing"):
            _validate_added_summons(fight, transaction, 1134)


if __name__ == "__main__":
    unittest.main()
