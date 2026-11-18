"""Real-source ownership, native timers and original-victory qualification."""

from contextlib import nullcontext
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server.achievements import source_quest_encounters as source
from wakfu_server.application import source_quest_encounter_dispatch as dispatch
from wakfu_server.combat_state import Fight, Actor
from wakfu_server.application.world_publication import WorldPublication


def state():
    return dict(
        variables={},
        objectives=[],
        running=[2145, 2146],
        completed=[],
        tracking=[],
        recent=[],
        completion_dates={},
        active=[2145, 2146],
        active_periods={},
        active_unknown=[],
    )


class SourceQuestEncounterTests(unittest.TestCase):
    def setUp(self):
        self.document = source.document()
        self.binding = next(
            row for row in self.document["bindings"] if row["quest_id"] == 2145
        )
        self.character = dict(
            id=7, account_id=2, map_id=527, instance_id=0, x=-134, y=42, z=0
        )
        self.originals = [dict(id=-111, ref=3284, x=-133, y=42, z=0)]
        self.payload = dict(
            schema=source.SCHEMA,
            owner=7,
            binding=self.binding["id"],
            source_sha256=source.digest(self.document),
            group_key=[527, 0, 333],
            members=self.originals,
            fight_id=123,
        )

    def test_sources_separate_three_gathers_from_four_actual_scenario_ambushes(self):
        bindings = [
            row for row in self.document["bindings"] if row["quest_id"] in (2145, 2146)
        ]
        self.assertEqual(len(bindings), 7)
        self.assertEqual(
            len([row for row in bindings if row["mode"] == "gather"]),
            3,
        )
        self.assertEqual(
            {row["scenario"]["id"] for row in bindings if row["mode"] == "encounter"},
            {1747, 1749, 1751, 1753},
        )
        self.assertTrue(all(row["native_occupation_ms"] == 3000 for row in bindings))
        self.assertEqual(self.binding["roster"], [dict(reference=3284, count=1)])
        for row in bindings:
            self.assertFalse(
                any(
                    "hp" in actor or "level" in actor or "spells" in actor
                    for actor in row["roster"]
                )
            )

    def test_sewer_declarations_reuse_exact_sources_native_floor_and_scenario_guards(
        self,
    ):
        rows = [
            row for row in self.document["bindings"] if row["quest_id"] in (2150, 2151)
        ]
        self.assertEqual(len(rows), 7)
        self.assertEqual(
            {row["source"]["id"] for row in rows},
            {24126, 24138, 24139, 24140, 24141, 24142, 24143},
        )
        self.assertEqual(
            {row["scenario"]["id"] for row in rows if row["scenario"]},
            {1726, 1768, 1766, 1764},
        )
        progress = state()
        progress["running"] = progress["active"] = [2150, 2151]
        for row in rows:
            self.assertTrue(
                source.recognizes(546, struct.pack(">qHH", row["source"]["id"], 0, 0))
            )
            self.assertTrue(
                source.source_guard(row["action"]["criterion"], progress, is_hero=False)
            )
            active_effects = [
                effect
                for effect in row["action"]["effects"]
                if source.source_guard(effect["criterion"], progress, is_hero=False)
            ]
            self.assertTrue(active_effects)
            if row["scenario"]:
                self.assertEqual(
                    [
                        effect["parameters"]
                        for effect in active_effects
                        if effect["effect_type"] == 10
                    ],
                    [[str(row["scenario"]["id"])]],
                )
        nest = next(row for row in rows if row["quest_id"] == 2150)
        self.assertEqual(nest["source"]["z"], 3)
        self.assertEqual(nest["approaches"], [[-29, -51, 0]])
        source._source_position(
            dict(self.character, map_id=546, x=-29, y=-51, z=0),
            nest,
            struct.pack(">qHH", 24126, 0, 0),
        )

    def test_four_astrub_field_rosters_keep_owner_attack_path_with_full_native_formation(
        self,
    ):
        from wakfu_server import (
            combat_actor_snapshot,
            combat_sn_path,
            combat_walk_surface_policy,
        )
        from wakfu_server.actor_approach import combat_approach
        from wakfu_server.combat_geometry import published_geometry

        geometry = published_geometry(546)
        profiles = combat_actor_snapshot.native_actor_catalog()
        columns = combat_sn_path.NativeSnColumns.from_published(546)
        rows = [
            row
            for row in source.document()["bindings"]
            if row.get("source", {}).get("id") in (24126, 24139, 24141, 24143)
        ]
        self.assertEqual(
            {row["source"]["id"] for row in rows}, {24126, 24139, 24141, 24143}
        )
        original_cells = geometry.cells
        original_outgoing = geometry.outgoing
        original_incoming = geometry.incoming
        for row in rows:
            with self.subTest(source_id=row["source"]["id"]):
                origin = tuple(row["approaches"][0])
                references = [
                    entry["reference"]
                    for entry in row["roster"]
                    for _ in range(entry["count"])
                ]
                self.assertTrue(
                    combat_walk_surface_policy.native_player_point_placement_allowed(
                        columns, origin
                    )
                )
                positions = source.ordinary_source_formation(
                    geometry, origin, references, profiles, set(), columns
                )
                self.assertEqual(len(positions), len(references))
                members = [
                    dict(
                        id=-(index + 1), ref=reference, x=cell[0], y=cell[1], z=cell[2]
                    )
                    for index, (reference, cell) in enumerate(
                        zip(references, positions)
                    )
                ]
                legal, _ = combat_approach(
                    geometry,
                    members,
                    members[0]["id"],
                    profiles,
                    final_cell_allowed=lambda cell: (
                        combat_walk_surface_policy.native_player_point_placement_allowed(
                            columns, cell
                        )
                    ),
                )
                self.assertIn(origin, legal)
                self.assertEqual(len(set(positions)), len(positions))
                for reference, cell in zip(references, positions):
                    radius = profiles["npc_profiles"][str(reference)]["physical_radius"]
                    if radius == 0:
                        self.assertTrue(
                            combat_walk_surface_policy.native_npc_point_placement_allowed(
                                columns, cell
                            )
                        )
                if row["source"]["id"] == 24126:
                    self.assertEqual(len(positions), 3)
                    self.assertGreater(
                        abs(origin[0] - positions[2][0])
                        + abs(origin[1] - positions[2][1]),
                        1,
                    )
        self.assertIs(geometry.cells, original_cells)
        self.assertIs(geometry.outgoing, original_outgoing)
        self.assertIs(geometry.incoming, original_incoming)

    def test_magnum_well_native_formation_keeps_owner_route_and_rejects_walls(self):
        from pathlib import Path
        from wakfu_server import (
            combat_actor_snapshot,
            combat_sn_path,
            combat_walk_surface_policy,
        )
        from wakfu_server.actor_approach import (
            ApproachUnavailable,
            approach_path,
            combat_approach,
        )
        from wakfu_server.combat_geometry import (
            prepare_geometry,
            published_geometry,
            reachable,
        )

        profile = source._read_document(
            Path(__file__).parents[1]
            / "wakfu_server/achievements/quest_source_profiles/astrub-magnum-well.v1.json"
        )
        row = next(
            binding for binding in profile["bindings"] if binding["quest_id"] == 2706
        )
        origin = tuple(row["approaches"][0])
        references = [
            entry["reference"] for entry in row["roster"] for _ in range(entry["count"])
        ]
        geometry = published_geometry(1134)
        profiles = combat_actor_snapshot.native_actor_catalog()
        columns = combat_sn_path.NativeSnColumns.from_published(1134)
        positions = source.ordinary_source_formation(
            geometry, origin, references, profiles, set(), columns
        )
        self.assertEqual(positions, [(142, 8, 0), (145, 9, 0)])
        bodies = []
        from wakfu_server.combat_obstacle_condition import footprint

        for reference, cell in zip(references, positions):
            body = set(
                footprint(
                    cell, profiles["npc_profiles"][str(reference)]["physical_radius"]
                )
            )
            self.assertFalse(any(body & previous for previous in bodies))
            bodies.append(body)

        members = [
            dict(id=-(index + 1), ref=reference, x=cell[0], y=cell[1], z=cell[2])
            for index, (reference, cell) in enumerate(zip(references, positions))
        ]
        legal, blocked = combat_approach(
            geometry,
            members,
            members[0]["id"],
            profiles,
            final_cell_allowed=lambda cell: combat_walk_surface_policy.native_player_point_placement_allowed(
                columns, cell
            ),
        )
        self.assertNotIn(origin, blocked)
        route = approach_path(geometry, origin, legal.__contains__, blocked=blocked)
        self.assertEqual(route[0], origin)
        self.assertIn(route[-1], legal)
        self.assertIn((145, 8, 2), route)

        disconnected = prepare_geometry(
            dict(
                map_id=1134,
                cells=geometry.cells,
                edges=[
                    (start, end) for start, end in geometry.edges if start != origin
                ],
            )
        )
        self.assertEqual(
            reachable(origin, disconnected.cells, disconnected.outgoing), {origin}
        )
        with self.assertRaisesRegex(ValueError, "no ordinary native attack approach"):
            source.ordinary_source_formation(
                disconnected, origin, references, profiles, set(), columns
            )

    def test_four_existing_map527_ambushes_keep_their_declared_owner_approaches(self):
        from wakfu_server import (
            combat_actor_snapshot,
            combat_sn_path,
            combat_walk_surface_policy,
        )
        from wakfu_server.actor_approach import combat_approach
        from wakfu_server.combat_geometry import published_geometry

        expected = {
            4250: (24086, 3284, (-134, 42, 0)),
            4252: (24104, 3285, (-64, 106, 0)),
            4254: (24113, 3287, (-63, 110, 0)),
            4256: (24114, 3288, (-57, 114, 0)),
        }
        geometry = published_geometry(527)
        profiles = combat_actor_snapshot.native_actor_catalog()
        columns = combat_sn_path.NativeSnColumns.from_published(527)
        rows = [
            row
            for row in source.document()["bindings"]
            if row["objective_id"] in expected
        ]
        self.assertEqual({row["objective_id"] for row in rows}, set(expected))
        original = (geometry.cells, geometry.outgoing, geometry.incoming)
        for row in rows:
            objective = row["objective_id"]
            with self.subTest(objective=objective):
                source_id, reference, origin = expected[objective]
                self.assertEqual(row["source"]["id"], source_id)
                self.assertEqual(row["roster"], [{"reference": reference, "count": 1}])
                self.assertEqual(tuple(row["approaches"][0]), origin)
                self.assertTrue(
                    combat_walk_surface_policy.native_player_point_placement_allowed(
                        columns, origin
                    )
                )
                positions = source.ordinary_source_formation(
                    geometry, origin, [reference], profiles, set(), columns
                )
                self.assertEqual(len(positions), 1)
                cell = positions[0]
                member = [dict(id=-1, ref=reference, x=cell[0], y=cell[1], z=cell[2])]
                legal, _ = combat_approach(
                    geometry,
                    member,
                    -1,
                    profiles,
                    final_cell_allowed=lambda candidate: (
                        combat_walk_surface_policy.native_player_point_placement_allowed(
                            columns, candidate
                        )
                    ),
                )
                self.assertIn(origin, legal)
        self.assertIs(
            (geometry.cells, geometry.outgoing, geometry.incoming)[0], original[0]
        )
        self.assertIs(
            (geometry.cells, geometry.outgoing, geometry.incoming)[1], original[1]
        )
        self.assertIs(
            (geometry.cells, geometry.outgoing, geometry.incoming)[2], original[2]
        )

    def test_native_source_request_never_accepts_replay_action_or_other_object(self):
        self.assertTrue(source.recognizes(527, struct.pack(">qHH", 24086, 0, 0)))
        for body in (
            struct.pack(">qHH", 24086, 1, 0),
            struct.pack(">qHH", 24105, 0, 0),
            struct.pack(">qHH", 24086, 0, 1),
            b"",
        ):
            self.assertFalse(source.recognizes(527, body))
        self.assertFalse(source.recognizes(528, struct.pack(">qHH", 24086, 0, 0)))

    def test_native_guard_requires_owned_running_objective_and_real_nonhero(self):
        expression = "IsAchievementRunning(2146) and !IsAchievementObjectiveComplete(4252) && !IsHero()"
        self.assertTrue(source.source_guard(expression, state(), is_hero=False))
        self.assertFalse(source.source_guard(expression, state(), is_hero=True))
        completed = state()
        completed["objectives"] = [4252]
        self.assertFalse(source.source_guard(expression, completed, is_hero=False))
        with self.assertRaises(ValueError):
            source.source_guard(expression, state(), is_hero=None)
        with self.assertRaises(ValueError):
            source.source_guard(
                "IsAchievementRunning(9999) && UnknownSource()", state(), is_hero=False
            )

    def test_only_receipted_owner_sees_and_starts_its_actual_world_group(self):
        group = dict(key=(527, 0, 333), members=self.originals)
        db = Mock()
        db.execute.return_value.fetchall.return_value = [
            dict(
                character_id=7, event_key="quest-source-actor:111", payload=self.payload
            )
        ]
        self.assertEqual(source.visible_groups(db, [group], 7), [group])
        self.assertEqual(source.visible_groups(db, [group], 8), [])
        with self.assertRaisesRegex(ValueError, "another character"):
            source.admit(db, dict(self.character, id=8), self.originals, (527, 0, 333))
        damaged = deepcopy(group)
        damaged["members"][0]["x"] += 1
        with self.assertRaisesRegex(ValueError, "original group"):
            source.group_owners(db, [damaged])

    def test_ordinary_monsters_have_no_owner_or_settlement_queries(self):
        db = Mock()
        group = dict(key=(527, 0, 999), members=[dict(id=-444, ref=2616)])
        self.assertEqual(source.visible_groups(db, [group], 7), [group])
        self.assertEqual(
            source.settle(
                db, object(), self.character, SimpleNamespace(id=123), group["members"]
            ),
            [],
        )
        db.execute.assert_not_called()

    def fight(self, *, death=True):
        cells = [(0, 0, 0), (1, 0, 0), (2, 0, 0)]
        fight = Fight(
            123,
            [
                Actor(7, 0, cells[0], 100, 6, 3, 10, 6, owner_id=2, controlled=True),
                Actor(-111, 1, cells[1], 250, 6, 4, 18, 20),
            ],
            cells,
            {0: cells[:1], 1: cells[1:]},
        )
        fight.phase = "finished"
        fight.winner = 0
        fight.actors[-111].hp = 0
        fight.events = [dict(kind="death", actor_id=-111)] if death else []
        return fight

    def test_ordinary_or_animation_only_win_cannot_impersonate_a_source_victory(self):
        db = Mock()
        db.execute.return_value.fetchone.return_value = None
        with patch.object(source, "_advance") as advance:
            self.assertEqual(
                source.settle(
                    db, object(), self.character, self.fight(), self.originals
                ),
                [],
            )
            advance.assert_not_called()
        db.execute.return_value.fetchone.return_value = dict(payload=self.payload)
        with patch.object(source, "_advance") as advance:
            with self.assertRaisesRegex(ValueError, "real original enemy deaths"):
                source.settle(
                    db,
                    object(),
                    self.character,
                    self.fight(death=False),
                    self.originals,
                )
            advance.assert_not_called()

        marker = dict(
            kind="administrative_outcome",
            command="!winfight",
            account_id=self.character["account_id"],
            character_id=self.character["id"],
            winner=0,
        )
        administrative = self.fight(death=False)
        administrative.events = [marker]
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            dict(payload=self.payload),
            dict(members=self.originals, status="defeated"),
            dict(team=0, status="finished"),
        ]
        with patch.object(
            source, "_advance", return_value=[(13832, b"objective")]
        ) as advance:
            packets = source.settle(
                db, object(), self.character, administrative, self.originals
            )
        self.assertEqual([opcode for opcode, _ in packets], [13411, 13832])
        self.assertEqual(
            advance.call_args.kwargs["evidence"]["kind"],
            "administrative_original_encounter_victory",
        )

        for changed in (
            dict(marker, account_id=self.character["account_id"] + 1),
            dict(marker, character_id=self.character["id"] + 1),
            dict(marker, winner=1),
            dict(marker, command="!another-command"),
        ):
            with self.subTest(marker=changed):
                invalid = self.fight(death=False)
                invalid.events = [changed]
                rejected_db = Mock()
                rejected_db.execute.return_value.fetchone.return_value = dict(
                    payload=self.payload
                )
                with patch.object(source, "_advance") as advance:
                    with self.assertRaisesRegex(
                        ValueError, "real original enemy deaths"
                    ):
                        source.settle(
                            rejected_db,
                            object(),
                            self.character,
                            invalid,
                            self.originals,
                        )
                advance.assert_not_called()
                rejected_db.execute.assert_called_once()

        # An authenticated marker never bypasses the ordinary durable group and
        # participant terminal receipts required by this settlement.
        rejected_db = Mock()
        rejected_db.execute.return_value.fetchone.side_effect = [
            dict(payload=self.payload),
            dict(members=self.originals, status="available"),
            dict(team=0, status="finished"),
        ]
        with patch.object(source, "_advance") as advance:
            with self.assertRaisesRegex(ValueError, "normal durable settlement"):
                source.settle(
                    rejected_db,
                    object(),
                    self.character,
                    administrative,
                    self.originals,
                )
        advance.assert_not_called()

    def test_real_original_terminal_with_durable_group_reaches_shared_progress_once(
        self,
    ):
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            dict(payload=self.payload),
            dict(members=self.originals, status="defeated"),
            dict(team=0, status="finished"),
        ]
        with patch.object(
            source, "_advance", return_value=[(13832, b"objective")]
        ) as advance:
            packets = source.settle(
                db, object(), self.character, self.fight(), self.originals
            )
        self.assertEqual([opcode for opcode, _ in packets], [13411, 13832])
        self.assertEqual(advance.call_args.kwargs["evidence"]["source_object"], 24086)
        self.assertEqual(
            advance.call_args.kwargs["evidence"]["original_actor_ids"], [-111]
        )
        db.execute.return_value.fetchone.side_effect = [
            dict(payload=self.payload),
            dict(members=self.originals, status="defeated"),
            dict(team=0, status="finished"),
        ]
        with patch.object(source, "_advance", return_value=[]):
            self.assertEqual(
                source.settle(
                    db, object(), self.character, self.fight(), self.originals
                ),
                [],
            )

    def test_source_click_starts_only_native_delay_not_a_fight_or_objective(self):
        db = Mock()
        store = Mock()
        store.connection.return_value = nullcontext(db)
        store.character.return_value = self.character
        store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        groups = SimpleNamespace(lock=nullcontext())
        with patch("wakfu_server.paid_containers._leased_owner"), patch(
            "wakfu_server.environment_interactions._guard"
        ), patch.object(source, "_owner"), patch.object(
            source, "_publication", return_value={}
        ), patch.object(
            source, "_source_position"
        ), patch.object(
            source, "_eligible", return_value=(state(), {})
        ), patch.object(
            source.storage, "record_event", return_value=True
        ), patch.object(
            source, "_spawn"
        ) as spawn, patch.object(
            source, "_advance"
        ) as advance:
            result = source.interact(
                store,
                groups,
                2,
                "generation",
                self.character,
                struct.pack(">qHH", 24086, 0, 0),
                loaded=True,
                blocked=False,
            )
        self.assertIsNone(result["target"])
        self.assertEqual(
            result["ticket"]["due_ms"], int(store.now().timestamp() * 1000) + 3000
        )
        spawn.assert_not_called()
        advance.assert_not_called()

    def test_public_source_rejections_do_not_escape_disconnect_boundary(self):
        from psycopg import Error as DatabaseError
        from psycopg_pool import PoolTimeout
        from wakfu_server.ecology_feedback import information

        for error in (
            ValueError("source out of range"),
            DatabaseError("private SQL detail"),
            PoolTimeout("private pool detail"),
        ):
            with self.subTest(error=type(error).__name__):
                session = SimpleNamespace(
                    state=SimpleNamespace(
                        character=self.character,
                        account_id=2,
                        generation="lease",
                        body=struct.pack(">qHH", 24086, 0, 0),
                        quest_source_ticket=None,
                        environment_ticket=None,
                        loaded=True,
                        connection=object(),
                        service=object(),
                    ),
                    runtime=SimpleNamespace(
                        STORE=object(),
                        COMBAT_GROUPS=object(),
                        POSITIONS=SimpleNamespace(
                            account_barrier=lambda account: nullcontext()
                        ),
                        flush_positions=Mock(),
                        record=Mock(),
                        send=Mock(),
                    ),
                    environment_blocked=Mock(return_value=False),
                )
                with patch.object(source, "interact", side_effect=error):
                    self.assertTrue(dispatch.handle(session))
                session.runtime.send.assert_called_once_with(
                    session.state.connection,
                    session.state.service,
                    *information(
                        "This interaction is unavailable. Move next to the object and try again."
                    )
                )
                self.assertFalse(hasattr(session.state, "rejection"))
                if not isinstance(error, ValueError):
                    self.assertEqual(
                        session.runtime.record.call_args.kwargs["reason"],
                        type(error).__name__,
                    )

    def test_public_dispatch_with_no_source_or_timer_does_no_sql_or_combat(self):
        session = SimpleNamespace(
            state=SimpleNamespace(
                character=self.character, body=struct.pack(">qHH", 123, 0, 0)
            ),
            runtime=SimpleNamespace(),
        )
        self.assertFalse(dispatch.handle(session))
        self.assertFalse(dispatch.poll(session))

    def test_completed_source_enqueues_real_admission_without_calling_combat_from_idle(
        self,
    ):
        target = dict(id=-33, x=-134, y=42, z=0)
        session = SimpleNamespace(
            state=SimpleNamespace(connection=object(), service=object()),
            runtime=SimpleNamespace(send=Mock()),
            handle_encounter_start=Mock(),
            publish_settled_quest_packets=Mock(),
        )
        dispatch._apply(
            session,
            dict(
                character=self.character,
                packets=[],
                target=target,
                scene_packet=(12608, b"actual source roster"),
                binding=self.binding["id"],
            ),
        )
        self.assertEqual(
            session.state.pending_guardian_attack,
            struct.pack(">qiihB", -33, -134, 42, 0, 0),
        )
        session.handle_encounter_start.assert_not_called()
        session.runtime.send.assert_called_once_with(
            session.state.connection,
            session.state.service,
            12608,
            b"actual source roster",
        )

    def test_actual_public_world_publication_keeps_ordinary_monsters_unchanged(self):
        runtime = SimpleNamespace(
            WORLD=Mock(),
            STORE=Mock(),
            owned_scene_spawn_group=Mock(return_value=b"native ordinary spawn"),
        )
        world = WorldPublication(runtime)
        key = (527, 0, 999)
        members = [dict(id=-444, ref=2616)]
        world.publish_available_group(key, members)
        runtime.STORE.connection.assert_not_called()
        runtime.WORLD.emit_location.assert_called_once_with(
            527,
            0,
            12608,
            b"native ordinary spawn",
            exclude_generation=None,
            only_character_id=None,
        )


if __name__ == "__main__":
    unittest.main()
