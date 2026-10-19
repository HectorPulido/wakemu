"""Defensive NPC facing uses live, certified threat evidence cheaply."""
import subprocess
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_ai_facing import apply, choose


class DefensiveFacingTests(unittest.TestCase):
    @staticmethod
    def actor(identity, team, position, *, level=1, hp=40, direction=3):
        value = Actor(identity, team, position, hp, 0, 0, 1, level)
        value.direction = direction
        value.effect_stats = {20: 0, 48: 0, 27: 0, 28: 0, 29: 0, 30: 0, 31: 0}
        value.effect_maxima = {2: 10, 3: 4}
        value.native_fight_affiliation = team
        return value

    @classmethod
    def mock_fight(cls, rows, *, events=None):
        actors = {row.id: row for row in rows}
        fight = SimpleNamespace(
            id=1,
            actors=actors,
            events=[] if events is None else events,
            native_carry_pairs={},
            _in_play=lambda actor: actor.hp > 0,
        )
        fight._event = lambda kind, **fields: fight.events.append(
            dict(kind=kind, **fields)
        )
        return fight

    def test_first_turn_uses_offensive_stats_not_raw_level(self):
        actor = self.actor(-1, 0, (0, 0, 0))
        weak_high_level = self.actor(20, 1, (2, 0, 0), level=999)
        strong_low_level = self.actor(10, 1, (3, 0, 0), level=1)
        weak_high_level.effect_stats[20] = 5
        strong_low_level.effect_stats.update({20: 180, 48: 25, 9: 50, 52: 20})
        fight = self.mock_fight([actor, weak_high_level, strong_low_level])

        selected = choose(fight, actor)

        self.assertEqual(selected["targetId"], 10)
        self.assertEqual(
            selected["basis"], "native_offensive_characteristics_heuristic"
        )
        self.assertGreater(selected["offensivePotential"], 0)
        self.assertIn(
            "fallback_spell_base_range_los_unverified", selected["unknownDependencies"]
        )

    def test_certified_personal_loss_beats_stronger_global_offense(self):
        actor = self.actor(-1, 0, (0, 0, 0))
        certified = self.actor(10, 1, (5, 0, 0))
        global_risk = self.actor(20, 1, (1, 0, 0))
        global_risk.effect_stats[20] = 500
        fight = self.mock_fight([actor, certified, global_risk])
        evidence = {
            "actors": [
                {"id": item.id, "position": item.position}
                for item in fight.actors.values()
            ],
            "visibleActorIds": [-1, 10, 20],
            # Loss fields are from each rival's same native outcome against
            # this actor; an unrelated target's risk is not a personal threat.
            "rivals": [
                {"actorId": 10, "actorHpLoss": 8, "actorArmorLoss": 5, "actorLoss": 13},
                {"actorId": 20, "actorHpLoss": 0, "actorArmorLoss": 0, "actorLoss": 0},
            ],
        }

        selected = choose(fight, actor, evidence)

        self.assertEqual(selected["targetId"], 10)
        self.assertEqual(selected["certifiedLoss"], 13)
        self.assertEqual(selected["basis"], "certified_native_personal_loss")

    def test_excludes_dead_off_play_allied_and_unobserved_rivals(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            set_global_fighter_status,
        )

        actor = self.actor(-1, 0, (0, 0, 0))
        dead = self.actor(10, 1, (1, 0, 0))
        dead.hp = 0
        withdrawn = self.actor(11, 1, (0, 1, 0))
        ally = self.actor(12, 0, (0, -1, 0))
        hidden = self.actor(13, 1, (-1, 0, 0))
        fight = Fight(
            901,
            [actor, dead, withdrawn, ally, hidden],
            {a.position for a in (actor, dead, withdrawn, ally, hidden)},
            {
                0: {actor.position, ally.position},
                1: {dead.position, withdrawn.position, hidden.position},
            },
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        set_global_fighter_status(fight, 11, "OUT_OF_PLAY")
        evidence = {
            "actors": [
                {"id": a.id, "position": a.position} for a in fight.actors.values()
            ],
            "visibleActorIds": [-1, 10, 11, 12],
        }

        self.assertIsNone(choose(fight, actor, evidence))

    def test_tie_is_stable_stale_forecast_is_ignored_and_same_cell_is_skipped(self):
        actor = self.actor(-1, 0, (0, 0, 0))
        first = self.actor(10, 1, (2, 0, 0))
        second = self.actor(20, 1, (0, 2, 0))
        fight = self.mock_fight([actor, second, first])
        evidence = {
            "actors": [
                {"id": -1, "position": actor.position},
                {"id": 10, "position": (99, 99, 0)},
                {"id": 20, "position": second.position},
            ],
            "visibleActorIds": [-1, 10, 20],
            "rivals": [{"actorId": 10, "actorHpLoss": 99, "actorLoss": 99}],
        }

        selected = choose(fight, actor, evidence)
        self.assertEqual(selected["targetId"], 10)  # tie-break by stable actor ID
        self.assertEqual(
            selected["certifiedLoss"], 0
        )  # positional witness became stale
        first.position = actor.position
        self.assertEqual(choose(fight, actor)["targetId"], 20)

    def test_observed_damage_fallback_reads_only_a_bounded_recent_window(self):
        class BoundedEvents(list):
            requested_slice = None

            def __getitem__(self, key):
                if isinstance(key, slice):
                    self.requested_slice = key
                return super().__getitem__(key)

        actor = self.actor(-1, 0, (0, 0, 0))
        stale = self.actor(10, 1, (2, 0, 0))
        recent = self.actor(20, 1, (3, 0, 0))
        events = BoundedEvents(
            [
                {
                    "kind": "damage",
                    "target_id": actor.id,
                    "source_id": stale.id,
                    "amount": 99,
                }
            ]
            + [
                {
                    "kind": "damage",
                    "target_id": actor.id,
                    "source_id": recent.id,
                    "amount": 1,
                }
                for _ in range(999)
            ]
        )
        fight = self.mock_fight([actor, stale, recent], events=events)

        selected = choose(fight, actor)

        self.assertEqual(events.requested_slice, slice(-256, None, None))
        self.assertEqual(selected["targetId"], recent.id)
        self.assertEqual(selected["observedIncoming"], 1)

    def test_same_xy_and_current_direction_are_noop(self):
        actor = self.actor(-1, 0, (0, 0, 4), direction=1)
        rival = self.actor(10, 1, (0, 0, 9))
        fight = self.mock_fight([actor, rival])
        self.assertIsNone(choose(fight, actor))

        actor.position = (0, 0, 0)
        actor.direction = 1
        rival.position = (1, 0, 0)
        runtime = SimpleNamespace(fight=fight, action_id=3, _flush=lambda: b"flush")
        self.assertEqual(apply(runtime, actor), [])
        self.assertEqual(runtime.action_id, 3)

    def test_carry_relation_receives_the_same_direction_delta(self):
        from wakfu_server.combat_carrying import NativeCarryPair

        carrier = self.actor(-9, 1, (0, 0, 0), direction=0)
        carried = self.actor(-10, 1, (0, 0, 0), direction=5)
        carrier.native_carried_actor_id = carried.id
        carrier.native_carrier_id = None
        carried.native_carrier_id = carrier.id
        carried.native_carried_actor_id = None
        rival = self.actor(7, 0, (0, 1, 0))
        fight = self.mock_fight([carrier, carried, rival])
        pair = NativeCarryPair(
            carrier_id=carrier.id,
            carried_id=carried.id,
            position=carrier.position,
            carried_direction=carried.direction,
            carrier_direction=carrier.direction,
            source_uid=12,
            source_reference=300,
        )
        fight.native_carry_pairs = {carrier.id: pair}
        runtime = SimpleNamespace(fight=fight, action_id=0, _flush=lambda: b"flush")

        packets = apply(runtime, carrier)

        self.assertEqual(packets[0][0], 13494)
        self.assertEqual(carrier.direction, 3)
        self.assertEqual(carried.direction, 0)
        self.assertEqual(fight.native_carry_pairs[carrier.id].carried_direction, 0)

    def test_apply_publishes_zero_cost_cardinal_packet_before_turn_ack(self):
        owner = Actor(7, 0, (1, 0, 0), 40, 6, 3, 1, 1, 7, True)
        npc = Actor(-9, 1, (0, 0, 0), 40, 6, 3, 200, 1)
        owner.effect_stats = {20: 0, 27: 0, 28: 0, 29: 0, 30: 0, 31: 0}
        npc.effect_stats = {20: 160, 48: 0, 27: 0, 28: 0, 29: 0, 30: 0, 31: 0}
        fight = Fight(
            902,
            [owner, npc],
            {owner.position, npc.position},
            {0: {owner.position}, 1: {npc.position}},
        )
        fight.ready(7)
        self.assertIs(fight.current, npc)
        runtime = RuntimeMessages(fight)
        before_resources = (npc.ap, npc.mp)

        cardinal = ModuleType("wakfu_server.combat.combat_cast_facing")
        cardinal.cast_direction = lambda dx, dy, *, diagonals: 1 if dx > 0 else 5
        with patch.dict(sys.modules, {cardinal.__name__: cardinal}):
            packets = runtime.end_server_turn(npc.id, fight.turn_id)

        opcodes = [opcode for opcode, _ in packets]
        self.assertLess(opcodes.index(13494), opcodes.index(12502))
        import struct

        _, action_id, _, actor_id, direction = struct.unpack(
            ">iiiqB", packets[opcodes.index(13494)][1]
        )
        self.assertEqual((actor_id, direction), (npc.id, 1))
        self.assertGreater(action_id, 0)
        event = next(event for event in fight.events if event.get("defensive_facing"))
        self.assertEqual((event["cost_ap"], event["cost_mp"]), (0, 0))
        self.assertEqual((npc.ap, npc.mp), before_resources)
        self.assertEqual(npc.direction, direction)

    def test_end_callback_replacement_and_movement_use_reacquired_registered_actor(
        self,
    ):
        owner = Actor(7, 0, (2, 0, 0), 40, 6, 3, 1, 1, 7, True)
        npc = Actor(-9, 1, (0, 0, 0), 40, 6, 3, 200, 1)
        owner.effect_stats = {20: 0, 27: 0, 28: 0, 29: 0, 30: 0, 31: 0}
        npc.effect_stats = {20: 160, 48: 0, 27: 0, 28: 0, 29: 0, 30: 0, 31: 0}
        cells = {(x, 0, 0) for x in range(4)}
        fight = Fight(
            903, [owner, npc], cells, {0: {owner.position}, 1: {npc.position}}
        )
        fight.ready(7)

        def callback(original, **_kwargs):
            candidate = deepcopy(original)
            # Model an end-effect's already-certified native displacement.
            candidate.actors[owner.id].position = (3, 0, 0)
            return candidate, ()

        runtime = RuntimeMessages(fight, turn_end_provider=callback)
        old_npc = runtime.fight.actors[npc.id]

        cardinal = ModuleType("wakfu_server.combat.combat_cast_facing")
        cardinal.cast_direction = lambda dx, dy, *, diagonals: 1 if dx > 0 else 5
        evidence = {
            "actorId": npc.id,
            "turnId": runtime.fight.turn_id,
            "stateRevision": runtime.fight.sequence,
            "actors": [
                {"id": npc.id, "position": npc.position},
                {"id": owner.id, "position": owner.position},
            ],
            "visibleActorIds": [npc.id, owner.id],
            "rivals": [
                {
                    "actorId": owner.id,
                    "actorHpLoss": 40,
                    "actorLoss": 40,
                    "actorLethal": True,
                }
            ],
        }
        with patch.dict(sys.modules, {cardinal.__name__: cardinal}):
            packets = runtime.end_server_turn(
                npc.id, runtime.fight.turn_id, defensive_facing=evidence
            )

        self.assertIs(runtime.fight.actors[npc.id], old_npc)
        self.assertEqual(runtime.fight.actors[owner.id].position, (3, 0, 0))
        facing = next(
            event for event in runtime.fight.events if event.get("defensive_facing")
        )
        self.assertEqual(facing["defensive_facing"]["targetId"], owner.id)
        self.assertEqual(facing["defensive_facing"]["distance"], 3)
        self.assertEqual(facing["defensive_facing"]["certifiedLoss"], 0)
        self.assertLess(
            [op for op, _ in packets].index(13494),
            [op for op, _ in packets].index(12502),
        )

    def test_end_callback_stats_only_change_invalidates_same_position_forecast(self):
        npc = Actor(-9, 1, (0, 0, 0), 40, 6, 3, 300, 1)
        first = Actor(7, 0, (1, 0, 0), 40, 6, 3, 100, 1, 7, True)
        stronger_after_callback = Actor(8, 0, (2, 0, 0), 40, 6, 3, 90, 1, 8, True)
        npc.effect_stats = {20: 0, 48: 0, 27: 0, 28: 0, 29: 0, 30: 0, 31: 0}
        first.effect_stats = {20: 30, 48: 0, 27: 0, 28: 0, 29: 0, 30: 0, 31: 0}
        stronger_after_callback.effect_stats = {
            20: 1,
            48: 0,
            27: 0,
            28: 0,
            29: 0,
            30: 0,
            31: 0,
        }
        for actor in (npc, first, stronger_after_callback):
            actor.effect_maxima = {2: 10, 3: 4}
        cells = {actor.position for actor in (npc, first, stronger_after_callback)}
        fight = Fight(
            904,
            [npc, first, stronger_after_callback],
            cells,
            {0: {first.position, stronger_after_callback.position}, 1: {npc.position}},
        )
        fight.ready(7)
        fight.ready(8)
        self.assertIs(fight.current, npc)

        def callback(original, **_kwargs):
            candidate = deepcopy(original)
            candidate.actors[stronger_after_callback.id].effect_stats[20] = 1000
            # A silent callback snapshot can change stats without emitting an
            # event or moving either target; runtime action identity still changes.
            return candidate, ()

        runtime = RuntimeMessages(fight, turn_end_provider=callback)
        evidence = {
            "actorId": npc.id,
            "turnId": runtime.fight.turn_id,
            "stateRevision": runtime.fight.sequence,
            "actors": [
                {"id": actor.id, "position": actor.position}
                for actor in runtime.fight.actors.values()
            ],
            "visibleActorIds": [npc.id, first.id, stronger_after_callback.id],
            "rivals": [
                {
                    "actorId": first.id,
                    "actorHpLoss": 40,
                    "actorArmorLoss": 0,
                    "actorLoss": 40,
                    "actorLethal": True,
                },
                {
                    "actorId": stronger_after_callback.id,
                    "actorHpLoss": 0,
                    "actorArmorLoss": 0,
                    "actorLoss": 0,
                },
            ],
        }
        self.assertEqual(choose(runtime.fight, npc, evidence)["targetId"], first.id)

        packets = runtime.end_server_turn(
            npc.id, runtime.fight.turn_id, defensive_facing=evidence
        )
        facing = next(
            event for event in runtime.fight.events if event.get("defensive_facing")
        )
        self.assertEqual(
            facing["defensive_facing"]["targetId"], stronger_after_callback.id
        )
        self.assertEqual(
            facing["defensive_facing"]["basis"],
            "native_offensive_characteristics_heuristic",
        )
        self.assertEqual(facing["defensive_facing"]["certifiedLoss"], 0)
        opcodes = [opcode for opcode, _ in packets]
        self.assertLess(opcodes.index(13494), opcodes.index(12502))

    def test_helper_import_has_no_catalog_or_equipment_damage_dependency(self):
        code = (
            "import sys; sys.path.insert(0, 'server'); "
            "from types import SimpleNamespace as N; "
            "from wakfu_server.combat.combat_ai_facing import apply; "
            "a=N(id=-9, team=1, native_fight_affiliation=1, position=(0,0,0), "
            "hp=40, direction=3, controlled=False, effect_stats={20:100,48:0,27:0,28:0,29:0,30:0,31:0}, "
            "effect_maxima={2:10,3:4}, max_ap=10, max_mp=4); "
            "r=N(id=7, team=0, native_fight_affiliation=0, position=(1,0,0), "
            "hp=40, effect_stats={20:0,27:0,28:0,29:0,30:0,31:0}); "
            "f=N(id=1, actors={-9:a,7:r}, events=[], native_carry_pairs={}, "
            "_in_play=lambda actor: actor.hp>0); "
            "f._event=lambda kind, **fields: f.events.append(dict(kind=kind, **fields)); "
            "runtime=N(fight=f, action_id=0, _flush=lambda: b'flush'); "
            "packets=apply(runtime,a); assert packets[0][0]==13494 and a.direction==1; "
            "assert f.events[-1]['cost_ap']==f.events[-1]['cost_mp']==0; "
            "assert 'wakfu_server.native_catalog' not in sys.modules; "
            "assert 'wakfu_server.equipment_damage' not in sys.modules; "
            "assert 'wakfu_server.items.equipment_damage' not in sys.modules"
        )
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).parents[2],
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
