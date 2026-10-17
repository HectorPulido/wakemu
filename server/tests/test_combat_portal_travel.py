"""Original portal ingress12161 and atomic actual Ready/area/QI travel."""
import os
import random
import struct
import unittest


class PortalNetworkContractTests(unittest.TestCase):
    def test_pair_affiliation_comes_from_gates_not_actor_or_owner(self):
        from wakfu_server.combat_portal_travel import portal_network_pair

        def gate(uid, team):
            return dict(
                uid=uid,
                native_fight_affiliation=team,
                native_fight_affiliation_source="faV.j(PV).bcM",
            )

        self.assertEqual(portal_network_pair((gate(1, 1),), (gate(2, 1),)), (1, 2))
        self.assertIsNone(portal_network_pair((gate(1, 0),), (gate(2, 1),)))
        self.assertIsNone(portal_network_pair((gate(1, -1),), (gate(2, -1),)))
        self.assertIsNone(portal_network_pair((gate(1, 0), gate(3, 1)), (gate(2, 0),)))

    def test_gate_receipt_distinguishes_nominal_cost_from_actual_raw_debit(self):
        from wakfu_server.combat_gate_movement_boundary import (
            POLICY,
            validate_gate_boundary_facts,
        )

        facts = dict(
            policy=POLICY,
            actor_id=7,
            owner_id=3,
            turn_id=1,
            from_cell=(0, 0, 0),
            to_cell=(4, 0, 0),
            entry_uid=11,
            exit_uid=12,
            affiliation=0,
            ap_before=6,
            mp_before=7,
            ap_after=6,
            mp_after=6,
            tackle_ap=0,
            tackle_mp=0,
            obstacle_id=0,
            ap_paid=0,
            mp_paid=1,
            ap_effective_after=6,
            mp_effective_after=3,
            ap_raw_post=6,
            mp_raw_post=6,
        )
        # Pure receipt unit cases; these do not fabricate a native combat state.
        self.assertEqual(validate_gate_boundary_facts(facts).mp_paid, 1)
        frozen = dict(facts, mp_before=3, mp_after=3, mp_paid=0, mp_raw_post=3)
        self.assertEqual(validate_gate_boundary_facts(frozen).mp_paid, 0)
        with self.assertRaisesRegex(ValueError, "Invalid native gate movement receipt"):
            validate_gate_boundary_facts(dict(facts, mp_paid=2))

    def test_unattested_nonadjacent_movement_still_rejects(self):
        from wakfu_server.combat_external_movement_recipient import (
            POLICY,
            validate_movement_boundary_context,
        )

        context = dict(
            policy=POLICY,
            actor_id=7,
            turn_id=1,
            action_id=1,
            from_cell=(0, 0, 0),
            to_cell=(4, 0, 0),
            event_id=1005,
        )
        with self.assertRaisesRegex(
            ValueError, "Invalid committed movement boundary step"
        ):
            validate_movement_boundary_context(context)
        context["gate_boundary"] = {}
        with self.assertRaisesRegex(
            ValueError, "Invalid native gate movement receipt fields"
        ):
            validate_movement_boundary_context(context)

    def test_native_gate_animation_uses_original_ordinal_and_endpoint(self):
        from wakfu_server.combat_movement import movement, portal_movement

        points = [(1, 2, 3), (8, 9, 3)]
        opcode, standard = movement(17, 2, 7, points, 5)
        gate_opcode, gate = portal_movement(17, 2, 7, *points, 5)
        self.assertEqual((opcode, gate_opcode), (13624, 13624))
        self.assertEqual(standard[21], 0)
        self.assertEqual(gate[21], 3)
        self.assertEqual(gate[:21] + gate[22:], standard[:21] + standard[22:])
        self.assertEqual(list(struct.iter_unpack(">iih", gate[22:])), points)


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class NativePortalTravelTests(unittest.TestCase):
    def test_actual_portal_pair_12161_roundtrip_and_atomic_rejections(self):
        from test_combat_spell_transaction import SpellTransactionTests
        from test_combat_eliotrope_runtime import EliotropeRuntimeTests
        from test_combat_eliotrope_white_dimension_runtime import (
            EliotropeWhiteDimensionRuntimeTests,
        )
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.combat_area_transaction import prepare_area_movement
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_reproduction_state import encode_state
        from wakfu_server.combat_qi_fight import current_registry
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.combat_wire import decode_actor_state
        from wakfu_server.spells import encode_deck

        # World-legal190 native NPC HP8784; no targetHP inflation or resource
        # grants. The real4678 grant and paid casts create both actual gates.
        character, monster, fight = SpellTransactionTests().native_server_fixture(
            18,
            200,
            full_health=True,
            native_qi=True,
            target_ref=4168,
            target_level=190,
            target_distance=4,
            variation_seed=17,
        )
        self.assertEqual(
            (fight.actors[-7].hp, fight.actors[-7].effective_level), (8784, 190)
        )
        deck = encode_deck((4668, 4692, 4699))
        rng = random.Random(17)
        fight, packets = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=rng,
            fight_start=True,
        )
        data = (character, monster, fight, deck, rng, packets)
        helper = EliotropeRuntimeTests()
        first = helper.place_portal(data, near=fight.actors[7].position, action_id=10)
        data = (*data[:2], first.fight, *data[3:])
        entries = {
            uid: row
            for uid, row in data[2].native_effect_areas.items()
            if row["native_type_id"] == 19
        }
        self.assertEqual(len(entries), 1)
        entry = next(iter(entries.values()))
        second = helper.place_portal(data, near=(-8, -10, -1), action_id=11)
        data = (*data[:2], second.fight, *data[3:])
        gates = {
            uid: row
            for uid, row in data[2].native_effect_areas.items()
            if row["native_type_id"] == 19
        }
        self.assertEqual(len(gates), 2)
        exit = next(row for uid, row in gates.items() if uid != entry["uid"])
        origin, destination = tuple(entry["cell"]), tuple(exit["cell"])
        self.assertGreater(
            abs(origin[0] - destination[0]) + abs(origin[1] - destination[1]), 1
        )
        EliotropeWhiteDimensionRuntimeTests().walk_to_portal(data, origin)
        self.assertEqual(data[2].actors[7].position, origin)

        def stats(actor, state=None):
            state = data[2] if state is None else state
            kwargs = dict(
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=state,
                direction=actor.direction,
            )
            if actor.id == 7:
                return actual_actor_stats(character, actor, state.id, **kwargs)
            return actual_monster_actor_stats(
                dict(monster, level=actor.effective_level), actor, state.id, **kwargs
            )

        runtime = RuntimeMessages(
            data[2], stats_serializer=stats, runtime_stats_serializer=stats
        )
        calls = []
        receipts = []

        def provider(preview, **kw):
            from wakfu_server.combat_gate_movement_boundary import (
                current_gate_movement_boundary,
            )

            boundary = current_gate_movement_boundary(
                preview, 7, kw["origin"], kw["path"][0]
            )
            self.assertIsNotNone(boundary)
            self.assertEqual(
                (boundary.entry_uid, boundary.exit_uid),
                (entry["uid"], exit["uid"])
                if tuple(kw["origin"]) == origin
                else (exit["uid"], entry["uid"]),
            )
            self.assertEqual(boundary.mp_before - boundary.mp_after, 1)
            receipts.append(boundary)
            calls.append((tuple(kw["origin"]), tuple(kw["path"][0])))
            return prepare_area_movement(
                character, {-7: monster}, preview, deck, rng=rng, **kw
            )

        def request(identity, cell):
            return struct.pack(">qiih", identity, *cell)

        def reject(owner, identity, cell, pattern):
            before = encode_state(runtime)
            count = len(calls)
            with self.assertRaisesRegex(ValueError, pattern):
                apply_client(
                    runtime,
                    owner,
                    request(identity, cell),
                    stats,
                    runtime_stats_serializer=stats,
                    area_provider=provider,
                )
            self.assertEqual(encode_state(runtime), before)
            self.assertEqual(len(calls), count)

        reject(999, 7, destination, "owned|Owner|owner")
        unrelated = next(
            cell
            for cell in sorted(runtime.fight.walkable)
            if cell not in (origin, destination)
            and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) > 1
        )
        reject(3, 7, unrelated, "native facing vector|movement path|Terrain")
        # Failure after the actual candidate move/payment must not publish it.
        before_failure = encode_state(runtime)
        rng_before = rng.getstate()
        actor_reference = runtime.fight.actors[7]

        def failed_provider(preview, **kw):
            self.assertEqual(preview.actors[7].position, destination)
            self.assertEqual(preview.actors[7].mp, runtime.fight.actors[7].mp - 1)
            raise ValueError("test area callback failure")

        with self.assertRaisesRegex(ValueError, "test area callback failure"):
            apply_client(
                runtime,
                3,
                request(7, destination),
                stats,
                runtime_stats_serializer=stats,
                area_provider=failed_provider,
            )
        self.assertEqual(encode_state(runtime), before_failure)
        self.assertIs(runtime.fight.actors[7], actor_reference)
        self.assertEqual(rng.getstate(), rng_before)
        serializations = []

        def failed_serializer(actor, state):
            serializations.append(tuple(actor.position))
            if actor.position == destination:
                raise ValueError("test final serializer failure")
            return stats(actor, state)

        with self.assertRaisesRegex(ValueError, "test final serializer failure"):
            apply_client(
                runtime,
                3,
                request(7, destination),
                stats,
                runtime_stats_serializer=failed_serializer,
            )
        self.assertEqual(serializations, [origin, destination])
        self.assertEqual(encode_state(runtime), before_failure)
        self.assertIs(runtime.fight.actors[7], actor_reference)
        self.assertEqual(rng.getstate(), rng_before)
        before_mp = runtime.fight.actors[7].mp
        facing = runtime.fight.actors[7].direction
        self.assertGreaterEqual(before_mp, 2)
        outgoing, event = apply_client(
            runtime,
            3,
            request(7, destination),
            stats,
            runtime_stats_serializer=stats,
            area_provider=provider,
        )
        self.assertTrue(event["on_gates"])
        self.assertEqual(
            (event["gate_entry_uid"], event["gate_exit_uid"]),
            (entry["uid"], exit["uid"]),
        )
        self.assertEqual(
            (event["cost"], event["tackle_ap"], event["tackle_mp"]), (1, 0, 0)
        )
        self.assertEqual(runtime.fight.actors[7].mp, before_mp - 1)
        resource = decode_actor_state(
            12873,
            next(
                body
                for opcode, body in outgoing
                if opcode == 12873 and decode_actor_state(opcode, body)["actor_id"] == 7
            ),
        )["state"]
        self.assertEqual(resource[0], 40)
        count = struct.unpack_from(">H", resource, 1)[0]
        characteristics = {
            row[0]: row[1:] for row in struct.iter_unpack(">Biiii", resource[3:])
        }
        self.assertEqual(len(characteristics), count)
        self.assertEqual(characteristics[3][0], runtime.fight.actors[7].mp)
        self.assertEqual(runtime.fight.actors[7].position, destination)
        self.assertEqual(runtime.fight.actors[7].direction, facing)
        self.assertEqual(calls, [(origin, destination)])
        self.assertFalse(
            hasattr(runtime.fight, "_wakemu_native_gate_movement_boundary")
        )
        # An authentic prior receipt cannot authorize another publication after
        # its scoped callback completed; neither matching facts nor UID suffice.
        from wakfu_server.combat_external_movement_recipient import (
            POLICY,
            validate_movement_boundary_context,
        )

        captured = receipts[0]
        stale = dict(
            policy=POLICY,
            actor_id=7,
            turn_id=runtime.fight.turn_id,
            action_id=runtime.action_id,
            from_cell=origin,
            to_cell=destination,
            event_id=1005,
            gate_boundary=captured.facts(),
        )
        snapshot_before = encode_state(runtime)
        with self.assertRaisesRegex(
            ValueError, "Unattested native gate movement receipt"
        ):
            validate_movement_boundary_context(stale, fight=runtime.fight)
        self.assertEqual(encode_state(runtime), snapshot_before)
        malformed = dict(stale, from_cell=None)
        with self.assertRaisesRegex(
            ValueError, "Invalid committed movement boundary step"
        ):
            validate_movement_boundary_context(malformed, fight=runtime.fight)
        native = next(body for opcode, body in outgoing if opcode == 13624)
        self.assertEqual(native[21], 3)
        self.assertEqual(
            list(struct.iter_unpack(">iih", native[22:])), [origin, destination]
        )
        slot = runtime.fight.actors[7].native_obstacle_id
        self.assertEqual(
            tuple(current_registry(runtime.fight).slots[slot]["position"]),
            destination[:2],
        )
        apply_client(
            runtime,
            3,
            request(7, origin),
            stats,
            runtime_stats_serializer=stats,
            area_provider=provider,
        )
        self.assertEqual(runtime.fight.actors[7].position, origin)
        self.assertEqual(runtime.fight.actors[7].mp, before_mp - 2)
        self.assertEqual(calls, [(origin, destination), (destination, origin)])
        self.assertEqual(before_mp, 2)  # One real entry step spent the third nativeMP.
        reject(3, 7, destination, "Insufficient AP/MP")
