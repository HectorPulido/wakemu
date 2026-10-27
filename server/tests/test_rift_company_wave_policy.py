"""Company-scaled Rift populations and frozen ordinary/milestone selection."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.rift_policy import bind_company_size, select_wave, validate
from test_rift_runtime import policy as legacy_policy


COUNTS = {"1": 4, "2": 5, "3": 5, "4": 6, "5": 7, "6": 8}
KINDS = ("INFINITE_WAVE", "ULTIMATE_INFINITE_WAVE")


def current_policy():
    return dict(
        legacy_policy(),
        max_members=6,
        ultimate_enabled=True,
        wave_size_by_company_size=dict(COUNTS),
        elite_wave_interval=5,
        selection="shuffled_species_cycles",
    )


def catalog(kind):
    return dict(
        wave_id=3,
        type=kind,
        map_id=1314,
        species_refs=[1, 3, 4, 5, 41, 704],
        additional_species_refs=[50, 60],
        milestone_species_refs=[1001, 1002],
    )


class RiftCompanyWavePolicyTests(unittest.TestCase):
    def test_all_company_sizes_both_types_keep_count_and_one_periodic_elite(self):
        for kind in KINDS:
            source = current_policy()
            before = deepcopy(source)
            for quantity in range(1, 7):
                bound = bind_company_size(source, quantity)
                self.assertEqual(bound["company_size"], quantity)
                self.assertEqual(bound["classic_wave_size"], COUNTS[str(quantity)])
                self.assertEqual(bound["ultimate_wave_size"], COUNTS[str(quantity)])
                for wave in (1, 4, 5, 10):
                    with self.subTest(kind=kind, members=quantity, wave=wave):
                        definition = catalog(kind)
                        first = select_wave(definition, bound, "company-fixture", wave)
                        self.assertEqual(
                            first,
                            select_wave(definition, bound, "company-fixture", wave),
                        )
                        self.assertEqual(len(first), COUNTS[str(quantity)])
                        elites = [
                            ref
                            for ref in first
                            if ref in definition["milestone_species_refs"]
                        ]
                        self.assertEqual(len(elites), int(wave % 5 == 0))
                        self.assertTrue(
                            set(first[:-1])
                            <= set(
                                definition["species_refs"]
                                + definition.get("additional_species_refs", [])
                            )
                        )
                        if wave % 5 == 0:
                            self.assertIn(
                                first[-1], definition["milestone_species_refs"]
                            )
                        else:
                            self.assertTrue(
                                set(first)
                                <= set(
                                    definition["species_refs"]
                                    + definition.get("additional_species_refs", [])
                                )
                            )
            self.assertEqual(source, before)
            definition = catalog(kind)
            seen = {
                ref
                for seed in map(str, range(50))
                for ref in select_wave(
                    definition, bind_company_size(source, 1), seed, 1
                )
            }
            self.assertEqual(
                seen,
                set(definition["species_refs"] + definition["additional_species_refs"]),
            )
            largest = bind_company_size(source, 6)
            full = select_wave(definition, largest, "full-pool", 1)
            self.assertEqual(len(full), 8)
            self.assertEqual(len(set(full)), 8)
            tiny = {
                **definition,
                "species_refs": [1, 3, 4],
                "additional_species_refs": [],
            }
            exhausted = select_wave(tiny, largest, "small-pool", 1)
            self.assertEqual(len(exhausted), 8)
            self.assertEqual(set(exhausted[:3]), {1, 3, 4})
            self.assertEqual(set(exhausted[3:6]), {1, 3, 4})
            self.assertEqual(len(set(exhausted[6:])), 2)
            milestones = {**definition, "milestone_species_refs": [1001, 1002, 1003]}
            elite_cycle = [
                select_wave(milestones, largest, "elite-cycle", wave)[-1]
                for wave in (5, 10, 15, 20)
            ]
            self.assertEqual(set(elite_cycle[:3]), {1001, 1002, 1003})
            self.assertEqual(elite_cycle[3], elite_cycle[0])

    def test_enter_freezes_actual_members_and_initial_successor_policy(self):
        from wakfu_server import rift_runtime

        class AdmissionDatabase:
            def __init__(self, members):
                self.members = members

            def execute(self, query, parameters):
                if query.startswith("SELECT id FROM characters"):
                    return SimpleNamespace(
                        fetchall=lambda: [{"id": uid} for uid in self.members]
                    )
                if query.startswith("INSERT INTO rift_instances"):
                    wave_id, owner, members, definition, frozen, seed, wave = parameters
                    return SimpleNamespace(
                        fetchone=lambda: dict(
                            wave_definition_id=wave_id,
                            owner_character_id=owner,
                            members=json.loads(members),
                            catalog=json.loads(definition),
                            policy=json.loads(frozen),
                            seed=seed,
                            wave=wave,
                        )
                    )
                return SimpleNamespace(fetchone=lambda: None)

        for kind in KINDS:
            for quantity in range(1, 7):
                with self.subTest(kind=kind, members=quantity):
                    members = list(range(40, 40 + quantity))
                    source = current_policy()
                    definition = catalog(kind)
                    settings = {
                        "rift_policy": source,
                        "rift_catalog": {"3": definition},
                    }
                    admitted = []
                    with patch.object(
                        rift_runtime,
                        "_setting",
                        side_effect=lambda db, name: settings[name],
                    ), patch(
                        "wakfu_server.rift_native_gameplay_policy.load",
                        return_value=None,
                    ), patch(
                        "wakfu_server.rift_key_admission.contract", return_value=None
                    ):
                        run = rift_runtime.enter(
                            AdmissionDatabase(members),
                            3,
                            members[0],
                            iter(members),
                            seed="admission",
                            authorize=lambda actual, roster: admitted.append(
                                (actual, roster)
                            )
                            or True,
                        )
                    self.assertEqual(run["members"], members)
                    self.assertEqual(admitted[0][1], tuple(members))
                    self.assertEqual(run["policy"]["company_size"], quantity)
                    expected = {
                        wave: select_wave(
                            definition,
                            bind_company_size(source, quantity),
                            "admission",
                            wave,
                        )
                        for wave in (1, 2, 5, 10)
                    }
                    # Later settings and roster edits cannot resize/reselect a
                    # run already frozen by the normal admission serializer.
                    source["wave_size_by_company_size"][str(quantity)] = 1
                    definition["species_refs"][:] = [9999]
                    members.append(999)
                    for wave, refs in expected.items():
                        self.assertEqual(
                            select_wave(
                                run["catalog"], run["policy"], run["seed"], wave
                            ),
                            refs,
                        )
                        self.assertEqual(len(refs), COUNTS[str(quantity)])

    def test_legacy_frozen_runs_preserve_original_sizes_without_added_elites(self):
        for kind in KINDS:
            old = dict(legacy_policy(), max_members=6)
            definition = catalog(kind)
            definition.pop("milestone_species_refs")
            definition.pop("additional_species_refs")
            original = deepcopy(old)
            bound = bind_company_size(old, 6)
            self.assertEqual(bound, original)
            frozen_choices = {
                1: (4, 3, 704, 704),
                5: (41, 4, 41, 704),
                10: (704, 1, 3, 704),
            }
            for wave in (1, 5, 10):
                expected = (
                    frozen_choices[wave][:2]
                    if kind == KINDS[1]
                    else frozen_choices[wave]
                )
                self.assertEqual(select_wave(definition, old, "old", wave), expected)
                self.assertEqual(
                    select_wave(definition, old, "old", wave),
                    select_wave(definition, bound, "old", wave),
                )
                self.assertEqual(
                    len(select_wave(definition, bound, "old", wave)),
                    2 if kind == KINDS[1] else 4,
                )

    def test_malformed_sizes_intervals_and_milestone_pools_fail_closed(self):
        for change in (
            dict(wave_size_by_company_size={}),
            dict(wave_size_by_company_size={**COUNTS, "1": True}),
            dict(wave_size_by_company_size={**COUNTS, "1": 0}),
            dict(wave_size_by_company_size={**COUNTS, "1": 65}),
            dict(wave_size_by_company_size=list(COUNTS.values())),
            dict(elite_wave_interval=True),
            dict(elite_wave_interval=1),
            dict(company_size=0),
            dict(company_size=True),
            dict(company_size=3, classic_wave_size=4, ultimate_wave_size=4),
        ):
            with self.subTest(policy=change), self.assertRaises(ValueError):
                validate({**current_policy(), **change})
        for quantity in (0, 7, True, "2"):
            with self.subTest(quantity=quantity), self.assertRaises(ValueError):
                bind_company_size(current_policy(), quantity)
        for change in (
            dict(species_refs=[]),
            dict(species_refs=[True]),
            dict(milestone_species_refs=[1001, 1001]),
            dict(milestone_species_refs=[0]),
            dict(milestone_species_refs=[True]),
            dict(milestone_species_refs="1001"),
            dict(milestone_species_refs=[1]),
            dict(milestone_species_refs=[50]),
            dict(additional_species_refs=[50, 50]),
            dict(additional_species_refs=[0]),
            dict(additional_species_refs=[True]),
            dict(additional_species_refs="50"),
        ):
            with self.subTest(catalog=change), self.assertRaises(ValueError):
                select_wave(
                    {**catalog(KINDS[0]), **change},
                    bind_company_size(current_policy(), 1),
                    "bad",
                    5,
                )

    def test_frozen_native_roles_include_scoped_elites_and_reject_foreign_species(self):
        from wakfu_server.rift_encounter_roles import (
            roles_for_catalog,
            roles_from_record,
            POLICY,
        )
        from wakfu_server.rift_native_gameplay_policy import POLICY as GAMEPLAY_POLICY

        for kind in KINDS:
            bound = bind_company_size(current_policy(), 6)
            bound["native_gameplay"] = dict(
                enabled=True,
                policy=GAMEPLAY_POLICY,
                authority="native_consumers_with_reconstructed_producers",
                enabled_types=list(KINDS),
                encounter_roles=dict(policy=POLICY, player_team=1, npc_team=0),
            )
            definition = catalog(kind)
            selected = select_wave(definition, bound, "roles", 5)
            roles = roles_for_catalog(definition, bound, monster_references=selected)
            frozen = roles.record()
            self.assertEqual(
                frozen["rift_scope"]["catalog"]["species_refs"],
                sorted(
                    definition["species_refs"]
                    + definition["additional_species_refs"]
                    + definition["milestone_species_refs"]
                ),
            )
            self.assertEqual(roles_from_record(frozen).record(), frozen)
            with self.assertRaisesRegex(ValueError, "original catalog"):
                roles_for_catalog(
                    definition, bound, monster_references=(*selected[:-1], 9999)
                )
            definition["milestone_species_refs"].append(9999)
            self.assertEqual(roles_from_record(frozen).record(), frozen)
