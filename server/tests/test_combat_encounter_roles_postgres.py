"""Database authority and immutable committed versions across active changes."""
from unittest.mock import patch

import psycopg

from postgres_case import PostgresCase


class EncounterRoleAuthorityTests(PostgresCase):
    def setUp(self):
        super().setUp()
        from wakfu_server import combat_encounter_roles as roles

        roles._version.cache_clear()
        self.addCleanup(roles._version.cache_clear)
        self.enterContext(patch.object(roles, "_database", return_value=self.store))

    def test_ogrest_ivory_scope_excludes_neo_and_preserves_committed_ordinary_roles(
        self,
    ):
        from wakfu_server.combat_encounter_roles import (
            EncounterRoles,
            ORDINARY_POLICY,
            role_assignment,
            roles_from_record,
        )

        roles = role_assignment(1156, [4378])
        self.assertEqual(roles.policy, "wakemu-ogrest-player1-npc0-v1")
        self.assertEqual((roles.player_team, roles.npc_team), (1, 0))
        self.assertEqual(roles_from_record(roles.record()), roles)
        for map_id, roster in (
            (1156, [5806]),
            (1156, [4378, 5806]),
            (1156, [4378, 4378]),
            (363, [4378]),
        ):
            with self.subTest(map_id=map_id, roster=roster):
                selected = role_assignment(map_id, roster)
                self.assertEqual((selected.player_team, selected.npc_team), (0, 1))
        historical = EncounterRoles(
            ORDINARY_POLICY,
            "ordinary-existing-constructor-role-policy",
            1156,
            (4378,),
            0,
            1,
        )
        self.assertEqual(roles_from_record(historical.record()), historical)

    def test_steel_beak_cliff_roles_are_scoped_to_the_published_initial_roster(self):
        from wakfu_server.combat_encounter_roles import (
            role_assignment,
            roles_from_record,
        )

        roles = role_assignment(959, [3582])
        self.assertEqual(roles.policy, "wakemu-steel-beak-player1-npc0-v1")
        self.assertEqual((roles.player_team, roles.npc_team), (1, 0))
        self.assertEqual(
            roles_from_record(roles.record(), map_id=959, monster_references=[3582]),
            roles,
        )
        for map_id, roster in ((959, [3582, 3582]), (959, [3582, 1988]), (363, [3582])):
            with self.subTest(map_id=map_id, roster=roster):
                selected = role_assignment(map_id, roster)
                self.assertEqual((selected.player_team, selected.npc_team), (0, 1))

    def test_black_crow_policy_scopes_initial_admission_without_inventing_phase_rosters(
        self,
    ):
        from wakfu_server.combat_encounter_roles import (
            role_assignment,
            roles_from_record,
        )

        roles = role_assignment(363, [1988])
        self.assertEqual(roles.policy, "wakemu-black-crow-player1-npc0-v1")
        self.assertEqual((roles.player_team, roles.npc_team), (1, 0))
        self.assertEqual(
            roles_from_record(roles.record(), map_id=363, monster_references=[1988]),
            roles,
        )
        # Native phase births inherit/fix their own team. Their existence is
        # not authority for a separately published initial encounter roster.
        for map_id, roster in (
            (363, [1989]),
            (363, [5356]),
            (363, [1988, 1802]),
            (363, [1988, 1989]),
            (1435, [1988]),
        ):
            with self.subTest(map_id=map_id, roster=roster):
                selected = role_assignment(map_id, roster)
                self.assertEqual((selected.player_team, selected.npc_team), (0, 1))

    def test_tal_kasha_clair_policy_is_exact_and_does_not_reinfer_legacy_fights(self):
        from types import SimpleNamespace
        from wakfu_server.combat_encounter_roles import (
            role_assignment,
            roles_from_record,
            assigned_roles,
        )

        roles = role_assignment(1400, [5500])
        self.assertEqual(roles.policy, "wakemu-tal-kasha-player1-npc0-v1")
        self.assertEqual(
            roles.authority, "wakemu-reconstructed-tal-kasha-clair-role-contract"
        )
        self.assertEqual((roles.player_team, roles.npc_team), (1, 0))
        self.assertEqual(
            roles_from_record(roles.record(), map_id=1400, monster_references=[5500]),
            roles,
        )
        for map_id, roster in (
            (1400, [5502]),
            (1400, [5500, 5502]),
            (1400, [5500, 5500]),
            (1056, [5500]),
        ):
            with self.subTest(map_id=map_id, roster=roster):
                self.assertEqual(
                    (
                        role_assignment(map_id, roster).player_team,
                        role_assignment(map_id, roster).npc_team,
                    ),
                    (0, 1),
                )
        # Historical fights lack the policy record and must not inherit a new
        # interpretation merely because their map now has an active policy.
        legacy = SimpleNamespace(map_id=1400)
        self.assertEqual(
            (assigned_roles(legacy).player_team, assigned_roles(legacy).npc_team),
            (0, 1),
        )
        self.assertFalse(hasattr(legacy, "native_encounter_roles"))

    def test_database_scopes_authorize_both_scenes_and_reject_immutable_mutation(self):
        from wakfu_server.combat_encounter_roles import (
            role_assignment,
            roles_from_record,
        )

        for map_id, reference in ((1435, 5664), (1332, 5306), (1056, 3870)):
            roles = role_assignment(map_id, [reference])
            self.assertEqual((roles.player_team, roles.npc_team), (1, 0))
            self.assertEqual(roles_from_record(roles.record()), roles)
            self.assertEqual(
                role_assignment(map_id, [reference, reference]).player_team, 0
            )
        self.assertEqual(
            role_assignment(1056, [3870]).policy, "wakemu-ful-moon-player1-npc0-v1"
        )
        self.assertEqual(role_assignment(1056, [3870, 5525]).player_team, 0)
        with self.assertRaisesRegex(psycopg.Error, "immutable"):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE encounter_role_versions SET player_team=0,npc_team=1 "
                    "WHERE policy='wakemu-nox-player1-npc0-v1'"
                )
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE encounter_role_active SET policy='wakemu-rushu-player1-npc0-v1' "
                    "WHERE map_id=1435"
                )

    def test_active_switch_affects_only_new_admissions_and_frozen_lookup_is_cached(
        self,
    ):
        from wakfu_server import combat_encounter_roles as roles

        old = roles.role_assignment(1435, [5664])
        committed = old.record()
        # Changing the active pointer never rewrites a committed policy version.
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO encounter_role_versions VALUES "
                "('test-reviewed-next-version','test-reconstructed-authority',1435,ARRAY[5664],0,1)"
            )
            db.execute(
                "UPDATE encounter_role_active SET policy='test-reviewed-next-version' WHERE map_id=1435"
            )
        self.assertEqual(roles.role_assignment(1435, [5664]).player_team, 0)
        # Warm committed lookup is independent of both active DB and connection.
        with patch.object(
            roles,
            "_database",
            side_effect=AssertionError("Unexpected condition-time DB query"),
        ):
            self.assertEqual(roles.roles_from_record(committed), old)
        changed = dict(committed, policy="test-reviewed-next-version")
        with self.assertRaises(ValueError):
            roles.roles_from_record(changed)
        # A cache miss also resolves the old immutable row, not the active one.
        roles._version.cache_clear()
        self.assertEqual(roles.roles_from_record(committed), old)
        with self.store.connection() as db:
            db.execute("DELETE FROM encounter_role_active WHERE map_id=1435")
        self.assertEqual(roles.role_assignment(1435, [5664]).player_team, 0)
        self.assertEqual(roles.roles_from_record(committed), old)
