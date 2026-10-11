import json
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from test_combat_qi_death_lifecycle import NativeQIDeathLifecycleTests
from wakfu_server.combat_ordinary_qi_retirement import (
    complete_ordinary_qi_death,
    retired_ordinary_qi_ids,
)
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.combat_casting_los import native_casting_ray


class OrdinaryQICompletionTests(unittest.TestCase):
    def test_retired_npc_slot_minus_one_serializes_in_spectator_and_owner_reconnect(
        self,
    ):
        from copy import deepcopy
        from types import SimpleNamespace

        from wakfu_server.combat_actor import actual_monster_actor_stats
        from wakfu_server.combat_global_pv_collections import global_fighter_guards
        from wakfu_server.combat_spectator_snapshot import current_snapshot
        from wakfu_server.combat_spectator_wire import decode_spectator_bootstrap
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_wire import arena, decode_bootstrap

        fight, _pc, retired, survivor = NativeQIDeathLifecycleTests().fight()
        # The QI-only helper deliberately lacks wire characteristics. Install a
        # real native NPC snapshot before damage for this serializer scenario.
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_actor_snapshot import build_npc_snapshot

        previous = retired
        retired = Actor(
            previous.id,
            previous.team,
            previous.position,
            previous.hp,
            previous.ap,
            previous.mp,
            previous.initiative,
            previous.effective_level,
            max_hp=previous.max_hp,
        )
        build_npc_snapshot(
            {"id": retired.id, "ref": 5525},
            retired,
            wp_current=0,
            wp_maximum=0,
            running_effects=(),
        ).install(retired)
        retired.native_obstacle_id = previous.native_obstacle_id
        retired.native_fight_property_counts = dict(
            previous.native_fight_property_counts
        )
        fight.actors[retired.id] = retired
        retired.native_controlled_by_ai = False  # Actual fresh NPC constructor fact.
        # Use the actual damage/death path and its typed retirement record.
        fight.apply_effect_damage(7, retired.id, retired.hp)
        self.assertTrue(complete_ordinary_qi_death(fight, retired))
        self.assertEqual(retired.native_obstacle_id, -1)
        self.assertEqual(
            global_fighter_guards(fight, retired.id),
            dict(baF=False, baG=False, baK=True),
        )

        terrain = arena(1134, 0, fight.walkable, fight.placement)
        context = {
            "arena": terrain,
            "terrain_effect_id": 378,
            "terrain_instance_id": -300,
            "leaders": {0: 7, 1: survivor.id},
        }
        shared = SimpleNamespace(
            fight=fight,
            map_id=1134,
            instance_id=0,
            is_duel=False,
            runtime=SimpleNamespace(
                native_action_id=4, turn_deadline=30, clock=lambda: 0, awaiting_ack=None
            ),
            join_context=context,
            ack=SimpleNamespace(turn=None, received=set()),
        )
        fight.native_fight_model = 2
        fight.native_retained_tracking = True
        fight.native_retained_records = {}
        fight.native_retained_order = []
        monster = dict(
            id=retired.id,
            team=retired.team,
            ref=5525,
            level=10,
            hp=retired.hp,
            max_hp=retired.max_hp,
            ap=retired.ap,
            max_ap=retired.max_ap,
            mp=retired.mp,
            max_mp=retired.max_mp,
            wp=0,
            max_wp=0,
            initiative=retired.initiative,
            x=retired.position[0],
            y=retired.position[1],
            z=retired.position[2],
            map_id=1134,
        )

        def stats(_fight, actor, *_session):
            if actor.id != retired.id:
                return b"fixture-actor", b"\x00\x00"
            return (
                actual_monster_actor_stats(
                    monster, actor, fight.id, wp_current=0, wp_maximum=0
                ),
                b"\x00\x00",
            )

        spectator = current_snapshot(
            fight, shared, actor_payload=lambda f, a: stats(f, a), deadline_ms=12345
        )
        spectator_snapshot = decode_spectator_bootstrap(spectator[0][1])
        spectator_actor = next(
            row
            for row in spectator_snapshot["participants"]
            if row["actor_id"] == retired.id
        )
        self.assertEqual(
            struct.unpack_from(">iBBBBbB", spectator_actor["myE"], 21)[5], -1
        )

        # The owner reconnect uses the same real actor serializer; its bootstrap
        # and actor-state stream must retain the attested signed -1 obstacle.
        reconnect = owned_snapshot(
            fight,
            shared,
            SimpleNamespace(account_id=1),
            actor_payload=lambda f, a, session: stats(f, a, session),
        )
        decoded = decode_bootstrap(reconnect[0][1])
        reconnect_actor = next(
            row for row in decoded["participants"] if row["actor_id"] == retired.id
        )
        self.assertEqual(
            struct.unpack_from(">iBBBBbB", reconnect_actor["myE"], 21)[5], -1
        )
        actor_update = next(
            payload
            for opcode, payload in reconnect
            if opcode == 12873 and struct.unpack_from(">q", payload, 4)[0] == retired.id
        )
        self.assertEqual(
            struct.unpack_from(">iBBBBbB", actor_update, 4 + 8 + 2 + 21)[5], -1
        )

        # A bare -1 is not enough: the producer must carry exact retirement
        # provenance or the public NPC serializer rejects the slot byte.
        forged = deepcopy(retired)
        forged.native_ordinary_qi_retirement = dict(
            source="unverified", actor_id=forged.id
        )
        with self.assertRaisesRegex(ValueError, "obstacle byte"):
            actual_monster_actor_stats(
                monster, forged, fight.id, wp_current=0, wp_maximum=0
            )

    def test_completed_registered_death_removes_los_and_movement_occupancy(self):
        fixture = NativeQIDeathLifecycleTests()
        fight, pc, first, second = fixture.fight()
        fixture.kill_first(fight, first)
        self.assertTrue(current_registry(fight).ordered_U(3, 3))
        self.assertTrue(complete_ordinary_qi_death(fight, first))
        self.assertFalse(complete_ordinary_qi_death(fight, first))
        self.assertEqual(first.native_obstacle_id, -1)
        self.assertEqual(current_registry(fight).ordered_U(3, 3), ())
        self.assertEqual(retired_ordinary_qi_ids(fight), {first.id})
        self.assertIn(first.id, fight.actors)
        with patch(
            "wakfu_server.combat_native_los_ray.cast_rays",
            return_value=((True, ((3, 3),)),),
        ):
            self.assertTrue(
                native_casting_ray(
                    fight,
                    SimpleNamespace(properties=lambda *_: ()),
                    1,
                    (0, 0, 0),
                    (3, 2, 0),
                    source_height=6,
                    target_height=6,
                    ignored_slots=(),
                )
            )
        # Plain checkpoint keys preserve the same validated source record.
        fight.native_ordinary_qi_retirements = json.loads(
            json.dumps(fight.native_ordinary_qi_retirements)
        )
        first.native_ordinary_qi_retirement = json.loads(
            json.dumps(first.native_ordinary_qi_retirement)
        )
        self.assertEqual(current_registry(fight).ordered_U(3, 3), ())
        self.assertTrue(current_registry(fight).ordered_U(*second.position[:2]))

    def test_hp_zero_in_play_never_retires(self):
        from wakfu_server.combat_hp_raw import (
            SOURCE,
            install_fresh_hp_operand,
            set_hp_raw_current,
        )

        fight, _, actor, _ = NativeQIDeathLifecycleTests().fight()
        actor.effect_stats = {1: actor.hp}
        actor.effect_minima = {1: 0}
        actor.effect_maxima = {1: actor.max_hp}
        actor.effect_frozen = frozenset()
        install_fresh_hp_operand(
            actor, dict(producer=SOURCE, actor_id=actor.id, raw_current=actor.hp)
        )
        set_hp_raw_current(actor, 0)
        self.assertFalse(complete_ordinary_qi_death(fight, actor))
        self.assertTrue(current_registry(fight).ordered_U(3, 3))
