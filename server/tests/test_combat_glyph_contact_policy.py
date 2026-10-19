"""Content-qualified movement consumption for the native cocoon marker."""
from random import Random
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_area_contact_policy import permits_ally_contact_consumption
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_movement_runtime import apply_ai
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import server_runtime

import test_combat_effect_area_events as area_event_tests
import test_larva_glyph_movement_integration as cocoon_tests


class GlyphContactPolicyTests(unittest.TestCase):
    def test_actual_signature_is_narrow_and_nonmatching_glyph_keeps_ally_guard(self):
        row = dict(native_area_contract="faY", remaining_activations=1)
        definition = dict(
            type="GLYPH",
            raw_bde=1,
            raw_bdf=0,
            native_shape_class="anD",
            native_shape_description="point",
            shape_parameters=[],
            entry_masks=[10001],
            exit_masks=[],
            native_area_properties=[1, 2],
            effect_ids=[183348],
        )
        effects = {
            "183348": dict(effect_class=400, criteria="", children=[], parameters=[])
        }
        self.assertTrue(permits_ally_contact_consumption(row, definition, effects))

        # The existing simplified 1474 same-affiliation unit fixture does not
        # carry 411's complete one-charge, empty-root contact capability.
        feca_runtime, feca_row, calls = area_event_tests.AreaEventTests().fixture()
        feca_definition = feca_runtime.definitions["1474"]
        feca_definition["native_area_properties"] = (1, 2)
        self.assertFalse(
            permits_ally_contact_consumption(feca_row, feca_definition, {})
        )
        for changed in (
            dict(remaining_activations=2),
            dict(native_area_contract="faN"),
        ):
            candidate = dict(row, **changed)
            self.assertFalse(
                permits_ally_contact_consumption(candidate, definition, effects)
            )

        feca_row.update(
            remaining_activations=1,
            native_fight_affiliation=0,
            native_fight_affiliation_source="faV.j(PV).bcM",
        )
        target = feca_runtime.fight.actors[8]
        target.native_is_amO = True
        target.native_fight_affiliation = 0
        feca_event = feca_definition["entry_masks"][0]
        self.assertEqual(
            feca_runtime._deliver_event(
                feca_row, feca_definition, target, feca_event, movement_contact=True
            ),
            (False,),
        )
        self.assertEqual((feca_row["remaining_activations"], calls), (1, []))

    def test_real_npc_body_only_entry_consumes_411_once_through_ai_movement(self):
        (
            character,
            monster,
            fight,
            deck,
            dispatcher,
        ) = cocoon_tests.LarvaGlyphMovementIntegrationTests().fixture(target_distance=5)
        actor = fight.actors[-7]
        self.assertGreaterEqual(actor.physical_radius, 1)
        origin = tuple(actor.position)
        occupied = {
            tuple(other.position)
            for other in fight.actors.values()
            if other.id != actor.id and other.hp > 0
        }
        from wakfu_server.combat_qi_movement import movement_blocked_cells

        blocked = movement_blocked_cells(fight, actor, fight.walkable)
        destination = next(
            end
            for start, end in sorted(fight.edges)
            if tuple(start) == origin
            and tuple(end) in fight.walkable
            and tuple(end) not in occupied
            and (blocked is None or tuple(end) not in blocked)
            and abs(end[0] - origin[0]) + abs(end[1] - origin[1]) == 1
            and end[2] == origin[2]
        )
        body_cell = next(
            cell
            for cell in sorted(fight.walkable)
            if cell != origin
            and cell != destination
            and cell not in occupied
            and cell[2] == destination[2]
            and max(abs(cell[0] - destination[0]), abs(cell[1] - destination[1]))
            <= actor.physical_radius
        )
        row = cocoon_tests.LarvaGlyphMovementIntegrationTests().install_glyph(
            fight, dispatcher, body_cell
        )
        definition = dispatcher.native_area_events._definition(row)
        self.assertFalse(
            permits_ally_contact_consumption(
                row,
                dispatcher.native_area_events.definitions["1474"],
                dispatcher.effects,
            )
        )
        from wakfu_server.combat_effect_area_geometry import (
            contains_area_actor,
            contains_area_cell,
        )

        self.assertFalse(contains_area_cell(row, destination))
        self.assertTrue(contains_area_actor(row, destination, actor.physical_radius))

        # Neither an ordinary callback nor an already-inside event may use
        # the contact exception. The real AI movement wrapper marks only its
        # actual 10001 step callback as movement contact.
        self.assertEqual(
            dispatcher.native_area_events._deliver_event(row, definition, actor, 10001),
            (False,),
        )
        self.assertEqual(
            dispatcher.native_area_events._deliver_event(
                row, definition, actor, 10008, movement_contact=True
            ),
            (),
        )
        self.assertEqual(row["remaining_activations"], 1)

        # Select this genuine registered NPC's turn in the fixture; the
        # movement itself goes through apply_ai -> server_move -> native area
        # preparation/commit, with the installed native map edges and actor.
        fight.turn_index = fight.order.index(actor.id)
        fight._begin_turn()
        runtime = RuntimeMessages(fight, stats_serializer=lambda current: b"")
        rng = Random(0)

        def area_provider(preview, **boundary):
            return prepare_area_movement(
                character,
                {-7: monster},
                preview,
                deck,
                rng=rng,
                **boundary,
            )

        with patch(
            "wakfu_server.combat_ai.plan",
            return_value={"path": [destination], "attack": None},
        ):
            packets, result = apply_ai(
                runtime,
                lambda current: b"",
                direction=actor.direction,
                area_provider=area_provider,
            )

        self.assertEqual(result.get("path"), [destination], repr(result))
        self.assertIn("event", result, repr(result))
        self.assertEqual(result["event"]["path"], [destination])
        self.assertEqual(tuple(runtime.fight.actors[actor.id].position), destination)
        self.assertNotIn(row["uid"], runtime.fight.native_effect_areas)
        retirements = [
            struct.unpack(">iiiq", payload)[3]
            for opcode, payload in packets
            if opcode == 13726
            and len(payload) == struct.calcsize(">iiiq")
            and struct.unpack(">iiiq", payload)[3] == row["uid"]
        ]
        self.assertEqual(len(retirements), 1)
        self.assertTrue(
            any(opcode in (12613, 13497) for opcode, _ in packets),
            "The native 411 entry root did not execute",
        )

        # A fresh 411 centered on the next step consumes on center entry too.
        current = runtime.fight.actors[actor.id]
        occupied = {
            tuple(other.position)
            for other in runtime.fight.actors.values()
            if other.id != current.id and other.hp > 0
        }
        blocked = movement_blocked_cells(runtime.fight, current, runtime.fight.walkable)
        center_destination = next(
            end
            for start, end in sorted(runtime.fight.edges)
            if tuple(start) == tuple(current.position)
            and tuple(end) in runtime.fight.walkable
            and tuple(end) not in occupied
            and (blocked is None or tuple(end) not in blocked)
            and abs(end[0] - current.position[0]) + abs(end[1] - current.position[1])
            == 1
            and end[2] == current.position[2]
        )
        next_factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=runtime.action_id,
            critical=False,
            rng=Random(0),
        )
        center_dispatcher, _ = next_factory(
            runtime.fight, {"native_retained_container": {"present": False}}
        )
        center_row = cocoon_tests.LarvaGlyphMovementIntegrationTests().install_glyph(
            runtime.fight, center_dispatcher, tuple(center_destination)
        )
        center_definition = center_dispatcher.native_area_events._definition(center_row)
        self.assertTrue(contains_area_cell(center_row, center_destination))
        with patch(
            "wakfu_server.combat_ai.plan",
            return_value={"path": [center_destination], "attack": None},
        ):
            center_packets, center_result = apply_ai(
                runtime,
                lambda current: b"",
                direction=current.direction,
                area_provider=area_provider,
            )
        self.assertEqual(center_result["event"]["path"], [center_destination])
        self.assertNotIn(center_row["uid"], runtime.fight.native_effect_areas)
        center_retirements = [
            struct.unpack(">iiiq", payload)[3]
            for opcode, payload in center_packets
            if opcode == 13726 and len(payload) == struct.calcsize(">iiiq")
        ]
        self.assertEqual(center_retirements.count(center_row["uid"]), 1)
        self.assertEqual(retirements.count(row["uid"]), 1)

        # A fresh movement-event pass after retirement has no row to replay.
        replay_factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=runtime.action_id,
            critical=False,
            rng=Random(0),
        )
        replay_dispatcher, replay_packets = replay_factory(
            runtime.fight, {"native_retained_container": {"present": False}}
        )
        replay_destination = next(
            cell
            for cell in sorted(runtime.fight.walkable)
            if cell != center_destination and cell not in occupied
        )
        replay_result = replay_dispatcher.native_area_events.movement(
            actor.id,
            from_cell=tuple(center_destination),
            to_cell=tuple(replay_destination),
        )
        self.assertEqual(replay_result, ((), (), ()))
        self.assertEqual(replay_packets, [])
        self.assertNotIn(center_row["uid"], runtime.fight.native_effect_areas)
