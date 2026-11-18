"""Focused Kelba port timeline and convoy render-only actor contracts."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server import owned_story_admission, owned_story_controller
from wakfu_server import owned_story_mechanics, owned_story_npcs
from wakfu_server import owned_story_terminal_returns


PROFILE_ROOT = Path(__file__).parents[1] / "wakfu_server/maps/owned_story_profiles"


def load(name):
    return json.loads((PROFILE_ROOT / name).read_text())


class _Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _ReceiptDB:
    def __init__(self, times):
        self.times = times
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        step = params[1].rsplit(":", 1)[-1]
        return _Cursor({"payload": {"created_ms": self.times[step]}})


class _Store:
    def __init__(self, db, character, now_ms=0):
        self.db = db
        self.current = character
        self.now_ms = now_ms

    def now(self):
        return datetime.fromtimestamp(self.now_ms / 1000, timezone.utc)

    @contextmanager
    def connection(self):
        yield self.db


class KelbaOwnedStoryProfileTests(unittest.TestCase):
    def test_port946_zero_room_native_action_and_deadline_graph(self):
        manifest = load("kelba-port-946.instance.json")
        selected = load("kelba-port-946.json")
        compiled = load("kelba-port-946.configuration.json")
        npcs = load("../owned_story_npc_profiles/kelba-port-946.json")

        self.assertEqual(compiled["route"]["key"], "quest-map-946-25104-2195")
        self.assertEqual(compiled["compiled_plan"]["rooms"], [])
        self.assertEqual(compiled["topology"]["policy"], "owned-story-narrative-v1")
        self.assertEqual(
            manifest["entry"], dict(map_id=943, object_id=25104, destination_id=2195)
        )
        arrival_start = owned_story_controller.plan(
            selected, set(), kind="world_ready", reference=946
        )
        self.assertEqual(arrival_start["id"], "port-arrival")
        self.assertEqual(arrival_start["effects"][0]["event"], 15772)

        native = owned_story_npcs.npc_dialogue.catalog()
        speaker = next(row for row in native["speakers"] if row["ref"] == 1147)
        action = next(row for row in speaker["actions"] if row["id"] == 61)
        self.assertEqual(action["type"], 4)
        self.assertEqual(action["criteria"], "")
        self.assertNotIn("dialogue_root", npcs["npcs"][0])
        self.assertEqual(npcs["npcs"][0]["controller_reference"], 1147)

        character = dict(
            id=81,
            account_id=19,
            map_id=946,
            instance_id=(1 << 57) + 13,
            x=9,
            y=2,
            z=0,
        )
        npc = dict(
            npcs["npcs"][0],
            actor_id=owned_story_npcs.actor_id(character["instance_id"], 1),
            map_id=946,
            instance_id=character["instance_id"],
            enabled=True,
        )
        state = dict(running=[2536], completed=[], objectives=[], variables={})
        db = _ReceiptDB({})
        store = _Store(db, character)
        apply_packet = (13411, b"native-15657")

        with (
            patch.object(
                owned_story_npcs, "_locked", return_value=(character, npcs, npc, state)
            ),
            patch.object(owned_story_npcs, "_criterion", return_value=True),
            patch.object(
                owned_story_controller,
                "_scope",
                return_value=(
                    selected,
                    {
                        "port-arrival",
                        "port-arrival-done",
                    },
                ),
            ),
            patch.object(owned_story_controller, "pending_scene", return_value=None),
            patch.object(
                owned_story_controller,
                "_settle",
                return_value={"packets": [apply_packet]},
            ) as settle,
        ):
            session, packets = owned_story_npcs.begin(
                store,
                character["account_id"],
                "generation",
                character,
                npc["actor_id"],
                61,
            )
        self.assertIsNone(session)
        self.assertEqual(packets, [apply_packet])
        self.assertEqual(settle.call_args.kwargs["kind"], "npc_spoken")
        self.assertEqual(settle.call_args.kwargs["reference"], 1147)
        self.assertEqual(settle.call_args.kwargs["evidence"]["action_id"], 61)
        with (
            patch.object(
                owned_story_npcs, "_locked", return_value=(character, npcs, npc, state)
            ),
            patch.object(owned_story_npcs, "_criterion", return_value=True),
            patch.object(
                owned_story_controller,
                "_scope",
                return_value=(
                    selected,
                    {
                        "port-arrival",
                        "port-arrival-done",
                    },
                ),
            ),
            patch.object(
                owned_story_controller, "pending_scene", return_value={"event": 15657}
            ),
            patch.object(owned_story_controller, "_settle") as blocked_settle,
        ):
            with self.assertRaisesRegex(ValueError, "waiting for its native cinematic"):
                owned_story_npcs.begin(
                    store,
                    character["account_id"],
                    "generation",
                    character,
                    npc["actor_id"],
                    61,
                )
        blocked_settle.assert_not_called()

        # Only authentic scene deadlines make the callbacks available. The
        # quest objective is attached to the second callback, after departure.
        receipts = _ReceiptDB({"port-arrival": 1000, "package-briefing": 20000})
        store = _Store(receipts, character, now_ms=19499)
        arrival = owned_story_controller.pending_scene(
            receipts, store, character, selected, {"port-arrival"}
        )
        departure = owned_story_controller.pending_scene(
            receipts,
            store,
            character,
            selected,
            {"port-arrival", "port-arrival-done", "package-briefing"},
        )
        self.assertEqual(
            (arrival["event"], arrival["callback"], arrival["due_ms"]),
            (15772, 15772, 19500),
        )
        self.assertEqual(
            (departure["event"], departure["callback"], departure["due_ms"]),
            (15657, 15658, 61000),
        )
        with (
            patch.object(
                owned_story_controller,
                "_scope",
                return_value=(selected, {"port-arrival"}),
            ),
            patch.object(
                owned_story_controller.storage, "record_event", return_value=True
            ) as record,
        ):
            early = owned_story_controller.complete_due_scene(
                receipts, store, character
            )
            self.assertFalse(early["applied"])
            store.now_ms = 19500
            arrived = owned_story_controller.complete_due_scene(
                receipts, store, character
            )
        self.assertTrue(arrived["applied"])
        self.assertEqual(arrived["step"], "port-arrival-done")
        self.assertEqual(record.call_count, 1)
        self.assertIsNone(
            owned_story_controller.plan(
                selected,
                {"port-arrival", "port-arrival-done"},
                kind="scenario_complete",
                reference=15772,
            )
        )

        # The departure callback is the only point where the native end scene,
        # reviewed position and objective effects are applied together.
        store.now_ms = 60999
        effects_seen = []

        def apply(_db, _store, _character, effects):
            effects_seen.extend(effects)
            return [(13411, b"native-end"), (13405, b"objective")]

        with (
            patch.object(
                owned_story_controller,
                "_scope",
                return_value=(
                    selected,
                    {
                        "port-arrival",
                        "port-arrival-done",
                        "package-briefing",
                    },
                ),
            ),
            patch.object(
                owned_story_controller.storage, "record_event", return_value=True
            ) as record_departure,
            patch.object(owned_story_mechanics, "executor", return_value=apply),
        ):
            early_departure = owned_story_controller.complete_due_scene(
                receipts, store, character
            )
            self.assertFalse(early_departure["applied"])
            store.now_ms = 61000
            departed = owned_story_controller.complete_due_scene(
                receipts, store, character
            )
        self.assertTrue(departed["applied"])
        self.assertEqual(departed["step"], "departure-finished")
        self.assertEqual(record_departure.call_count, 1)
        self.assertEqual(
            [effect["kind"] for effect in effects_seen],
            ["scenario_event", "scene_position", "quest_objective"],
        )
        briefing = next(
            row for row in selected["steps"] if row["id"] == "package-briefing"
        )
        self.assertFalse(
            any(effect["kind"] == "quest_objective" for effect in briefing["effects"])
        )
        final_step = owned_story_controller.plan(
            selected,
            {
                "port-arrival",
                "port-arrival-done",
                "package-briefing",
                "departure-finished",
            },
            kind="scenario_complete",
            reference=15658,
        )
        self.assertIsNone(final_step)
        departure_step = next(
            row for row in selected["steps"] if row["id"] == "departure-finished"
        )
        self.assertEqual(
            next(
                effect
                for effect in departure_step["effects"]
                if effect["kind"] == "quest_objective"
            ),
            dict(kind="quest_objective", quest_id=2536, objective_id=5035),
        )
        declaration = owned_story_terminal_returns.policy(selected)
        returned = owned_story_terminal_returns._step_destination(selected, declaration)
        self.assertEqual(returned, dict(map_id=943, x=-6, y=0, z=-80))
        return_db = Mock()
        return_db.execute.return_value.fetchone.return_value = dict(
            entry_map_id=943, entry_object_id=25104
        )
        with patch.object(
            owned_story_controller, "recognizes_instance", return_value=True
        ), patch.object(
            owned_story_controller,
            "_scope",
            return_value=(selected, {"departure-finished"}),
        ):
            self.assertEqual(
                owned_story_terminal_returns.pending(return_db, store, character),
                dict(map_id=943, x=-6, y=0, z=-80),
            )
        self.assertIn("entry_map_id", return_db.execute.call_args.args[0])

    def test_retained_convoy_admission_supplies_unused_cinematic_argument(self):
        selected = load("kelba-convoy-947.json")
        self.assertEqual(
            owned_story_mechanics.scenario_packet(selected, 15660),
            (13411, struct.pack(">BiiBq", 0, 15660, 1962, 1, 0)),
        )
        with self.assertRaisesRegex(ValueError, "arguments differ"):
            owned_story_mechanics.scenario_packet(selected, 15660, (0, 0))
        with self.assertRaisesRegex(ValueError, "arguments differ"):
            owned_story_mechanics.scenario_packet(selected, 15725)
        with self.assertRaisesRegex(ValueError, "arguments differ"):
            owned_story_mechanics.scenario_packet(dict(selected, id="other"), 15660)

    def test_convoy_room_one_keeps_exact_carrier_native_bootstrap_and_level_zero_glyph(
        self,
    ):
        from native_recorded_instance_fixture import original_bootstrap_publication
        from jondo_native_support_probe import build_fixture
        from wakfu_server import monsters
        from wakfu_server.combat_encounter_roles import role_assignment
        from wakfu_server.combat_encounter_glyph_bootstrap import (
            glyph_row,
            prepare_declared_glyphs,
        )
        from wakfu_server.combat_environment_glyphs import verify_environment_glyph
        from wakfu_server.combat_effect_area import native_effect_areas

        config = load("kelba-convoy-947.configuration.json")
        encounter = load("kelba-convoy-947.encounters.json")
        room = config["topology"]["rooms"][0]
        scene = room["encounter_scene"]
        self.assertEqual(
            [
                (row["ref_id"], row["count"])
                for row in config["compiled_plan"]["rooms"][0]["monsters"]
            ],
            [(3565, 2), (3566, 2), (3567, 2), (3589, 1)],
        )
        self.assertEqual(
            encounter["rooms"][0]["encounter_scene"]["native_initial_glyphs"],
            [
                dict(reference=902, level=0, cell=[-6, -2, 0]),
            ],
        )

        # Exercise the real NPC constructor/initial-state path for the exact
        # carrier; no synthetic state receipt or fight result is supplied.
        with original_bootstrap_publication():
            case = build_fixture(3589, 70)
        carrier = case.fight.actors[-7]
        receipt = case.fight.native_npc_initialization_receipts[-7]
        self.assertEqual(receipt["raw_triples"][:3], [3478, 1, 0])
        self.assertIn(3478, {state.reference for state in carrier.state_ledger.entries})
        native_carrier = monsters.reference(3589)
        self.assertEqual(
            native_carrier["native_abilities"],
            [
                {"level_parameter": -1, "spell_id": 4849},
                {"level_parameter": -1, "spell_id": 4850},
            ],
        )

        # Run the real native faY constructor validation against the pinned
        # first-room actor cells and map947 floor. The profile declares the
        # glyph seed explicitly; there is no guessed/relocated area point.
        placements = scene["fixed_actor_placements"]
        references = [row["reference"] for row in placements]
        roles = role_assignment(947, references)
        player_position = tuple(room["anchor"])
        actors = {
            1: SimpleNamespace(
                position=player_position,
                physical_radius=0,
                hp=100,
                team=roles.player_team,
            )
        }
        for index, placement in enumerate(placements):
            actors[-index - 1] = SimpleNamespace(
                position=tuple(placement["cell"]),
                physical_radius=0,
                hp=100,
                team=roles.npc_team,
            )
        fight = SimpleNamespace(
            actors=actors,
            walkable={tuple(cell) for cell in room["cells"]},
            native_effect_areas={},
            native_border_cells=(),
            native_encounter_roles=roles.record(),
        )
        arena = dict(
            map_id=947,
            native_initial_glyphs=scene["native_initial_glyphs"],
            native_initial_glyph_policy=scene["native_initial_glyph_policy"],
            native_initial_glyph_authority=scene["native_initial_glyph_authority"],
            native_initial_glyph_source_url=scene["native_initial_glyph_source_url"],
            native_encounter_roles=roles.record(),
            native_encounter_scene_layout=dict(
                party_placement_cells=[list(player_position)],
                boss_footprint=[row["cell"] for row in placements],
            ),
        )
        constructors = prepare_declared_glyphs(
            fight, arena, 100000, native_effect_areas()
        )
        self.assertEqual(
            [(row["reference"], row["level"], row["cell"]) for row in constructors],
            [(902, 0, (-6, -2, 0))],
        )
        fight.native_environment_glyph_constructors = constructors
        row = glyph_row(constructors[0], native_effect_areas()["902"])
        verify_environment_glyph(fight, row)

        handoff = next(
            step
            for step in load("kelba-convoy-947.json")["steps"]
            if step["id"] == "convoy-birds-handoff"
        )
        with patch.object(
            owned_story_mechanics, "move", return_value=(13417, b"native-position")
        ) as move:
            packets = owned_story_mechanics.executor(load("kelba-convoy-947.json"))(
                SimpleNamespace(),
                SimpleNamespace(),
                dict(id=91, account_id=22, map_id=947, instance_id=(1 << 57) + 31),
                handoff["effects"],
            )
        move.assert_called_once()
        self.assertEqual(move.call_args.args[2], [282, 0, 0])
        self.assertIn((13417, b"native-position"), packets)

    def test_convoy_final_models_are_actual_render_only_actors_and_native_arguments(
        self,
    ):
        selected = load("kelba-convoy-947.json")
        source = load("kelba-convoy-947.native.v1.json")
        character = dict(id=91, account_id=22, map_id=947, instance_id=(1 << 57) + 31)
        db, store = Mock(), object()

        def rows(completed):
            with patch.object(
                owned_story_controller, "_scope", return_value=(selected, completed)
            ):
                return owned_story_admission.scene_actor_rows(db, store, character)

        self.assertEqual(rows(set()), [])
        declared = rows({"convoy-final-handoff"})
        self.assertEqual(
            [
                (row["role"], row["reference_id"], row["native_action_ids"])
                for row in declared
            ],
            [("black-crow", 3586, []), ("box", 3712, [])],
        )
        self.assertTrue(all(row["owner_id"] == character["id"] for row in declared))
        self.assertTrue(
            all(row["instance_id"] == character["instance_id"] for row in declared)
        )
        with patch.object(
            owned_story_controller,
            "_scope",
            return_value=(selected, {"convoy-final-handoff"}),
        ):
            packets = owned_story_admission.scene_actor_packets(db, store, character)
            effect = next(
                effect
                for step in selected["steps"]
                for effect in step["effects"]
                if effect.get("kind") == "scenario_event"
                and effect.get("event") == 15665
            )
            arguments = owned_story_mechanics._arguments(
                db, character, effect, selected, store=store
            )
        self.assertEqual([opcode for opcode, _body in packets], [12608, 12608])
        self.assertEqual(arguments[0], declared[0]["actor_id"])
        self.assertEqual(arguments[-1], declared[1]["actor_id"])
        self.assertEqual(source["scene_positions"]["15665"], [578, 2, 0])
        self.assertEqual(
            source["reviewed_stage_positions"]["15675"]["position"], [282, 0, 0]
        )


if __name__ == "__main__":
    unittest.main()
