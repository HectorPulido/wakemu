"""Reviewed role scopes and pre-admission invariants, without native catalog loads."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_server.combat_encounter_roles import (
    assigned_roles,
    bind_roles,
    role_assignment,
    roles_from_record,
    validate_participant_role,
)


class EncounterRoleContractTests(unittest.TestCase):
    def setUp(self):
        from encounter_role_fixture import role_database_fixture

        self.enterContext(role_database_fixture())

    def test_nox_scope_is_exact_and_legacy_fights_are_not_inferred(self):
        roles = role_assignment(1435, (5664,))
        self.assertEqual(
            (roles.policy, roles.player_team, roles.npc_team),
            ("wakemu-nox-player1-npc0-v1", 1, 0),
        )
        rushu = role_assignment(1332, (5306,))
        self.assertEqual((rushu.player_team, rushu.npc_team), (1, 0))
        for map_id, references in (
            (1134, (5664,)),
            (1435, (5788,)),
            (1435, (5664, 5525)),
            (1332, (5306, 5525)),
        ):
            with self.subTest(map_id=map_id, references=references):
                selected = role_assignment(map_id, references)
                self.assertEqual((selected.player_team, selected.npc_team), (0, 1))
        legacy = SimpleNamespace()
        self.assertEqual(
            (assigned_roles(legacy).player_team, assigned_roles(legacy).npc_team),
            (0, 1),
        )
        self.assertFalse(vars(legacy))
        with self.assertRaisesRegex(ValueError, "Unscoped"):
            assigned_roles(legacy).record()

    def test_frozen_record_is_exact_and_rejects_scope_or_team_drift(self):
        roles = role_assignment(1435, (5664,))
        record = roles.record()
        self.assertEqual(
            roles_from_record(record, map_id=1435, monster_references=(5664,)), roles
        )
        for key, value in (
            ("player_team", 0),
            ("npc_team", 1),
            ("map_id", 1134),
            ("monster_references", [5788]),
            ("authority", "invented"),
            ("player_team", True),
        ):
            with self.subTest(key=key, value=value):
                changed = dict(record, **{key: value})
                with self.assertRaises(ValueError):
                    roles_from_record(changed)
        with self.assertRaisesRegex(ValueError, "another map"):
            roles_from_record(record, map_id=1134)
        with self.assertRaisesRegex(ValueError, "another initial roster"):
            roles_from_record(record, monster_references=(5664, 5525))

    def test_role_placement_is_an_input_for_encoding_and_does_not_mutate_cells(self):
        players, npcs = {(0, 0, 0), (1, 0, 0)}, {(5, 5, 0)}
        before = deepcopy((players, npcs))
        self.assertEqual(
            role_assignment(1435, (5664,)).placement_cells(players, npcs),
            {1: players, 0: npcs},
        )
        self.assertEqual(
            role_assignment(1134, (5525,)).placement_cells(players, npcs),
            {0: players, 1: npcs},
        )
        self.assertEqual((players, npcs), before)
        with self.assertRaises(ValueError):
            role_assignment(1435, (5664,)).placement_cells(players, players)

    def test_bind_and_late_admission_validate_original_teams_without_retagging(self):
        roles = role_assignment(1435, (5664,))
        player = SimpleNamespace(team=1, position=(0, 0, 0))
        boss = SimpleNamespace(team=0, position=(5, 5, 0))
        fight = SimpleNamespace(
            phase="placement",
            actors={7: player, -7: boss},
            placement=roles.placement_cells({player.position}, {boss.position}),
        )
        bind_roles(fight, roles, player_ids=(7,), npc_ids=(-7,))
        self.assertEqual(assigned_roles(fight), roles)
        for owned in (SimpleNamespace(team=1), SimpleNamespace(team=1)):
            validate_participant_role(
                fight, owned, player=True
            )  # PC/hero and owned companion.
        validate_participant_role(fight, SimpleNamespace(team=0), player=False)
        with self.assertRaises(ValueError):
            validate_participant_role(fight, SimpleNamespace(team=0), player=True)
        wrong = SimpleNamespace(
            phase="placement",
            actors={7: SimpleNamespace(team=0, position=player.position), -7: boss},
            placement=fight.placement,
        )
        with self.assertRaisesRegex(ValueError, "wrong encounter side"):
            bind_roles(wrong, roles, player_ids=(7,), npc_ids=(-7,))
        self.assertFalse(hasattr(wrong, "native_encounter_roles"))
        self.assertEqual(wrong.actors[7].team, 0)
