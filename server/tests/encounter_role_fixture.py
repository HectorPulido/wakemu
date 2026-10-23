"""Explicit content rows for bounded role contracts without a database/catalog."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch


ROLE_ROWS = (
    dict(
        policy="wakemu-nox-player1-npc0-v1",
        authority="wakemu-reconstructed-nox-artifact-role-contract",
        map_id=1435,
        monster_references=[5664],
        player_team=1,
        npc_team=0,
    ),
    dict(
        policy="wakemu-rushu-player1-npc0-v1",
        authority="wakemu-reconstructed-rushu-vestige-role-contract",
        map_id=1332,
        monster_references=[5306],
        player_team=1,
        npc_team=0,
    ),
)


@contextmanager
def role_database_fixture():
    from wakfu_server import combat_encounter_roles as roles

    class Database:
        @contextmanager
        def connection(self):
            yield self

        def execute(self, query, parameters):
            if any(
                table in query
                for table in (
                    "FROM encounter_area_activation_active",
                    "FROM encounter_group_population_active",
                    "FROM encounter_table_listener_active",
                    "FROM encounter_turn_end_order_active",
                    "FROM encounter_recipient_binding_active",
                    "FROM encounter_owned_start_binding_active",
                    "FROM encounter_effect_recipient_active",
                    "FROM encounter_terminal_cleanup_active",
                    "FROM encounter_event_population_active",
                    "FROM encounter_movement_binding_active",
                    "FROM encounter_npc_start_binding_active",
                    "FROM encounter_area_callback_program_active",
                )
            ):
                row = None  # These role-only contracts have no area publisher.
            elif "FROM encounter_role_active" in query:
                map_id, references = parameters
                row = next(
                    (
                        dict(policy=r["policy"])
                        for r in ROLE_ROWS
                        if (r["map_id"], r["monster_references"])
                        == (map_id, references)
                    ),
                    None,
                )
            else:
                row = next((r for r in ROLE_ROWS if r["policy"] == parameters[0]), None)
            return SimpleNamespace(fetchone=lambda: row)

    roles._version.cache_clear()
    try:
        from wakfu_server import combat_encounter_area_activation as areas
        from wakfu_server import combat_encounter_group_selection as groups

        from wakfu_server import combat_encounter_table_listeners as tables
        from wakfu_server import combat_encounter_turn_end_order as end_order
        from wakfu_server import combat_encounter_recipient_binding as recipient_binding
        from wakfu_server import combat_encounter_owned_start_binding as owned_start
        from wakfu_server import combat_encounter_effect_recipient as effect_recipient
        from wakfu_server import combat_encounter_terminal_cleanup as terminal_cleanup
        from wakfu_server import combat_encounter_event_population as event_population
        from wakfu_server import combat_encounter_movement_binding as movement
        from wakfu_server import combat_encounter_npc_start_binding as npc_start
        from wakfu_server import (
            combat_encounter_area_callback_programs as callback_programs,
        )

        database = Database()
        with patch.object(roles, "_database", return_value=database), patch.object(
            areas, "_database", return_value=database
        ), patch.object(groups, "_database", return_value=database), patch.object(
            tables, "_database", return_value=database
        ), patch.object(
            end_order, "_database", return_value=database
        ), patch.object(
            recipient_binding, "_database", return_value=database
        ), patch.object(
            owned_start, "_database", return_value=database
        ), patch.object(
            effect_recipient, "_database", return_value=database
        ), patch.object(
            terminal_cleanup, "_database", return_value=database
        ), patch.object(
            event_population, "_database", return_value=database
        ), patch.object(
            movement, "_database", return_value=database
        ), patch.object(
            npc_start, "_database", return_value=database
        ), patch.object(
            callback_programs, "_database", return_value=database
        ):
            yield
    finally:
        roles._version.cache_clear()
