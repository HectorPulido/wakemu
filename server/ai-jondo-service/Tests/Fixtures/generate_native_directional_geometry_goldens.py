"""Generate advisory geometry goldens from the actual pure World implementation.

No catalog, database or runtime factory is loaded. Keep origin=aim and
reference=caster identical to the production native API; actor membership is
not reconstructed from enumerated forward cells.
"""
from pathlib import Path
import hashlib
import json
import sys

SERVER = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SERVER))
from wakfu_server.combat_area_geometry import (  # noqa: E402
    native_area_shape,
    native_area_rotation,
    native_area_contains,
    oriented_area_offsets,
)

SHAPES = [
    ("cone3", dict(area_class="anv", area_native="cone-3")),
    ("inverseCone3", dict(area_class="anC", area_native="cone_inv-3")),
    ("directedRectangle", dict(area_class="anz", area_native="Directed rectangle-3x4")),
    ("tee", dict(area_class="anI", area_native="t-2-3")),
    ("inverseTee", dict(area_class="anJ", area_native="t inv-barre:2-pied:3")),
    (
        "orderedE",
        dict(
            area_class="anE",
            area_native="original ordered fixture",
            native_area_points=[[2, 1], [0, 0], [-1, 2], [2, 1]],
        ),
    ),
    (
        "orderedJ",
        dict(
            area_class="anJ",
            area_native="original ordered fixture",
            native_area_points=[[0, -2], [3, 1], [0, 0], [0, -2]],
        ),
    ),
    ("rectangleG", dict(area_class="anG", area_native="rectangle or square-3x5")),
    ("squareG", dict(area_class="anG", area_native="rectangle or square-2x2")),
    (
        "ringF",
        dict(area_class="anF", area_native="rectangular or square ring-w:1-2 / h:0-1"),
    ),
    ("emptyCone", dict(area_class="anv", area_native="cone--1")),
]


def contexts():
    rows = []
    for direction in range(8):
        rows.append(
            dict(
                id=f"coincidentFacing{direction}",
                origin=[10, -4, 7],
                reference=[10, -4, -99],
                direction=direction,
            )
        )
    for name, vector in (
        ("east", (1, 0)),
        ("south", (0, 1)),
        ("west", (-1, 0)),
        ("north", (0, -1)),
    ):
        rows.append(
            dict(
                id=f"cardinal_{name}",
                origin=[0, 0, 3],
                reference=[-vector[0], -vector[1], 700],
                direction=7,
            )
        )
    # Integer coordinates expose the actual float32 conversion of atan2's
    # operands and result at all four45-degree boundaries, including collapse.
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        for delta in (-1, 0, 1, 2):
            dx, dy = sx * 16777216, sy * (16777216 + delta)
            rows.append(
                dict(
                    id=f"float32Tie_{sx}_{sy}_{delta}",
                    origin=[0, 0, 31],
                    reference=[-dx, -dy, -31],
                    direction=3,
                )
            )
    return rows


def generate():
    shapes, cases, counterexamples = [], [], []
    for shape_id, effect in SHAPES:
        raw, isotropic = native_area_shape(effect)
        shapes.append(
            dict(id=shape_id, effect=effect, rawOffsets=raw, isotropic=isotropic)
        )
        for context in contexts():
            origin, reference, direction = (
                context[k] for k in ("origin", "reference", "direction")
            )
            rotation = native_area_rotation(origin, reference, direction)
            forward = oriented_area_offsets(
                effect, origin=origin, reference=reference, direction=direction
            )
            forward_set = set(forward)
            # Include ordinary forward points, asymmetric misses, body-edge
            # contacts and a deterministic transpose/forward disagreement.
            probes = [(0, 0), (1, 0), (0, 1), (2, -1), (-2, 1), (5, 0)]
            probes.extend(forward[:2])
            disagreement = None
            if (
                not isotropic
                and direction % 2 == 0
                and context["id"].startswith("coincident")
            ):
                for y in range(-7, 8):
                    for x in range(-7, 8):
                        inside = native_area_contains(
                            effect,
                            origin=origin,
                            reference=reference,
                            point=(origin[0] + x, origin[1] + y, 900),
                            direction=direction,
                            radius=0,
                        )
                        if inside != ((x, y) in forward_set):
                            disagreement = (x, y)
                            break
                    if disagreement is not None:
                        break
                if disagreement is not None:
                    probes.append(disagreement)
            probes = list(dict.fromkeys(probes))
            memberships = []
            for x, y in probes:
                point = (origin[0] + x, origin[1] + y, 900)
                for radius in (0, 1, -7):
                    memberships.append(
                        dict(
                            point=point,
                            radius=radius,
                            contains=native_area_contains(
                                effect,
                                origin=origin,
                                reference=reference,
                                point=point,
                                direction=direction,
                                radius=radius,
                            ),
                        )
                    )
            # Native area membership ignores Z; include an explicit paired case.
            memberships.append(
                dict(
                    point=(origin[0] + 1, origin[1], -900),
                    radius=0,
                    contains=native_area_contains(
                        effect,
                        origin=origin,
                        reference=reference,
                        point=(origin[0] + 1, origin[1], -900),
                        direction=direction,
                    ),
                )
            )
            case_id = shape_id + ":" + context["id"]
            cases.append(
                dict(
                    id=case_id,
                    shapeId=shape_id,
                    **{k: context[k] for k in ("origin", "reference", "direction")},
                    rotation=rotation,
                    forwardOffsets=forward,
                    memberships=memberships,
                )
            )
            if disagreement is not None:
                point = (origin[0] + disagreement[0], origin[1] + disagreement[1], 900)
                counterexamples.append(
                    dict(
                        caseId=case_id,
                        point=point,
                        enumerated=disagreement in forward_set,
                        contains=native_area_contains(
                            effect,
                            origin=origin,
                            reference=reference,
                            point=point,
                            direction=direction,
                        ),
                    )
                )
    paths = [
        SERVER / "wakfu_server/combat/combat_area_geometry.py",
        SERVER / "wakfu_server/combat/combat_parameters.py",
    ]
    return dict(
        schema="world-native-directional-geometry-goldens-v1",
        oracle="actual production pure combat_area_geometry functions",
        coordinateConvention="origin=aim; reference=caster; XY-only; native transpose actor membership",
        sourceSha256={
            str(p.relative_to(SERVER.parent)): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in paths
        },
        shapes=shapes,
        cases=cases,
        forwardMembershipCounterexamples=counterexamples,
        counts=dict(
            shapes=len(shapes),
            cases=len(cases),
            memberships=sum(len(c["memberships"]) for c in cases),
            forwardMembershipCounterexamples=len(counterexamples),
        ),
    )


if __name__ == "__main__":
    destination = Path(__file__).with_name("NativeDirectionalGeometryGoldens.json")
    result = generate()
    destination.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(json.dumps(dict(path=str(destination), **result["counts"]), sort_keys=True))
