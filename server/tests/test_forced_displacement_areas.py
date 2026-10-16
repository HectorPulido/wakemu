"""Forced movement dispatches area events after committing its parent packet."""

import os
import random
import struct
import unittest

import test_combat_displacement as fixtures
from wakfu_server.combat_effect_dispatch import EffectInvocation


class ForcedDisplacementAreaCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.NativeDisplacementTests.setUpClass()

    def setUp(self):
        self.base = fixtures.NativeDisplacementTests()
        self.base.setUp()
        self.events = []

        class AreaEvents:
            def __init__(inner):
                inner.callbacks = []

            def movement(inner, actor_id, *, from_cell, to_cell):
                inner.callbacks.append((actor_id, from_cell, to_cell))
                self.events.append(("movement", actor_id, from_cell, to_cell))

        self.area_events = AreaEvents()
        self.bind_events()

    def bind_events(self):
        self.base.handler.area_events = self.area_events

        class Packets(list):
            def append(inner, packet):
                self.events.append(("packet", packet[0]))
                super().append(packet)

        packets = Packets()
        self.base.packets = packets
        self.base.handler.packets = packets

    def run_effect(self, reference, *, target=-7, cell=(4, 0, 0)):
        return self.base.handler(
            self.base.effects[str(reference)],
            None,
            EffectInvocation(reference, 1, 7, target, cell),
        )

    def test_push_pull_teleport_and_swap_notify_after_their_parent_packet(self):
        cases = (
            (358000, -7, (4, 0, 0)),  # push
            (326690, -7, (0, 0, 0)),  # pull
            (351394, -7, (3, 3, 0)),  # target teleport
            (349546, -7, (4, 0, 0)),  # swap
        )
        for reference, target, cell in cases:
            with self.subTest(reference=reference):
                self.base.setUp()
                self.events.clear()
                self.area_events.callbacks.clear()
                self.bind_events()
                before = {
                    i: actor.position for i, actor in self.base.preview.actors.items()
                }
                self.run_effect(reference, target=target, cell=cell)
                moved = {
                    i: actor.position
                    for i, actor in self.base.preview.actors.items()
                    if actor.position != before[i]
                }
                self.assertTrue(moved)
                self.assertEqual(
                    list(self.area_events.callbacks),
                    [(i, before[i], position) for i, position in moved.items()],
                )
                self.assertEqual(self.events[0], ("packet", 12613))
                self.assertTrue(all(row[0] == "movement" for row in self.events[1:]))
                self.area_events.callbacks.clear()

    def test_noop_and_callback_moving_target_keep_native_final_position(self):
        # A same-cell teleport emits its native phases but has no movement event.
        self.base.preview.actors[-7].position = (3, 3, 0)
        fixtures.install_synthetic_qi_occupancy(self.base.preview)
        self.run_effect(351394, cell=(3, 3, 0))
        self.assertEqual(self.area_events.callbacks, [])

        # A callback may recursively move the actor. The outer displacement
        # must not restore its earlier endpoint after returning from the event.
        self.base.setUp()
        self.area_events.callbacks.clear()
        self.bind_events()
        original = self.area_events.movement

        def move_during_event(actor_id, *, from_cell, to_cell):
            original(actor_id, from_cell=from_cell, to_cell=to_cell)
            if actor_id == -7:
                self.base.preview.actors[-7].position = (6, 0, 0)

        self.area_events.movement = move_during_event
        self.run_effect(358000)
        self.assertEqual(self.base.preview.actors[-7].position, (6, 0, 0))


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class RealRepulsionTrapForcedDisplacementTests(unittest.TestCase):
    """An original 778 trap reacts to a real forced displacement."""

    def test_push_through_real_trap_uses_final_recursive_position_and_retires(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_server_spell import server_runtime
        from tools.class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_effect_area import native_effect_areas
        from wakfu_server.combat_effect_area_geometry import registered_area_cells
        from wakfu_server.combat_qi_fight import move_registered_actor
        from wakfu_server.combat_displacement import NativeDisplacementHandler

        fight, characters, monster, decks = TwoXelorFixture().fixture(
            level=200,
            caster_breed=4,
            compact_arena=False,
            enemy_position=(-5, -7, -1),
        )
        common = dict(
            player_characters=characters,
            deck_blobs=decks,
            rng=random.Random(4),
        )
        uid = granted_spells(fight, 7)[5182]["uid"]
        factory, adapter = server_runtime(
            characters[7],
            {-7: monster},
            decks[7],
            action_id=1,
            critical=False,
            **common,
        )
        selection = eligible_cast_targets(
            fight,
            characters[7],
            decks[7],
            uid,
            adapter=adapter,
            actor_id=7,
            limit=512,
            maximum_eligible=16,
            line_of_sight=lambda *args: True,
        )
        trap_cast = None
        for choice in selection["eligible"]:
            candidate = prepare_server_spell(
                struct.pack(">qqiih", 7, uid, *choice["target"]),
                characters[7],
                {-7: monster},
                fight,
                3,
                decks[7],
                action_id=1,
                line_of_sight=lambda *args: True,
                critical=False,
                **common,
            )
            traps = [
                row
                for row in candidate.fight.native_effect_areas.values()
                if row.get("reference") == 778 and row.get("owner_id") == 7
            ]
            if len(traps) != 1:
                continue
            trap = traps[0]
            cells = set(
                registered_area_cells(
                    native_effect_areas()["778"], trap["cell"], trap["direction"]
                )
            )
            trap_cast = candidate
            break
        self.assertIsNotNone(trap_cast, selection)
        fight = trap_cast.fight
        trap = next(
            row
            for row in fight.native_effect_areas.values()
            if row.get("reference") == 778
        )
        parent_uid = trap["effect_uid"]
        trap_cells = set(
            registered_area_cells(
                native_effect_areas()["778"], trap["cell"], trap["direction"]
            )
        )
        target = fight.actors[-7]
        # Find a legal real push whose committed endpoint enters the registered
        # trap footprint. Geometry is checked against the actual native cells.
        dispatcher, packets = factory(fight, dict(spell_id=6266, evaluation_level=1))
        push = dispatcher.effects["358000"]
        handler = NativeDisplacementHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=fight.allocate_effect_uid,
            authority=factory.displacement_authority,
            selected_surface=factory.contexts.selected_surface,
        )
        handler.area_events = dispatcher.native_area_events
        # Find a real neighboring start cell whose catalog push endpoint enters
        # this trap. Probe the native handler with callbacks disabled, restore
        # the actor through QI after every probe, then perform one live push.
        before = target.position
        occupied = {
            actor.position for actor in fight.actors.values() if actor.id != target.id
        }
        owner = fight.actors[7]
        caster_cells = [
            cell
            for cell in fight.walkable
            if cell[0] < min(x for x, _ in trap_cells)
            and cell[1] == trap["cell"][1]
            and cell not in occupied
            and cell != owner.position
        ]
        self.assertTrue(caster_cells, (trap["cell"], sorted(trap_cells)))
        caster_cell = min(
            caster_cells,
            key=lambda cell: (
                abs(cell[0] - owner.position[0]) + abs(cell[1] - owner.position[1]),
                cell,
            ),
        )
        move_registered_actor(fight, owner, caster_cell)
        starts = sorted(
            {
                (x + dx, y + dy, trap["cell"][2])
                for x, y in trap_cells
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if (x + dx, y + dy, trap["cell"][2]) in fight.walkable
                and (x + dx, y + dy, trap["cell"][2]) not in occupied
                and (x + dx, y + dy) not in trap_cells
            }
        )
        selected_start = None
        area_events = handler.area_events
        handler.area_events = None
        for start in starts:
            move_registered_actor(fight, target, start)
            try:
                handler(push, None, EffectInvocation(358000, 1, 7, -7, start))
            except (ValueError, KeyError):
                pass
            else:
                if target.position != start and target.position[:2] in trap_cells:
                    selected_start = start
            move_registered_actor(fight, target, before)
            if selected_start is not None:
                break
        handler.area_events = area_events
        self.assertIsNotNone(selected_start, (trap["cell"], sorted(trap_cells), starts))
        move_registered_actor(fight, target, selected_start)
        before = target.position
        self.assertTrue(handler(push, None, EffectInvocation(358000, 1, 7, -7, before)))
        self.assertNotIn(target.position[:2], trap_cells)
        self.assertNotEqual(target.position, before)
        self.assertEqual(
            len(
                [
                    row
                    for row in fight.native_effect_areas.values()
                    if row.get("reference") == 778
                ]
            ),
            0,
        )
        self.assertNotIn(parent_uid, fight.native_owned_area_effects)
        self.assertNotIn(parent_uid, fight.native_retained_records)
        self.assertEqual(
            sum(
                opcode == 13560
                and len(body) >= 16
                and struct.unpack(">qq", body[-16:]) == (7, parent_uid)
                for opcode, body in packets
            ),
            1,
        )
        self.assertTrue(any(opcode == 12613 for opcode, _ in packets))
