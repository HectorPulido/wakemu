"""General admitted-cast policy, native exceptions, wire order and authority."""
from copy import deepcopy
from dataclasses import replace
from random import Random
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_cast_facing import (
    begin_cast_facing,
    finish_mirrored_cast_facing,
    native_cast_facing,
)
from wakfu_server.combat_orientation import decode_request, facing_response, response
from wakfu_server.combat_effect_removal import _identity_fields


class CastFacingPolicyTests(unittest.TestCase):
    def actor(self):
        actor = SimpleNamespace(id=7, position=(0, 0, 0), direction=7)
        return SimpleNamespace(id=10, actors={7: actor}), actor

    def test_missing_and_pending_contracts_face_before_animation(self):
        for contracts in ({}, {"999": {"status": "pending"}}):
            fight, actor = self.actor()
            packets = begin_cast_facing(
                actor,
                {"spell_id": 999, "target": (2, 0, 0)},
                fight=fight,
                action_id=3,
                contracts=contracts,
            )
            self.assertEqual(actor.direction, 1)
            self.assertEqual([op for op, _ in packets], [13494, 13420])
            self.assertEqual(struct.unpack(">iiiqB", packets[0][1]), (10, 3, -1, 7, 1))
            self.assertEqual(packets[1][1], struct.pack(">i", 10))

    def test_literal_no_turn_and_diagonal_are_honored_even_when_pending(self):
        fight, actor = self.actor()
        plan = {"spell_id": 999, "target": (1, -1, 0)}
        contracts = {"999": {"status": "pending", "turnCasterTowardTargetCell": False}}
        self.assertEqual(
            begin_cast_facing(
                actor, plan, fight=fight, action_id=3, contracts=contracts
            ),
            (),
        )
        self.assertEqual(actor.direction, 7)
        contracts["999"] = {"status": "pending", "useDiags": True}
        packets = begin_cast_facing(
            actor, plan, fight=fight, action_id=3, contracts=contracts
        )
        self.assertEqual(actor.direction, 0)
        self.assertEqual(packets[0][1][-1], 0)

    def test_same_xy_weapon_and_spell_preserve_direction_without_wire(self):
        for plan in ({"spell_id": 999, "target": (0, 0, 9)}, {"target": (0, 0, -5)}):
            fight, actor = self.actor()
            self.assertEqual(
                begin_cast_facing(actor, plan, fight=fight, action_id=3, contracts={}),
                (),
            )
            self.assertEqual(actor.direction, 7)

    def test_native_cast_wire_allows_diagonals_but_voluntary_request_stays_cardinal(
        self,
    ):
        for direction in range(8):
            self.assertEqual(facing_response(10, 3, 7, direction)[1][-1], direction)
        for direction in (0, 2, 4, 6):
            with self.assertRaises(ValueError):
                response(10, 3, 7, direction)
            with self.assertRaises(ValueError):
                decode_request(struct.pack(">qB", 7, direction))
        for direction in (-1, 8, 9, True):
            with self.assertRaises(ValueError):
                facing_response(10, 3, 7, direction)

    def test_supplement_is_bound_to_attested_script_identity(self):
        from wakfu_server.combat_cast_facing_contracts import SCRIPT_CONTRACTS

        records = {
            "a": {"status": "pending", "script_id": -1797056500},
            "b": {"status": "pending", "script_id": -1142083330},
            "c": {"status": "pending", "script_id": 1},
            "d": {
                "status": "verified",
                "script_id": -1797056500,
                "turnCasterTowardTargetCell": True,
            },
        }
        native_cast_facing.cache_clear()
        try:
            with patch(
                "wakfu_server.combat_cast_facing.protocol_catalog.load",
                return_value={"spells": records},
            ):
                result = native_cast_facing()
            self.assertIs(result["a"]["turnCasterTowardTargetCell"], False)
            self.assertIs(result["b"]["turnCasterTowardTargetCell"], False)
            self.assertNotIn("turnCasterTowardTargetCell", result["c"])
            self.assertNotIn("turnCasterTowardTargetCell", records["a"])
            self.assertIs(result["d"]["turnCasterTowardTargetCell"], True)
            for row in SCRIPT_CONTRACTS.values():
                self.assertEqual(len(row["script_content_sha256"]), 64)
        finally:
            native_cast_facing.cache_clear()

    def test_carrying_uses_native_relative_direction_propagation(self):
        from test_combat_carrying import CarryingLifecycleTests
        from wakfu_server.combat_carrying import carry_registered, carrying_relations

        fight, carrier, carried = CarryingLifecycleTests().fixture()
        carry_registered(fight, carrier, carried, source_uid=1)
        before_carrier, before_carried = carrier.direction, carried.direction
        packets = begin_cast_facing(
            carrier,
            {
                "target": (
                    carrier.position[0] - 2,
                    carrier.position[1],
                    carrier.position[2],
                )
            },
            fight=fight,
            action_id=3,
        )
        self.assertEqual(carrier.direction, 5)
        self.assertEqual(carried.direction, (before_carried + 5 - before_carrier) % 8)
        self.assertTrue(carrying_relations(fight, carrier)["is_carrying"])
        self.assertEqual(packets[0][0], 13494)

    def test_forced_orientation_after_default_keeps_its_native_result_and_gate(self):
        from test_combat_orientation_effect import OrientationEffectTests

        for blocked in (False, True):
            fight, packets, handler, invocation, _ = OrientationEffectTests().fixture(
                property51=blocked
            )
            actor = fight.actors[7]
            begin = begin_cast_facing(
                actor, {"target": (2, 0, 0)}, fight=fight, action_id=1
            )
            self.assertEqual(actor.direction, 1)  # Voluntary cast has no eWF51 gate.
            invocation = replace(invocation, target_id=actor.id)
            applied = handler({"effect_class": 303}, {"parameters": [2]}, invocation)
            self.assertEqual(applied, not blocked)
            self.assertEqual(actor.direction, 1 if blocked else 7)
            self.assertFalse(
                finish_mirrored_cast_facing(
                    actor,
                    {"spell_id": 999, "target": (2, 0, 0)},
                    fight=fight,
                    contracts={},
                )
            )
            self.assertEqual(actor.direction, 1 if blocked else 7)
            if applied:
                self.assertEqual(_identity_fields(packets[0][1][19:])[4], 7)
                self.assertEqual(
                    [op for op, _ in (*begin, *packets)], [13494, 13420, 12613]
                )

    def test_real_weapon_damage_faces_target_and_preserves_live_source(self):
        from test_combat_weapon import weapon_fixture, equipped
        from wakfu_server.combat_weapon import prepare_server_weapon
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck

        character, monster, fight = weapon_fixture(11, 200)
        character = equipped(character, 2027)
        fight.actors[7].direction = 7
        before = snapshot(fight)
        tx = prepare_server_weapon(
            struct.pack(">qqbiih", 7, 1000, 15, 1, 0, 0),
            character,
            {-7: monster},
            fight,
            3,
            encode_deck((), ()),
            action_id=1,
            line_of_sight=lambda *_: True,
            critical=False,
            rng=Random(1),
        )
        self.assertEqual(snapshot(fight), before)
        self.assertEqual(tx.fight.actors[7].direction, 1)
        self.assertEqual([op for op, _ in tx.packets[:3]], [13494, 13420, 13509])
        self.assertLess(tx.fight.actors[-7].hp, fight.actors[-7].hp)

    def test_real_npc_admission_defaults_facing_and_keeps_paid_native_attack(self):
        from test_combat_spatial_pilot_new_attack import SpatialPilotNewAttackTests
        from wakfu_server.combat_npc_spell import prepare_npc_spell
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.spells import default_deck

        SpatialPilotNewAttackTests.setUpClass()
        template = SpatialPilotNewAttackTests.template
        fight = deepcopy(template.fight)
        npc = fight.actors[template.npc.id]
        npc.direction = 1
        before = source_snapshot(fight)
        with patch(
            "wakfu_server.combat_cast_facing.native_cast_facing", return_value={}
        ):
            tx = prepare_npc_spell(
                fight,
                dict(
                    type="cast",
                    spellId=5868,
                    level=42,
                    target=list(template.pc.position),
                    targetId=template.pc.id,
                ),
                template.character,
                {template.monster["id"]: template.monster},
                default_deck(template.character),
                action_id=11,
                rng=Random(7),
            )
        self.assertEqual(source_snapshot(fight), before)
        self.assertEqual(tx.fight.actors[npc.id].direction, 5)
        self.assertEqual(tx.fight.actors[npc.id].ap, npc.ap - 2)
        self.assertEqual([op for op, _ in tx.packets[:4]], [13494, 13420, 12588, 12678])

    def test_real_player_native_damage_and_rejected_admission_keep_source_immutable(
        self,
    ):
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.spells import encode_deck

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            8, 21, full_health=True, native_qi=True, target_ref=4168, target_level=190
        )
        fight.actors[7].direction = 7
        before = source_snapshot(fight)
        target = fight.actors[-7]
        body = struct.pack(">qqiih", 7, (7 << 32) | 4780, *target.position)
        kwargs = dict(action_id=1, critical=False, rng=Random(1))
        with patch(
            "wakfu_server.combat_cast_facing.native_cast_facing", return_value={}
        ):
            tx = prepare_server_spell(
                body,
                character,
                {-7: monster},
                fight,
                3,
                encode_deck([4780]),
                line_of_sight=lambda *_: True,
                **kwargs
            )
        self.assertEqual(source_snapshot(fight), before)
        self.assertEqual(tx.fight.actors[7].direction, 1)
        self.assertEqual([op for op, _ in tx.packets[:4]], [13494, 13420, 12588, 12678])
        self.assertLess(tx.fight.actors[-7].hp, target.hp)
        self.assertEqual(
            tx.fight.actors[7].ap, fight.actors[7].ap - tx.plan["costs"]["ap"]
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        runtime = RuntimeMessages(fight)
        for malformed in (
            struct.pack(">i", fight.id + 1),
            bytearray(struct.pack(">i", fight.id)),
        ):
            with self.assertRaisesRegex(ValueError, "another combat action"):
                commit_spell_transaction(
                    runtime,
                    replace(tx, packets=((13420, malformed), *tx.packets)),
                    stats_serializer=lambda *_: b"owned",
                )
            self.assertEqual(source_snapshot(runtime.fight), before)
            self.assertEqual(runtime.action_id, 0)
        with self.assertRaises(ValueError):
            prepare_server_spell(
                body,
                character,
                {-7: monster},
                fight,
                3,
                encode_deck([]),
                line_of_sight=lambda *_: True,
                **kwargs
            )
        self.assertEqual(source_snapshot(fight), before)

    def test_native_action_allocator_keeps_facing_flush_before_cast_ids(self):
        from wakfu_server.combat_native_action_ids import prepare_native_delivery

        fight, actor = self.actor()
        prefix = begin_cast_facing(
            actor, {"target": (2, 0, 0)}, fight=fight, action_id=3
        )
        # A real cast-action common header follows the completed facing block.
        cast = (12588, struct.pack(">iiiq", 10, 3, -1, 7))
        delivery, last = prepare_native_delivery(
            (*prefix, cast), fight_id=10, previous_id=0
        )
        self.assertEqual([op for op, _ in delivery], [13494, 13420, 12588])
        self.assertEqual(struct.unpack_from(">i", delivery[0][1], 4)[0], 1)
        self.assertEqual(struct.unpack_from(">i", delivery[2][1], 4)[0], 2)
        self.assertEqual(last, 2)
