"""Neutral prototype geometry and reconstructed source-event guards, not scenes."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import struct
from types import SimpleNamespace as N
import unittest
from unittest.mock import Mock, patch

from wakfu_server.combat_encounter_glyph_bootstrap import (
    SOURCE,
    TRAP_SOURCE,
    glyph_cells,
    glyph_row,
    environment_section,
    point_glyph_section,
    prepare_declared_glyphs,
    validate_environment_prototype,
)
from wakfu_server.combat_scene_area_activation import (
    OwnedSceneEventReceipt,
    activate_declared_scene_traps,
)

DATA = json.loads(
    (
        Path(__file__).parent / "fixtures/native_declared_environment_prototypes.json"
    ).read_text()
)


class DeclaredEnvironmentExtensionTests(unittest.TestCase):
    def source(self, reference=841):
        return dict(
            uid=93,
            reference=reference,
            cell=(10, 20, 3),
            level=0,
            policy="wakemu.qualification.original-areas-v1",
            authority="explicit component fixture",
            source_url="native prototype plus explicitly reconstructed test controller",
            source=TRAP_SOURCE if reference == 841 else SOURCE,
            activation=dict(kind="objective", reference=9001, event_id=10009),
        )

    def trait_patch(self):
        return patch(
            "wakfu_server.combat_trap_area.trap_characteristics",
            return_value=DATA["trapCharacteristics"],
        )

    def fixture(self):
        source = self.source()
        with self.trait_patch():
            row = glyph_row(source, DATA["areas"]["841"])
        actor = N(id=7, hp=100, physical_radius=0, position=source["cell"])
        receipt = OwnedSceneEventReceipt(
            1, 7, 3, 4, 501, "objective", 9001, source["policy"], source["authority"]
        )
        fight = N(
            id=1,
            phase="active",
            turn_id=3,
            sequence=4,
            current=actor,
            actors={7: actor},
            walkable={source["cell"]},
            native_border_cells=set(),
            native_effect_areas={93: row},
            native_retired_area_managers={},
            native_environment_glyph_constructors=[source],
            native_scene_event_receipts={501: receipt},
            _in_play=lambda current: current is actor,
        )
        callbacks = N(
            _definition=Mock(return_value=DATA["areas"]["841"]),
            _deliver_event=Mock(return_value=("native-consumer-output",)),
        )
        return (
            fight,
            row,
            source,
            receipt,
            N(native_retention=N(fight=fight), native_area_events=callbacks),
            callbacks,
        )

    def invoke(self, dispatcher, receipt):
        with self.trait_patch(), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=DATA["areas"],
        ):
            return activate_declared_scene_traps(dispatcher, 7, receipt)

    def test_original_circle_and_crosses_keep_complete_unclipped_shape(self):
        source = self.source(842)
        circle = set(glyph_cells(source, DATA["areas"]["842"]))
        self.assertEqual(len(circle), 25)
        self.assertTrue({(7, 20), (13, 20), (10, 17), (10, 23)} <= circle)
        self.assertNotIn((13, 23), circle)
        expected = {(10, 20), (9, 20), (11, 20), (10, 19), (10, 21)}
        for reference in (847, 849, 850):
            with self.subTest(reference=reference):
                self.assertEqual(
                    set(
                        glyph_cells(
                            self.source(reference), DATA["areas"][str(reference)]
                        )
                    ),
                    expected,
                )
        fight = N(actors={}, walkable={source["cell"]}, native_effect_areas={})
        arena = dict(
            native_initial_glyphs=[dict(reference=842, cell=list(source["cell"]))],
            native_initial_glyph_policy=source["policy"],
            native_initial_glyph_authority=source["authority"],
        )
        constructors = prepare_declared_glyphs(fight, arena, 100, DATA["areas"])
        self.assertEqual(
            set(glyph_row(constructors[0], DATA["areas"]["842"])["native_cells_xy"]),
            circle,
        )

    def test_glyph_codec_stays_exact_and_trap_has_only_native_common_header(self):
        source = self.source(847)
        packed = environment_section(source, cell=source["cell"], visual_owner=-1)
        expected = struct.pack(
            ">qqiihqhib", 847, 93, 10, 20, 3, -1, 0, -1, -1
        ) + struct.pack(">Biihb", 0, 0, 0, 0, -1)
        self.assertEqual(packed, expected)
        self.assertEqual(
            packed, point_glyph_section(source, cell=source["cell"], visual_owner=-1)
        )
        trap = self.source()
        self.assertEqual(
            environment_section(trap, cell=trap["cell"], visual_owner=-1),
            struct.pack(">qqiihqhib", 841, 93, 10, 20, 3, -1, 0, -1, -1),
        )

    def test_invalid_orientation_parameters_level_and_prototype_are_rejected(self):
        for change in (
            dict(native_shape_class="anG"),
            dict(shape_parameters=[-1]),
            dict(shape_parameters=[True]),
            dict(shape_parameters=[3.0]),
            dict(native_shape_description="circle-4"),
            dict(native_container_type=4),
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_environment_prototype(
                    dict(DATA["areas"]["842"], **change), level=0
                )
        with self.assertRaises(ValueError):
            validate_environment_prototype(DATA["areas"]["842"], level=True)

    def test_neutral_trap_has_real_fbc_characteristics_without_fake_parent(self):
        with self.trait_patch():
            row = glyph_row(self.source(), DATA["areas"]["841"])
        self.assertEqual(row["native_area_contract"], "fbc")
        self.assertNotIn("effect_uid", row)
        self.assertIsNone(row["owner_id"])
        self.assertEqual(row["remaining_activations"], 1)
        self.assertEqual(
            row["native_trap_characteristics"],
            {
                int(k): v["current"]
                for k, v in DATA["trapCharacteristics"]["characteristics"].items()
            },
        )

    def test_exact_committed_scene_receipt_activates_once_and_preserves_roots(self):
        fight, row, source, receipt, dispatcher, callbacks = self.fixture()
        self.assertEqual(self.invoke(dispatcher, receipt), ("native-consumer-output",))
        self.assertEqual(self.invoke(dispatcher, receipt), ())
        callbacks._deliver_event.assert_called_once_with(
            row, DATA["areas"]["841"], fight.current, 10009
        )
        self.assertEqual(DATA["areas"]["841"]["effect_ids"], [147092])

    def test_forged_stale_foreign_and_cross_policy_receipts_cannot_activate(self):
        for change in (
            dict(sequence=3),
            dict(turn_id=2),
            dict(fight_id=2),
            dict(actor_id=True),
            dict(source_uid=999),
        ):
            fight, row, source, receipt, dispatcher, callbacks = self.fixture()
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.invoke(dispatcher, replace(receipt, **change))
            callbacks._deliver_event.assert_not_called()
        fight, row, source, receipt, dispatcher, callbacks = self.fixture()
        forged = replace(receipt)
        with self.assertRaises(ValueError):
            self.invoke(dispatcher, forged)
        for change in (
            dict(policy="wakemu.foreign"),
            dict(authority="foreign"),
            dict(reference=9002),
        ):
            fight, row, source, receipt, dispatcher, callbacks = self.fixture()
            other = replace(receipt, **change)
            fight.native_scene_event_receipts[501] = other
            self.assertEqual(self.invoke(dispatcher, other), ())
            callbacks._deliver_event.assert_not_called()

    def test_outside_removed_or_missing_rule_never_becomes_a_guessed_turn_trigger(self):
        for change in ("outside", "removed", "missingrule", "suppressed"):
            fight, row, source, receipt, dispatcher, callbacks = self.fixture()
            if change == "outside":
                fight.current.position = (9, 20, 3)
            elif change == "removed":
                fight.native_effect_areas.clear()
            elif change == "missingrule":
                source.pop("activation")
            else:
                row["remaining_activations"] = 0
            self.assertEqual(self.invoke(dispatcher, receipt), ())
            callbacks._deliver_event.assert_not_called()

    def test_tampered_geometry_reference_and_membership_fail_authority(self):
        for change in (
            dict(native_cells_xy=((99, 99),)),
            dict(native_geometry_reference=(1, 0, 0)),
            dict(native_geometry_reference_source="invented"),
        ):
            fight, row, source, receipt, dispatcher, callbacks = self.fixture()
            row.update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.invoke(dispatcher, receipt)

    def test_finite_neutral_trap_retirement_uses_registered_qs_without_fake_uid(self):
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
        from wakfu_server.combat_trap_area import retire_exhausted_trap

        fight, row, source, receipt, dispatcher, callbacks = self.fixture()
        actual = object.__new__(NativeAreaEventRuntime)
        actual.fight = fight
        actual.dispatcher = dispatcher
        row["remaining_activations"] = 0

        def remove(current, identity, **kwargs):
            self.assertIs(current, fight)
            self.assertEqual(identity, 93)
            current.native_effect_areas.pop(identity)

        with self.trait_patch(), patch(
            "wakfu_server.combat_effect_area.native_effect_areas",
            return_value=DATA["areas"],
        ), patch(
            "wakfu_server.combat_effect_area.remove_owned_hour_area", side_effect=remove
        ) as qs:
            self.assertTrue(retire_exhausted_trap(fight, row, callbacks=actual))
            qs.assert_called_once()
        self.assertNotIn(93, fight.native_effect_areas)
        self.assertNotIn("effect_uid", row)
        fight, row, source, receipt, dispatcher, callbacks = self.fixture()
        actual = object.__new__(NativeAreaEventRuntime)
        actual.fight = fight
        actual.dispatcher = dispatcher
        row.pop("native_environment_source")
        with self.assertRaises(ValueError):
            actual.remove_parent(row)
