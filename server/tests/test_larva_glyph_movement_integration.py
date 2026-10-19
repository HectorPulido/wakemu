"""Native ref411 entry via paid movement and Steamer forced displacement."""
from copy import deepcopy
from random import Random
import struct
import unittest

import test_combat_spell_transaction as spell_fixtures
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_effect_area_targets import area_targets
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import server_runtime
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class LarvaGlyphMovementIntegrationTests(unittest.TestCase):
    def fixture(self, *, target_distance=3, target_ref=2157, target_level=23):
        # These are fight368's real Shin Larva owner profile and level. The
        # test isolates cocoon entry instead of requiring the entire dungeon.
        (
            character,
            monster,
            fight,
        ) = spell_fixtures.SpellTransactionTests().native_server_fixture(
            16,
            23,
            native_qi=True,
            target_ref=target_ref,
            target_level=target_level,
            target_distance=target_distance,
        )
        deck = encode_deck()
        factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=2,
            critical=False,
            rng=Random(0),
        )
        dispatcher, packets = factory(
            fight, {"native_retained_container": {"present": False}}
        )
        dispatcher.native_witness_packets = packets
        return character, monster, fight, deck, dispatcher

    def install_glyph(self, fight, dispatcher, cell):
        # Actual native producer, not a fabricated area or target type flag.
        before = set(fight.native_effect_areas)
        with fight.effect_resolution():
            dispatcher.execute(
                EffectInvocation(
                    183360,
                    1,
                    -7,
                    None,
                    cell,
                    native_retained_container={"present": False},
                )
            )
        rows = [
            row
            for uid, row in fight.native_effect_areas.items()
            if uid not in before and row["reference"] == 411
        ]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(tuple(row["cell"]), cell)
        self.assertEqual(row["remaining_activations"], 1)
        self.assertEqual(row["native_fight_affiliation"], 1)
        return row

    def test_paid_player_step_executes_real_enemy_glyph_and_publishes_atomically(self):
        character, monster, fight, deck, dispatcher = self.fixture()
        actor = fight.actors[7]
        destination = (actor.position[0] + 1, *actor.position[1:])
        self.assertIn((actor.position, destination), fight.edges)
        row = self.install_glyph(fight, dispatcher, destination)
        runtime = RuntimeMessages(fight)
        before = snapshot(fight)
        before_mp = actor.mp
        rng = Random(9)

        def area_provider(preview, **boundary):
            return prepare_area_movement(
                character,
                {-7: monster},
                preview,
                deck,
                rng=rng,
                **boundary,
            )

        request = struct.pack(">qiih", actor.id, *destination)

        def fail_final_serializer(candidate):
            if candidate.position == destination:
                raise ValueError("glyph final serialization failure")
            return b"before-step"

        with self.assertRaisesRegex(ValueError, "glyph final serialization failure"):
            apply_client(
                runtime, 3, request, fail_final_serializer, area_provider=area_provider
            )
        self.assertTrue(snapshot(fight) == before, "Failed move mutated source")
        self.assertFalse(fight.native_effect_areas[row["uid"]]["native_qq_bhi"])
        self.assertEqual(runtime.action_id, 0)
        packets, event = apply_client(
            runtime,
            3,
            request,
            lambda candidate: b"owned-final-state",
            area_provider=area_provider,
        )
        self.assertEqual(event["path"], [destination])
        self.assertEqual(fight.actors[7].position, destination)
        self.assertLess(fight.actors[7].mp, before_mp)
        self.assertNotIn(row["uid"], fight.native_effect_areas)
        # The server retires a successfully spent finite area after its entry
        # children settle, so later spell selection cannot reuse it.
        self.assertNotIn(row["uid"], {area.id for area in area_targets(fight)})
        checkpoint = snapshot(fight)
        self.assertNotIn(str(row["uid"]), checkpoint["native_effect_areas"])
        self.assertNotIn(str(row["uid"]), checkpoint["native_retired_area_managers"])
        removal_uids = [
            struct.unpack(">iiiq", payload)[3]
            for opcode, payload in packets
            if opcode == 13726
        ]
        self.assertEqual(removal_uids.count(row["uid"]), 1)
        self.assertTrue(
            any(opcode in (12613, 13497) for opcode, _ in packets),
            "Real glyph child execution was not published",
        )
        self.assertFalse(hasattr(fight.actors[7], "native_is_amO"))

    def test_successful_null_target_charge_retires_finite_glyph(self):
        _, _, fight, _, dispatcher = self.fixture()
        actor = fight.actors[7]
        cell = next(
            candidate
            for candidate in sorted(fight.walkable)
            if candidate != tuple(actor.position)
        )
        row = self.install_glyph(fight, dispatcher, cell)
        definition = dispatcher.native_area_events._definition(row)
        with fight.effect_resolution():
            self.assertTrue(
                dispatcher.native_area_events._activate(row, definition, None)
            )
        self.assertNotIn(row["uid"], fight.native_effect_areas)
        removals = [
            struct.unpack(">iiiq", payload)[3]
            for opcode, payload in dispatcher.native_witness_packets
            if opcode == 13726
        ]
        self.assertEqual(removals.count(row["uid"]), 1)

    def test_one_paid_path_can_activate_two_distinct_cocoons_once_each(self):
        character, monster, fight, deck, dispatcher = self.fixture()
        actor = fight.actors[7]
        occupied = {
            tuple(other.position)
            for other in fight.actors.values()
            if other.id != actor.id and other.hp > 0
        }
        from wakfu_server.combat_qi_movement import movement_blocked_cells

        blocked = movement_blocked_cells(fight, actor, fight.walkable)
        outgoing = {}
        for origin, destination in fight.edges:
            outgoing.setdefault(tuple(origin), set()).add(tuple(destination))
        path = next(
            (
                (first, second)
                for first in sorted(outgoing.get(tuple(actor.position), ()))
                for second in sorted(outgoing.get(first, ()))
                if first != second
                and first not in occupied
                and second not in occupied
                and (blocked is None or first not in blocked and second not in blocked)
            ),
            None,
        )
        self.assertIsNotNone(path, "Fixture has no clear two-step native route")
        first, second = path
        first_area = self.install_glyph(fight, dispatcher, first)
        second_area = self.install_glyph(fight, dispatcher, second)
        third = next(
            cell
            for cell in sorted(fight.walkable, reverse=True)
            if cell not in occupied and cell not in (first, second)
        )
        unrelated_area = self.install_glyph(fight, dispatcher, third)
        runtime = RuntimeMessages(fight)
        rng = Random(9)

        def area_provider(preview, **boundary):
            return prepare_area_movement(
                character,
                {-7: monster},
                preview,
                deck,
                rng=rng,
                **boundary,
            )

        packets, event = apply_client(
            runtime,
            3,
            struct.pack(">q", actor.id)
            + struct.pack(">iih", *first)
            + struct.pack(">iih", *second),
            lambda candidate: b"owned-final-state",
            area_provider=area_provider,
        )

        self.assertEqual(event["path"], [first, second])
        self.assertEqual(fight.actors[7].position, second)
        for area in (first_area, second_area):
            self.assertNotIn(area["uid"], fight.native_effect_areas)
        removal_uids = [
            struct.unpack(">iiiq", payload)[3]
            for opcode, payload in packets
            if opcode == 13726
        ]
        self.assertEqual(removal_uids.count(first_area["uid"]), 1)
        self.assertEqual(removal_uids.count(second_area["uid"]), 1)
        self.assertEqual(removal_uids.count(unrelated_area["uid"]), 0)
        self.assertIn(unrelated_area["uid"], fight.native_effect_areas)
        self.assertTrue(any(opcode in (12613, 13497) for opcode, _ in packets))

    def test_native_hatch_5798_does_not_hatch_spent_cocoon_underfoot(self):
        """Reproduce the reported server bug with real 411 registrations.

        The exact 183362 root is executed after a paid player stomp. User
        behavior requires the spent cocoon not to hatch under the player. The
        the server must retire the spent Qq after its successful final
        activation so IsSpecificArea(411) only sees the fresh cocoon.
        """
        character, monster, fight, deck, dispatcher = self.fixture()
        actor = fight.actors[7]
        occupied = {
            tuple(other.position)
            for other in fight.actors.values()
            if other.id != actor.id and other.hp > 0
        }
        from wakfu_server.combat_qi_movement import movement_blocked_cells

        blocked = movement_blocked_cells(fight, actor, fight.walkable)
        outgoing = {}
        for origin, destination in fight.edges:
            outgoing.setdefault(tuple(origin), set()).add(tuple(destination))
        path = next(
            (
                (first, second)
                for first in sorted(outgoing.get(tuple(actor.position), ()))
                for second in sorted(outgoing.get(first, ()))
                if first != second
                and first not in occupied
                and second not in occupied
                and (blocked is None or first not in blocked and second not in blocked)
            ),
            None,
        )
        self.assertIsNotNone(path, "Fixture has no clear native two-cell path")
        spent_cell, fresh_cell = path
        spent = self.install_glyph(fight, dispatcher, spent_cell)
        fresh = self.install_glyph(fight, dispatcher, fresh_cell)
        runtime = RuntimeMessages(fight)
        rng = Random(9)

        def area_provider(preview, **boundary):
            return prepare_area_movement(
                character,
                {-7: monster},
                preview,
                deck,
                rng=rng,
                **boundary,
            )

        movement_packets, event = apply_client(
            runtime,
            3,
            struct.pack(">qiih", actor.id, *spent_cell),
            lambda candidate: b"owned-final-state",
            area_provider=area_provider,
        )
        self.assertEqual(event["path"], [spent_cell])
        self.assertEqual(fight.actors[7].position, spent_cell)
        self.assertNotIn(spent["uid"], fight.native_effect_areas)
        self.assertNotIn(spent["uid"], fight.native_retired_area_managers)
        stomp_removals = [
            struct.unpack(">iiiq", payload)[3]
            for opcode, payload in movement_packets
            if opcode == 13726
        ]
        self.assertEqual(stomp_removals.count(spent["uid"]), 1)
        self.assertEqual(
            fight.native_effect_areas[fresh["uid"]]["remaining_activations"], 1
        )

        # State1574's native class426 runner casts spell5798, whose actual
        # native-spell-casting root is 183362. Invoke that exact root directly
        # to isolate its real selector and children without granting 5798.
        before_ids = set(fight.actors)
        with fight.effect_resolution():
            dispatcher.execute(
                EffectInvocation(
                    183362,
                    fight.actors[-7].effective_level,
                    -7,
                    None,
                    tuple(fight.actors[-7].position),
                    native_retained_container={"present": False},
                )
            )

        new_larvae = [
            candidate
            for identity, candidate in fight.actors.items()
            if identity not in before_ids
            and isinstance(candidate.native_summon_source, dict)
            and candidate.native_summon_source.get("ref") == 735
        ]
        hatch_packets = dispatcher.native_witness_packets
        print(
            "native hatch witness",
            dict(
                spent_cell=spent_cell,
                fresh_cell=fresh_cell,
                spent_active=spent["uid"] in fight.native_effect_areas,
                fresh_active=fresh["uid"] in fight.native_effect_areas,
                larvae=[(candidate.id, candidate.position) for candidate in new_larvae],
                hatch_opcodes=[opcode for opcode, _ in hatch_packets],
            ),
        )
        self.assertEqual(
            {tuple(candidate.position) for candidate in new_larvae},
            {fresh_cell},
            "A spent cocoon must not hatch a larva under the stomping player",
        )
        self.assertEqual(len(new_larvae), 1)
        self.assertNotIn(spent["uid"], fight.native_effect_areas)
        self.assertNotIn(fresh["uid"], fight.native_effect_areas)
        retired_area_uids = {
            struct.unpack(">iiiq", payload)[3]
            for opcode, payload in hatch_packets
            if opcode == 13726
        }
        self.assertEqual(
            retired_area_uids,
            {fresh["uid"]},
            "Only the fresh cocoon is selected and retired by the hatch root",
        )

    def test_real_corriente_push_enters_allied_larva_glyph_without_spending_charge(
        self,
    ):
        # Fight368's actual pushed recipient was ref123, not the protected
        # Shin Larva boss. Isolate the native glyph constructor on that allied
        # NPC owner: this is an effect fixture, not a claim of its legal deck.
        character, monster, fight, deck, dispatcher = self.fixture(
            target_distance=1,
            target_ref=123,
            target_level=8,
        )
        target = fight.actors[-7]
        origin = target.position
        destination = (origin[0] + 1, *origin[1:])
        self.assertIn(destination, fight.walkable)
        row = self.install_glyph(fight, dispatcher, destination)
        source = snapshot(fight)
        preview = deepcopy(fight)
        factory, _ = server_runtime(
            character,
            {-7: monster},
            deck,
            action_id=3,
            critical=False,
            rng=Random(0),
        )
        moved, packets = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        with preview.effect_resolution():
            # Exact Steamer push leaf observed failing in fight368. Ally area
            # filtering must happen before child execution and charge debit.
            moved.execute(
                EffectInvocation(
                    343186,
                    23,
                    7,
                    -7,
                    origin,
                    native_explicit_target=True,
                )
            )
        self.assertEqual(preview.actors[-7].position, destination)
        self.assertEqual(
            preview.native_effect_areas[row["uid"]]["remaining_activations"], 1
        )
        self.assertFalse(hasattr(preview.actors[-7], "native_is_amO"))
        self.assertTrue(packets, "Real native push did not produce its wire action")
        self.assertTrue(snapshot(fight) == source, "Push preview mutated source")
