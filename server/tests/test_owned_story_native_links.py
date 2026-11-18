"""Owned story native links preserve literal portal and progression guards."""

import json
from pathlib import Path
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server import generic_transports, owned_story_native_links as links
from wakfu_server import owned_story_mechanics as mechanics
from wakfu_server.dungeon_encounters import room_members
from wakfu_server import owned_story_controller as controller
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.monsters import reference
from wakfu_server.owned_story_configuration import compile_story


ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"


class OwnedStoryNativeLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.selected = json.loads((ROOT / "zinit-reef-980.json").read_text())
        cls.native = json.loads((ROOT / "zinit-reef-980.native.v1.json").read_text())

    @staticmethod
    def body(source, destination, flag=0, mode=2):
        return struct.pack(">qiBi", source, destination, flag, mode)

    @staticmethod
    def character(source, *, item=False):
        position = source["approach_positions"][0]
        return dict(
            id=7,
            account_id=3,
            map_id=980,
            instance_id=99,
            x=position["x"],
            y=position["y"],
            z=position["z"],
            level=1,
            effective_level=1,
            inventory_items=(
                [dict(uid=7001, reference=18722, quantity=1)] if item else []
            ),
            quest_items=[],
            account_quest_items=[],
        )

    def test_literal_native_sources_endpoints_costs_and_modes_are_pinned(self):
        links.validate_sources(self.selected, self.native)
        compass = generic_transports.source(980, 25404)
        self.assertEqual(
            (
                compass["map_id"],
                compass["id"],
                compass["destinations"][0]["destination_id"],
            ),
            (980, 25404, 2241),
        )
        target = compass["destinations"][0]
        self.assertEqual((target["item_reference"], target["cyW"]), (0, 0))
        self.assertEqual(target["criterion"], "GetItemQuantity(18722) > 0")
        self.assertEqual(
            links.selected_link(self.selected, self.body(25404, 2241))["requires"],
            ["reef-room5-victory"],
        )
        self.assertEqual(
            links.selected_link(self.selected, self.body(25420, 2249))["requires"],
            ["reef-room6-victory"],
        )
        self.assertIsNone(links.selected_link(self.selected, self.body(25404, 2242)))
        for malformed in (b"", self.body(25404, 2241)[:-1]):
            with self.subTest(malformed=malformed), self.assertRaisesRegex(
                ValueError, "Malformed"
            ):
                links.selected_link(self.selected, malformed)
        for mode in ((1, 2), (0, 1), (1, 10)):
            with self.subTest(mode=mode), self.assertRaisesRegex(ValueError, "mode"):
                links.selected_link(
                    self.selected,
                    self.body(25404, 2241, flag=mode[0], mode=mode[1]),
                )
        tampered = json.loads(json.dumps(self.native))
        tampered["teleporters"]["25404"]["x"] += 1
        with self.assertRaisesRegex(ValueError, "pinned source"):
            links.validate_sources(self.selected, tampered)

    def test_internal_compass_requires_real_item_approach_and_finished_room_then_moves(
        self,
    ):
        source = generic_transports.source(980, 25404)
        character = self.character(source)
        body = self.body(25404, 2241)
        events = []
        db = object()
        settle = Mock(
            side_effect=lambda *_a, **_k: events.append(("settle", db))
            or dict(applied=True, packets=[])
        )

        with patch.object(
            controller, "_scope", return_value=(self.selected, set())
        ), patch(
            "wakfu_server.owned_story_mechanics.sources", return_value=self.native
        ), patch.object(
            controller, "_settle", settle
        ), patch(
            "wakfu_server.owned_story_mechanics.executor", return_value=object()
        ), patch(
            "wakfu_server.owned_story_mechanics.move",
            side_effect=lambda _db, _character, destination, *, direction: events.append(
                ("move", _db, destination, direction)
            )
            or (123, b"move"),
        ):
            with self.assertRaisesRegex(ValueError, "blocking encounter"):
                links.travel(
                    db,
                    None,
                    3,
                    "lease",
                    character,
                    body,
                    source_allowed=lambda *_: True,
                    in_fight=lambda _: False,
                )
            settle.assert_not_called()

            with patch.object(
                controller,
                "_scope",
                return_value=(self.selected, {"reef-room5-victory"}),
            ):
                with self.assertRaisesRegex(ValueError, "item or world condition"):
                    links.travel(
                        db,
                        None,
                        3,
                        "lease",
                        character,
                        body,
                        source_allowed=lambda *_: True,
                        in_fight=lambda _: False,
                    )
                settle.assert_not_called()

                # Native source approach is checked independently of quest and item state.
                with self.assertRaisesRegex(ValueError, "original approach"):
                    links.travel(
                        db,
                        None,
                        3,
                        "lease",
                        dict(character, x=character["x"] + 1),
                        body,
                        source_allowed=lambda *_: False,
                        in_fight=lambda _: False,
                    )
                settle.assert_not_called()

                result = links.travel(
                    db,
                    None,
                    3,
                    "lease",
                    self.character(source, item=True),
                    body,
                    source_allowed=lambda actor, actual: (
                        actual["id"] == source["id"]
                        and [actor[k] for k in ("x", "y", "z")]
                        == [source["approach_positions"][0][k] for k in ("x", "y", "z")]
                    ),
                    in_fight=lambda _: False,
                )
        self.assertTrue(result["internal"])
        self.assertEqual([event[0] for event in events], ["settle", "move"])
        self.assertTrue(all(event[1] is db for event in events))

    def test_terminal_external_link_leaves_with_same_db_after_settlement(self):
        source = generic_transports.source(980, 25420)
        character = self.character(source)
        body = self.body(25420, 2249)
        events = []
        db = object()
        with patch.object(
            controller,
            "_scope",
            return_value=(self.selected, {"reef-room6-victory"}),
        ), patch(
            "wakfu_server.owned_story_mechanics.sources", return_value=self.native
        ), patch.object(
            controller,
            "_settle",
            side_effect=lambda *_a, **_k: events.append(("settle", db))
            or dict(applied=True, packets=[]),
        ), patch(
            "wakfu_server.owned_story_mechanics.executor", return_value=object()
        ):
            with patch(
                "wakfu_server.dungeon_exit._leave",
                side_effect=lambda store, account, generation, identity, **kwargs: events.append(
                    ("leave", kwargs["_db"], kwargs["destination_for"]())
                ),
            ):
                result = links.travel(
                    db,
                    None,
                    3,
                    "lease",
                    character,
                    body,
                    source_allowed=lambda actor, actual: (
                        actual["id"] == source["id"]
                        and [actor[k] for k in ("x", "y", "z")]
                        == [source["approach_positions"][0][k] for k in ("x", "y", "z")]
                    ),
                    in_fight=lambda _: False,
                )
        self.assertFalse(result["internal"])
        self.assertEqual([event[0] for event in events], ["settle", "leave"])
        self.assertIs(events[0][1], db)
        self.assertIs(events[1][1], db)
        self.assertEqual(events[1][2], dict(map_id=986, x=-60, y=0, z=0))

    def test_eligible_cinematic_continuation_begins_after_settlement_before_leave(self):
        from wakfu_server import owned_story_mechanics as mechanics
        from wakfu_server.achievements import storage
        from wakfu_server import owned_cinematic_continuations

        selected = dict(
            self.selected,
            cinematic_continuation={"path": "reviewed-continuation.json"},
        )
        source = generic_transports.source(980, 25420)
        character = self.character(source)
        body = self.body(25420, 2249)
        db, store = object(), object()
        state = dict(running=[], completed=[2170])
        continuation = dict(id="reviewed-continuation")
        events = []
        settle = Mock(
            side_effect=lambda *_args, **_kwargs: events.append(("settle", db))
            or dict(applied=True, packets=[])
        )

        def begin(actual_db, actual_store, *_args, **_kwargs):
            events.append(("begin", actual_db, actual_store))

        with patch.object(
            controller, "_scope", return_value=(selected, {"reef-room6-victory"})
        ), patch(
            "wakfu_server.owned_story_mechanics.sources", return_value=self.native
        ), patch.object(
            mechanics, "executor", return_value=object()
        ), patch.object(
            controller, "_settle", settle
        ), patch(
            "wakfu_server.maps.dungeon_criteria.evaluate", return_value=True
        ), patch.object(
            storage, "load_locked", return_value=state
        ), patch.object(
            owned_cinematic_continuations, "policy", return_value=continuation
        ), patch.object(
            owned_cinematic_continuations, "recognizes", return_value=True
        ), patch.object(
            owned_cinematic_continuations, "eligible", return_value=True
        ) as eligible, patch.object(
            owned_cinematic_continuations, "begin", side_effect=begin
        ), patch(
            "wakfu_server.dungeon_exit._leave"
        ) as leave:
            result = links.travel(
                db,
                store,
                3,
                "lease",
                character,
                body,
                source_allowed=lambda *_: True,
                in_fight=lambda _: False,
            )

        self.assertFalse(result["internal"])
        self.assertEqual([event[0] for event in events], ["settle", "begin"])
        self.assertIs(events[0][1], db)
        self.assertIs(events[1][1], db)
        self.assertIs(events[1][2], store)
        eligible.assert_called_once_with(continuation, state)
        leave.assert_not_called()

    def test_cave_987_native_room_roster_binds_real_ordered_actors_and_positions(self):
        path = ROOT / "zinit-cult-cave-987.configuration.json"
        config = json.loads(path.read_text())
        selected = config["topology"]["owned_story_controller"]
        compiled_room = config["compiled_plan"]["rooms"][2]
        roster = [
            dict(
                ref_id=row["ref_id"],
                count=row["count"],
                min_level=row["native_min_level"],
                max_level=row["native_max_level"],
            )
            for row in compiled_room["monsters"]
        ]
        run = dict(
            status="active",
            current_room=3,
            instance_id=919,
            rooms=[dict(order=3, monsters=roster)],
        )
        scene = config["topology"]["rooms"][2]["encounter_scene"]
        cells = list(map(tuple, config["topology"]["rooms"][2]["cells"]))
        members = room_members(
            run,
            asset_map_id=987,
            anchor=config["topology"]["rooms"][2]["anchor"],
            geometry={"cells": cells},
            group_id=999,
            select_level=lambda native, frozen: frozen["min_level"],
            fixed_actor_placements=scene["fixed_actor_placements"],
        )
        self.assertEqual(
            [(row["ref"], row["level"]) for row in members],
            [(2881, 20), *[(2876, 20)] * 6],
        )
        expected_positions = [
            tuple(row["cell"]) for row in scene["fixed_actor_placements"]
        ]
        self.assertEqual(
            [(row["x"], row["y"], row["z"]) for row in members],
            expected_positions,
        )
        from wakfu_server.combat_fixed_actor_placement import world_placement

        self.assertEqual(
            [world_placement(member) for member in members],
            scene["fixed_actor_placements"],
        )

        db = Mock()
        db.execute.return_value.fetchone.return_value = dict(
            members=list(members), status="available", asset_map_id=987
        )
        native = json.loads((ROOT / "zinit-cult-cave-987.native.v1.json").read_text())
        effect = next(
            effect
            for step in selected["steps"]
            for effect in step["effects"]
            if effect.get("event") == 16039
        )
        with patch.object(mechanics, "sources", return_value=native):
            arguments = mechanics._arguments(
                db, dict(id=369, instance_id=919), effect, selected
            )
        self.assertEqual(arguments, [0, *(row["id"] for row in members)])

    def test_compiler_selects_foreign_branch_from_dual_native_source(self):
        encounters = json.loads((ROOT / "zinit-reef-980.encounters.json").read_text())
        exploration = json.loads((ROOT / "zinit-reef-980.exploration.json").read_text())
        native_rows = {
            (row["map_id"], row["id"]): row for row in generic_transports._CATALOG
        }
        entry_source = native_rows[(980, 25420)]
        entry = next(
            row for row in entry_source["destinations"] if row["destination_id"] == 2254
        )
        manifest = dict(
            schema="owned-story-instance-v1",
            id="zinit-reef-980-dual-exit-test",
            version=1,
            map_id=980,
            entry=dict(map_id=980, object_id=25420, destination_id=2254),
            native_entry_criterion=entry["criterion"],
            native_entry_payment=dict(reference=0, quantity=0),
            exit_sources=[dict(source_id=25401, destination_id=2255)],
            provenance="Focused dual-destination compiler regression",
        )
        compiled = compile_story(
            manifest,
            controller=self.selected,
            encounters=encounters,
            geometry=published_geometry(980),
            exploration=exploration,
            sources=native_rows,
            monster=reference,
        )
        exits = compiled["topology"]["native_story_exits"]
        self.assertEqual(
            [(row["source_id"], row["destination_id"]) for row in exits],
            [(25401, 2255)],
        )


if __name__ == "__main__":
    unittest.main()
