"""Actual shared-fight routing, native codecs and tactical metadata boundaries."""
from collections import deque
from copy import deepcopy
import json
import struct
import unittest

from wakfu_server.combat_shared import Registry, Session, SharedFight
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat import combat_tactical_markers as markers
from wakfu_server.fight_checkpoint_store import snapshot


class TacticalMarkersTests(unittest.TestCase):
    def setUp(self):
        actors = [
            Actor(i, team, pos, 50, 6, 3, 100 - i, 1, owner, True)
            for i, team, pos, owner in (
                (10, 0, (0, 0, 0), 1),
                (11, 0, (1, 0, 0), 1),
                (20, 0, (2, 0, 0), 2),
                (30, 1, (3, 0, 0), 3),
            )
        ]
        self.cells = {(i, 0, 0) for i in range(5)}
        self.fight = Fight(
            77,
            actors,
            self.cells,
            {0: {(0, 0, 0), (1, 0, 0), (2, 0, 0)}, 1: {(3, 0, 0)}},
        )
        self.sessions = {
            i: Session(i, i * 10, "lease" + str(i), 100, 5) for i in (1, 2, 3)
        }
        self.valid = set(self.sessions.values())
        self.registry = Registry(lambda session: session in self.valid)
        self.shared = SharedFight(
            self.fight,
            100,
            5,
            None,
            participants=dict(self.sessions),
            connected={1, 2, 3},
            outboxes={i: deque() for i in (1, 2, 3)},
        )
        self.registry.fights[77] = self.shared

    def action(
        self, opcode=markers.ADD, position=(4, 0, 0), icon=0, owner=1, actor=10, now=100
    ):
        body = struct.pack(">iih", *position)
        if opcode != markers.PING:
            body += bytes((icon,))
        return markers.handle(
            self.registry, self.sessions[owner], 77, actor, opcode, body, now=now
        )

    def test_all_native_icons_add_replace_remove_and_stale_replay(self):
        for icon in range(8):
            added = self.action(icon=icon)
            self.assertEqual(
                added["packets"],
                ((12226, struct.pack(">iiihqBB", 77, 4, 0, 0, 10, icon, 1)),),
            )
            sequence = self.shared.sequence
            self.assertFalse(self.action(icon=icon)["accepted"])
            self.assertEqual(self.shared.sequence, sequence)
        self.action(position=(2, 0, 0), icon=0, owner=2, actor=20)
        self.assertFalse(self.action(markers.REMOVE, icon=0)["accepted"])
        self.assertEqual(self.fight.tactical_markers["0"]["0"]["position"], [2, 0, 0])
        removed = self.action(markers.REMOVE, position=(2, 0, 0), icon=0)
        self.assertEqual(removed["packets"][0][1][-1], 0)
        self.assertNotIn("0", self.fight.tactical_markers["0"])
        self.assertFalse(self.action(markers.REMOVE, position=(2, 0, 0))["accepted"])

    def test_private_team_routing_and_hero_sender_outside_current_turn(self):
        self.shared.ack.arm(3, self.sessions.values())
        ack_before = deepcopy(self.shared.ack.__dict__)
        before = deepcopy(snapshot(self.fight))
        self.action(markers.PING, actor=11)
        expected = ((13788, struct.pack(">iiihq", 77, 4, 0, 0, 11)),)
        self.assertEqual(self.registry.drain(77, self.sessions[1])[0].packets, expected)
        self.assertEqual(self.registry.drain(77, self.sessions[2])[0].packets, expected)
        self.assertEqual(self.registry.drain(77, self.sessions[3]), [])
        after = snapshot(self.fight)
        after.pop("tactical_ping_times")
        self.assertEqual(before, after)
        self.assertEqual(self.shared.ack.__dict__, ack_before)

    def test_ping_five_second_cooldown_per_actor_and_no_replay_on_bootstrap(self):
        self.assertTrue(self.action(markers.PING)["accepted"])
        self.assertFalse(self.action(markers.PING, now=104.999)["accepted"])
        self.assertTrue(self.action(markers.PING, actor=11, now=101)["accepted"])
        self.assertTrue(self.action(markers.PING, now=105)["accepted"])
        self.assertEqual(markers.snapshots(self.registry, self.sessions[2], 77), ())

    def test_every_icon_reaches_sender_and_ally_and_reconnect_excludes_spectator(self):
        for icon in range(8):
            result = self.action(icon=icon)
            for account in (1, 2):
                self.assertEqual(
                    self.registry.drain(77, self.sessions[account])[0].packets,
                    result["packets"],
                )
            self.assertEqual(self.registry.drain(77, self.sessions[3]), [])
        replacement = Session(2, 20, "replacement", 100, 5)
        self.valid.remove(self.sessions[2])
        self.valid.add(replacement)
        self.shared.participants[2] = replacement
        replay = markers.snapshots(self.registry, replacement, 77)
        self.assertEqual([body[-2] for _, body in replay], list(range(8)))
        self.assertTrue(
            all(opcode == 12226 and body[-1] == 1 for opcode, body in replay)
        )
        spectator = Session(4, 40, "spectator", 100, 5)
        self.valid.add(spectator)
        with self.assertRaises(ValueError):
            markers.snapshots(self.registry, spectator, 77)
        result = self.action(markers.REMOVE, icon=7)
        self.assertEqual(
            self.registry.drain(77, replacement)[0].packets, result["packets"]
        )
        self.assertEqual(
            self.registry.drain(77, self.sessions[1])[0].packets, result["packets"]
        )

    def test_snapshot_only_own_team_icons_checkpoint_and_deepcopy_safe(self):
        self.action(icon=7)
        self.action(icon=2, owner=3, actor=30)
        own = markers.snapshots(self.registry, self.sessions[2], 77)
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0][1][-2:], b"\x07\x01")
        self.fight.actors[20].native_fight_properties = frozenset({72})
        self.assertEqual(markers.snapshots(self.registry, self.sessions[2], 77), own)
        state = json.loads(json.dumps(snapshot(self.fight)))
        self.assertEqual(state["tactical_markers"]["0"]["7"]["position"], [4, 0, 0])
        self.shared.fight = deepcopy(self.fight)
        self.assertEqual(markers.snapshots(self.registry, self.sessions[2], 77), own)

    def test_ownership_lease_location_withdrawal_phase_and_native_property_fences(self):
        for mutation in (
            "foreign",
            "stale",
            "location",
            "withdrawn",
            "finished",
            "disabled",
        ):
            with self.subTest(mutation=mutation):
                self.setUp()
                actor = 10
                if mutation == "foreign":
                    actor = 30
                if mutation == "stale":
                    self.valid.remove(self.sessions[1])
                if mutation == "location":
                    self.shared.map_id = 101
                if mutation == "withdrawn":
                    self.shared.withdrawals[1] = True
                if mutation == "finished":
                    self.fight.phase = "finished"
                if mutation == "disabled":
                    self.fight.actors[10].native_fight_properties = frozenset({72})
                before = self.shared.sequence
                with self.assertRaises(ValueError):
                    self.action(actor=actor)
                self.assertEqual(self.shared.sequence, before)
                self.assertFalse(any(self.shared.outboxes.values()))

    def test_cell_bounds_altitude_and_malformed_packets_are_rejected_without_delivery(
        self,
    ):
        for position in ((4, 0, 1), (100000, 0, 0)):
            with self.assertRaises(ValueError):
                self.action(position=position)
        for opcode, body in (
            (markers.PING, b""),
            (markers.ADD, b"\0" * 10),
            (markers.ADD, struct.pack(">iihB", 4, 0, 0, 8)),
            (1, b"\0" * 10),
            (markers.REMOVE, b"\0" * 12),
        ):
            with self.assertRaises(ValueError):
                markers.handle(self.registry, self.sessions[1], 77, 10, opcode, body)
        self.assertEqual(self.shared.sequence, 0)

    def test_active_and_dead_participant_signal_without_turn_or_resource_changes(self):
        self.fight.phase = "active"
        self.fight.actors[10].hp = 0
        before = (
            self.fight.actors[10].hp,
            self.fight.actors[10].ap,
            self.fight.actors[10].mp,
        )
        self.assertTrue(self.action()["accepted"])
        self.assertEqual(
            before,
            (
                self.fight.actors[10].hp,
                self.fight.actors[10].ap,
                self.fight.actors[10].mp,
            ),
        )
