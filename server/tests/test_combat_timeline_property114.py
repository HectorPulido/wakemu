import struct
import unittest
import ast
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace as NS

from wakfu_server.combat_recovery import recovery_packet, timeline
from wakfu_server.combat_state import Actor, Fight


class NativeProperty114TimelineTests(unittest.TestCase):
    def make_fight(self, *, include_normal=True):
        player = Actor(5, 0, (0, 0, 0), 60, 6, 3, 100, 1, 9, True)
        ordinary = Actor(-201, 1, (1, 0, 0), 30, 4, 2, 50, 1)
        beacon = Actor(-200, 1, (2, 0, 0), 30, 0, 0, 75, 1)
        beacon.native_fight_properties = frozenset({114})
        actors = [player, beacon]
        if include_normal:
            actors.append(ordinary)
        fight = Fight(
            190982471,
            actors,
            {actor.position for actor in actors},
            {
                0: {player.position},
                1: {actor.position for actor in actors if actor.team == 1},
            },
        )
        # Initial clock reconstruction is unrelated to the timeline order and
        # otherwise loads spell catalogs; keep this regression catalog-free.
        with patch(
            "wakfu_server.combat_initial_finite_clock_policy.bind_initial_finite_clocks"
        ):
            fight.ready(9)
        return fight

    @staticmethod
    def timeline_parts(raw):
        offset = 15  # round, turn ID, status, deadline
        count = raw[offset]
        order = list(struct.unpack_from(f">{count}q", raw, offset + 1))
        offset += 1 + count * 8
        next_count = raw[offset]
        next_order = list(struct.unpack_from(f">{next_count}q", raw, offset + 1))
        offset += 1 + next_count * 8
        progress_count = raw[offset]
        progress = {}
        offset += 1
        for _ in range(progress_count):
            identity, value = struct.unpack_from(">qh", raw, offset)
            progress[identity] = value
            offset += 10
        turn_index = raw[offset]
        offset += 1
        removed_count = raw[offset]
        offset += 1 + removed_count * 16
        actor_count = raw[offset]
        roster = [
            struct.unpack_from(">qi", raw, offset + 1 + index * 12)[0]
            for index in range(actor_count)
        ]
        return order, next_order, progress, turn_index, roster

    def test_ready_keeps_property114_in_roster_but_excludes_it_from_timeline(self):
        fight = self.make_fight()

        self.assertEqual(set(fight.actors), {5, -200, -201})
        self.assertEqual(fight.order, [5, -201])
        self.assertEqual(set(fight.native_timeline_member_counters), {"5", "-201"})
        self.assertNotIn(-200, fight.order)
        self.assertEqual(fight.actors[-200].turn_count, 0)

    def test_recovery_keeps_property114_roster_entry_without_turn_or_progress(self):
        fight = self.make_fight()
        raw = timeline(fight, deadline_ms=31_000)
        order, next_order, progress, current_index, roster = self.timeline_parts(raw)

        self.assertEqual(order, [5, -201])
        self.assertEqual(next_order, [5, -201])
        self.assertEqual(set(progress), {5, -201})
        self.assertEqual(roster, [5, -200, -201])
        self.assertEqual(order[current_index], fight.current.id)
        self.assertNotIn(-200, order)
        self.assertNotIn(-200, progress)

        opcode, packet = recovery_packet(
            fight, struct.pack(">i", fight.id), deadline_ms=31_000
        )
        self.assertEqual(opcode, 12053)
        self.assertEqual(packet[6:], struct.pack(">BBiBh", 1, 0, 6, 0, len(raw)) + raw)

    def test_property114_actor_never_takes_turn_during_a_complete_round(self):
        fight = self.make_fight(include_normal=False)
        self.assertEqual(fight.order, [5])
        initial_round = fight.native_timeline_round
        # Turn resource refill is independent from the timeline membership
        # contract; keep this one-round scheduler check catalog-free.
        fight._refill_turn_resources = lambda actor: None

        with patch(
            "wakfu_server.combat_initial_finite_clock_policy.bind_initial_finite_clocks"
        ):
            fight._advance()

        self.assertEqual(fight.native_timeline_round, initial_round + 1)
        self.assertEqual(fight.current.id, 5)
        self.assertEqual(fight.actors[-200].turn_count, 0)
        self.assertNotIn("-200", fight.native_timeline_member_counters)

    def test_ordinary_live_actor_without_timeline_membership_remains_invalid(self):
        fight = self.make_fight()
        fight.order.remove(-201)
        fight.native_timeline_member_counters.pop("-201")

        with self.assertRaisesRegex(
            ValueError, "Live actor lacks authoritative timeline membership"
        ):
            timeline(fight, deadline_ms=31_000)


class NativeStateClockProperty114Tests(unittest.TestCase):
    @staticmethod
    def native_state_timeline_from_source():
        source_path = (
            Path(__file__).resolve().parents[1]
            / "wakfu_server"
            / "combat"
            / "combat_native_timing_context.py"
        )
        module = ast.parse(source_path.read_text())
        function = next(
            node
            for node in module.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "native_state_timeline"
        )

        def state_timeline(
            round_number,
            current_actor_id,
            current_actor_index,
            clock_actor_index,
            phase,
        ):
            return NS(
                round_number=round_number,
                current_actor_id=current_actor_id,
                current_actor_index=current_actor_index,
                clock_actor_index=clock_actor_index,
                phase=phase,
            )

        namespace = {"StateTimeline": state_timeline}
        isolated = ast.fix_missing_locations(
            ast.Module(body=[function], type_ignores=[])
        )
        exec(compile(isolated, str(source_path), "exec"), namespace)
        return namespace["native_state_timeline"]

    def fight(self, actors, order):
        return NS(
            phase="active",
            current=actors[order[0]],
            actors=actors,
            order=order,
            turn_index=0,
            native_summon_registrations={},
            native_base_turn_order=None,
            native_timeline_round=1,
            _resolution_depth=0,
        )

    def test_property114_can_be_clock_actor_without_summon_registration(self):
        current = NS(id=7, hp=60, turn_count=1)
        passive = NS(
            id=4875, hp=5000, turn_count=0, native_fight_properties=frozenset({114})
        )
        fight = self.fight({7: current, 4875: passive}, [7])

        result = self.native_state_timeline_from_source()(fight, 4875)

        self.assertEqual(result.clock_actor_index, -1)
        self.assertIn(4875, fight.actors)
        self.assertEqual(fight.native_summon_registrations, {})

    def test_ordinary_actor_missing_from_timeline_still_rejects_clock(self):
        current = NS(id=7, hp=60, turn_count=1)
        ordinary = NS(id=-200, hp=30, turn_count=0, native_fight_properties=frozenset())
        fight = self.fight({7: current, -200: ordinary}, [7])

        with self.assertRaisesRegex(
            ValueError, "Inconsistent eligible fixed actor timeline"
        ):
            self.native_state_timeline_from_source()(fight, -200)


if __name__ == "__main__":
    unittest.main()
