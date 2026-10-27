"""Original nineteen PT exclusion descriptors share one PV/QI preflight."""
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import combat_native_pt as pt
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_state import Actor
from wakfu_server.combat_qi_registry import NativeQIRegistry
from wakfu_server.combat_effect_area_targets import (
    NativeAreaTarget,
    area_target_context,
)


class NativePtExclusionTests(unittest.TestCase):
    def test_original_bulk19_pv_terrain_rotation_admission_and_null_branch(self):
        directory = Path(".runtime/rift-phase2-dataset")
        raw = (directory / "original-pt19-native/original.json").read_bytes()
        self.assertEqual(
            hashlib.sha256(raw).hexdigest(),
            "cdcc5dca6b8a3e61bc46e96036ea1937e2efa6a27bbab49e629a5e027062258d",
        )
        roots = json.loads(raw)["roots"]
        self.assertEqual(len(roots), 19)
        preflight = json.loads(
            (directory / "casting-full-native-pt-preflight.json").read_bytes()
        )
        manifest_dir = (
            Path(__file__).resolve().parents[1] / "data/installation/catalogs"
        )
        manifest = json.loads(
            (manifest_dir / "manifest-rift-pt-metadata-v1.json").read_bytes()
        )
        release = next(
            row
            for row in manifest["releases"]
            if row["revision"] == manifest["active_revision"]
        )
        digest = next(
            row["sha256"]
            for row in release["documents"]
            if row["path"] == "native-class-casting-roots.json"
        )
        packed = gzip.decompress(
            (manifest_dir / "parts" / (digest + ".json.gz")).read_bytes()
        )
        self.assertEqual(hashlib.sha256(packed).hexdigest(), digest)
        published = json.loads(packed)["roots"]
        for reference, row in roots.items():
            self.assertEqual(published[reference], row)
        source = Actor(7, 0, (0, 10, 0), 100, 6, 3, 1, 1, 3, True)
        source.physical_radius = 0
        source.direction = 1
        fight = SimpleNamespace(actors={7: source})
        arena = dict(x=-20, y=-20, width=61, height=61, cell_masks=[0] * (61 * 61))

        def registry(*, blocked=None, obstacle=None):
            value = dict(arena, cell_masks=list(arena["cell_masks"]))
            if blocked is not None:
                x, y = blocked
                value["cell_masks"][
                    (y - value["y"]) * value["width"] + x - value["x"]
                ] = -1
            slots = [None] * 127
            if obstacle is not None:
                slots[0] = dict(
                    identity=["actor", -71],
                    position=list(obstacle),
                    radius=0,
                    indexed=True,
                    movement_blocking=True,
                )
            result = NativeQIRegistry(value, slots)
            result.capture_fresh_cell_topology(() if obstacle is None else (0,))
            return result

        def context(actor):
            return dict(
                is_eGj=True,
                is_Qq=False,
                is_eHH=True,
                bEe=True,
                is_amO=True,
                UNTARGETTABLE_BY_OTHER=False,
                buX=False,
            )

        application = dict(
            area_class="unknown-application-shape", area_native="separate from fKX"
        )
        original_load = pt.protocol_catalog.load

        def load(path):
            return (
                preflight
                if Path(path).name == "native-pt-preflight.json"
                else original_load(path)
            )

        pt.null_exclusion_references.cache_clear()
        self.addCleanup(pt.null_exclusion_references.cache_clear)
        with patch.object(pt.protocol_catalog, "load", side_effect=load), patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            return_value={"roots": roots},
        ), patch("wakfu_server.combat_qi_fight.current_registry") as current:
            for reference, row in roots.items():
                invocation = EffectInvocation(int(reference), 1, 7, None, (10, 10, 0))
                shape = row["native_casting_collision_area"]
                # Original raw getters provide this independent east-facing
                # first-cell oracle; terrain/occupancy checks inspect fKX,
                # never the unrelated effect application area.
                offset = (
                    shape.get("native_area_points")
                    or ([[0, 0]] if shape["area_class"] == "anD" else [[1, 0]])
                )[0]
                cell = (10 + offset[0], 10 + offset[1])

                def admit(population=(source,), contexts=None):
                    return pt.native_pt_preflight(
                        application,
                        invocation,
                        fight=fight,
                        candidates=lambda: population,
                        native_context=lambda: contexts or {7: context(source)},
                    )

                current.return_value = registry()
                self.assertTrue(admit(), reference)
                occupant = Actor(-7, 1, (*cell, 0), 20, 4, 2, 1, 1)
                occupant.hp = 0
                occupant.physical_radius = 0
                self.assertFalse(
                    admit(
                        (source, occupant), {7: context(source), -7: context(occupant)}
                    ),
                    reference,
                )
                current.return_value = registry()
                area = NativeAreaTarget(99, (*cell, 0), 1, 7, native_targeting_bcR=True)
                contexts = {7: context(source), 99: area_target_context(area)}
                self.assertTrue(admit((source, area), contexts), reference)
                blocking = replace(area, native_movement_blocking=True)
                self.assertFalse(admit((source, blocking), contexts), reference)
                current.return_value = registry(blocked=cell)
                self.assertFalse(admit(), reference)
                current.return_value = registry(obstacle=cell)
                self.assertFalse(admit(), reference)
                current.return_value = registry()
                # PT allocation happens before Qe execution. A rejected area
                # cannot reach even an installed executor or reserve a UID.
                execute = Mock(return_value=False)
                dispatcher = SimpleNamespace(
                    effects={reference: application},
                    pt_preflight=lambda effect, inv: admit(),
                    execute=execute,
                )
                result = EffectDispatcher.execute_pt(dispatcher, invocation)
                self.assertTrue(result.present)
                execute.assert_called_once()
                execute.reset_mock()
                current.return_value = registry(blocked=cell)
                result = EffectDispatcher.execute_pt(dispatcher, invocation)
                self.assertFalse(result.present)
                execute.assert_not_called()

            reference = next(
                key
                for key, row in roots.items()
                if row["native_casting_collision_area"]["area_class"] == "anE"
            )
            invocation = EffectInvocation(int(reference), 1, 7, None, (10, 10, 0))
            source.position = (10, 10, 0)

            def call():
                return pt.native_pt_preflight(
                    application,
                    invocation,
                    fight=fight,
                    candidates=lambda: (),
                    native_context=lambda: {7: context(source)},
                )

            current.return_value = registry()
            raw_x, raw_y = roots[reference]["native_casting_collision_area"][
                "native_area_points"
            ][0]
            for direction, (dx, dy) in enumerate(
                ((1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1))
            ):
                source.direction = direction
                current.return_value = registry()
                self.assertTrue(call())
                rotated = (10 + dx * raw_x - dy * raw_y, 10 + dy * raw_x + dx * raw_y)
                current.return_value = registry(blocked=rotated)
                self.assertFalse(call())
            current.return_value = registry()
            source.direction = None
            with self.assertRaisesRegex(ValueError, "authoritative actor facing"):
                call()
            source.direction = 1
            invocation = replace(invocation, cell=(1.5, 10, 0))
            with self.assertRaisesRegex(ValueError, "target cell"):
                call()
            invocation = replace(invocation, cell=(10, 10, 0))
            unknown = replace(invocation, reference=999999999)
            with self.assertRaisesRegex(ValueError, "Unknown native PT exclusion"):
                pt.native_pt_preflight(application, unknown)
            with patch(
                "wakfu_server.combat_casting_context.casting_root_catalog",
                return_value={"roots": {}},
            ):
                with self.assertRaisesRegex(
                    ValueError, "Missing original native PT exclusion"
                ):
                    call()
            # The shared selector path retains relation filtering even when
            # fcE does not request area membership. Original19 all use mask1;
            # this perturbed descriptor is a generic negative control only.
            enemy = Actor(-71, 1, (40, 40, 0), 20, 4, 2, 1, 1)
            enemy.physical_radius = 0
            relation_row = dict(
                roots[reference], native_target_selector={"class": "fcE", "mask": 8}
            )
            current.return_value = registry()
            with patch(
                "wakfu_server.combat_casting_context.casting_root_catalog",
                return_value={"roots": {reference: relation_row}},
            ):
                for population, expected in (
                    ((source,), True),
                    ((source, enemy), False),
                ):
                    self.assertEqual(
                        pt.native_pt_preflight(
                            application,
                            invocation,
                            fight=fight,
                            candidates=lambda: population,
                            native_context=lambda: {
                                7: context(source),
                                -71: context(enemy),
                            },
                        ),
                        expected,
                    )
            # Null fKX is the exact old immediate-return path, even without
            # an actor, area, terrain or any runtime context provider.
            current.reset_mock()
            null_reference = preflight["null_exclusion_references"][0]
            self.assertTrue(
                pt.native_pt_preflight(
                    {},
                    replace(invocation, reference=null_reference),
                    candidates=Mock(side_effect=AssertionError("null read population")),
                )
            )
            current.assert_not_called()
