"""Explicit gate actions preserve native ownership, payment and publication."""
from collections import deque
from contextlib import contextmanager
from copy import deepcopy
import os
import random
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class GateServerControlTests(unittest.TestCase):
    def test_server_route_requires_actual_current_alive_ai_and_no_owner(self):
        from wakfu_server.combat_portal_travel import _gate_actor

        actor = SimpleNamespace(id=-7, controlled=False)
        fight = SimpleNamespace(
            current=actor,
            actors={-7: actor},
            phase="active",
            _in_play=lambda candidate: candidate is actor,
        )
        self.assertIs(_gate_actor(fight, None, -7, server_controlled=True), actor)
        for owner, identity in ((3, -7), (None, 7)):
            with self.assertRaises(ValueError):
                _gate_actor(fight, owner, identity, server_controlled=True)
        actor.controlled = True
        with self.assertRaises(ValueError):
            _gate_actor(fight, None, -7, server_controlled=True)
        actor.controlled = False
        fight._in_play = lambda candidate: False
        with self.assertRaises(ValueError):
            _gate_actor(fight, None, -7, server_controlled=True)
        with self.assertRaises(ValueError):
            _gate_actor(fight, None, -7, server_controlled=1)

    def test_player_route_keeps_the_original_owner_validator(self):
        from wakfu_server.combat_portal_travel import _gate_actor

        calls = []
        actor = object()
        fight = SimpleNamespace(
            _current_owned=lambda owner, identity: calls.append((owner, identity))
            or actor
        )
        self.assertIs(_gate_actor(fight, 3, 7), actor)
        self.assertEqual(calls, [(3, 7)])

    def test_receipt_preserves_exact_fieldset_and_accepts_none_only_for_owner(self):
        from wakfu_server.combat_gate_movement_boundary import (
            POLICY,
            NativeGateMovementBoundary,
            validate_gate_boundary_facts,
        )

        facts = dict(
            policy=POLICY,
            actor_id=-7,
            owner_id=None,
            turn_id=1,
            from_cell=(0, 0, 0),
            to_cell=(4, 0, 0),
            entry_uid=1,
            exit_uid=2,
            affiliation=0,
            ap_before=6,
            mp_before=3,
            ap_after=6,
            mp_after=2,
            tackle_ap=0,
            tackle_mp=0,
            obstacle_id=0,
            ap_paid=0,
            mp_paid=1,
            ap_effective_after=6,
            mp_effective_after=2,
            ap_raw_post=6,
            mp_raw_post=2,
        )
        self.assertEqual(
            set(facts), set(NativeGateMovementBoundary.__dataclass_fields__)
        )
        self.assertIsNone(validate_gate_boundary_facts(facts).owner_id)
        self.assertEqual(
            validate_gate_boundary_facts(dict(facts, owner_id=3)).owner_id, 3
        )
        for invalid in (True, False, "3", 3.0):
            with self.assertRaises(ValueError):
                validate_gate_boundary_facts(dict(facts, owner_id=invalid))
        with self.assertRaises(ValueError):
            validate_gate_boundary_facts(dict(facts, actor_id=None))


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class NativePortalOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_combat_spell_transaction import SpellTransactionTests
        from test_combat_eliotrope_runtime import EliotropeRuntimeTests
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import encode_deck

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
        deck, rng = encode_deck((4668, 4692, 4699)), random.Random(17)
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
        first = helper.place_portal(data, near=fight.actors[-7].position, action_id=10)
        data = (*data[:2], first.fight, *data[3:])
        first_gate = next(
            row
            for row in first.fight.native_effect_areas.values()
            if row.get("native_type_id") == 19
        )
        second = helper.place_portal(data, near=fight.actors[7].position, action_id=11)
        data = (*data[:2], second.fight, *data[3:])
        gates = [
            row
            for row in second.fight.native_effect_areas.values()
            if row.get("native_type_id") == 19
        ]
        assert len(gates) == 2
        other = next(row for row in gates if row["uid"] != first_gate["uid"])
        cls.seed = data
        cls.entry, cls.destination = tuple(first_gate["cell"]), tuple(other["cell"])
        assert cls.entry != cls.destination

    def fixture(self, *, callbacks=True):
        from wakfu_ai.native.native_oracle import NativeOracle
        from wakfu_ai.native.native_stats import NativeStats
        from wakfu_server.combat_runtime_messages import RuntimeMessages

        character, monster, fight, deck, _, _ = deepcopy(self.seed)
        # The paid-server fixture leaves the descriptor level implicit. Use
        # the actual instantiated NPC level, as the existing 12161 test does.
        self.assertEqual(fight.actors[-7].effective_level, 190)
        monster = dict(monster, level=fight.actors[-7].effective_level)
        fight.order, fight.turn_index = [-7, 7], 0
        fight.current.turn_count = 1
        runtime = RuntimeMessages(fight)
        stats = NativeStats(
            characters={7: character}, monsters={-7: monster}, fight_id=fight.id
        )
        oracle = NativeOracle(
            runtime,
            characters={7: character},
            monsters={-7: monster},
            decks={7: deck},
            excluded_decks={7: frozenset()},
            viewer_id=7,
            flags=dict(native_area_callbacks=callbacks, native_start_events=True),
        )
        origin = fight.current.position
        queue, seen = deque([(origin, [])]), {origin}
        blocked = {
            actor.position
            for actor in fight.actors.values()
            if actor.hp > 0 and actor.id != -7
        }
        route = None
        while queue:
            cell, path = queue.popleft()
            if cell == self.entry:
                route = path
                break
            if len(path) >= fight.current.mp - 1:
                continue
            for source, destination in sorted(fight.edges):
                if (
                    source == cell
                    and destination not in seen
                    and destination not in blocked
                ):
                    seen.add(destination)
                    queue.append((destination, path + [list(destination)]))
        self.assertIsNotNone(route, "Actual NPC cannot approach the paid entry gate")
        if route:
            oracle.commit(dict(type="move", path=route), stats_serializer=stats)
        self.assertEqual(runtime.fight.current.position, self.entry)
        self.assertGreaterEqual(runtime.fight.current.mp, 1)
        return runtime, oracle, stats

    def test_actual_npc_preview_commit_uses_paid_pair_receipt_qi_and_portal_animation(
        self,
    ):
        from wakfu_ai.context.native_fingerprint import fingerprint
        from wakfu_ai.native.native_portal_travel import portal_destinations
        from wakfu_server import combat_gate_movement_boundary as boundary
        from wakfu_server.combat_qi_fight import current_registry

        runtime, oracle, stats = self.fixture()
        source = fingerprint(runtime)
        metadata = portal_destinations(oracle, runtime, -7, source_state="actual-root")
        self.assertIn(list(self.destination), metadata["destinations"])
        self.assertEqual(metadata["sourceState"], "actual-root")
        receipts = []
        original = boundary.native_gate_movement_scope

        @contextmanager
        def observe(fight, receipt):
            receipts.append(receipt)
            with original(fight, receipt):
                yield

        action = dict(type="portal_travel", destination=list(self.destination))
        with patch.object(boundary, "native_gate_movement_scope", observe):
            private, packets, _ = oracle.preview(runtime, action)
            self.assertEqual(fingerprint(runtime), source)
            committed = oracle.commit(action, stats_serializer=stats)
        self.assertEqual(runtime.fight.current.position, self.destination)
        self.assertEqual(private.fight.current.position, self.destination)
        self.assertTrue(receipts)
        self.assertTrue(all(receipt.owner_id is None for receipt in receipts))
        self.assertTrue(all(receipt.mp_paid >= 1 for receipt in receipts))
        self.assertEqual(runtime.fight.current.mp, private.fight.current.mp)
        slot = current_registry(runtime.fight).slots[
            runtime.fight.current.native_obstacle_id
        ]
        self.assertEqual(tuple(slot["position"]), self.destination[:2])
        self.assertTrue(
            any(opcode == 13624 and payload[21] == 3 for opcode, payload in packets)
        )
        self.assertTrue(
            any(opcode == 13624 and payload[21] == 3 for opcode, payload in committed)
        )
        self.assertTrue(
            any(event.get("on_gates") is True for event in runtime.fight.events)
        )

    def test_unmatched_explicit_portal_and_ordinary_nonadjacent_move_reject_atomically(
        self,
    ):
        from wakfu_ai.context.native_fingerprint import fingerprint

        runtime, oracle, stats = self.fixture(callbacks=False)
        source = fingerprint(runtime)
        from wakfu_server.combat_effect_area_geometry import contains_area_cell

        gates = [
            row
            for row in runtime.fight.native_effect_areas.values()
            if row.get("native_type_id") == 19
        ]
        empty = next(
            cell
            for cell in runtime.fight.walkable
            if not any(contains_area_cell(row, cell) for row in gates)
        )
        for action in (
            dict(type="portal_travel", destination=list(empty)),
            dict(type="portal_travel", destination=[True, 0, 0]),
            dict(type="move", path=[list(self.destination)]),
        ):
            with self.subTest(action=action):
                with self.assertRaises(ValueError):
                    oracle.preview(runtime, action)
                with self.assertRaises(ValueError):
                    oracle.commit(action, stats_serializer=stats)
                self.assertEqual(fingerprint(runtime), source)

    def test_hidden_gate_is_not_disclosed_or_accepted_by_native_preview(self):
        from wakfu_ai.context.native_fingerprint import fingerprint
        from wakfu_ai.native.native_portal_travel import portal_destinations
        from wakfu_server.combat_observation_scope import unobserved_area_forecast

        runtime, oracle, _ = self.fixture()
        source = fingerprint(runtime)
        identities = frozenset(
            row["uid"]
            for row in runtime.fight.native_effect_areas.values()
            if row.get("native_type_id") == 19
        )
        action = dict(type="portal_travel", destination=list(self.destination))
        for scoped in (False, True):
            with self.subTest(scoped=scoped):
                context = (
                    unobserved_area_forecast(identities)
                    if scoped
                    else patch.object(
                        oracle, "unobserved_areas", return_value=identities
                    )
                )
                with context:
                    metadata = portal_destinations(
                        oracle, runtime, -7, source_state="actual-root"
                    )
                    self.assertEqual(metadata["destinations"], [])
                    with self.assertRaisesRegex(
                        ValueError, "No observed native portal pair"
                    ):
                        oracle.preview(runtime, action)
                self.assertEqual(fingerprint(runtime), source)

    def test_failed_real_serializer_does_not_publish_or_pay_portal_travel(self):
        from wakfu_ai.context.native_fingerprint import fingerprint

        runtime, oracle, _ = self.fixture()
        source = fingerprint(runtime)

        def fail(actor, fight):
            raise ValueError("native serialization rejected")

        with self.assertRaisesRegex(ValueError, "native serialization rejected"):
            oracle.commit(
                dict(type="portal_travel", destination=list(self.destination)),
                stats_serializer=fail,
            )
        self.assertEqual(fingerprint(runtime), source)
