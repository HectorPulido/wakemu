"""A boss's own recurring mechanic survives valid entourage changes."""
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import combat_encounter_table_listeners as listeners


POLICY = dict(
    policy="wild-gobball-test",
    authority="reviewed-native-constructor",
    map_id=712,
    monster_references=[2768],
    catalog_revision="0" * 64,
    boss_reference=2768,
    boss_constructor_state=2334,
    owner_reference=2768,
    owner_constructor_state=2334,
    effect_reference=316157,
    event_id=1003,
    channel=61,
    timing="owned_boss_table_start",
    roster_scope="owned_boss",
    additional_effect_references=[],
)


class ListenerDatabase:
    def __init__(self, exact=None):
        self.exact = exact
        self.rows = {POLICY["policy"]: deepcopy(POLICY)}

    @contextmanager
    def connection(self):
        yield self

    def execute(self, query, parameters):
        if "SELECT * FROM encounter_table_listener_versions" in query:
            return SimpleNamespace(fetchone=lambda: deepcopy(self.rows[parameters[0]]))
        if "version.roster_scope='owned_boss'" in query:
            map_id, references = parameters
            rows = (
                [dict(policy=POLICY["policy"])]
                if map_id == 712 and 2768 in references
                else []
            )
            return SimpleNamespace(fetchall=lambda: rows)
        return SimpleNamespace(fetchone=lambda: self.exact)


def native_record(path, collection, reference):
    if collection == "states":
        return dict(effect_ids=[316157])
    if path.name == "native-retained-effect-metadata.json":
        return dict(
            subscription=True,
            event_global_subscription=True,
            event_reverse_subscription=False,
            event_caster_code=2,
            event_target_code=2,
        )
    return dict(target_masks=[None, None, None, None, None, [1003], None])


class OwnedBossTableListenerScopeTests(unittest.TestCase):
    def setUp(self):
        listeners._version.cache_clear()
        self.addCleanup(listeners._version.cache_clear)
        self.database = ListenerDatabase()
        self.patches = [
            patch.object(listeners, "_database", return_value=self.database),
            patch.object(listeners, "source_revision_matches", return_value=True),
            patch("wakfu_server.native_catalog.record", side_effect=native_record),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_different_complete_rosters_keep_same_self_owned_constructor(self):
        for roster in (
            [2768],
            [2764, 2764, 2765, 2766, 2768],
            [2764, 2765, 2765, 2766, 2767, 2768],
        ):
            with self.subTest(roster=roster):
                frozen = listeners.freeze_table_listener_policy(712, roster)
                self.assertEqual(frozen["effect_reference"], 316157)
                self.assertEqual(frozen["owner_constructor_state"], 2334)

    def test_other_map_no_boss_and_duplicate_boss_do_not_gain_listener(self):
        for map_id, roster in ((711, [2768]), (712, [2764, 2765]), (712, [2768, 2768])):
            with self.subTest(map_id=map_id, roster=roster):
                self.assertIsNone(
                    listeners.freeze_table_listener_policy(
                        map_id, roster, required=False
                    )
                )

    def test_exact_roster_policy_still_takes_precedence_and_keeps_old_shape(self):
        exact = dict(
            POLICY,
            policy="old-exact",
            roster_scope="exact",
            monster_references=[2764, 2768],
        )
        self.database.rows["old-exact"] = exact
        self.database.exact = dict(policy="old-exact")
        frozen = listeners.freeze_table_listener_policy(712, [2764, 2768])
        self.assertEqual(frozen["policy"], "old-exact")
        self.assertNotIn("roster_scope", frozen)
        with self.assertRaisesRegex(ValueError, "differs from admission"):
            listeners.freeze_table_listener_policy(712, [2768])

    def test_summoned_controller_cannot_use_self_owned_scope(self):
        self.database.rows[POLICY["policy"]]["owner_reference"] = 4371
        self.assertIsNone(
            listeners.freeze_table_listener_policy(712, [2764, 2768], required=False)
        )

    def test_existing_none_admission_is_preserved_and_new_fight_freezes_scope(self):
        roles = SimpleNamespace(map_id=712, monster_references=(2764, 2768))
        old = SimpleNamespace(native_encounter_table_listener_policy=None)
        self.assertIsNone(
            listeners.freeze_encounter_table_listener_policy(old, roles=roles)
        )
        fresh = SimpleNamespace()
        frozen = listeners.freeze_encounter_table_listener_policy(fresh, roles=roles)
        self.assertEqual(frozen["policy"], POLICY["policy"])
        self.assertEqual(
            listeners.freeze_encounter_table_listener_policy(fresh, roles=roles), frozen
        )
        with self.assertRaisesRegex(ValueError, "differs from encounter"):
            listeners.freeze_encounter_table_listener_policy(
                fresh, roles=SimpleNamespace(map_id=711, monster_references=(2768,))
            )

    def test_native_metadata_still_required_before_freezing(self):
        with patch("wakfu_server.native_catalog.record", return_value=None):
            with self.assertRaisesRegex(ValueError, "original native metadata"):
                listeners.freeze_table_listener_policy(712, [2768])


if __name__ == "__main__":
    unittest.main()
