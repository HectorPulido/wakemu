"""Ordinary team encoding still admits optional immutable encounter policies."""
from contextlib import ExitStack
from copy import deepcopy
import json
from unittest.mock import patch

from postgres_case import PostgresCase


class OrdinaryEncounterPolicyAdmissionTests(PostgresCase):
    def test_prepare_scene_binds_ordinary_ombrage_policy_and_pins_absence_on_retry(
        self,
    ):
        from wakfu_server import combat_encounter_roles as roles
        from wakfu_server import combat_encounter_area_activation as areas
        from wakfu_server import combat_encounter_group_selection as groups
        from wakfu_server import combat_encounter_table_listeners as tables
        from wakfu_server import combat_encounter_turn_end_order as ordering
        from wakfu_server import combat_encounter_recipient_binding as recipients
        from wakfu_server import combat_encounter_owned_start_binding as owned_start
        from wakfu_server import combat_encounter_event_population as event_population
        from wakfu_server import combat_encounter_movement_binding as movement
        from wakfu_server import combat_encounter_npc_start_binding as npc_start
        from wakfu_server import (
            combat_encounter_area_callback_programs as callback_programs,
        )
        from wakfu_server import combat_encounter_effect_recipient as effect_recipients
        from wakfu_server import combat_encounter_terminal_cleanup as terminal_cleanup
        from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.fight_checkpoint_store import snapshot

        roles._version.cache_clear()
        tables._version.cache_clear()
        self.addCleanup(roles._version.cache_clear)
        self.addCleanup(tables._version.cache_clear)
        character = dict(map_id=1229)
        members = [dict(ref=4770)]
        cells = {(0, 0, 0), (1, 0, 0)}
        placement = {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        arena = dict(
            map_id=1229,
            validated_cells=cells,
            placement_cells=placement,
            cell_masks=b"original-masks",
            cell_flags=b"original-flags",
            wire=b"original-selected-wire",
        )

        def construct(prepared):
            assignment = roles.roles_from_record(
                prepared["native_encounter_roles"],
                map_id=1229,
                monster_references=[4770],
            )
            fight = Fight(
                78,
                [
                    Actor(
                        7,
                        assignment.player_team,
                        (0, 0, 0),
                        100,
                        6,
                        3,
                        10,
                        200,
                        1,
                        True,
                    ),
                    Actor(-200, assignment.npc_team, (1, 0, 0), 100, 6, 3, 1, 200),
                ],
                cells,
                prepared["placement_cells"],
            )
            roles.bind_roles(fight, assignment, player_ids=(7,), npc_ids=(-200,))
            return fight, assignment

        with ExitStack() as stack:
            for module in (
                roles,
                areas,
                groups,
                tables,
                ordering,
                recipients,
                owned_start,
                event_population,
                movement,
                npc_start,
                callback_programs,
                effect_recipients,
                terminal_cleanup,
            ):
                stack.enter_context(
                    patch.object(module, "_database", return_value=self.store)
                )
            # The arena is already selected. Geometry reconstruction is an
            # independent producer; this contract covers its shared admission.
            stack.enter_context(
                patch(
                    "wakfu_server.combat_encounter_scene_layout.resolve_layout",
                    return_value=None,
                )
            )
            prepared = prepare_encounter_scene(character, members, arena)
            self.assertNotIn("native_encounter_roles", arena)
            self.assertEqual(
                prepared["native_encounter_roles"]["policy"], roles.ORDINARY_POLICY
            )
            for key in arena:
                self.assertIs(prepared[key], arena[key])
            fight, assignment = construct(prepared)
            self.assertEqual((fight.actors[7].team, fight.actors[-200].team), (0, 1))
            self.assertEqual(
                fight.native_encounter_table_listener_policy["effect_reference"], 266725
            )
            persisted = snapshot(fight)
            self.assertIsNone(persisted["native_encounter_owned_start_binding"])
            self.assertIsNone(persisted["native_encounter_effect_recipient_policy"])
            self.assertIsNone(persisted["native_encounter_terminal_cleanup_policy"])
            self.assertIsNone(persisted["native_encounter_event_population"])
            self.assertIsNone(persisted["native_encounter_movement_binding"])
            self.assertIsNone(persisted["native_encounter_npc_start_binding"])
            self.assertIsNone(persisted["native_encounter_area_callback_programs"])
            self.assertEqual(
                persisted["native_encounter_roles"], fight.native_encounter_roles
            )
            self.assertEqual(
                persisted["native_encounter_table_listener_policy"],
                fight.native_encounter_table_listener_policy,
            )
            restored = deepcopy(fight)
            restored.native_encounter_roles = json.loads(
                json.dumps(fight.native_encounter_roles)
            )
            self.assertEqual(roles.assigned_roles(restored), assignment)
            with self.store.connection() as db:
                db.execute(
                    "DELETE FROM encounter_table_listener_active WHERE map_id=1229"
                )
            # Rebinding the existing admission keeps its original policy.
            roles.bind_roles(restored, assignment, player_ids=(7,), npc_ids=(-200,))
            self.assertEqual(
                restored.native_encounter_table_listener_policy,
                fight.native_encounter_table_listener_policy,
            )
            empty_prepared = prepare_encounter_scene(character, members, arena)
            empty, ordinary = construct(empty_prepared)
            self.assertTrue(hasattr(empty, "native_encounter_table_listener_policy"))
            self.assertIsNone(empty.native_encounter_table_listener_policy)
            self.assertIn("native_encounter_table_listener_policy", snapshot(empty))
            self.assertIsNone(snapshot(empty)["native_encounter_table_listener_policy"])
            self.assertIsNone(snapshot(empty)["native_encounter_owned_start_binding"])
            self.assertIsNone(snapshot(empty)["native_encounter_event_population"])
            self.assertIsNone(snapshot(empty)["native_encounter_movement_binding"])
            self.assertIsNone(snapshot(empty)["native_encounter_npc_start_binding"])
            self.assertIsNone(
                snapshot(empty)["native_encounter_area_callback_programs"]
            )
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO encounter_table_listener_active VALUES(%s,%s::integer[],%s)",
                    (
                        1229,
                        [4770],
                        fight.native_encounter_table_listener_policy["policy"],
                    ),
                )
            # A role pointer appearing later must not overwrite scoped ordinary
            # roles either. The committed record is resolved without a query.
            with patch.object(
                roles,
                "_active_policy",
                side_effect=AssertionError("active role reread"),
            ):
                self.assertIs(
                    prepare_encounter_scene(character, members, empty_prepared),
                    empty_prepared,
                )
                roles.bind_roles(empty, ordinary, player_ids=(7,), npc_ids=(-200,))
            self.assertIsNone(empty.native_encounter_table_listener_policy)
            self.assertEqual((empty.actors[7].team, empty.actors[-200].team), (0, 1))
