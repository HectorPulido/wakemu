import unittest
import struct
from random import Random
from wakfu_server.combat_weapon import (
    decode_request,
    owned_weapon,
    prepare_server_weapon,
    animation,
)
from wakfu_server.wire import proto_field
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck
import test_combat_spell_transaction as fixture


def equipped(character, reference, uid=1000):
    character = dict(character)
    character["inventory_items"] = [
        dict(uid=uid, character_id=character["id"], reference=reference, quantity=1)
    ]
    blob = proto_field(10, proto_field(8, uid) + proto_field(16, 15))
    character["builds"] = {0: dict(equipment=blob.hex())}
    return character


class WeaponTests(unittest.TestCase):
    def test_owned_active_sheet_uid_and_slot_are_required(self):
        character = equipped(dict(id=7, level=20), 2027)
        request = decode_request(struct.pack(">qqbiih", 7, 1000, 15, 1, 0, 0))
        self.assertEqual(owned_weapon(character, request)[0]["reference"], 2027)
        for bad in (dict(request, item_uid=1001), dict(request, slot=16)):
            with self.assertRaises(ValueError):
                owned_weapon(character, bad)
        with self.assertRaises(ValueError):
            owned_weapon(dict(character, builds={}), request)
        with self.assertRaises(ValueError):
            owned_weapon(
                dict(
                    character,
                    inventory_items=[
                        dict(uid=1000, character_id=8, reference=2027, quantity=1)
                    ],
                ),
                request,
            )

    def test_item_animation_identity_and_critical_branch(self):
        packet = animation(78, 2, 7, 2027, 7, (1, 0, 0), True)
        self.assertEqual(
            struct.unpack(">iiiqihBBB iih", packet),
            (78, 2, -1, 7, 2027, 7, 0, 0, 1, 1, 0, 0),
        )

    def test_native_damage_weapon_uses_shared_dispatcher_and_private_preview(self):
        (
            character,
            monster,
            fight,
        ) = fixture.SpellTransactionTests().native_server_fixture(11, 200)
        character = equipped(character, 2027)
        fight.actors[-7].position = (1, 0, 0)
        before = snapshot(fight)
        transaction = prepare_server_weapon(
            struct.pack(">qqbiih", 7, 1000, 15, 1, 0, 0),
            character,
            {-7: monster},
            fight,
            3,
            encode_deck((), ()),
            action_id=1,
            line_of_sight=lambda *args: True,
            critical=False,
            rng=Random(1),
        )
        self.assertEqual(snapshot(fight), before)
        self.assertLess(transaction.fight.actors[-7].hp, fight.actors[-7].hp)
        self.assertEqual(transaction.plan["native_retained_container"]["type"], 12)
        self.assertEqual(transaction.packets[0][0], 13509)
        self.assertEqual(
            transaction.fight.actors[7].ap,
            fight.actors[7].ap - transaction.plan["costs"]["ap"],
        )

    def test_foreign_uid_or_insufficient_resources_preserve_checkpoint(self):
        (
            character,
            monster,
            fight,
        ) = fixture.SpellTransactionTests().native_server_fixture(11, 20)
        character = equipped(character, 2027)
        before = snapshot(fight)
        for body in (
            struct.pack(">qqbiih", 7, 1001, 15, 1, 0, 0),
            struct.pack(">qqbiih", 7, 1000, 15, 2, 0, 0),
        ):
            with self.assertRaises(ValueError):
                prepare_server_weapon(
                    body,
                    character,
                    {-7: monster},
                    fight,
                    3,
                    encode_deck((), ()),
                    action_id=1,
                    line_of_sight=lambda *args: True,
                    critical=False,
                    rng=Random(1),
                )
            self.assertEqual(snapshot(fight), before)

    def test_two_native_weapons_normal_and_critical_commit_on_common_boundary(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_spell_commit import commit_spell_transaction

        for reference, expected_cost in ((2027, 5), (2037, 6)):
            damages = []
            for critical in (False, True):
                with self.subTest(reference=reference, critical=critical):
                    (
                        character,
                        monster,
                        fight,
                    ) = fixture.SpellTransactionTests().native_server_fixture(11, 200)
                    character = equipped(character, reference)
                    fight.actors[-7].position = (1, 0, 0)
                    before = snapshot(fight)
                    transaction = prepare_server_weapon(
                        struct.pack(">qqbiih", 7, 1000, 15, 1, 0, 0),
                        character,
                        {-7: monster},
                        fight,
                        3,
                        encode_deck((), ()),
                        action_id=1,
                        line_of_sight=lambda *args: True,
                        critical=critical,
                        rng=Random(1),
                    )
                    damages.append(200 - transaction.fight.actors[-7].hp)
                    self.assertEqual(snapshot(fight), before)
                    self.assertEqual(transaction.fight.actors[7].ap, 6 - expected_cost)
                    runtime = RuntimeMessages(fight)
                    packets = commit_spell_transaction(
                        runtime,
                        transaction,
                        stats_serializer=lambda *args: b"owned-stats",
                    )
                    self.assertIs(runtime.fight, transaction.fight)
                    self.assertEqual(runtime.action_id, 1)
                    self.assertEqual(packets[0][0], 13509)
                    self.assertEqual(
                        [opcode for opcode, _ in packets][-4:],
                        [13420, 12873, 12873, 13420],
                    )
            self.assertGreater(damages[0], 0)
            self.assertGreaterEqual(damages[1], damages[0])

    def test_absent_native_critical_branch_rejects_without_running_dispatch(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from wakfu_server.combat_weapon import catalog

        character = equipped(dict(id=7, level=200), 2027)
        rule = dict(
            catalog()[2027],
            roots=[dict(root, variant=0) for root in catalog()[2027]["roots"]],
        )
        actor = SimpleNamespace(id=7, controlled=True, owner_id=3, hp=100)
        fight = SimpleNamespace(phase="active", current=actor, actors={7: actor})
        with patch(
            "wakfu_server.combat_weapon.catalog", return_value={2027: rule}
        ), patch(
            "wakfu_server.combat_weapon.weapon_runtime_catalog"
        ) as compile_catalog:
            with self.assertRaisesRegex(ValueError, "no native critical"):
                prepare_server_weapon(
                    struct.pack(">qqbiih", 7, 1000, 15, 1, 0, 0),
                    character,
                    {},
                    fight,
                    3,
                    b"",
                    action_id=1,
                    line_of_sight=lambda *args: True,
                    critical=True,
                )
            compile_catalog.assert_not_called()

    def test_owned_random_element_weapon_bonus_reaches_common_damage(self):
        from wakfu_server.equipment_stats import effective_character, combat_resources
        from wakfu_server.combat_actor_snapshot import build_player_snapshot

        damages = []
        for metadata in ({}, dict(damage_elements=22, resistance_elements=0)):
            (
                character,
                monster,
                fight,
            ) = fixture.SpellTransactionTests().native_server_fixture(11, 200)
            character = equipped(character, 2869)
            character["inventory_items"][0].update(metadata)
            character = effective_character(character)
            from wakfu_server.combat_state import Actor

            resources = combat_resources(character, wp=6)
            caster = Actor(
                7,
                0,
                (0, 0, 0),
                character["hp"],
                resources["ap"],
                resources["mp"],
                resources["initiative"],
                200,
                3,
                True,
                max_hp=character["max_hp"],
            )
            caster.direction = 0
            fight.actors[7] = caster
            build_player_snapshot(
                character, caster, wp_current=6, wp_maximum=6, running_effects=()
            ).install(caster)
            fight.actors[-7].position = (1, 0, 0)
            before = snapshot(fight)
            transaction = prepare_server_weapon(
                struct.pack(">qqbiih", 7, 1000, 15, 1, 0, 0),
                character,
                {-7: monster},
                fight,
                3,
                encode_deck((), ()),
                action_id=1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=Random(1),
            )
            damages.append(200 - transaction.fight.actors[-7].hp)
            self.assertEqual(snapshot(fight), before)
        self.assertGreater(damages[1], damages[0])
