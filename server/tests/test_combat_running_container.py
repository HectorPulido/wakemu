import unittest
from wakfu_server.combat_running_container import running_container_scope
from wakfu_server.combat_stat_effects import owned_effect_payload
from wakfu_server.combat_effect_removal import _identity_fields


class NativeContainerTests(unittest.TestCase):
    def payload(self):
        return owned_effect_payload(
            uid=1,
            base_uid=None,
            generic_effect=150327,
            caster_id=33,
            target_id=33,
            value=0,
        )

    def fields(self):
        return _identity_fields(
            self.payload(), integer_fields=(1, 2, 3, 4, 6, 7, 9, 10)
        )

    def test_actual_state_container_and_nested_absence_restore(self):
        self.assertNotIn(9, self.fields())
        container = dict(container_present=True, container_type=1)
        with running_container_scope(container, 3442 << 16 | 20):
            self.assertEqual(
                (self.fields()[9], self.fields()[10]), (1, 3442 << 16 | 20)
            )
            with running_container_scope(dict(container_present=False), None):
                self.assertNotIn(9, self.fields())
            self.assertEqual(self.fields()[10], 3442 << 16 | 20)
        self.assertNotIn(9, self.fields())

    def test_failure_restores_scope_without_fabricating_uid_container(self):
        with self.assertRaises(RuntimeError):
            with running_container_scope(
                dict(container_present=True, container_type=11), 754 << 16 | 20
            ):
                self.assertEqual(self.fields()[9], 11)
                raise RuntimeError("rollback")
        self.assertNotIn(9, self.fields())


class CommonInitializationContainerTests(unittest.TestCase):
    def test_native_state_children_keep_actual_fyw_in_common_entry(self):
        from random import Random
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck
        from test_combat_spell_transaction import SpellTransactionTests

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            11, 20, native_qi=True
        )
        before = snapshot(fight)
        preview, packets = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            encode_deck((), [5051]),
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        states = {
            state.uid: state
            for actor in preview.actors.values()
            for state in actor.state_ledger.entries
        }
        checked = 0
        for row in preview.owned_stat_effects.values():
            if row.get("state_uid") is None:
                continue
            state = states[row["state_uid"]]
            fields = _identity_fields(
                bytes.fromhex(row["payload"]), integer_fields=(1, 2, 3, 4, 6, 7, 9, 10)
            )
            self.assertEqual(fields[9], 1)
            self.assertEqual(fields[10], (state.reference << 16) | state.level)
            self.assertEqual(fields[1], row["uid"])
            checked += 1
        self.assertGreater(checked, 0)
        self.assertTrue(packets)
        self.assertEqual(snapshot(fight), before)

    def test_real_iop_cast_keeps_display_children_with_native_containers(self):
        import struct
        from random import Random
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
        )
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.spells import encode_deck
        from test_combat_spell_transaction import SpellTransactionTests

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            8, 20, native_qi=True, target_ref=4085, target_level=23
        )
        self.assertEqual((fight.actors[-7].effective_level, monster["ref"]), (23, 4085))
        deck = encode_deck([4780])
        ready, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        before = snapshot(ready)
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 4780, *fight.actors[-7].position),
            character,
            {-7: monster},
            ready,
            3,
            deck,
            action_id=2,
            critical=False,
            line_of_sight=lambda *args: True,
            rng=Random(7),
        )
        preview, packets = result.fight, result.packets
        null_rows = [
            row
            for row in (
                *preview.native_owned_group_effects.values(),
                *preview.owned_stat_effects.values(),
            )
            if row["effect_class"] == 400
            and row["uid"] not in ready.owned_stat_effects
            and row["uid"] not in ready.native_owned_group_effects
        ]
        self.assertTrue(null_rows)
        for row in null_rows:
            matching = [
                body
                for opcode, body in packets
                if opcode == 12613 and body.endswith(bytes.fromhex(row["payload"]))
            ]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0][12], 0)
        states = {
            state.reference: state
            for actor in preview.actors.values()
            for state in actor.state_ledger.entries
        }
        self.assertIn(3442, states)
        self.assertIn(8913, states)
        self.assertEqual(preview.actors[7].effect_stats[67], states[3442].level)
        self.assertEqual(preview.actors[7].native_hud_breed, 8)
        visible_group = [
            row
            for row in preview.native_owned_group_effects.values()
            if row["invocation"]["reference"] == 408737
        ]
        self.assertEqual(len(visible_group), 1)
        fields = _identity_fields(
            bytes.fromhex(visible_group[0]["payload"]), integer_fields=(9, 10)
        )
        self.assertEqual(fields, {9: 1, 10: 8913 << 16 | 30})
        self.assertTrue(
            any(
                op == 13497
                and body.endswith(bytes.fromhex(visible_group[0]["payload"]))
                for op, body in packets
            )
        )
        self.assertEqual(snapshot(ready), before)


class NativeOwnedDeliveryTests(unittest.TestCase):
    def test_null400_registration_and_group330_observation_keep_pl_bytes(self):
        from wakfu_server.combat_stat_effects import owned_effect_delivery

        with running_container_scope(
            dict(container_present=True, container_type=1), 3442 << 16 | 20
        ):
            payload = owned_effect_payload(
                uid=9,
                base_uid=None,
                generic_effect=150327,
                caster_id=7,
                target_id=7,
                value=0,
            )
        args = dict(target_id=7, uid=9, running_effect_payload=payload)
        opcode, null = owned_effect_delivery(
            3, 8, native_opcode=12613, effect_class=400, **args
        )
        self.assertEqual(opcode, 12613)
        self.assertEqual(null[12], 0)
        opcode, group = owned_effect_delivery(3, 8, effect_class=330, **args)
        self.assertEqual(opcode, 13497)
        from wakfu_server.combat_stat_effects import owned_effect_application

        observed400 = owned_effect_application(3, 8, effect_class=400, **args)
        self.assertEqual(null[:12] + null[13:], observed400)
        self.assertEqual(payload, null[-len(payload) :])
