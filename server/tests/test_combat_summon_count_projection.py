"""GF count identity projection preserves fresh ordinary creation authority."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
import sys
from unittest.mock import patch

import test_combat_ordinary_authority as fixtures
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_summon_count import registered_summon_counts
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections


class SummonCountProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.OrdinaryAuthorityTests.setUpClass()

    def setUp(self):
        fixture = fixtures.OrdinaryAuthorityTests()
        fixture.setUp()
        self.preview = fixture.preview
        self.authority = fixture.authority
        initialize_global_pv_collections(
            self.preview, tuple(self.preview.actors), controller_registration=True
        )

    def test_projection_matches_full_native_flags_and_zero_counts(self):
        for actor in self.preview.actors.values():
            metadata = self.authority(self.preview, actor)
            self.assertEqual(
                self.authority.summon_count_flags(self.preview, actor),
                (
                    metadata.targeting.get("is_eGj"),
                    metadata.targeting.get("dTE"),
                ),
            )
        legacy = lambda preview, actor: self.authority(preview, actor)
        self.assertEqual(
            registered_summon_counts(self.preview, 7, {}, self.authority, self.preview),
            (0, {}),
        )
        self.assertEqual(
            registered_summon_counts(self.preview, 7, {}, legacy, self.preview), (0, {})
        )

    def test_projection_never_constructs_spellbooks_or_full_actor_metadata(self):
        with patch.object(
            OrdinaryActorAuthority,
            "__call__",
            side_effect=AssertionError("Full metadata should not be projected"),
        ):
            self.assertEqual(
                registered_summon_counts(
                    self.preview, 7, {}, self.authority, self.preview
                ),
                (0, {}),
            )

    def test_count_walk_shares_only_one_population_proof_and_rebuilds_next_query(self):
        counts = {"identity": 0, "facts": 0}
        identity_code = self.authority._creation_identity.__func__.__code__
        facts_code = self.authority._creation_facts.__func__.__code__

        def observe(frame, event, arg):
            if event == "call":
                if frame.f_code is identity_code:
                    counts["identity"] += 1
                elif frame.f_code is facts_code:
                    counts["facts"] += 1

        previous_profile = sys.getprofile()
        with patch.object(
            self.authority,
            "_creation_population",
            wraps=self.authority._creation_population,
        ) as population:
            try:
                # Observe code objects without replacing either bound method:
                # custom method replacements deliberately take the legacy path.
                sys.setprofile(observe)
                for _ in range(2):
                    self.assertEqual(
                        registered_summon_counts(
                            self.preview, 7, {}, self.authority, self.preview
                        ),
                        (0, {}),
                    )
            finally:
                sys.setprofile(previous_profile)
            self.assertEqual(population.call_count, 2)
            self.assertEqual(counts["identity"], 2 * len(self.preview.actors))
            self.assertEqual(counts["facts"], 0)
        # A later query cannot reuse the successful roster/source proof.
        self.authority.monsters = {}
        with self.assertRaisesRegex(ValueError, "roster changed"):
            registered_summon_counts(self.preview, 7, {}, self.authority, self.preview)

    def test_count_kind_short_circuit_keeps_full_dynamic_authority_checks(self):
        actor_id = 7
        for field, value in (
            ("native_master_id", -7),
            ("native_carrier_id", -7),
        ):
            with self.subTest(field=field):
                preview, authority = deepcopy((self.preview, self.authority))
                actor = preview.actors[actor_id]
                setattr(actor, field, value)
                if field == "native_master_id":
                    with self.assertRaisesRegex(
                        ValueError, "changed native relationships"
                    ):
                        registered_summon_counts(preview, 7, {}, authority, preview)
                else:
                    self.assertEqual(
                        registered_summon_counts(preview, 7, {}, authority, preview),
                        (0, {}),
                    )
                with self.assertRaises(ValueError):
                    authority(preview, actor)
        self.preview.native_controller_registry["fighters"][str(actor_id)][
            "current_controller"
        ] = "unknown"
        self.assertEqual(
            registered_summon_counts(self.preview, 7, {}, self.authority, self.preview),
            (0, {}),
        )
        with self.assertRaises(ValueError):
            self.authority(self.preview, self.preview.actors[actor_id])

    def test_detached_flags_do_not_force_an_ordinary_population_proof(self):
        detached = SimpleNamespace(targeting={"is_eGj": True, "dTE": True})
        with patch(
            "wakfu_server.combat_native_actor_lookup.detached_authority",
            return_value=detached,
        ):
            self.assertEqual(
                self.authority.summon_count_flags(
                    self.preview,
                    self.preview.actors[7],
                    _population=lambda: self.fail("Detached path must stay lazy"),
                ),
                (True, True),
            )

    def test_custom_catalog_callbacks_keep_fresh_population_checks(self):
        from wakfu_server.combat_trove_long_map import NativeTroveLongMap

        identities = NativeTroveLongMap(
            self.preview.native_global_pv_collections["fighters"]
        ).order()
        catalog = self.authority.catalog
        last = self.preview.actors[identities[-1]]

        class CallbackCatalog:
            def __getitem__(self, key):
                value = catalog[key]
                last.pve_withdrawn = True
                return value

        self.authority.catalog = CallbackCatalog()
        with self.assertRaisesRegex(ValueError, "Withdrawn PvE actor"):
            registered_summon_counts(self.preview, 7, {}, self.authority, self.preview)

    def test_unrelated_invalid_components_grant_no_capabilities_and_full_query_rejects(
        self,
    ):
        actor = self.preview.actors[-7]
        self.authority.npc_spellbook = lambda *args: object()
        self.assertEqual(
            self.authority.summon_count_flags(self.preview, actor), (True, False)
        )
        with self.assertRaisesRegex(ValueError, "Invalid ordinary NPC spellbook"):
            self.authority(self.preview, actor)
        self.authority.npc_spellbook = None
        actor.native_cosmetic_state = {"unknown": True}
        self.assertEqual(
            self.authority.summon_count_flags(self.preview, actor), (True, False)
        )
        with self.assertRaisesRegex(ValueError, "Malformed native cosmetic"):
            self.authority(self.preview, actor)

    def test_fresh_critical_mutations_reject_full_and_projected_authority(self):
        def remove_roster(preview, authority, actor):
            preview.actors.pop(-7)

        def remove_profile(preview, authority, actor):
            authority.catalog = {"player": None, "npc": {}}

        def invalid_source(preview, authority, actor):
            authority.characters[7]["id"] = 999

        def invalid_kind(preview, authority, actor):
            actor.controlled = False

        def invalid_carry(preview, authority, actor):
            actor.native_carrier_id = -7

        def invalid_master(preview, authority, actor):
            actor.native_master_id = -7

        def invalid_team(preview, authority, actor):
            actor.team = 128

        def invalid_status(preview, authority, actor):
            preview.native_global_pv_collections["fighter_status"]["7"] = "UNKNOWN"

        def invalid_controller(preview, authority, actor):
            preview.native_controller_registry["fighters"]["7"][
                "current_controller"
            ] = "unknown"

        def withdrawn(preview, authority, actor):
            actor.pve_withdrawn = True

        for mutate in (
            remove_roster,
            remove_profile,
            invalid_source,
            invalid_kind,
            invalid_master,
            withdrawn,
        ):
            with self.subTest(mutation=mutate.__name__):
                preview, authority = deepcopy((self.preview, self.authority))
                actor = preview.actors[7]
                mutate(preview, authority, actor)
                for query in (authority, authority.summon_count_flags):
                    with self.assertRaises(ValueError):
                        query(preview, actor)
        # GF short-circuits ordinary dTE=false before dynamic team/life/
        # carrying/controller reads; full actor authority still validates them.
        for mutate in (invalid_carry, invalid_team, invalid_status, invalid_controller):
            with self.subTest(dynamic_mutation=mutate.__name__):
                preview, authority = deepcopy((self.preview, self.authority))
                actor = preview.actors[7]
                mutate(preview, authority, actor)
                self.assertEqual(
                    authority.summon_count_flags(preview, actor), (True, False)
                )
                with self.assertRaises(ValueError):
                    authority(preview, actor)
                if mutate is invalid_status:
                    # The count's actual fdt population remains strictly checked.
                    with self.assertRaises(ValueError):
                        registered_summon_counts(preview, 7, {}, authority, preview)
        actor_copy = deepcopy(self.preview.actors[7])
        for query in (self.authority, self.authority.summon_count_flags):
            with self.assertRaisesRegex(ValueError, "current preview"):
                query(self.preview, actor_copy)

    def test_custom_subclass_and_function_callbacks_keep_full_legacy_contract(self):
        class CustomAuthority(OrdinaryActorAuthority):
            def __call__(self, preview, actor):
                metadata = super().__call__(preview, actor)
                return replace(metadata, targeting={**metadata.targeting, "dTE": None})

        custom = CustomAuthority(
            characters=self.authority.characters,
            monsters=self.authority.monsters,
            decks=self.authority.decks,
            excluded_decks=self.authority.excluded_decks,
            catalog=self.authority.catalog,
        )
        for provider in (custom, lambda preview, actor: custom(preview, actor)):
            self.assertIsNone(
                registered_summon_counts(self.preview, 7, {}, provider, self.preview)
            )
        self.assertEqual(
            custom.summon_count_flags(self.preview, self.preview.actors[7]),
            (True, None),
        )
