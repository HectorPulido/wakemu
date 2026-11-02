"""Owner KO removes native Qs areas with !keep_after, preserving the PV clone."""
import struct
import unittest
from copy import deepcopy
from types import SimpleNamespace

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_qi_registry import NativeQIRegistry
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    register_global_area,
    set_global_fighter_status,
)
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_owned_area_death import apply_owned_area_death
from wakfu_server.combat_wall_area import wall_constructor


class OwnedAreaDeathTests(unittest.TestCase):
    def fixture(self, *, registered_death=True, include_kept=True):
        actors = [
            Actor(7, 0, (0, 0, 0), 50, 6, 3, 10, 1, 3, True),
            Actor(-7, 1, (1, 0, 0), 10, 6, 3, 1, 1),
        ]
        fight = Fight(
            507,
            actors,
            {actor.position for actor in actors},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(3)
        fight.native_qi_snapshot = {
            "x": 0,
            "y": 0,
            "width": 4,
            "height": 4,
            "cell_masks": [0] * 16,
        }
        fight.native_qi_slots = [None] * 127
        fight.native_qi_touched_cells = []
        fight.native_qi_byte_topology = {}
        fight.native_retired_area_managers = {}
        fight.native_effect_uid_next = 3000
        fight.native_retained_records = {}
        fight.native_owned_area_effects = {}

        definition = native_effect_areas()["196"]
        constructor = wall_constructor(definition, 1)
        registry = NativeQIRegistry(
            fight.native_qi_snapshot,
            fight.native_qi_slots,
            touched_cells=fight.native_qi_touched_cells,
            byte_topology=fight.native_qi_byte_topology,
        )
        rows = {}
        fighter_slots = {}
        for actor in actors:
            fighter_slots[actor.id] = registry.register(
                {
                    "identity": ("actor", actor.id),
                    "position": actor.position[:2],
                    "radius": 0,
                    "indexed": False,
                    "movement_blocking": False,
                }
            )
            actor.native_obstacle_id = fighter_slots[actor.id]
            actor.physical_radius = 0
        area_specs = [(901, (2, 2), False)]
        if include_kept:
            area_specs.append((902, (3, 3), True))
        for uid, cell, keep_after in area_specs:
            slot = registry.register(
                {
                    "identity": ("effect_area", uid),
                    "position": cell,
                    "radius": 0,
                    "indexed": False,
                    "movement_blocking": constructor["movement_blocking"],
                }
            )
            rows[uid] = dict(
                uid=uid,
                reference=196,
                effect_uid=uid + 2000,
                owner_id=-7,
                keep_after=keep_after,
                native_area_contract="fbd",
                native_type_id=7,
                native_running_effect_manager=True,
                level=1,
                native_wall_constructor=constructor,
                native_wall_hp_current=constructor["hp_initial"],
                native_wall_hp_source="fbd.PA.sgC.aYS",
                native_obstacle_id=slot,
                native_obstacle_source="QI.f(QK)",
                cell=(*cell, 0),
                native_cells_xy=(cell,),
                native_qq_bhi=False,
                native_qq_guard_source="Qq.constructor",
                child_effect_uids={},
            )
            # The retained Qf/eYQ creator is a separate native object from
            # the Qs spatial area. Qs retirement must preserve that runner.
            creator_uid = uid + 2000
            creator = dict(
                uid=creator_uid,
                area_uid=uid,
                effect_class=339,
                target_id=-7,
                caster_id=7,
                state_uid=None,
                payload="native-eYQ-creator",
                keep_after=keep_after,
                executed=True,
                timer=None,
            )
            fight.native_owned_area_effects[creator_uid] = dict(creator)
            fight.native_retained_records[creator_uid] = dict(
                creator,
                manager_id=creator_uid,
                container_kind="effect_area",
                container_id=uid,
            )
        fight.native_qi_slots = registry.serialized_slots()
        fight.native_qi_touched_cells = registry.serialized_cells()
        fight.native_qi_byte_topology = registry.serialized_byte_topology()
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_effect_areas.update(rows)
        for uid in rows:
            register_global_area(fight, uid)

        if registered_death:
            # A real owned damage event and fdy transition establish the corpse.
            with fight.effect_resolution():
                fight.apply_effect_damage(7, -7, 10)
            set_global_fighter_status(fight, -7, "OFF_PLAY")
        return fight, definition, rows, fighter_slots

    def retention(self, fight, definition, *, fail_removal=False, packets=None):
        dispatcher = SimpleNamespace(effects={})
        events = NativeAreaEventRuntime(
            fight, dispatcher, definitions={"196": definition}
        )
        packet_rows = [] if packets is None else packets

        def area_removed(uid):
            if fail_removal:
                raise ValueError("synthetic callback failure")
            if packets is not None:
                from wakfu_server.combat_effect_area_codec import area_retirement

                packet_rows.append(area_retirement(fight.id, 4, uid))

        events.area_removed = area_removed
        return SimpleNamespace(
            fight=fight,
            area_events=events,
            synchronize=lambda: None,
        )

    def test_real_off_play_death_removes_owned_qs_area_and_its_qi_only(self):
        fight, definition, rows, _ = self.fixture()
        uid_start = fight.native_effect_uid_next
        source_rows = tuple(fight.native_effect_areas)
        source_creators = deepcopy(fight.native_owned_area_effects)
        source_retained = deepcopy(fight.native_retained_records)
        preview = deepcopy(fight)
        removed = apply_owned_area_death(
            preview, -7, retention=self.retention(preview, definition)
        )
        self.assertEqual(removed, (901,))
        self.assertEqual(set(preview.native_effect_areas), {902})
        self.assertEqual(preview.native_owned_area_effects, source_creators)
        self.assertEqual(preview.native_retained_records, source_retained)
        self.assertTrue(preview.native_effect_areas[902]["keep_after"])
        self.assertIsNone(preview.native_qi_slots[rows[901]["native_obstacle_id"]])
        self.assertIsNotNone(preview.native_qi_slots[rows[902]["native_obstacle_id"]])
        self.assertEqual(tuple(fight.native_effect_areas), source_rows)
        self.assertEqual(fight.native_owned_area_effects, source_creators)
        self.assertEqual(fight.native_retained_records, source_retained)
        self.assertEqual(fight.native_effect_uid_next, uid_start)
        self.assertEqual(preview.native_effect_uid_next, uid_start)
        self.assertEqual(fight.actors[-7].hp, 0)

    def test_callback_failure_discards_private_qs_and_qi_mutations(self):
        fight, definition, rows, _ = self.fixture()
        before_slots = list(fight.native_qi_slots)
        before_uid = fight.native_effect_uid_next
        before_creators = deepcopy(fight.native_owned_area_effects)
        before_retained = deepcopy(fight.native_retained_records)
        preview = deepcopy(fight)
        with self.assertRaisesRegex(ValueError, "synthetic callback failure"):
            apply_owned_area_death(
                preview,
                -7,
                retention=self.retention(preview, definition, fail_removal=True),
            )
        self.assertEqual(set(fight.native_effect_areas), {901, 902})
        self.assertEqual(fight.native_qi_slots, before_slots)
        self.assertEqual(fight.native_effect_uid_next, before_uid)
        self.assertEqual(fight.native_owned_area_effects, before_creators)
        self.assertEqual(fight.native_retained_records, before_retained)
        self.assertEqual(
            fight.native_effect_areas[901]["native_obstacle_id"],
            rows[901]["native_obstacle_id"],
        )

    def test_owned_death_callback_removes_qs_before_terminal_settlement(self):
        from wakfu_server.combat_death_events import deliver_owned_death
        from wakfu_server.combat_event_replay import NativeEventSource
        from wakfu_server.combat_global_pv_collections import global_fighter_guards

        fight, definition, rows, _ = self.fixture(
            registered_death=False, include_kept=False
        )
        packets = []
        deliveries = []
        events = NativeAreaEventRuntime(
            fight, SimpleNamespace(effects={}), definitions={"196": definition}
        )
        from wakfu_server.combat_effect_area_codec import area_retirement

        events.area_removed = lambda uid: packets.append(
            area_retirement(fight.id, 4, uid)
        )
        synchronizations = []
        retention = SimpleNamespace(
            fight=fight,
            area_events=events,
            synchronize=lambda: synchronizations.append("sync"),
        )
        source = NativeEventSource(
            3001,
            123,
            10,
            7,
            -7,
            fight.actors[-7].position,
            (1013,),
            6,
            -7,
            None,
            False,
            False,
            False,
            True,
        )

        def replay(event_source, *, authority):
            self.assertEqual(fight.phase, "active")
            self.assertEqual(set(fight.native_effect_areas), set())
            self.assertIsNone(fight.native_qi_slots[rows[901]["native_obstacle_id"]])
            self.assertEqual(
                global_fighter_guards(fight, -7),
                {
                    "baF": False,
                    "baG": True,
                    "baK": False,
                },
            )
            self.assertTrue(fight.native_death_event_deliveries)
            deliveries.append((event_source.event_ids, event_source.channel))
            return ()

        def deliver(actor_id):
            return deliver_owned_death(
                fight,
                actor_id,
                source=source,
                replay=replay,
                authority=object(),
                retention=retention,
            )

        with fight.effect_resolution():
            fight.apply_effect_damage(7, -7, 10, native_death_delivery=deliver)
            self.assertEqual(fight.phase, "active")
        self.assertEqual(set(fight.native_effect_areas), set())
        self.assertIn(2901, fight.native_owned_area_effects)
        self.assertIn(2901, fight.native_retained_records)
        self.assertEqual(fight.phase, "finished")
        self.assertEqual(len(packets), 1)
        self.assertEqual(struct.unpack(">iiiq", packets[0][1]), (fight.id, 4, -1, 901))
        self.assertEqual(synchronizations, ["sync"])
        self.assertTrue(deliveries)


if __name__ == "__main__":
    unittest.main()
