"""GF reads current ordinary kind before unrelated dynamic authority."""
from copy import copy, deepcopy
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_combat_ordinary_authority as fixtures
from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    register_global_fighter,
)
from wakfu_server.combat_summon_count import registered_summon_counts


def legacy_flags(authority, preview, actor, *, _population=None):
    """Prior exact-native GF branch: full facts even for ordinary dTE=false."""
    authority._creation_facts(
        preview, actor, _population=None if _population is None else _population()
    )
    return True, False


class GFIdentityProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.OrdinaryAuthorityTests.setUpClass()

    def setUp(self):
        fixture = fixtures.OrdinaryAuthorityTests()
        fixture.setUp()
        self.fight, self.authority = fixture.preview, fixture.authority
        initialize_global_pv_collections(
            self.fight, tuple(self.fight.actors), controller_registration=True
        )

    def test_ordinary_flags_counts_and_live_identity_guards(self):
        for actor in self.fight.actors.values():
            self.assertEqual(
                self.authority.summon_count_flags(self.fight, actor),
                legacy_flags(self.authority, self.fight, actor),
            )
        with patch(
            "wakfu_server.combat_carrying.carrying_relations",
            side_effect=AssertionError("GF must not query dynamic carry facts"),
        ):
            self.assertEqual(
                registered_summon_counts(self.fight, 7, {}, self.authority, self.fight),
                (0, {}),
            )
        for change in ("source", "master", "membership"):
            fight, authority = deepcopy((self.fight, self.authority))
            actor = fight.actors[7]
            if change == "source":
                authority.characters[7]["id"] = 999
            elif change == "master":
                actor.native_master_id = -7
            else:
                actor = deepcopy(actor)
            with self.assertRaises(ValueError):
                authority.summon_count_flags(fight, actor)

    def test_unrelated_carry_controller_remain_full_query_guards(self):
        for change in ("carry", "controller"):
            fight, authority = deepcopy((self.fight, self.authority))
            actor = fight.actors[7]
            if change == "carry":
                actor.native_carrier_id = -7
            else:
                fight.native_controller_registry["fighters"]["7"][
                    "current_controller"
                ] = "unknown"
            # Actual native GF short-circuits when this ordinary actor dTE=false.
            self.assertEqual(authority.summon_count_flags(fight, actor), (True, False))
            with self.assertRaises(ValueError):
                legacy_flags(authority, fight, actor)
            with self.assertRaises(ValueError):
                authority(fight, actor)

    def test_registered_summon_counts_keep_current_native_filters(self):
        from wakfu_server.combat_native_death_status import (
            initialize_fresh_bje_death_status,
        )

        summon = deepcopy(self.fight.actors[-7])
        summon.id = 901
        summon.native_controller_id = 7
        summon.native_fight_properties = frozenset()
        summon.native_world_properties = frozenset()
        if hasattr(summon, "native_death_status"):
            del summon.native_death_status
        initialize_fresh_bje_death_status(summon)
        self.fight.actors[901] = summon
        register_global_fighter(self.fight, 901, controller_id=7)
        view = copy(self.fight)
        view.actors = {
            uid: actor for uid, actor in self.fight.actors.items() if uid != 901
        }
        records = {
            901: {
                "authority": {
                    "targeting": {"is_eGj": True, "dTE": True},
                    "breed_id": 5525,
                },
                "controller_id": 7,
            }
        }
        self.assertEqual(
            registered_summon_counts(self.fight, 7, records, self.authority, view),
            (1, {5525: 1}),
        )
        summon.native_fight_properties = frozenset({103})
        self.assertEqual(
            registered_summon_counts(self.fight, 7, records, self.authority, view),
            (0, {}),
        )
        summon.native_fight_properties = frozenset()
        summon.native_controller_id = -7
        self.assertIsNone(
            registered_summon_counts(self.fight, 7, records, self.authority, view)
        )

    def test_custom_catalog_subclass_and_detached_keep_existing_contract(self):
        self.authority.catalog = dict(self.authority.catalog)
        with patch.object(
            self.authority, "_creation_facts", wraps=self.authority._creation_facts
        ) as full:
            self.assertEqual(
                self.authority.summon_count_flags(self.fight, self.fight.actors[7]),
                (True, False),
            )
            self.assertEqual(full.call_count, 1)

        class Custom(OrdinaryActorAuthority):
            def __call__(self, preview, actor):
                return SimpleNamespace(targeting={"is_eGj": True, "dTE": None})

        custom = object.__new__(Custom)
        self.assertEqual(
            custom.summon_count_flags(self.fight, self.fight.actors[7]), (True, None)
        )
        with patch(
            "wakfu_server.combat_native_actor_lookup.detached_authority",
            return_value=SimpleNamespace(targeting={"is_eGj": True, "dTE": True}),
        ), patch.object(
            self.authority,
            "_creation_facts",
            side_effect=AssertionError("Detached must not query ordinary"),
        ):
            self.assertEqual(
                self.authority.summon_count_flags(self.fight, self.fight.actors[7]),
                (True, True),
            )

    def test_custom_fact_or_identity_delegate_preserves_full_fallback_order(self):
        from types import MethodType

        actor = self.fight.actors[7]
        for name in ("_creation_facts", "_creation_identity"):
            for placement in ("instance", "class"):
                with self.subTest(delegate=name, placement=placement):
                    trace = []

                    def delegated(owner, preview, selected, *, _population=None):
                        trace.append(name)
                        raise ValueError("actual custom delegate invoked")

                    if placement == "instance":
                        context = patch.object(
                            self.authority, name, MethodType(delegated, self.authority)
                        )
                    else:
                        context = patch.object(OrdinaryActorAuthority, name, delegated)
                    with context, patch(
                        "wakfu_server.combat_carrying.carrying_relations",
                        side_effect=AssertionError("callback order changed"),
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "actual custom delegate invoked"
                        ):
                            self.authority.summon_count_flags(self.fight, actor)
                    self.assertEqual(trace, [name])
