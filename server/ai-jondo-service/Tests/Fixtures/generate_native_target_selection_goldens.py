"""Generate public World selector witnesses without catalogs or runtime heaps.

Native actor capabilities are explicit fixture properties, never inferred from
ID sign, team or physical radius. Expected IDs come from the production public
selector, including NULL anchor and fcE body-radius semantics.
"""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import sys

SERVER = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SERVER))
from wakfu_server.combat_effect_targets import (  # noqa: E402
    native_selector_policy,
    select_native_effect_targets,
)


def native_properties():
    return dict(
        is_amO=True,
        is_eGj=True,
        is_Qq=False,
        is_eHH=False,
        bEe=True,
        baF=True,
        baG=False,
        baK=False,
        dTE=False,
        dpu_id=None,
        dpr_id=None,
        UNTARGETTABLE_BY_OTHER=False,
        buX=False,
        bcR=True,
        bcN=0,
    )


def actor_records():
    rows = [
        dict(
            id=55,
            team=0,
            position=[0, 0, 0],
            direction=2,
            physicalRadius=0,
            role="caster",
        )
    ]
    # Both clusters are3x3. A circle uses Manhattan area offsets, while a
    # radius1 actor contributes its native square physical footprint.
    identity = 100
    for anchor in (0, 5):
        for y in (-1, 0, 1):
            for x in (anchor - 1, anchor, anchor + 1):
                identity += 1
                rows.append(
                    dict(
                        id=identity,
                        team=(x + y) % 2,
                        position=[x, y, 80 if y == 1 else 0],
                        direction=7,
                        physicalRadius=(0, 1, -7)[(identity - 101) % 3],
                        role=f"grid_{anchor}_{x}_{y}",
                    )
                )
    for x, y, radius, team, name in (
        (-3, 0, 0, 1, "negative_axis_enemy"),
        (-2, 0, 1, 0, "negative_axis_ally_body"),
        (7, 0, 0, 1, "forward_enemy"),
        (8, 1, 1, 1, "forward_enemy_body"),
        (12, 12, 1, 1, "far_enemy"),
        (12, 11, 0, 0, "far_ally"),
    ):
        identity += 1
        rows.append(
            dict(
                id=identity,
                team=team,
                position=[x, y, -40],
                direction=5,
                physicalRadius=radius,
                role=name,
            )
        )
    for row in rows:
        row["hp"] = row["maxHp"] = 100
        row["nativeContext"] = native_properties()
    return rows


def generate():
    records = actor_records()
    actors = [
        SimpleNamespace(
            id=row["id"],
            team=row["team"],
            position=tuple(row["position"]),
            direction=row["direction"],
            physical_radius=row["physicalRadius"],
            hp=row["hp"],
            max_hp=row["maxHp"],
        )
        for row in records
    ]
    caster = actors[0]
    contexts = {row["id"]: row["nativeContext"] for row in records}
    shapes = [
        ("point", dict(area_class="anD", area_native="point")),
        ("circle1", dict(area_class="anu", area_native="circle-1")),
        ("cone3", dict(area_class="anv", area_native="cone-3")),
        ("rectangle", dict(area_class="anz", area_native="Directed rectangle-3x4")),
        ("emptyCone", dict(area_class="anv", area_native="cone-0")),
    ]
    selectors = [
        ("null", None),
        ("fcE_inArea", 1),
        ("fcE_enemyInArea", 9),
        ("fcE_alliedInArea", 5),
        ("fcE_selfBypassArea", 2),
        ("fcE_enemyBypassArea", 8),
        ("fcE_allyBypassArea", 128),
        ("fcE_allBypassArea", 0),
    ]
    cases = []
    for shape_id, shape in shapes:
        for selector_id, mask in selectors:
            for aim in ((5, 0, 0), (0, 0, -900)):
                effect = dict(
                    shape,
                    native_target_selector=(
                        None if mask is None else dict(**{"class": "fcE"}, mask=mask)
                    ),
                )
                policy = native_selector_policy(effect)
                selected = select_native_effect_targets(
                    effect,
                    caster,
                    aim,
                    actors,
                    native_context=contexts,
                )
                cases.append(
                    dict(
                        id=f"{shape_id}:{selector_id}:aim{aim[0]}",
                        shapeId=shape_id,
                        effect=effect,
                        casterId=caster.id,
                        aim=aim,
                        nativeAreaCenterOnCaster=mask is None,
                        nativeAreaUseTargetRadius=mask is not None,
                        nativeInArea=policy["in_area"],
                        relations=sorted(policy["relations"]),
                        selectedIds=[actor.id for actor in selected],
                    )
                )
    paths = [
        SERVER / "wakfu_server/combat" / name
        for name in (
            "combat_effect_targets.py",
            "combat_area_geometry.py",
            "combat_parameters.py",
        )
    ]
    return dict(
        schema="world-native-target-selection-goldens-v1",
        oracle="actual production PUBLIC select_native_effect_targets",
        sourceSha256={
            str(path.relative_to(SERVER.parent)): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in paths
        },
        actors=records,
        cases=cases,
        counts=dict(actors=len(records), cases=len(cases)),
    )


if __name__ == "__main__":
    result = generate()
    path = Path(__file__).with_name("NativeTargetSelectionGoldens.json")
    path.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(json.dumps(dict(path=str(path), **result["counts"]), sort_keys=True))
