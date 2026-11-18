import json
from pathlib import Path
import unittest

from wakfu_server import combat_scene_ball_goals as goals


PROFILE = (
    Path(__file__).parents[1]
    / "wakfu_server"
    / "maps"
    / "owned_story_profiles"
    / "wild-estate-bworkball-719-encounters.json"
)


class CombatSceneBallGoalsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rooms = json.loads(PROFILE.read_text())["rooms"]
        cls.room = cls.rooms[0]
        cls.descriptor = cls.room["encounter_scene"]

    def test_actual_room_declarations_and_native_sources_are_sealed(self):
        descriptor = self.descriptor
        room_cells = [
            (x, y, self.room["z"])
            for y in range(self.room["bounds"][1], self.room["bounds"][3] + 1)
            for x in range(self.room["bounds"][0], self.room["bounds"][2] + 1)
        ]
        # The published topology supplies the floor cells; the room rectangle
        # only bounds which of those cells belong to this encounter.
        exploration = json.loads(
            PROFILE.with_name("wild-estate-bworkball-719.exploration.json").read_text()
        )
        room_cells = [
            tuple(cell)
            for cell in exploration["cells"]
            if self.room["bounds"][0] <= cell[0] <= self.room["bounds"][2]
            and self.room["bounds"][1] <= cell[1] <= self.room["bounds"][3]
            and cell[2] == self.room["z"]
        ]
        selected = goals.declaration(descriptor, room_cells)
        self.assertEqual(
            (
                selected["quest_id"],
                selected["objective_id"],
                selected["match_index"],
                selected["source_id"],
            ),
            (1638, 3079, 1, 20383),
        )

        native = goals.native_sources()
        self.assertEqual(native["terminals"]["106824"]["effect_class"], 28)
        self.assertEqual(native["terminals"]["106850"]["effect_class"], 28)
        for room in self.rooms:
            declaration = goals.declaration(room["encounter_scene"])
            self.assertEqual(declaration["match_index"], room["order"])
            self.assertEqual(
                declaration["source_id"],
                room["monsters"][0]["source_id"]
                if "source_id" in room["monsters"][0]
                else declaration["source_id"],
            )

        changed = json.loads(json.dumps(descriptor))
        changed["ball_goals"]["source_id"] = 20384
        with self.assertRaises(ValueError):
            goals.declaration(changed, room_cells)
        changed = json.loads(json.dumps(descriptor))
        changed["ball_goals"]["player_goal_cells"][0] = [-8, -1, 0]
        with self.assertRaises(ValueError):
            goals.declaration(changed, room_cells)

    def test_only_matching_original_native_kill_death_pair_can_witness_goal(self):
        proof = dict(generic_effect=106824, caster_id=10, target_id=20)
        fight = type("FightEvents", (), {})()
        fight.events = [
            dict(
                kind="kill_hp_minimum_update",
                effect_class=28,
                generic_effect=106824,
                source_id=10,
                target_id=20,
                uid=501,
                hp_before=50,
                hp=0,
                minimum=0,
                sequence=7,
            ),
            dict(kind="death", actor_id=20, sequence=8),
        ]
        self.assertEqual(
            goals._kills(fight, proof),
            [dict(uid=501, target_id=20, kill_sequence=7, death_sequence=8)],
        )

        fight.events[1]["sequence"] = 9
        self.assertEqual(goals._kills(fight, proof), [])
        fight.events[1]["sequence"] = 8
        fight.events[0]["source_id"] = 11
        self.assertEqual(goals._kills(fight, proof), [])

    def test_actual_4044_group_runs_canonical_106824_and_records_ball_death(self):
        import json
        from copy import deepcopy
        from pathlib import Path
        from types import SimpleNamespace
        from unittest.mock import patch
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_effect_resolver import (
            EffectResolutionContext,
            NativeEffectResolver,
        )
        from wakfu_server.combat_effect_groups import (
            decode_group_mode,
            execute_ordered_group,
        )
        from wakfu_server.combat_definitions import effect_profile
        from wakfu_server.combat_kill import NativeKillHandler
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from test_combat_kill import NativeKillTests

        root = Path(__file__).resolve().parents[2]
        native = json.loads(
            (
                root / ".runtime/quest-archetypes/bworkball/native-source.json"
            ).read_text()
        )
        root_effect = native["effects"]["107034"]
        terminal = json.loads(
            (
                Path(__file__).parent
                / "fixtures/native_bworkball_106824_executable.json"
            ).read_text()
        )
        self.assertEqual(
            (root_effect["effect_class"], root_effect["children"]), (330, [106824])
        )
        self.assertEqual(
            (
                terminal["effect_class"],
                terminal["native_active_effect"] is not None,
                terminal["native_timing_checks"] is not None,
            ),
            (28, True, True),
        )

        (
            fight,
            ball,
            packets,
            _phases,
            _old_handler,
            _old_effect,
            _old_invocation,
        ) = NativeKillTests().fixture()
        player_id, ball_id = 7, -7
        fight.actors[player_id].position = (7, 1, 0)
        ball.native_reference = 2783
        ball.position = (8, 1, 0)
        fight.walkable = {
            tuple(cell)
            for cell in json.loads(
                PROFILE.with_name(
                    "wild-estate-bworkball-719.exploration.json"
                ).read_text()
            )["cells"]
        }
        room_cells = [
            cell
            for cell in fight.walkable
            if cell[2] == 0 and -8 <= cell[0] <= 8 and -5 <= cell[1] <= 5
        ]
        room = self.room
        descriptor = room["encounter_scene"]
        record = dict(
            descriptor=descriptor,
            sha256="b" * 64,
            room_cells=[list(cell) for cell in room_cells],
            scope=dict(
                map_id=719,
                room_order=1,
                actor_bindings=[dict(actor_id=ball_id, ref=2783)],
            ),
        )
        fight.native_encounter_scene = record
        fight.native_active_spell_id = 4044
        glyphs = []
        areas = {}
        area_definitions = {
            str(key): native["areas"][str(key)] for key in (625, 626, 635)
        }
        from wakfu_server.combat_encounter_glyph_bootstrap import (
            constructor_source,
            glyph_row,
        )

        for index, declaration in enumerate(descriptor["native_initial_glyphs"]):
            reference = declaration["reference"]
            source = dict(
                uid=5000 + index,
                reference=reference,
                cell=tuple(declaration["cell"]),
                level=declaration.get("level", 0),
                policy=descriptor["native_initial_glyph_policy"],
                authority=descriptor["native_initial_glyph_authority"],
                source=constructor_source(area_definitions[str(reference)]),
                source_url=descriptor["native_initial_glyph_source_url"],
            )
            glyphs.append(source)
            areas[source["uid"]] = glyph_row(source, area_definitions[str(reference)])
        fight.native_environment_glyph_constructors = glyphs
        fight.native_effect_areas = areas
        fight.native_environment_glyphs_installed = True

        resolver = NativeEffectResolver(
            actors=lambda effect, invocation: (
                fight.actors[player_id],
                fight.actors[ball_id],
            ),
            native_context=lambda effect, invocation: {
                player_id: dict(
                    is_amO=True,
                    is_Qq=False,
                    is_eGj=True,
                    bEe=True,
                    is_eHH=False,
                    UNTARGETTABLE_BY_OTHER=False,
                ),
                ball_id: dict(
                    is_amO=True,
                    is_Qq=False,
                    is_eGj=True,
                    bEe=True,
                    is_eHH=False,
                    UNTARGETTABLE_BY_OTHER=False,
                ),
            },
            context=lambda effect, invocation: EffectResolutionContext(
                "ALL",
                "immediate",
                "actors",
                True,
            ),
        )
        root_invocation = EffectInvocation(107034, 1, player_id, ball_id, ball.position)
        selected = resolver(root_effect, root_invocation)
        self.assertEqual([row.target_id for row in selected], [ball_id])

        kill = NativeKillHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=lambda: 901,
            context=lambda effect, invocation: StatExecutionContext(
                True, True, None, False, b"", None
            ),
            rng=lambda: 0,
            authority=SimpleNamespace(property_counts=lambda f, a: {}),
        )
        from wakfu_server.combat_active_spell import active_spell_scope
        from wakfu_server.combat_encounter_roles import assigned_roles

        mode = decode_group_mode(effect_profile(root_effect, 1)["parameters"][:6])

        def run_terminal(child):
            terminal_invocation = EffectInvocation(
                106824,
                child.level if hasattr(child, "level") else 1,
                child.caster_id,
                child.target_id,
                child.cell,
            )
            selected_child = resolver(terminal, terminal_invocation)
            self.assertEqual([item.target_id for item in selected_child], [ball_id])
            return kill(terminal, effect_profile(terminal, 1), selected_child[0])

        with patch(
            "wakfu_server.combat_encounter_scene_policy.frozen_scene",
            return_value=descriptor,
        ), patch(
            "wakfu_server.combat_encounter_roles.assigned_roles",
            return_value=SimpleNamespace(player_team=0, npc_team=1),
        ), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=area_definitions,
        ), patch(
            "wakfu_server.combat_environment_glyphs.verify_environment_glyph",
            return_value=None,
        ), patch(
            "wakfu_server.combat_effect_dispatch.evaluate_condition", return_value=True
        ):
            with active_spell_scope(fight, 4044, level=1):
                execute_ordered_group(
                    mode,
                    root_effect["children"],
                    caster_id=player_id,
                    target_id=ball_id,
                    target_cell=ball.position,
                    execute_child=lambda child: run_terminal(child),
                )
            self.assertTrue(goals.settle_terminal(fight))
            self.assertEqual(ball.hp, 0)
            self.assertEqual(
                [
                    event["kind"]
                    for event in fight.events
                    if event.get("kind") in ("kill_hp_minimum_update", "death")
                ],
                ["kill_hp_minimum_update", "death"],
            )
            self.assertEqual(fight.native_ball_goal_receipt["spell_id"], 4044)
            self.assertEqual(fight.native_ball_goal_receipt["generic_effect"], 106824)
            self.assertEqual(
                fight.native_ball_goal_receipt["native_kill"]["target_id"], ball_id
            )

    def test_original_ball_follows_only_a_paid_linked_walk_and_uses_qi_writer(self):
        from copy import deepcopy
        from unittest.mock import patch
        from wakfu_server import combat_scene_ball_follow
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_movement_payment_events import committed_step_payment
        from wakfu_server.combat_qi_fight import (
            current_registry,
            install_fresh_actor_slots,
            prepare_fresh_actor_slots,
        )
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        def fixture():
            carrier = Actor(7, 0, (-1, 0, 0), 60, 6, 3, 20, 50, 1, True)
            ball = Actor(-7, 0, (0, 0, 0), 100, 0, 0, 10, 50)
            ball.native_reference = 2783
            opponent = Actor(-8, 1, (0, 1, 0), 100, 6, 3, 5, 50)
            for actor in (carrier, ball, opponent):
                actor.physical_radius = 0
            cells = {(x, y, 0) for x in (-1, 0) for y in (0, 1)}
            fight = Fight(
                71901,
                [carrier, ball, opponent],
                cells,
                {0: {(-1, 0, 0), (0, 0, 0)}, 1: {(0, 1, 0)}},
            )
            fight.native_qi_snapshot = {
                "x": -1,
                "y": 0,
                "width": 2,
                "height": 2,
                "cell_masks": [0] * 4,
            }
            fight.valid_edges = {((-1, 0, 0), (-1, 1, 0)), ((-1, 1, 0), (-1, 0, 0))}
            initialize_global_pv_collections(fight, (7, -7, -8))
            prepared = prepare_fresh_actor_slots(
                fight,
                physical_radii={
                    identity: actor.physical_radius
                    for identity, actor in fight.actors.items()
                },
            )
            install_fresh_actor_slots(fight, prepared)
            fight.native_movement_links = {7: -7, -7: 7}
            fight.ready(1)
            return fight, carrier, ball

        room = self.room
        descriptor = room["encounter_scene"]
        room_cells = [
            tuple(cell)
            for cell in json.loads(
                PROFILE.with_name(
                    "wild-estate-bworkball-719.exploration.json"
                ).read_text()
            )["cells"]
            if -8 <= cell[0] <= 8 and -5 <= cell[1] <= 5 and cell[2] == 0
        ]
        selected = goals.declaration(descriptor, room_cells)
        scene = dict(
            descriptor=descriptor,
            room_cells=[list(cell) for cell in room_cells],
            scope={"map_id": 719},
        )

        def invoke(fight, carrier, ball, callback):
            from wakfu_server.combat_movement_payment_events import (
                committed_step_payment,
            )
            from unittest.mock import patch

            origin, destination = (-1, 0, 0), (-1, 1, 0)
            with patch(
                "wakfu_server.combat_tackle_movement.movement_tackle_cost",
                return_value=(0, 0),
            ):
                event = fight.move(1, carrier.id, [destination])
            self.assertEqual(event["cost"], 1)
            with committed_step_payment(
                fight,
                carrier,
                origin=origin,
                destination=destination,
                index=0,
                ap_before=6,
                mp_before=3,
                ap_paid=0,
                mp_paid=1,
                ap_after=6,
                mp_after=2,
            ):
                result = combat_scene_ball_follow.follow_paid_walk(
                    fight,
                    moving_id=carrier.id,
                    origin=origin,
                    destination=destination,
                    area_events=callback,
                )
            return result

        fight, carrier, ball = fixture()
        observations = []
        peer_events = []

        class AreaEvents:
            def movement(self, actor_id, *, from_cell, to_cell):
                from wakfu_server.combat_movement_payment_events import _step_payment

                peer_events.append((actor_id, from_cell, to_cell, _step_payment.get()))

        def runtime(character, monsters, deck_blob, **kwargs):
            def factory(preview, options):
                return type("Dispatcher", (), {"native_area_events": AreaEvents()})(), [
                    (1005, b"native-area")
                ]

            return factory, None

        def real_area_callback(_fight, peer, origin, destination):
            from wakfu_server.combat_area_transaction import prepare_area_movement

            preview, packets = prepare_area_movement(
                {},
                {},
                _fight,
                b"",
                actor_id=peer.id,
                action_id=1005,
                path=[destination],
                origin=origin,
            )
            return list(packets)

        with patch(
            "wakfu_server.combat_scene_ball_follow._scene",
            return_value=(scene, selected),
        ), patch(
            "wakfu_server.combat_scene_ball_follow._ball", return_value=ball
        ), patch(
            "wakfu_server.combat_scene_ball_follow._areas", return_value=[]
        ), patch(
            "wakfu_server.combat_server_spell.server_runtime", side_effect=runtime
        ):
            packets = invoke(
                fight,
                carrier,
                ball,
                lambda _fight, peer, origin, destination: (
                    observations.append(
                        (
                            _fight,
                            peer,
                            origin,
                            destination,
                            __import__(
                                "wakfu_server.combat_movement_payment_events",
                                fromlist=["_step_payment"],
                            )._step_payment.get(),
                        )
                    ),
                    real_area_callback(_fight, peer, origin, destination),
                )[1],
            )
            self.assertEqual(packets, [(1005, b"native-area")])
            self.assertEqual(ball.position, (-1, 1, 0))
            self.assertIsNone(observations[0][4])
            self.assertEqual(peer_events, [(-7, (0, 0, 0), (-1, 1, 0), None)])
            occupied = current_registry(fight).snapshot().U(-1, 1)
            self.assertIn(
                ball.native_obstacle_id,
                occupied,
                msg=f"ball={ball.id}/{ball.native_obstacle_id} carrier="
                f"{carrier.id}/{carrier.native_obstacle_id} occupied={occupied}",
            )
            unpaid, unpaid_carrier, unpaid_ball = fixture()
            self.assertEqual(
                combat_scene_ball_follow.follow_paid_walk(
                    unpaid,
                    moving_id=unpaid_carrier.id,
                    origin=(-1, 0, 0),
                    destination=(-1, 1, 0),
                    area_events=lambda *args: self.fail("unpaid movement dispatched"),
                ),
                [],
            )
            self.assertEqual(unpaid_ball.position, (0, 0, 0))

            original, _, original_ball = fixture()
            rollback = deepcopy(original)
            rollback_carrier, rollback_ball = rollback.actors[7], rollback.actors[-7]
            with patch(
                "wakfu_server.combat_tackle_movement.movement_tackle_cost",
                return_value=(0, 0),
            ):
                rollback.move(1, rollback_carrier.id, [(-1, 1, 0)])
            with patch(
                "wakfu_server.combat_scene_ball_follow._scene",
                return_value=(scene, selected),
            ), patch(
                "wakfu_server.combat_scene_ball_follow._ball",
                return_value=rollback_ball,
            ), patch(
                "wakfu_server.combat_scene_ball_follow._areas", return_value=[]
            ):
                with self.assertRaisesRegex(RuntimeError, "area failure"):
                    with committed_step_payment(
                        rollback,
                        rollback_carrier,
                        origin=(-1, 0, 0),
                        destination=(-1, 1, 0),
                        index=0,
                        ap_before=6,
                        mp_before=3,
                        ap_paid=0,
                        mp_paid=1,
                        ap_after=6,
                        mp_after=2,
                    ):
                        combat_scene_ball_follow.follow_paid_walk(
                            rollback,
                            moving_id=rollback_carrier.id,
                            origin=(-1, 0, 0),
                            destination=(-1, 1, 0),
                            area_events=lambda *args: (_ for _ in ()).throw(
                                RuntimeError("area failure")
                            ),
                        )
            # The outer movement operation owns the preview; its failure must
            # discard both the carrier debit and the ball QI relocation.
            self.assertEqual(rollback_ball.position, (-1, 1, 0))
            self.assertEqual(original_ball.position, (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
