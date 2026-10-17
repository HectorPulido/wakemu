"""Real Enutrof form/turn consumers of committed voluntary MP movement.

The original server mh caller is unavailable. These interactions qualify the
explicit Wakemu movement caller, never an invented native producer claim.
"""
from copy import deepcopy
from pathlib import Path
import importlib
import os
import random
import struct
import sys
import unittest

from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_area_transaction import (
    prepare_area_movement,
    prepare_area_event,
)
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_start,
    prepare_server_turn_end,
    server_runtime,
)
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck, validate_deck


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EnutrofCommittedMPMovementTests(unittest.TestCase):
    @staticmethod
    def levels(actor, reference):
        return sum(
            row.level
            for row in actor.state_ledger.entries
            if row.reference == reference
        )

    def fixture(self, passive=None):
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.combat_arena_selection import bounded_arena
        import wakfu_server

        tools = Path(wakfu_server.__file__).resolve().parents[1] / "tools"
        original_path = list(sys.path)
        try:
            sys.path.insert(0, str(tools))
            source = importlib.import_module("audit_active_spells")
            self.assertEqual(
                Path(source.__file__).resolve(), tools / "audit_active_spells.py"
            )
            geometry = map_geometry(1134)
            origin, target = (-8, -7, -1), (-4, -7, -1)
            terrain = bounded_arena(geometry, origin, [target], radius=12)
            character, monster, fight = source.fixture(
                3,
                200,
                target,
                terrain,
                origin,
                ready=False,
                monster_reference=4,
                monster_level=8,
            )
        finally:
            sys.path[:] = original_path
        self.assertEqual(fight.phase, "placement")
        self.assertEqual(fight.actors[7].hp, fight.actors[7].max_hp)
        self.assertEqual(fight.actors[-7].hp, fight.actors[-7].max_hp)
        self.assertEqual(monster["ref"], 4)
        deck = encode_deck([2008, 2014, 2018], () if passive is None else [passive])
        validate_deck(deck, 3, 200)
        rng = random.Random(7)

        def stats(actor, current):
            if actor.id == 7:
                return actual_actor_stats(
                    character,
                    actor,
                    current.id,
                    fight=current,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                )
            if actor.id in getattr(current, "native_summon_registrations", {}):
                from wakfu_server.combat_summon_stats import registered_summon_stats

                return registered_summon_stats(actor, current, current.map_id)
            self.assertEqual(actor.id, -7)
            return actual_monster_actor_stats(
                monster,
                actor,
                current.id,
                wp_current=monster["wp"],
                wp_maximum=monster["wp"],
            )

        def initialize(current, action_id):
            return prepare_server_initialization(
                character,
                {-7: monster},
                current,
                3,
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
            )

        def turn_start(current, **boundary):
            return prepare_server_turn_start(
                character,
                {-7: monster},
                current,
                deck,
                rng=rng,
                area_callbacks=True,
                **boundary
            )

        def turn_end(current, **boundary):
            return prepare_server_turn_end(
                character, {-7: monster}, current, deck, rng=rng, **boundary
            )

        fight, runtime, packets = prepare_ready(
            fight,
            3,
            True,
            initialize=initialize,
            stats_serializer=lambda actor: stats(actor, fight),
            runtime_stats_serializer=stats,
            effects_serializer=actor_effects,
            turn_start_provider=turn_start,
            turn_end_provider=turn_end,
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                {-7: monster},
                deck,
                action_id=action_id,
                rng=rng,
                critical=False,
            )[0],
        )
        self.assertIsNotNone(runtime)
        self.assertTrue(packets)
        # Native profile4 has its own initiative. Reach the first owner turn
        # through real server/controlled end and ACK callbacks, never reorder it.
        from tools.combat_audit_turns import advance_actual_turn

        for _ in range(20):
            if runtime.fight.current.id == 7:
                break
            advance_actual_turn(runtime)
        else:
            self.fail("Initial actual owner turn did not arrive")
        self.assertEqual(runtime.fight.current.id, 7)
        data = dict(
            character=character,
            monster=monster,
            deck=deck,
            rng=rng,
            runtime=runtime,
            stats=stats,
        )
        self.assertEqual(self.levels(runtime.fight.actors[7], 8590), 0)
        form_trace = []
        with combat_diagnostic_scope(lambda **row: form_trace.append(row), limit=8192):
            self.cast(data, 2038, runtime.fight.actors[7].position)
        self.assertGreater(self.levels(runtime.fight.actors[7], 702), 0)
        # Native702 root386130 has no event mask: its child386131 creates8590
        # immediately. Root385727 separately renews it through own1001/386129.
        self.assertTrue(
            any(
                row.get("effect_reference") == 386131
                and row.get("status") == "completed"
                and row.get("caster_id") == row.get("target_id") == 7
                for row in form_trace
            ),
            form_trace,
        )
        self.assert_owned_movement_state(runtime.fight)
        turn_trace = []
        with combat_diagnostic_scope(lambda **row: turn_trace.append(row), limit=8192):
            advance_actual_turn(runtime)
            for _ in range(20):
                if runtime.fight.current.id == 7:
                    break
                advance_actual_turn(runtime)
            else:
                self.fail("Actual owner turn did not return")
        self.assertTrue(
            any(
                row.get("effect_reference") == 386129
                and row.get("status") == "completed"
                and row.get("caster_id") == row.get("target_id") == 7
                for row in turn_trace
            ),
            turn_trace,
        )
        self.assert_owned_movement_state(runtime.fight)
        self.assertGreater(runtime.fight.actors[7].mp, 0)
        self.assertEqual(self.levels(runtime.fight.actors[7], 3462), 0)
        self.assertEqual(self.levels(runtime.fight.actors[7], 8607), 0)
        return data

    def assert_owned_movement_state(self, fight):
        states = [
            row for row in fight.actors[7].state_ledger.entries if row.reference == 8590
        ]
        self.assertTrue(states)
        self.assertTrue(all(row.caster_id == row.target_id == 7 for row in states))

    def cast(self, data, reference, cell):
        runtime = data["runtime"]
        before = snapshot(runtime.fight)
        uid = (
            granted_spells(runtime.fight, 7)
            .get(reference, {})
            .get("uid", (7 << 32) | reference)
        )
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, uid, *cell),
            data["character"],
            {-7: data["monster"]},
            runtime.fight,
            3,
            data["deck"],
            action_id=runtime.action_id + 1,
            line_of_sight=lambda origin, target, current: authoritative_visible(
                data["character"]["map_id"],
                origin,
                target,
                current,
                blocking_footprints={
                    actor.id: footprint(actor.position, actor.physical_radius)
                    for actor in current.actors.values()
                    if actor.hp > 0
                },
            ),
            critical=False,
            rng=data["rng"],
        )
        self.assertEqual(snapshot(runtime.fight), before)
        commit_spell_transaction(runtime, tx, stats_serializer=data["stats"])
        return tx

    def destination(self, data):
        from wakfu_server.combat_qi_movement import movement_blocked_cells

        fight = data["runtime"].fight
        actor = fight.actors[7]
        area_cells = {tuple(row["cell"]) for row in fight.native_effect_areas.values()}
        occupied = {
            row.position for row in fight.actors.values() if row.id != 7 and row.hp > 0
        }
        for origin, destination in sorted(fight.edges):
            if (
                origin != actor.position
                or destination in occupied
                or destination in area_cells
            ):
                continue
            if any(
                row.team != actor.team
                and row.hp > 0
                and sum(abs(destination[i] - row.position[i]) for i in (0, 1)) <= 1
                for row in fight.actors.values()
            ):
                continue
            if movement_blocked_cells(fight, actor, [destination]):
                continue
            return destination
        self.fail(
            "No legal untackled non-area adjacent move from the actual Enutrof footprint"
        )

    def move(self, data, destination, owner=3):
        def area(current, **boundary):
            return prepare_area_movement(
                data["character"],
                {-7: data["monster"]},
                current,
                data["deck"],
                rng=data["rng"],
                **boundary
            )

        return apply_client(
            data["runtime"],
            owner,
            struct.pack(">qiih", 7, *destination),
            lambda actor: b"",
            area_provider=area,
            runtime_stats_serializer=data["stats"],
        )

    def test_actual_form_owner_turn_paid_move_selects_damage_or_perfortanker(self):
        for passive, expected, forbidden in ((None, 3462, 8607), (5075, 8607, 3462)):
            with self.subTest(passive=passive):
                data = self.fixture(passive)
                runtime = data["runtime"]
                origin = runtime.fight.actors[7].position
                destination = self.destination(data)
                before_mp = runtime.fight.actors[7].mp
                trace = []
                with combat_diagnostic_scope(
                    lambda **row: trace.append(row), limit=8192
                ):
                    packets, result = self.move(data, destination)
                actor = runtime.fight.actors[7]
                self.assertEqual(actor.position, destination)
                self.assertNotEqual(actor.position, origin)
                self.assertEqual(actor.mp, before_mp - 1)
                self.assertGreater(self.levels(actor, expected), 0)
                self.assertEqual(self.levels(actor, forbidden), 0)
                self.assertTrue(packets)
                self.assertEqual(result["cost"], 1)
                self.assertTrue(
                    any(
                        row.get("effect_reference") == 386125
                        and row.get("status") == "completed"
                        and row.get("caster_id") == row.get("target_id") == 7
                        for row in trace
                    ),
                    trace,
                )
                self.assertEqual(actor.effect_stats[3], actor.mp)

    def test_foreign_control_cannot_pay_or_publish_owner_movement(self):
        data = self.fixture()
        runtime = data["runtime"]
        before = snapshot(runtime.fight)
        counters = (runtime.action_id, runtime.native_action_id)
        with self.assertRaises(ValueError):
            self.move(data, self.destination(data), owner=4)
        self.assertEqual(snapshot(runtime.fight), before)
        self.assertEqual((runtime.action_id, runtime.native_action_id), counters)
        self.assertEqual(self.levels(runtime.fight.actors[7], 3462), 0)

    def test_unpaid_qi_area_boundary_does_not_impersonate_committed_movement(self):
        # This is the actual forced-position/area boundary, not a claim that an
        # Enutrof forced-movement spell was cast. No MP debit receipt exists.
        from wakfu_server.combat_qi_fight import move_registered_actor

        data = self.fixture()
        fight = deepcopy(data["runtime"].fight)
        actor = fight.actors[7]
        origin, destination = actor.position, self.destination(data)
        resources = (actor.ap, actor.mp)
        move_registered_actor(fight, actor, destination)
        before = snapshot(fight)
        trace = []
        with combat_diagnostic_scope(lambda **row: trace.append(row), limit=8192):
            preview, _ = prepare_area_event(
                data["character"],
                {-7: data["monster"]},
                fight,
                data["deck"],
                actor_id=7,
                action_id=data["runtime"].action_id + 1,
                event="movement",
                from_cell=origin,
                to_cell=destination,
                rng=data["rng"],
            )
        self.assertEqual(snapshot(fight), before)
        self.assertEqual((preview.actors[7].ap, preview.actors[7].mp), resources)
        self.assertEqual(self.levels(preview.actors[7], 3462), 0)
        self.assertEqual(self.levels(preview.actors[7], 8607), 0)
        self.assertFalse(
            any(
                row.get("effect_reference") == 386125
                and row.get("status") == "completed"
                for row in trace
            )
        )
