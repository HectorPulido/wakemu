"""A new owner client must receive claimed NPC appearances before cvb."""
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from protocol_codec import Reader
from wakfu_server.combat_reconnect_world_actors import ordinary_npc_appearances
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.monsters import owned_instance


class ReconnectWorldActorTests(unittest.TestCase):
    def setUp(self):
        if (
            self._testMethodName
            == "test_npc_morph_reconnect_replays_same_uid_then_omits_after_removal"
        ):
            return  # This integrated fixture supplies its own NPC identity.
        self.monster = owned_instance(4, 8, -200, map_id=1134, x=-10, y=-2, z=-1)
        self.actor = SimpleNamespace(
            id=-200, controlled=False, team=1, position=(-9, -3, -1)
        )
        self.player = SimpleNamespace(
            id=13, controlled=True, team=0, position=(-8, -3, -1)
        )
        self.fight = SimpleNamespace(
            actors={13: self.player, -200: self.actor},
            native_summon_registrations={},
            phase="placement",
        )
        self.session = SimpleNamespace(character_id=13, account_id=0)
        self.shared = SimpleNamespace(
            map_id=1134,
            instance_id=0,
            join_context={
                "monsters": {-200: self.monster},
                "group_key": (1134, 0, 555),
            },
        )

    def test_claimed_npc_spawn_uses_current_position_and_original_profile(self):
        before = deepcopy(vars(self.fight)), deepcopy(vars(self.shared))
        packets = ordinary_npc_appearances(self.fight, self.shared)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0][0], 12608)
        outer = Reader(packets[0][1])
        self.assertEqual(
            tuple(outer.number(t) for t in ("B", "B", "B", "q")), (0, 1, 1, -200)
        )
        actor = Reader(outer.take(outer.number("H")))
        outer.finish()
        self.assertEqual(
            tuple(actor.number(t) for t in ("B", "q", "B", "q")), (11, -200, 1, -1)
        )
        actor.text("H")
        self.assertEqual(actor.number("h"), 4)
        self.assertEqual(
            tuple(actor.number(t) for t in ("i", "i", "h", "q")), (-9, -3, -1, 1134)
        )
        self.assertEqual((vars(self.fight), vars(self.shared)), before)

    def test_owned_reconnect_orders_appearance_before_placement_and_active_bootstrap(
        self,
    ):
        adapter = CombatSessionAdapter(SimpleNamespace())
        for phase in ("placement", "active"):
            with self.subTest(phase=phase):
                self.fight.phase = phase
                with patch(
                    "wakfu_server.combat_reconnect_snapshot.owned_snapshot",
                    return_value=((12847, b"combat"),),
                ):
                    packets = adapter.owned_reconnect_bootstrap(
                        self.fight, self.shared, self.session
                    )
                self.assertEqual([op for op, _ in packets], [12608, 12847])

    def test_npc_morph_reconnect_replays_same_uid_then_omits_after_removal(self):
        """The world appearance, fight roster and morph carrier keep one NPC ID."""
        from dataclasses import asdict
        import struct
        from unittest.mock import patch

        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_morph_handler import (
            NativeMorphHandler,
            remove_morph_effect,
        )
        from wakfu_server.combat_retained_effects import RetainedEffect
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_native_timing_context import native_time_payload

        player = Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 50, 10, True)
        npc = Actor(-200, 1, (2, 0, 0), 40, 6, 3, 40, 25)
        fight = Fight(
            901,
            [player, npc],
            {(x, 0, 0) for x in range(4)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(2, 0, 0), (3, 0, 0)}},
        )
        fight.ready(10)
        fight.native_retained_tracking = True
        effect_packets = []
        profile = {
            "profile_id": 2778,
            "minimum_level": 12,
            "abilities": [{"reference": 91, "casting_uid": 91, "maximum_level": 50}],
        }
        morph = NativeMorphHandler(
            fight,
            effect_packets,
            action_id=41,
            allocate_uid=lambda: 7501,
            context=lambda *_: StatExecutionContext(
                True, True, None, True, native_time_payload()
            ),
            rng=lambda: 0.5,
            profiles={"2778": profile},
        )
        effect = {
            "effect_class": 933,
            "parameter_count": 1,
            "parameters": [2778, 0],
            "target_masks": [[], [], [], [], [], [], []],
        }
        invocation = EffectInvocation(105267, 50, 10, -200, npc.position)

        class Runner:
            def __init__(self, uid, family, *, rng, value=0):
                self.uid, self.family, self.value = uid, family, value

            def set_calculated(self, value):
                self.value = value

            def finish_application(self):
                pass

        with patch("wakfu_server.combat_morph_handler.NativeRunnerAmount", Runner):
            self.assertTrue(morph(effect, {}, invocation))
        self.assertEqual([opcode for opcode, _ in effect_packets], [12613])
        original_payload = bytes.fromhex(fight.owned_stat_effects[7501]["payload"])
        entry = RetainedEffect(
            uid=7501,
            target_id=-200,
            effect_class=933,
            generic_effect=105267,
            manager_id=-200,
            definition_type=0,
            container_present=False,
        )
        fight.native_retained_records[7501] = asdict(entry)
        fight.native_retained_order.append(7501)

        shared = SimpleNamespace(
            map_id=1134,
            instance_id=0,
            runtime=SimpleNamespace(
                fight=fight,
                turn_deadline=None,
                native_action_id=41,
                awaiting_ack=None,
            ),
            join_context={
                "monsters": {
                    -200: {
                        "id": -200,
                        "ref": 4,
                        "level": 25,
                        "map_id": 1134,
                        "instance_id": 0,
                        "team": 1,
                    }
                },
                "group_key": (1134, 0, 555),
                "arena": {
                    "map_id": 1134,
                    "instance_id": 0,
                    "x": 0,
                    "y": 0,
                    "width": 4,
                    "height": 1,
                    "min_z": 0,
                    "max_z": 0,
                    "cell_masks": [0, 0, 0, 0],
                },
                "terrain_effect_id": 99,
                "terrain_instance_id": 0,
                "leaders": {0: 10, 1: -200},
            },
        )
        adapter = CombatSessionAdapter(SimpleNamespace())

        def fixture_instance(ref, level, actor_id, **kw):
            return {
                "id": actor_id,
                "ref": ref,
                "level": level,
                "map_id": kw["map_id"],
                "instance_id": kw["instance_id"],
                "team": kw["team"],
                **{key: kw[key] for key in ("x", "y", "z")},
            }

        def reconnect_packets():
            with (
                patch.object(adapter, "actor_payload", return_value=(b"stats", b"fx")),
                patch(
                    "wakfu_server.monsters.owned_instance", side_effect=fixture_instance
                ),
                patch(
                    "wakfu_server.combat_monster_world.owned_instance",
                    side_effect=fixture_instance,
                ),
                patch(
                    "wakfu_server.combat_monster_world.reference",
                    return_value={"name": "Native NPC"},
                ),
                patch(
                    "wakfu_server.combat_monster_world.corpse_collect_actions",
                    return_value=(),
                ),
            ):
                return adapter.owned_reconnect_bootstrap(
                    fight, shared, SimpleNamespace(character_id=10, account_id=0)
                )

        first = reconnect_packets()
        opcodes = [opcode for opcode, _ in first]
        self.assertEqual(opcodes[:2], [12608, 12847])
        self.assertEqual(opcodes[-1], 12613)
        self.assertIn(original_payload, first[-1][1])
        self.assertEqual(
            struct.unpack_from(">iiiBi", first[-1][1]), (901, 41, -1, 0, 933)
        )
        self.assertEqual(fight.actors[-200].id, -200)
        appearance = Reader(first[0][1])
        self.assertEqual(tuple(appearance.number(t) for t in ("B", "B")), (0, 1))
        self.assertEqual(appearance.number("B"), 1)
        self.assertEqual(appearance.number("q"), -200)
        actor = Reader(appearance.take(appearance.number("H")))
        self.assertEqual(actor.number("B"), 11)
        self.assertEqual(actor.number("q"), -200)
        self.assertEqual(actor.number("B"), 1)
        self.assertEqual(actor.number("q"), -1)
        from wakfu_server.combat_wire import decode_bootstrap

        roster = decode_bootstrap(first[1][1])
        self.assertIn(-200, {row["actor_id"] for row in roster["participants"]})

        remove_morph_effect(morph, 7501)
        retention = object.__new__(NativeRetainedRuntime)
        retention.fight = fight
        retention.synchronize()
        self.assertEqual([opcode for opcode, _ in effect_packets], [12613, 13560])
        from wakfu_server.combat_effect_removal import state_unapplication_payload

        self.assertIn(
            state_unapplication_payload(original_payload), effect_packets[-1][1]
        )
        self.assertNotIn(7501, fight.owned_stat_effects)
        self.assertNotIn(7501, fight.native_retained_records)
        self.assertNotIn(7501, fight.native_retained_order)

        second = reconnect_packets()
        self.assertEqual([opcode for opcode, _ in second][:2], [12608, 12847])
        self.assertFalse(
            any(
                opcode == 12613 and original_payload in payload
                for opcode, payload in second
            )
        )
        self.assertEqual(fight.actors[-200].id, -200)

    def test_friendly_duel_does_not_fabricate_npcs(self):
        self.shared.join_context = {}
        self.assertEqual(ordinary_npc_appearances(self.fight, self.shared), ())

    def test_rift_keeps_its_separate_wave_snapshot(self):
        self.fight.rift_wave_state = {"wave": 2}
        self.assertEqual(ordinary_npc_appearances(self.fight, self.shared), ())

    def test_registered_summons_are_not_recreated_as_world_monsters(self):
        summon = SimpleNamespace(id=88, controlled=False, team=0, position=(-8, -2, -1))
        self.fight.actors[88] = summon
        self.fight.native_summon_registrations[88] = {"owner": 13}
        packets = ordinary_npc_appearances(self.fight, self.shared)
        outer = Reader(packets[0][1])
        self.assertEqual(
            tuple(outer.number(t) for t in ("B", "B", "B", "q")), (0, 1, 1, -200)
        )

    def test_retired_snapshot_npc_is_not_restored_as_a_world_appearance(self):
        with patch(
            "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
            return_value={-200},
        ):
            self.assertEqual(ordinary_npc_appearances(self.fight, self.shared), ())

    def test_hidden_npc_is_filtered_without_dropping_surviving_npc_appearance(self):
        survivor = SimpleNamespace(
            id=-201, controlled=False, team=1, position=(-8, -4, -1)
        )
        self.fight.actors[survivor.id] = survivor
        self.shared.join_context["monsters"][survivor.id] = owned_instance(
            4, 8, survivor.id, map_id=1134, x=-8, y=-4, z=-1, team=1
        )
        emitted = []

        def capture_group(members, *, group_id):
            emitted.extend(members)
            return b"spawn-group"

        with (
            patch(
                "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
                return_value={-200},
            ),
            patch(
                "wakfu_server.combat_monster_world.spawn_group",
                side_effect=capture_group,
            ),
        ):
            packets = ordinary_npc_appearances(self.fight, self.shared)

        self.assertEqual(packets, ((12608, b"spawn-group"),))
        self.assertEqual([member["id"] for member in emitted], [-201])

    def test_incomplete_or_foreign_group_authority_is_rejected_without_mutation(self):
        cases = [
            {"monsters": {}, "group_key": (1134, 0, 555)},
            {"monsters": {-200: self.monster}, "group_key": (527, 0, 555)},
            {
                "monsters": {-200: dict(self.monster, id=-201)},
                "group_key": (1134, 0, 555),
            },
        ]
        for context in cases:
            with self.subTest(context=context):
                self.shared.join_context = context
                before = deepcopy(vars(self.fight)), deepcopy(vars(self.shared))
                with self.assertRaises(ValueError):
                    ordinary_npc_appearances(self.fight, self.shared)
                self.assertEqual((vars(self.fight), vars(self.shared)), before)


class ReconnectPlayerAppearanceTests(unittest.TestCase):
    def setUp(self):
        self.selected = SimpleNamespace(
            id=10, owner_id=100, controlled=True, team=0, position=(0, 0, 0)
        )
        self.ally = SimpleNamespace(
            id=11, owner_id=200, controlled=True, team=0, position=(1, 0, 0), hp=20
        )
        self.corpse = SimpleNamespace(
            id=12, owner_id=300, controlled=True, team=0, position=(2, 0, 0), hp=0
        )
        self.summon = SimpleNamespace(
            id=13, owner_id=200, controlled=True, team=0, position=(3, 0, 0)
        )
        self.hidden = SimpleNamespace(
            id=14, owner_id=200, controlled=True, team=0, position=(4, 0, 0)
        )
        self.withdrawn = SimpleNamespace(
            id=15,
            owner_id=200,
            controlled=True,
            team=0,
            position=(5, 0, 0),
            pve_withdrawn=True,
        )
        self.fight = SimpleNamespace(
            actors={
                actor.id: actor
                for actor in (
                    self.selected,
                    self.ally,
                    self.corpse,
                    self.summon,
                    self.hidden,
                    self.withdrawn,
                )
            },
            native_summon_registrations={13: {"owner": 11}},
            phase="placement",
        )
        self.shared = SimpleNamespace(map_id=1134, instance_id=0, join_context={})
        self.session = SimpleNamespace(character_id=10, account_id=100)

    def test_sources_only_visible_other_players_and_preserves_off_play_corpse(self):
        from wakfu_server.combat_reconnect_world_actors import (
            ordinary_player_appearances,
        )

        source_calls, serializer_calls = [], []

        def source(owner_id, character_id):
            source_calls.append((owner_id, character_id))
            return {
                "id": character_id,
                "account_id": owner_id,
                "name": str(character_id),
            }

        def serialize(character):
            serializer_calls.append(character["id"])
            return 12608, str(character["id"]).encode()

        with patch(
            "wakfu_server.combat_snapshot_actor_visibility.hidden_snapshot_actor_ids",
            return_value={14},
        ):
            packets = ordinary_player_appearances(
                self.fight,
                self.shared,
                self.session,
                character_source=source,
                serializer=serialize,
            )

        self.assertEqual(packets, ((12608, b"11"), (12608, b"12")))
        self.assertEqual(source_calls, [(200, 11), (300, 12)])
        self.assertEqual(serializer_calls, [11, 12])

    def test_missing_factory_and_foreign_character_source_fail_closed(self):
        from wakfu_server.combat_reconnect_world_actors import (
            ordinary_player_appearances,
        )

        with self.assertRaisesRegex(ValueError, "appearance authority"):
            ordinary_player_appearances(
                self.fight,
                self.shared,
                self.session,
                character_source=None,
                serializer=None,
            )

        with self.assertRaisesRegex(ValueError, "foreign"):
            ordinary_player_appearances(
                self.fight,
                self.shared,
                self.session,
                character_source=lambda owner, actor: {
                    "id": actor,
                    "account_id": owner + 1,
                },
                serializer=lambda source: (12608, b"partial"),
            )

    def test_real_spawn_wire_carries_source_name_and_equipment(self):
        import hashlib
        import struct
        from wakfu_server import wire
        from wakfu_server.combat_reconnect_world_actors import (
            ordinary_player_appearances,
        )

        template = (
            struct.pack(
                ">BqBqH",
                11,
                wire.TEMPLATE_CHARACTER,
                1,
                wire.TEMPLATE_ACCOUNT,
                len(b"Pekebu"),
            )
            + b"Pekebu"
            + struct.pack(">iihqBB", -12, -8, -1, 1134, 0, 1)
            + bytes(20)
            + b"\x00"
        )
        equipment_start = len(template) - 1
        layout = {
            "template_sha256": hashlib.sha256(template).hexdigest(),
            "sections": [
                {
                    "name": "EQUIPMENT_APPEARANCE",
                    "start": equipment_start,
                    "end": equipment_start + 1,
                }
            ],
        }
        character = dict(
            id=11,
            account_id=200,
            name="Mira Hero",
            level=6,
            breed=8,
            active_build_index=0,
            x=7,
            y=9,
            z=-1,
            map_id=1134,
            direction=2,
            inventory_items=[
                dict(uid=1001, character_id=11, reference=6823, quantity=1)
            ],
            builds={
                0: dict(
                    sheet=wire.proto_field(24, (1 << 64) - 1).hex(),
                    equipment=wire.proto_field(
                        10, wire.proto_field(8, 1001) + wire.proto_field(16, 0)
                    ).hex(),
                )
            },
        )
        self.fight.actors = {10: self.selected, 11: self.ally}
        with patch.dict(wire.ENTITY_LAYOUTS, {11: layout}):
            packets = ordinary_player_appearances(
                self.fight,
                self.shared,
                self.session,
                character_source=lambda owner, identity: character,
                serializer=lambda source: (12608, wire.spawn_player(template, source)),
            )

        self.assertEqual(len(packets), 1)
        packet = packets[0][1]
        self.assertIn(b"Mira Hero", packet)
        self.assertNotIn(b"Pekebu", packet)
        self.assertIn(struct.pack(">BBii", 1, 0, 6823, 0), packet)

    def test_owned_reconnect_prefix_order_for_placement_active_rift_and_duel(self):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter

        source_calls = []

        def source(owner_id, character_id):
            source_calls.append((owner_id, character_id))
            return {"id": character_id, "account_id": owner_id, "name": "Ally"}

        store = SimpleNamespace(character=source)
        context_packet = (12608, b"from-context")
        fallback_packet = (12608, b"from-fallback")
        adapter = CombatSessionAdapter(
            store, player_appearance=lambda character: fallback_packet
        )
        self.fight.actors = {10: self.selected, 11: self.ally}

        for phase, context, rift, expected in (
            (
                "placement",
                {"hero_appearance": lambda _: context_packet},
                False,
                [12608, 12847],
            ),
            (
                "active",
                {"hero_appearance": lambda _: context_packet},
                False,
                [12608, 12847],
            ),
            ("active", {}, False, [12608, 12847]),
            (
                "active",
                {"hero_appearance": lambda _: context_packet},
                True,
                [12608, 12608, 12847],
            ),
        ):
            self.fight.phase = phase
            if rift:
                self.fight.rift_wave_state = {"wave": 1}
            elif hasattr(self.fight, "rift_wave_state"):
                del self.fight.rift_wave_state
            self.shared.join_context = context
            with (
                patch(
                    "wakfu_server.combat_reconnect_snapshot.owned_snapshot",
                    return_value=((12847, b"combat"),),
                ),
                patch(
                    "wakfu_server.rift_combat_adapter.world_snapshot",
                    return_value=((12608, b"rift"),),
                ),
            ):
                packets = adapter.owned_reconnect_bootstrap(
                    self.fight, self.shared, self.session
                )
            self.assertEqual([opcode for opcode, _ in packets], expected)
            self.assertEqual(
                packets[0][1], context_packet[1] if context else fallback_packet[1]
            )

        self.assertEqual(source_calls, [(200, 11)] * 4)
