"""Owner-neutral selected PV lifetimes, isolation and first-round boundaries."""
import copy
import unittest
from types import SimpleNamespace

from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_effect_area_queries import own_specific_area
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_state_managers import (
    registered_area_pv,
    retained_area_pv_row,
    selected_area_pv_scope,
    state_manager,
)
from wakfu_server.combat_start_events import deliver_fight_start


class GenericPopulationLifecycleTests(unittest.TestCase):
    def fixture(self, owner_id):
        # Use a published real null-Qf glyph prototype, never a mocked validator.
        reference, definition = next(
            (int(reference), row)
            for reference, row in native_effect_areas().items()
            if row.get("type") == "GLYPH"
            and 12 not in row.get("native_area_properties", ())
            and isinstance(row.get("entry_masks"), (tuple, list))
        )
        row = dict(
            uid=91,
            reference=reference,
            owner_id=owner_id,
            cell=(2, 3, 0),
            native_area_contract="faY",
            native_running_effect_manager=False,
            native_cells_xy=((2, 3),),
        )
        fight = SimpleNamespace(
            actors={owner_id: SimpleNamespace(id=owner_id)},
            native_effect_areas={91: row},
            native_retired_area_managers={},
        )
        registered_area_pv(fight, 91)
        return fight, row

    def test_npc_and_summon_owner_removed_null_qf_is_not_spatial_or_state_manager(self):
        # These are generic PV identities, not assumed player7 or a breed gate.
        for owner_id in (-7, -8001):
            with self.subTest(owner_id=owner_id):
                fight, row = self.fixture(owner_id)
                with selected_area_pv_scope(fight, (owner_id, 91)):
                    del fight.native_effect_areas[91]
                    self.assertIs(retained_area_pv_row(fight, 91), row)
                    self.assertFalse(
                        registered_area_pv(fight, 91).native_running_effect_manager
                    )
                    self.assertIsNone(state_manager(fight, 91))
                    self.assertTrue(
                        own_specific_area(
                            fight,
                            reference=row["reference"],
                            selector="target",
                            caster_id=owner_id,
                            target_id=91,
                            cell=(2, 3, 0),
                        )
                    )
                    self.assertFalse(
                        own_specific_area(
                            fight,
                            reference=row["reference"],
                            selector="target",
                            caster_id=owner_id,
                            target_id=None,
                            cell=(2, 3, 0),
                        )
                    )
                self.assertIsNone(retained_area_pv_row(fight, 91))

    def test_failed_preview_releases_context_and_keeps_authoritative_population(self):
        original, row = self.fixture(-7)
        preview = copy.deepcopy(original)
        other, _ = self.fixture(-8001)
        del other.native_effect_areas[91]
        with self.assertRaisesRegex(RuntimeError, "reaction failed"):
            with selected_area_pv_scope(preview, (-7, 91)):
                del preview.native_effect_areas[91]
                self.assertIsNotNone(retained_area_pv_row(preview, 91))
                self.assertIsNone(retained_area_pv_row(other, 91))
                self.assertIs(original.native_effect_areas[91], row)
                raise RuntimeError("reaction failed")
        self.assertIsNone(retained_area_pv_row(preview, 91))
        self.assertIs(original.native_effect_areas[91], row)
        self.assertEqual(original.native_retired_area_managers, {})

    def test_multi_pc_and_npc_first_round_precedes_every_callback(self):
        actors = [
            Actor(31, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
            Actor(42, 0, (0, 1, 0), 60, 6, 3, 9, 1, 4, True),
            Actor(-8001, 1, (1, 0, 0), 20, 6, 3, 5, 1),
        ]
        fight = Fight(
            77,
            actors,
            {a.position for a in actors},
            {0: {(0, 0, 0), (0, 1, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(3)
        fight.ready(4)
        fight.native_class_initializations = {31: {"breed": 1}, 42: {"breed": 5}}
        seen = []

        def replay(event, **kwargs):
            seen.append(
                (
                    event.manager_actor_id,
                    event.event_ids,
                    fight.native_table_turn,
                    fight.native_timeline_round,
                )
            )
            return (True,)

        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=fight),
            native_clone_authority=object(),
            replay_event=replay,
        )
        deliver_fight_start(dispatcher, initialized_actor_ids=(31, 42, -8001))
        self.assertEqual(len(seen), 18)
        self.assertTrue(all(row[2:] == (1, 1) for row in seen))
        self.assertEqual({row[0] for row in seen if row[1] == (1028,)}, {31, 42, -8001})
        self.assertEqual({row[0] for row in seen if row[1] == (1003,)}, {31, 42, -8001})
        self.assertEqual(fight.turn_id, 1)
        self.assertTrue(fight.native_start_event_delivered)
