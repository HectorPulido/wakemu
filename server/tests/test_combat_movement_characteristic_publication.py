"""Movement followups publish native PCs without replaying POSITION."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import struct
import sys
import os
import unittest
from unittest.mock import patch

from test_combat_movement_runtime import MovementRuntimeTests, AIMovementRuntimeTests
from wakfu_server.combat_movement_runtime import (
    apply_client,
    apply_ai,
    movement_stats_snapshot,
)
from wakfu_server.combat_wire import decode_actor_state
from wakfu_server.combat_actor import actor_stats, monster_actor_stats
from wakfu_server.combat_characteristic_snapshot import characteristics_only_snapshot


def full_stats(actor, state=None):
    rows = [(2, actor.ap, 0, actor.max_ap, 0), (3, actor.mp, 0, actor.max_mp, 0)]
    table = struct.pack(">H", len(rows)) + b"".join(
        struct.pack(">Biiii", *row) for row in rows
    )
    record = dict(
        id=actor.id,
        account_id=7,
        level=1,
        breed=getattr(actor, "fixture_breed", 3),
        hp=actor.hp,
        max_hp=actor.max_hp,
        x=actor.position[0],
        y=actor.position[1],
        z=actor.position[2],
        map_id=1,
        team=actor.team,
        ref=getattr(actor, "fixture_reference", 1),
    )
    if actor.controlled and not getattr(actor, "native_summon_source", None):
        authority = getattr(actor, "native_controlled_by_ai", None)
        if authority is None:
            authority = False
        return actor_stats(
            record,
            2,
            actor.team,
            wp=0,
            direction=getattr(actor, "direction", None) or 0,
            characteristics_payload=table,
            native_controlled_by_ai=authority,
            fight_property_counts=getattr(actor, "native_fight_property_counts", None),
        )
    return monster_actor_stats(
        record,
        2,
        characteristics_payload=table,
        fight_property_counts=getattr(actor, "native_fight_property_counts", {}),
    )


def publications(packets):
    return [decode_actor_state(op, body) for op, body in packets if op == 12873]


class MovementCharacteristicPublicationTests(unittest.TestCase):
    def test_all_partial_producers_preserve_live_world_and_fight_counters(self):
        """Unit producer boundaries; no native paid gate/AI planning claim."""
        from wakfu_server.combat_movement_runtime import movement_stats_snapshots
        from wakfu_server.combat_property_stack import remove_property
        from wakfu_server.combat_characteristic_snapshot import (
            characteristics_and_properties_snapshots,
        )

        def seed(runtime):
            for index, actor in enumerate(runtime.fight.actors.values()):
                actor.native_fight_property_counts = {40: 1}
                actor.native_fight_properties = frozenset({40})
                actor.native_world_property_counts = {47: 3, 4: 0}
                actor.native_world_properties = frozenset({47})
                actor.native_obstacle_id = index
                actor.fixture_reference = 41
                actor.direction = 0
                actor.physical_radius = 0
            return runtime

        def properties(payload):
            self.assertEqual(payload[0], 26)
            cursor, namespaces = 1, []
            for _ in range(2):
                self.assertEqual(
                    payload[cursor], 1, "Both complete PB namespaces are required"
                )
                count = struct.unpack_from(">H", payload, cursor + 1)[0]
                cursor += 3
                pairs = list(
                    struct.iter_unpack(">bb", payload[cursor : cursor + 2 * count])
                )
                self.assertEqual(len(dict(pairs)), count)
                namespaces.append(dict(pairs))
                cursor += 2 * count
            self.assertEqual(cursor, len(payload))
            return namespaces

        def verify(packets, runtime):
            rows = publications(packets)
            partial = 0
            for index, row in enumerate(rows):
                if row["state"][0] != 40:
                    continue
                partial += 1
                self.assertLess(index + 1, len(rows))
                companion = rows[index + 1]
                self.assertEqual(companion["actor_id"], row["actor_id"])
                actor = runtime.fight.actors[row["actor_id"]]
                self.assertEqual(
                    properties(companion["state"]),
                    [
                        actor.native_world_property_counts,
                        actor.native_fight_property_counts,
                    ],
                )
                self.assertEqual(
                    row["state"], characteristics_only_snapshot(full_stats(actor))
                )
            self.assertGreater(
                partial, 0, "The actual producer must emit its partial snapshot"
            )
            return partial

        # Complete PC3, NPC2 and captured-summon2 encoders share the real
        # variable rK boundary. Counter removal is the original signed PB rule.
        for kind in ("player", "npc", "captured"):
            with self.subTest(codec=kind):
                runtime, actor = (
                    AIMovementRuntimeTests().setup_fight()
                    if kind != "player"
                    else MovementRuntimeTests().setup_fight()
                )
                seed(runtime)
                if kind == "captured":
                    actor.native_summon_source = {"ref": 41, "caster_id": 1}
                actor.native_fight_property_counts.update({3: 2, 88: 2, 103: 2})
                previous = full_stats(actor)
                for remaining in (2, 1, 0):
                    counts = actor.native_fight_property_counts
                    actor.native_fight_properties = frozenset(
                        k for k, v in counts.items() if v
                    )
                    current = full_stats(actor)
                    keys = (
                        "hp",
                        "max_hp",
                        "ap",
                        "mp",
                        "position",
                        "direction",
                        "native_obstacle_id",
                        "native_world_property_counts",
                        "native_fight_property_counts",
                    )
                    before = deepcopy({key: getattr(actor, key) for key in keys})
                    projected = movement_stats_snapshots(current, previous, actor=actor)
                    self.assertEqual([payload[0] for payload in projected], [40, 26])
                    self.assertEqual(properties(projected[1]), [{47: 3, 4: 0}, counts])
                    self.assertEqual(
                        {key: getattr(actor, key) for key in keys},
                        before,
                        "Projection cannot mutate stats/position/QI",
                    )
                    if kind == "player":
                        table_end = 39 + 2 + 2 * 17
                        property_end = table_end + 3 + 2 * len(counts)
                        self.assertEqual(
                            struct.unpack_from(">h", current, property_end)[0], 3
                        )
                        self.assertEqual(current[property_end + 2], 0)
                    previous = current
                    if remaining:
                        for identity in (3, 88, 103):
                            self.assertEqual(
                                remove_property(counts, identity), remaining - 1
                            )

        with self.subTest(codec="legacy_capture_world_constructor_guard"):
            from wakfu_server.combat_property_wire import actor_property_snapshot

            runtime, actor = AIMovementRuntimeTests().setup_fight()
            seed(runtime)
            actor.fixture_reference = 4
            actor.native_world_property_counts = None
            actor.native_world_properties = frozenset({47})
            source = dict(
                ref=4,
                native_relation_source="big.new_bje.fdt_initial_registration",
                native_symbiot_source="eZr324.after_common_factory_and_fan.lE_true",
            )
            actor.native_summon_source = source
            catalog = {
                "player": {"world_properties": [], "fight_properties": []},
                "npc": {"4": {"world_properties": [], "fight_properties": [40]}},
            }
            with patch(
                "wakfu_server.combat_ordinary_authority.native_property_catalog",
                return_value=catalog,
            ):
                full = full_stats(actor)
                self.assertEqual(
                    properties(actor_property_snapshot(full, actor))[0], {47: 1}
                )
                actor.native_summon_source = dict(
                    source, native_symbiot_source="eZl.new_eHD.pRO_false"
                )
                self.assertEqual(
                    properties(actor_property_snapshot(full, actor))[0], {47: 1}
                )
                for invalid in (
                    dict(source, ref=41),
                    dict(source, native_relation_source="foreign"),
                    dict(source, native_symbiot_source="foreign"),
                ):
                    actor.native_summon_source = invalid
                    with self.assertRaises(ValueError):
                        actor_property_snapshot(full, actor)
                actor.native_summon_source = source
                actor.native_world_properties = frozenset({47, 70})
                with self.assertRaises(ValueError):
                    actor_property_snapshot(full, actor)
                actor.native_world_properties = frozenset({47})
                actor.native_world_property_counts = {47: 2}
                self.assertEqual(
                    properties(actor_property_snapshot(full, actor))[0], {47: 2}
                )
                actor.native_world_property_counts = None
                catalog["npc"]["4"]["world_properties"] = [1, 1]
                actor.native_world_properties = frozenset({1, 47})
                self.assertEqual(
                    properties(actor_property_snapshot(full, actor))[0], {1: 2, 47: 1}
                )
                catalog["npc"]["4"]["world_properties"] = [47, 47]
                actor.native_world_properties = frozenset({47})
                self.assertEqual(
                    properties(actor_property_snapshot(full, actor))[0], {47: 2}
                )
                player_runtime, player = MovementRuntimeTests().setup_fight()
                seed(player_runtime)
                player.native_world_property_counts = None
                player.native_world_properties = frozenset({47})
                player.native_summon_source = source
                # A PC full3 cannot borrow the captured full2 constructor rule.
                player.native_summon_source = None
                pc = full_stats(player)
                player.native_summon_source = source
                with self.assertRaises(ValueError):
                    actor_property_snapshot(pc, player)

        with self.subTest(producer="apply_client"):
            runtime, actor = MovementRuntimeTests().setup_fight()
            seed(runtime)
            packets, _ = apply_client(
                runtime, 7, struct.pack(">qiih", actor.id, 1, 0, 0), full_stats
            )
            verify(packets, runtime)
            self.assertEqual((actor.position, actor.mp), ((1, 0, 0), 2))

        with self.subTest(producer="apply_ai"):
            runtime, actor = AIMovementRuntimeTests().setup_fight()
            seed(runtime)
            with patch(
                "wakfu_server.combat_ai.plan",
                return_value={"path": [(1, 0, 0)], "attack": None},
            ):
                packets, _ = apply_ai(runtime, full_stats, direction=2)
            verify(packets, runtime)

        with self.subTest(producer="area_nonmover_refresh"):
            runtime, actor = MovementRuntimeTests().setup_fight()
            seed(runtime)
            runtime.stats_serializer = full_stats
            runtime.runtime_stats_serializer = full_stats
            runtime.fight.actors[-2].effect_stats = {2: runtime.fight.actors[-2].ap}

            def area(state, **boundary):
                state = deepcopy(state)
                state.actors[-2].ap -= 1
                state.actors[-2].effect_stats[2] -= 1
                return state, [(12613, b"unit-area-resource-change")]

            packets, _ = apply_client(
                runtime,
                7,
                struct.pack(">qiih", actor.id, 1, 0, 0),
                full_stats,
                area_provider=area,
            )
            self.assertGreaterEqual(verify(packets, runtime), 2)

        from wakfu_server.combat_tactical_ai import NativeProvider, Preview

        for oracle_path in (False, True):
            if oracle_path and os.environ.get("WAKFU_QA_PROPERTIES_UNIT_NO_SDK") == "1":
                # Source-only qualification cannot replace the real compiled
                # spell catalog imported by NativeOracle's move caller. The
                # default complete-image run must execute this eighth path.
                print(
                    "UNIT_ONLY: native_oracle deferred to matching complete image",
                    flush=True,
                )
                continue
            with self.subTest(
                producer="native_oracle" if oracle_path else "native_provider"
            ):
                runtime, actor = AIMovementRuntimeTests().setup_fight()
                seed(runtime)
                candidate = deepcopy(runtime)
                candidate.fight.server_move(actor.id, [(1, 0, 0)])
                candidate.action_id = 1
                if oracle_path:
                    ai_root = str(Path(__file__).resolve().parents[1] / "ai-service")
                    if ai_root not in sys.path:
                        sys.path.insert(0, ai_root)
                    from wakfu_ai.native.native_oracle import NativeOracle

                    oracle = object.__new__(NativeOracle)
                    oracle.runtime, oracle.flags = runtime, {}
                    oracle.authorities = lambda state: {}
                    oracle.preview = lambda *args, **kwargs: (candidate, [], None)
                    with patch("wakfu_ai.native.native_oracle.check"), patch(
                        "wakfu_ai.native.native_oracle.complete_fingerprint",
                        return_value="unit-owned",
                    ):
                        packets = oracle.commit(
                            {"type": "move"}, stats_serializer=full_stats
                        )
                else:
                    provider = SimpleNamespace(
                        area_provider=None,
                        preview=lambda *args, **kwargs: Preview(candidate.fight),
                    )
                    with patch(
                        "wakfu_server.combat_tactical_ai._source_key",
                        return_value="unit-owned",
                    ):
                        packets = NativeProvider.commit(
                            provider, runtime, {"type": "move"}, full_stats
                        )
                verify(packets, runtime)

        # Unit gate collaborators provide known endpoint occupancy and actor
        # authority; the real admission/payment/serialization functions execute.
        from wakfu_server.combat_runtime_adapter import NativeActorAuthority
        from wakfu_server.combat_portal_travel import try_apply_portal_travel
        from wakfu_server.combat_hour_travel import try_apply_hour_travel

        authority = NativeActorAuthority(
            targeting={"baF": False, "baG": True, "baK": False, "dpu_id": None},
            is_player=True,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=5,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
        )
        for hour in (False, True):
            with self.subTest(producer="hour" if hour else "portal"):
                runtime, actor = MovementRuntimeTests().setup_fight()
                seed(runtime)
                actor.fixture_breed = 5
                actor.effect_stats = {2: actor.ap, 3: actor.mp, 4: 6}
                runtime.fight.native_rail_movement_authority = lambda *args: authority
                runtime.fight.native_rail_movement_authority.properties = (
                    lambda *args: frozenset()
                )
                rows = {
                    uid: dict(
                        uid=uid,
                        native_type_id=1 if hour else 19,
                        native_hour_contract=hour,
                        native_area_contract="faZ" if hour else "faV",
                        owner_id=actor.id,
                        cell=cell,
                        native_cells_xy=(cell[:2],),
                        native_fight_affiliation=0,
                        native_fight_affiliation_source="faV.j(PV).bcM",
                    )
                    for uid, cell in ((11, (0, 0, 0)), (12, (2, 0, 0)))
                }
                runtime.fight.native_effect_areas = rows
                from wakfu_server.combat_qi_registry import NativeQIRegistry
                from wakfu_server.combat_qi_fight import install_fresh_actor_slots

                arena = dict(x=0, y=0, width=4, height=1, cell_masks=[0] * 4)
                slots = [None] * 127
                for value in runtime.fight.actors.values():
                    slots[value.native_obstacle_id] = dict(
                        identity=["actor", value.id],
                        position=list(value.position[:2]),
                        radius=value.physical_radius,
                        indexed=True,
                        movement_blocking=True,
                    )
                registry = NativeQIRegistry(arena, slots)
                registry.capture_fresh_cell_topology(
                    [
                        value.native_obstacle_id
                        for value in runtime.fight.actors.values()
                    ]
                )
                runtime.fight.native_qi_snapshot = arena
                install_fresh_actor_slots(runtime.fight, registry)
                with patch(
                    "wakfu_server.combat_qi_movement.movement_blocked_cells",
                    return_value=frozenset(),
                ), patch(
                    "wakfu_server.combat_effect_area_queries._rows",
                    return_value=tuple(rows.values()),
                ):
                    fn = try_apply_hour_travel if hour else try_apply_portal_travel
                    result = fn(
                        runtime,
                        7,
                        actor.id,
                        [(2, 0, 0)],
                        full_stats,
                        step_callback=lambda *args: None,
                    )
                self.assertIsNotNone(result)
                verify(result[0], runtime)
                self.assertEqual(runtime.fight.actors[actor.id].position, (2, 0, 0))

        with self.subTest(producer="consumable_entry_health"):
            from wakfu_server.combat_consumable_states import _entry_health

            runtime, actor = MovementRuntimeTests().setup_fight()
            seed(runtime)
            actor.effect_frozen = frozenset()
            actor.effect_stats = {4: 6}
            actor.effect_maxima = {4: 6}
            character = dict(
                id=actor.id,
                account_id=7,
                breed=3,
                level=1,
                hp=actor.hp,
                max_hp=actor.max_hp,
                hp_damage=5,
                health_dead=False,
                x=0,
                y=0,
                z=0,
                map_id=1,
            )
            # The unit targets this producer's real wound policy and packet
            # publication; raw HP PA metadata and full gear serialization have
            # separate native paid qualification. No catalog guard is patched.
            with patch(
                "wakfu_server.combat_hp_raw.set_hp_raw_current",
                side_effect=lambda value, hp: setattr(value, "hp", hp),
            ), patch(
                "wakfu_server.combat_actor.actual_actor_stats",
                side_effect=lambda character, value, *args, **kwargs: full_stats(value),
            ):
                packets = _entry_health(runtime.fight, character, actor)
            self.assertEqual(actor.hp, actor.max_hp - 5)
            rows = publications(packets)
            self.assertEqual([row["state"][0] for row in rows], [40, 26])
            self.assertEqual(properties(rows[1]["state"]), [{47: 3, 4: 0}, {40: 1}])

    def test_nonmover_direction_change_retains_full_position(self):
        _, actor = MovementRuntimeTests().setup_fight()
        before = full_stats(actor)
        actor.direction = 3
        after = full_stats(actor)
        self.assertEqual(
            movement_stats_snapshot(after, before, position_owned=False), after
        )
        self.assertEqual(movement_stats_snapshot(after, before)[0], 40)

    def test_player_movement_publishes_paid_resources_without_position(self):
        runtime, actor = MovementRuntimeTests().setup_fight()
        packets, event = apply_client(
            runtime, 7, struct.pack(">qiih", actor.id, 1, 0, 0), full_stats
        )
        state = publications(packets)[0]["state"]
        self.assertEqual(state[0], 40)
        self.assertEqual(state, characteristics_only_snapshot(full_stats(actor)))
        self.assertEqual((actor.position, actor.mp, event["cost"]), ((1, 0, 0), 2, 1))
        self.assertEqual([op for op, _ in packets], [13624, 13420, 12873, 12873])

    def test_npc_movement_publishes_paid_resources_without_position(self):
        runtime, actor = AIMovementRuntimeTests().setup_fight()
        plan = {"path": [(1, 0, 0), (2, 0, 0), (3, 0, 0)], "attack": None}
        with patch("wakfu_server.combat_ai.plan", return_value=plan):
            packets, result = apply_ai(runtime, full_stats, direction=2)
        state = publications(packets)[0]["state"]
        self.assertEqual(state[0], 40)
        self.assertEqual(state, characteristics_only_snapshot(full_stats(actor)))
        self.assertEqual((actor.mp, result["event"]["cost"]), (0, 3))

    def test_area_callbacks_precede_partial_snapshot_with_final_resources(self):
        runtime, actor = MovementRuntimeTests().setup_fight()

        def area(state, **boundary):
            state = deepcopy(state)
            state.actors[actor.id].ap -= 2
            return state, [(12613, b"owned-relative-AP")]

        packets, _ = apply_client(
            runtime,
            7,
            struct.pack(">qiih", actor.id, 1, 0, 0),
            full_stats,
            area_provider=area,
        )
        state = publications(packets)[0]["state"]
        self.assertEqual(state[0], 40)
        self.assertEqual(struct.unpack_from(">i", state, 4)[0], actor.ap)
        self.assertLess(
            next(i for i, p in enumerate(packets) if p[0] == 12613),
            next(i for i, p in enumerate(packets) if p[0] == 12873),
        )

    def test_area_control_change_keeps_full_native_actor_state(self):
        runtime, actor = MovementRuntimeTests().setup_fight()

        def area(state, **boundary):
            state = deepcopy(state)
            state.actors[actor.id].native_controlled_by_ai = True
            return state, []

        packets, _ = apply_client(
            runtime,
            7,
            struct.pack(">qiih", actor.id, 1, 0, 0),
            full_stats,
            area_provider=area,
        )
        state = publications(packets)[0]["state"]
        self.assertEqual(state[0], 3)
        from wakfu_server.combat_property_wire import _fighter_property_section

        counts, breed = _fighter_property_section(state)
        table_end = 39 + 2 + 2 * 17
        property_end = (
            table_end + 1 + (2 + 2 * len(counts) if counts is not None else 0)
        )
        self.assertEqual(struct.unpack_from(">h", state, property_end)[0], breed)
        self.assertEqual(state[property_end + 2], 1)

    def test_both_native_ai_commit_paths_project_movement_followups(self):
        from wakfu_server.combat_tactical_ai import NativeProvider, Preview

        ai_root = str(Path(__file__).resolve().parents[1] / "ai-service")
        if ai_root not in sys.path:
            sys.path.insert(0, ai_root)
        from wakfu_ai.native.native_oracle import NativeOracle

        for oracle_path in (False, True):
            with self.subTest(oracle=oracle_path):
                runtime, actor = AIMovementRuntimeTests().setup_fight()
                candidate = deepcopy(runtime)
                candidate.fight.server_move(actor.id, [(1, 0, 0)])
                candidate.action_id = 1
                if oracle_path:
                    oracle = object.__new__(NativeOracle)
                    oracle.runtime = runtime
                    oracle.flags = {}
                    oracle.authorities = lambda state: {}
                    oracle.preview = lambda *args, **kwargs: (candidate, [], None)
                    with patch("wakfu_ai.native.native_oracle.check"), patch(
                        "wakfu_ai.native.native_oracle.complete_fingerprint",
                        return_value="owned",
                    ):
                        packets = oracle.commit(
                            {"type": "move"}, stats_serializer=full_stats
                        )
                else:
                    provider = SimpleNamespace(
                        area_provider=None,
                        preview=lambda *args, **kwargs: Preview(candidate.fight),
                    )
                    with patch(
                        "wakfu_server.combat_tactical_ai._source_key",
                        return_value="owned",
                    ):
                        packets = NativeProvider.commit(
                            provider, runtime, {"type": "move"}, full_stats
                        )
                self.assertEqual(len(publications(packets)), 4)
                self.assertTrue(
                    [row["state"][0] for row in publications(packets)]
                    == [40, 26, 40, 26]
                )
                self.assertEqual(runtime.fight.actors[actor.id].mp, 2)


if __name__ == "__main__":
    unittest.main()
