"""Private candidate tests through canonical production module namespace."""
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from psycopg.pq import TransactionStatus

from wakfu_server import (
    dungeon_ground_outcomes,
    dungeon_rotation,
    dungeon_excavation,
    dungeon_excavation_runtime,
    dungeon_physical_doors,
)
from wakfu_server import (
    dungeon_runtime_config,
    dungeon_progression,
    dungeon_stage_levels,
)


def configuration():
    # Small geometry fixtures test projection identity, not native path physics.
    # Actual published Sm/Sn and twelve formations have separate integration QA.
    entries = [
        (26635, [-5, -25, 9], [-16, -25, 17]),
        (26636, [10, -25, 9], [20, -29, 17]),
        (26637, [10, -50, 17], [22, -48, 9]),
        (26638, [-19, -50, 17], [-32, -50, 25]),
    ]
    roster = [
        [(4018, 2, 31), (4020, 1, 36)],
        [(4018, 2, 31), (4020, 2, 36), (4019, 1, 33)],
        [(4019, 3, 33), (4020, 2, 36), (4018, 1, 31)],
        [(4021, 1, 39), (4018, 2, 31), (4019, 2, 33)],
        [(4022, 1, 50)],
    ]
    rooms = [
        dict(order=n, anchor=a, native_arrival=a, cells=[a, p])
        for n, (identity, p, a) in enumerate(entries, 1)
    ]
    rooms.append(
        dict(
            order=5,
            anchor=[-72, -118, 0],
            native_arrival=[-72, -118, 0],
            cells=[[-72, -118, 0]],
        )
    )
    plan = dict(
        rooms=[
            dict(
                order=n,
                monsters=[
                    dict(
                        ref_id=r,
                        count=count,
                        native_min_level=level,
                        native_max_level=level,
                        role="boss" if r in (4021, 4022) else "monster",
                    )
                    for r, count, level in row
                ],
            )
            for n, row in enumerate(roster, 1)
        ]
    )
    topology = dict(
        asset_map_id=1075,
        rooms=rooms,
        branch_routes=[],
        auto_edges=[],
        doors=[],
        physical_exit_objects=[],
        physical_doors=[
            dict(
                source_id=identity,
                position=p,
                source_room=max(1, n - 1),
                destination_room=n,
            )
            for n, (identity, p, a) in enumerate(entries, 1)
        ],
        rotation_choice=dict(
            authority="reviewed_native_cycle_reconstruction",
            cycle_source_orders=[1, 2, 3],
            terminal_source_order=4,
            main_source_orders=[1, 2, 3, 4],
            selectors=[
                dict(source_id=identity, source_order=n)
                for n, (identity, p, a) in enumerate(entries[:3], 1)
            ],
        ),
        optional_room_policy=dict(
            policy="reviewed-main-and-optional-rooms-v1",
            main_room_orders=[1, 2, 3, 4],
            source_evidence={
                "fixture": "Optional island stays unresolved and separate"
            },
            optional_rooms=[
                dict(
                    order=5,
                    source_order=5,
                    access=dict(
                        status="unresolved_native_access",
                        evidence=["Separate native quest not implemented"],
                    ),
                )
            ],
        ),
    )
    return dict(
        topology=topology,
        compiled_plan=plan,
        level_policy=dict(
            mode="native_minimum", provenance="Explicit fixed native cycle"
        ),
        evidence_hashes={},
    )


class CandidateTest(unittest.TestCase):
    def test_three_real_door_rotations_keep_every_arena_and_optional_outside_main(self):
        config = configuration()
        original = deepcopy(config)
        for identity, sequence in [
            (26635, [1, 2, 3, 4]),
            (26636, [2, 3, 1, 4]),
            (26637, [3, 1, 2, 4]),
        ]:
            with self.subTest(identity=identity):
                projected = dungeon_rotation.project(config, identity)
                rooms = projected["compiled_plan"]["rooms"]
                self.assertEqual(
                    [r["native_source_order"] for r in rooms], sequence + [5]
                )
                for room, source_order in zip(rooms, sequence + [5]):
                    self.assertEqual(
                        room["monsters"],
                        original["compiled_plan"]["rooms"][source_order - 1][
                            "monsters"
                        ],
                    )
                    self.assertEqual(
                        projected["topology"]["rooms"][room["order"] - 1]["cells"],
                        original["topology"]["rooms"][source_order - 1]["cells"],
                    )
                gates = {
                    g["source_id"]: g for g in projected["topology"]["physical_doors"]
                }
                self.assertEqual(gates[identity]["destination_room"], 1)
                self.assertEqual(gates[26638]["destination_room"], 4)
                self.assertEqual(
                    projected["evidence_hashes"]["plan"],
                    dungeon_runtime_config.canonical_hash(projected["compiled_plan"]),
                )
                self.assertEqual(
                    projected["evidence_hashes"]["topology"],
                    dungeon_runtime_config.canonical_hash(projected["topology"]),
                )
        self.assertEqual(config, original)

    def test_optional_or_boss_cannot_become_first_choice(self):
        for identity in (26638, 26689, 0):
            with self.assertRaises(ValueError):
                dungeon_rotation.project(configuration(), identity)

    def test_duplicate_native_arenas_or_parallel_branch_are_rejected(self):
        for mutate in ("duplicate", "parallel"):
            config = configuration()
            if mutate == "duplicate":
                config["topology"]["rotation_choice"]["cycle_source_orders"] = [1, 1, 3]
            else:
                config["topology"]["branch_routes"] = [dict(key="unrelated")]
            with self.assertRaises(ValueError):
                dungeon_rotation.project(config, 26635)

    def test_three_small_victories_unlock_boss_and_fourth_finishes(self):
        order = 1
        for expected in (2, 3, 4):
            result = dungeon_progression.progression_result(order, 4, 0, 0)
            self.assertFalse(result["completed"])
            self.assertEqual(result["current_room"], expected)
            order = result["current_room"]
        self.assertTrue(
            dungeon_progression.progression_result(order, 4, 0, 0)["completed"]
        )
        self.assertEqual(
            dungeon_progression.progression_result(2, 4, 0, 1)["current_room"], 2
        )

    def test_existing_seed_outcome_does_not_reach_excavation_provider(self):
        body = struct.pack(">iqii", 7952, 99, 1, 2)
        called = []
        result = dungeon_ground_outcomes.dispatch(
            body,
            [dict(action_id=7952, enabled=True)],
            optional_group=lambda **kw: called.append("seed") or "seed",
            excavation_state=lambda **kw: called.append("wrong"),
            context={},
        )
        self.assertEqual(result, "seed")
        self.assertEqual(called, ["seed"])

    def test_reusable_shovel_keeps_uid_and_requires_zero_consumption(self):
        body = struct.pack(">iqii", 8143, 123456, -3, -25)
        rule = dict(
            action_id=8143, enabled=True, outcome="excavation_state", consume_units=0
        )
        result = dungeon_ground_outcomes.dispatch(
            body,
            [rule],
            optional_group=lambda **kw: self.fail("seed path"),
            excavation_state=lambda **kw: kw["request"],
            context={},
        )
        self.assertEqual(result["source_uid"], 123456)
        rule["consume_units"] = 1
        with self.assertRaises(ValueError):
            dungeon_ground_outcomes.dispatch(
                body,
                [rule],
                optional_group=lambda **kw: None,
                excavation_state=lambda **kw: None,
                context={},
            )

    def test_malformed_and_disabled_action_never_calls_provider(self):
        rule = dict(action_id=8143, enabled=False)
        for body in (struct.pack(">i", 8143), struct.pack(">iqii", 8143, 1, 0, 0)):
            with self.assertRaises(ValueError):
                dungeon_ground_outcomes.dispatch(
                    body,
                    [rule],
                    optional_group=lambda **kw: self.fail(),
                    excavation_state=lambda **kw: self.fail(),
                    context={},
                )
        self.assertIsNone(
            dungeon_ground_outcomes.dispatch(
                struct.pack(">i", 999),
                [rule],
                optional_group=None,
                excavation_state=None,
                context={},
            )
        )

    def test_rule_cannot_claim_native_timing_from_opaque_parameter(self):
        rule = dict(
            outcome="excavation_state",
            consume_units=0,
            key_probability=[1, 10],
            attempt_interval_ms=1000,
            timing_authority="explicit_reconstruction_not_native_action_parameters",
            ground_authority=dict(
                targets=[1], authority="reviewed_native_sand_reconstruction"
            ),
        )
        dungeon_excavation.validate_rule(rule)
        rule["timing_authority"] = "native_param_5000"
        with self.assertRaises(ValueError):
            dungeon_excavation.validate_rule(rule)

    def test_pending_runtime_defers_spawn_and_blocks_all_four_real_gates(self):
        config = configuration()
        config["topology"]["excavation_access"] = dict(key="review")

        class DB:
            def execute(self, sql, params):
                row = (
                    None
                    if "dungeon_excavation_runs" in sql
                    else dict(catalog_hash="catalog", branch_key=None)
                )
                return SimpleNamespace(fetchone=lambda: row)

        pending = dungeon_excavation_runtime.hydrate(DB(), 90, config)
        self.assertTrue(dungeon_excavation_runtime.defer_spawn(pending))
        self.assertEqual(
            dungeon_excavation_runtime.blocked_gate_ids(pending["topology"]),
            {26635, 26636, 26637, 26638},
        )
        # Supply real typed column fixtures for the newly composed generic
        # native-height resolver; this case still isolates pending gate locks.
        from wakfu_server.combat_sn_path import NativeSnColumns

        chunks = []
        for gate in config["topology"]["physical_doors"]:
            x, y, z = gate["position"]
            chunks.append(
                dict(
                    x=(x // 18) * 18,
                    y=(y // 18) * 18,
                    width=18,
                    height=18,
                    columns=[[x, y, [[z, 0, 0, 0, 0, False]]]],
                )
            )
        columns = NativeSnColumns(
            dict(
                schema="native-Sn-Vy-columns-v1",
                map_id=1075,
                source_sha256="f" * 64,
                chunks=chunks,
            ),
            map_id=1075,
            source_sha256="f" * 64,
        )
        with patch.object(NativeSnColumns, "from_published", return_value=columns):
            self.assertEqual(
                dungeon_physical_doors.blocked_cells(pending["topology"], 1),
                set(
                    map(
                        tuple,
                        (g["position"] for g in config["topology"]["physical_doors"]),
                    )
                ),
            )
        for actor, expected in ((7, {26635, 26636, 26637}), (8, set())):
            packets = dungeon_excavation_runtime.pending_gate_packets(
                pending, character_id=actor, key_character_id=7
            )
            enabled = {
                struct.unpack_from(">q", body)[0]
                for opcode, body in packets
                if body[20]
            }
            self.assertEqual(enabled, expected)
            self.assertEqual(len(packets), 4)

    def test_hydrated_selected_rotation_matches_durable_choice(self):
        config = configuration()
        config["topology"]["excavation_access"] = dict(key="review")

        class DB:
            def execute(self, sql, params):
                row = (
                    dict(catalog_hash="catalog", selected_source_id=26637)
                    if "dungeon_excavation_runs" in sql
                    else dict(catalog_hash="catalog", branch_key="26637")
                )
                return SimpleNamespace(fetchone=lambda: row)

        chosen = dungeon_excavation_runtime.hydrate(DB(), 90, config)
        self.assertEqual(chosen["topology"]["rotation_source_orders"], [3, 1, 2, 4])
        self.assertFalse(dungeon_excavation_runtime.defer_spawn(chosen))
        self.assertFalse(
            dungeon_excavation_runtime.blocked_gate_ids(chosen["topology"])
        )

    def test_ordinary_configuration_has_no_excavation_lookup_or_projection(self):
        config = configuration()

        class DB:
            def execute(*args):
                self.fail("ordinary dungeon queried excavation state")

        self.assertIs(dungeon_excavation_runtime.hydrate(DB(), 90, config), config)

    def test_rotation_never_fabricates_levels_for_actual_fixed_native_family(self):
        for source in (26635, 26636, 26637):
            config = dungeon_rotation.project(configuration(), source)
            config["level_policy"] = dict(
                mode="native_minimum",
                provenance="Explicit fixed native cycle exception",
            )
            for room in config["compiled_plan"]["rooms"][:4]:
                select = dungeon_stage_levels.selector(config, room_order=room["order"])
                for monster in room["monsters"]:
                    native = dict(
                        min_level=monster["native_min_level"],
                        max_level=monster["native_max_level"],
                    )
                    self.assertEqual(native["min_level"], native["max_level"])
                    self.assertEqual(select(native, native), native["min_level"])

    def test_retry_window_replays_without_rng_or_shovel_mutation(self):
        rule = dict(
            outcome="excavation_state",
            consume_units=0,
            key_probability=[1, 10],
            attempt_interval_ms=1000,
            timing_authority="explicit_reconstruction_not_native_action_parameters",
            item_reference=20485,
            action_id=8143,
            ground_authority=dict(
                map_id=1075,
                authority="reviewed_native_sand_reconstruction",
                targets=[dict(position=[1, 0, 0], approach_cells=[[0, 0, 0]])],
            ),
        )
        statements = []

        class DB:
            info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)

            def execute(self, sql, params):
                statements.append(sql)
                row = None
                if sql.startswith("SELECT * FROM dungeon_excavation_runs"):
                    row = dict(
                        catalog_hash="catalog",
                        rule_sha256=dungeon_excavation.digest(rule),
                        selected_source_id=None,
                        key_state_uid=None,
                    )
                elif sql.startswith("SELECT * FROM dungeon_excavation_actors"):
                    row = dict(last_attempt=1, next_attempt_ms=2000)
                elif sql.startswith("SELECT * FROM dungeon_excavation_attempts"):
                    row = dict(found_key=False)
                return SimpleNamespace(fetchone=lambda: row)

        character = dict(id=7, instance_id=90, map_id=1075, x=0, y=0, z=0)
        item = dict(uid=22, character_id=7, reference=20485, quantity=1)
        with patch.object(
            dungeon_excavation, "_fresh_run", return_value=dict(catalog_hash="catalog")
        ):
            result = dungeon_excavation.attempt_locked(
                SimpleNamespace(clock=lambda: 1),
                DB(),
                instance_id=90,
                character=character,
                item=item,
                request=dict(source_uid=22, action_id=8143, x=1, y=0),
                rule=rule,
                now_ms=1000,
                randbelow=lambda n: self.fail("retry rerolled"),
            )
        self.assertTrue(result["replay"])
        self.assertEqual(result["consumed"], 0)
        self.assertFalse(
            any(
                "INSERT INTO dungeon_excavation_attempts" in q
                or "UPDATE inventory_items" in q
                or "DELETE FROM inventory_items" in q
                for q in statements
            )
        )

    def test_existing_spawn_or_encounter_prevents_plan_replacement(self):
        for reject_table in ("dungeon_room_spawn_receipts", "dungeon_room_encounters"):

            class DB:
                def execute(self, sql, params):
                    if "FROM dungeon_room_runs" in sql:
                        row = dict(status="active", current_room=1, revision=1)
                    elif reject_table in sql:
                        row = {"owned": 1}
                    else:
                        row = None
                    return SimpleNamespace(fetchone=lambda: row)

            with self.subTest(table=reject_table), self.assertRaises(ValueError):
                dungeon_excavation._fresh_run(DB(), 90)

    def test_selected_choice_replay_never_reconsumes_missing_state(self):
        statements = []

        class DB:
            info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)

            def execute(self, sql, params):
                statements.append(sql)
                row = (
                    dict(catalog_hash="catalog", branch_key="26636")
                    if "FROM dungeon_room_runs" in sql
                    else dict(catalog_hash="catalog", selected_source_id=26636)
                )
                return SimpleNamespace(fetchone=lambda: row)

        result = dungeon_excavation.choose_locked(
            SimpleNamespace(clock=lambda: 1),
            DB(),
            instance_id=90,
            character_id=7,
            config={},
            source_id=26636,
        )
        self.assertTrue(result["replay"])
        self.assertTrue(all(q.startswith("SELECT") for q in statements))

    def test_position_barrier_contention_is_recoverable_not_socket_timeout(self):
        from wakfu_server import dungeon_excavation_provider
        from wakfu_server.position_buffer import PositionOwnerBusy

        class DB:
            def execute(self, query, args):
                row = (
                    dict(instance_id=90)
                    if "SELECT c.instance_id" in query
                    else dict(status="active", party_id=1)
                )
                return SimpleNamespace(fetchone=lambda: row)

        class Store:
            now = lambda self: 0

            @contextmanager
            def connection(self):
                yield DB()

        class Positions:
            @contextmanager
            def account_barrier(self, *args, **kwargs):
                raise PositionOwnerBusy("injected owner contention")
                yield

            def flush(*args, **kwargs):
                raise AssertionError("busy barrier flushed")

        with self.assertRaisesRegex(ValueError, "position is busy"):
            with dungeon_excavation_provider.owned(
                Store(),
                1,
                "lease",
                7,
                dict(enabled=True),
                in_fight=False,
                positions=Positions(),
            ):
                self.fail("busy owner entered source transaction")

    def test_temporary_unit_offer_has_safe_value_error_before_binding_or_writes(self):
        from wakfu_server import player_exchanges

        reads = []

        class DB:
            def execute(self, query, args):
                reads.append(query)
                self_result = dict(
                    uid=22, character_id=7, quantity=1, instance_custody_id=90
                )
                return SimpleNamespace(fetchone=lambda: self_result)

        with self.assertRaisesRegex(ValueError, "temporary dungeon tool"):
            player_exchanges._offered_item(None, DB(), 1, 7, 22, 1)
        self.assertEqual(len(reads), 1)
        self.assertTrue(reads[0].startswith("SELECT"))

    def test_frozen_excavation_rule_has_only_reviewed_unique_adjacent_targets(self):
        from wakfu_server.dungeon_excavation_rules import rules

        rule = next(row for row in rules() if row["outcome"] == "excavation_state")
        targets = rule["ground_authority"]["targets"]
        self.assertEqual(rule["ground_authority"]["map_id"], 1075)
        self.assertEqual(len(targets), 137)
        self.assertEqual(len({tuple(row["position"][:2]) for row in targets}), 137)
        for row in targets:
            x, y, z = row["position"]
            self.assertTrue(row["approach_cells"])
            for ax, ay, az in row["approach_cells"]:
                self.assertEqual(abs(ax - x) + abs(ay - y), 1)


from wakfu_server import dungeon_rotation_cache as cache


def cached_source_configuration():
    c = configuration()
    c["route"] = dict(key="native-cycle-fixture")
    c["context_policy"] = dict(policy_version=1)
    c["evidence_hashes"] = {
        name: dungeon_runtime_config.canonical_hash(value)
        for name, value in [
            ("plan", c["compiled_plan"]),
            ("topology", c["topology"]),
            ("route", c["route"]),
        ]
    }
    return c


class PinnedProjectionCacheTests(unittest.TestCase):
    def setUp(self):
        cache.clear()

    def test_three_rotations_equal_pure_and_json_round_trip(self):
        c = cached_source_configuration()
        for selector in (26635, 26636, 26637):
            self.assertEqual(
                cache.project_pinned(c, selector), dungeon_rotation.project(c, selector)
            )
            self.assertEqual(
                json.loads(json.dumps(cache.project_pinned(c, selector))),
                dungeon_rotation.project(c, selector),
            )

    def test_hits_do_not_repeat_projection_and_context_stays_fresh(self):
        c = cached_source_configuration()
        with patch.object(
            dungeon_rotation, "project", wraps=dungeon_rotation.project
        ) as build:
            first = cache.project_pinned(c, 26636)
            second_source = deepcopy(c)
            second_source["context_policy"]["policy_version"] = 2
            second_source["level_policy"]["provenance"] = "fresh context"
            second = cache.project_pinned(second_source, 26636)
            self.assertEqual(build.call_count, 1)
        self.assertIs(first["topology"], second["topology"])
        self.assertEqual(second["context_policy"]["policy_version"], 2)
        second["context_policy"]["policy_version"] = 3
        self.assertEqual(second_source["context_policy"]["policy_version"], 2)

    def test_readonly_nested_parts_cannot_poison_later_instances(self):
        c = cached_source_configuration()
        a = cache.project_pinned(c, 26635)
        with self.assertRaises(TypeError):
            a["topology"]["rooms"][0]["cells"][0][0] = 999
        with self.assertRaises(TypeError):
            a["compiled_plan"]["rooms"].append({})
        with self.assertRaises(TypeError):
            a["evidence_hashes"]["plan"] = "bad"
        self.assertEqual(
            cache.project_pinned(c, 26635), dungeon_rotation.project(c, 26635)
        )

    def test_pending_actor_flags_never_enter_shared_parts(self):
        c = cached_source_configuration()
        c["topology"]["_rotation_pending"] = True
        c["topology"]["_rotation_key_character_id"] = 7
        result = cache.project_pinned(c, 26635)
        self.assertNotIn("_rotation_pending", result["topology"])
        self.assertNotIn("_rotation_key_character_id", result["topology"])

    def test_dynamic_projection_bypasses_cache_and_changed_source_invalidates(self):
        c = cached_source_configuration()
        c["topology"]["_dynamic_instance_cells"] = [7]
        with patch.object(
            dungeon_rotation, "project", wraps=dungeon_rotation.project
        ) as build:
            cache.project_pinned(c, 26635)
            c["topology"]["_dynamic_instance_cells"] = [8]
            self.assertEqual(
                cache.project_pinned(c, 26635)["topology"]["_dynamic_instance_cells"],
                [8],
            )
            self.assertEqual(build.call_count, 2)
        c = cached_source_configuration()
        a = cache.project_pinned(c, 26635)
        c["compiled_plan"]["review"] = "updated source"
        c["evidence_hashes"]["plan"] = dungeon_runtime_config.canonical_hash(
            c["compiled_plan"]
        )
        b = cache.project_pinned(c, 26635)
        self.assertNotEqual(a["evidence_hashes"]["plan"], b["evidence_hashes"]["plan"])

    def test_invalid_selector_or_reprojecting_derived_state_is_rejected(self):
        for bad in (True, [], 0):
            with self.assertRaises(ValueError):
                cache.project_pinned(cached_source_configuration(), bad)
        with self.assertRaises(ValueError):
            cache.project_pinned(
                cache.project_pinned(cached_source_configuration(), 26635), 26635
            )


if __name__ == "__main__":
    unittest.main()
