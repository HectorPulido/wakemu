"""Native eYk/349 cell population, criterion, shuffle and ordered fanout."""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import dataclass
from functools import lru_cache
import json
import math

from .combat_group_cells import ordered_offsets
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_cell_group_metadata():
    data = protocol_catalog.load(DATA_ROOT / "native-class-cell-group-metadata.json")
    if data.get("schema") != "native-eYk-class-cell-group-v1":
        raise ValueError("Missing exact native eYk metadata schema")
    return data["effects"]


def native_cell_criterion_presence(effect, invocation):
    row = native_cell_group_metadata().get(str(invocation.reference))
    raw_parameters = effect.get("parameters")
    metadata_parameters = row.get("raw_parameters") if isinstance(row, dict) else None
    if (
        not isinstance(row, dict)
        or type(row.get("criterion_present")) is not bool
        or row.get("area_class") != effect.get("area_class")
        or not isinstance(raw_parameters, (list, tuple))
        or not isinstance(metadata_parameters, (list, tuple))
        or tuple(metadata_parameters) != tuple(raw_parameters)
    ):
        raise ValueError("Missing matching native eYk definition/criterion presence")
    return row["criterion_present"]


@dataclass(frozen=True)
class CellGroupMode:
    count: int
    filter_cells: bool
    point_toward_anchor: bool
    center_on_caster: bool
    shuffle: bool
    order: int


@dataclass(frozen=True)
class CellGroupSelection:
    cells: tuple
    eligible_count: int


def cell_group_mode(values):
    parameters = values["parameters"]
    if (
        not isinstance(parameters, (list, tuple))
        or not 1 <= len(parameters) <= 8
        or any(type(value) is not int for value in parameters)
    ):
        raise ValueError("Missing native eYk evaluated parameters")
    return CellGroupMode(
        parameters[0],
        len(parameters) > 2 and parameters[2] == 1,
        len(parameters) > 3 and parameters[3] == 1,
        len(parameters) > 4 and parameters[4] == 1,
        len(parameters) < 7 or parameters[6] == 1,
        parameters[7] if len(parameters) > 7 else 0,
    )


def selected_height(qi, surfaces, x, y):
    """QI.X reads the exact indexed Vy column; missing is Short.MIN_VALUE."""
    if not qi.aK(x, y):
        raise ValueError("Native QI.X cell is outside its actual rectangle")
    index = qi.masks[(y - qi.y) * qi.width + x - qi.x] & 63
    for (cx, cy, width, height), columns in surfaces.chunks:
        if cx <= x < cx + width and cy <= y < cy + height:
            column = columns.get((x, y), ())
            return column[index].z if index < len(column) else -32768
    return -32768


def native_cell_group_population(fight, effect, values, invocation):
    """Actual QI masks and native surface indices, never movement walkability."""
    from .combat_qi_fight import current_registry
    from .combat_qi_surface_catalog import (
        native_qi_surfaces,
        native_qi_surface_provenance,
    )

    mode = cell_group_mode(values)
    criterion_present = native_cell_criterion_presence(effect, invocation)
    qi = current_registry(fight).snapshot()
    provenance = getattr(fight, "native_qi_surface_provenance", None)
    if not isinstance(provenance, dict):
        raise ValueError("Cell group requires actual selected-surface provenance")
    map_id = provenance.get("map_id")
    if provenance != native_qi_surface_provenance(map_id):
        raise ValueError("Cell group selected-surface provenance mismatch")
    surfaces = native_qi_surfaces(map_id)
    caster = fight.actors.get(invocation.caster_id)
    if caster is None:
        raise ValueError("Missing native eYk caster position and direction")
    center = caster.position if mode.center_on_caster else invocation.cell
    # eYk treats and.EMPTY as QI.bdY, whose initial cache traverses mask
    # indices in row order and keeps columns with bit128 clear.
    whole_map = effect.get("area_class") == "anA"
    if whole_map:
        positions = (
            (qi.x + index % qi.width, qi.y + index // qi.width)
            for index, mask in enumerate(qi.masks)
            if not mask & 128
        )
    else:
        direction = caster.direction
        if mode.point_toward_anchor:
            dx = (invocation.cell[0] - caster.position[0] + 2**31) % 2**32 - 2**31
            dy = (invocation.cell[1] - caster.position[1] + 2**31) % 2**32 - 2**31
            if not dx and not dy:
                # Actual aBn.y is null, not NONE. amX's zero vector then
                # dereferences it; do not replace that native case by a facing.
                raise ValueError("Native eYk coincident anchor produces null facing")
            absolute = lambda value: value if value == -(2**31) else abs(value)
            direction = (
                (1 if dx > 0 else 5)
                if absolute(dx) > absolute(dy)
                else (3 if dy > 0 else 7)
            )
        offsets = ordered_offsets(
            effect, origin=center, reference=caster.position, direction=direction
        )
        positions = ((center[0] + dx, center[1] + dy) for dx, dy in offsets)
    result = []
    for x, y in positions:
        if not whole_map and (not qi.aK(x, y) or not qi.R(x, y)):
            continue
        z = selected_height(qi, surfaces, x, y)
        # The unfiltered whole-map branch returns bdY directly. Its child
        # call still receives QI.X's sentinel when the selected Vy is absent.
        if z == -32768 and (not whole_map or mode.filter_cells and criterion_present):
            continue
        result.append((x, y, z))
    return tuple(result)


def select_cell_group(
    values,
    cells,
    *,
    caster_position,
    condition,
    rng,
    criterion_present=True,
    reuse_condition_actors=False,
):
    mode = cell_group_mode(values)
    cells = list(cells)
    if type(criterion_present) is not bool:
        raise ValueError("Missing actual native eYk fKT presence")
    if mode.filter_cells and criterion_present:
        from .combat_condition_selection_scope import condition_actor_selection_scope

        # Native criterion callbacks only query state. End the scope before
        # RNG and child execution, either of which can change fight state.
        # Arbitrary callbacks suspend and invalidate any enclosing memo.
        with condition_actor_selection_scope(enabled=reuse_condition_actors):
            cells = [cell for cell in cells if condition(cell)]
    if not cells:
        return CellGroupSelection((), 0)
    if mode.shuffle:
        if not callable(rng):
            raise ValueError("Missing transaction-owned eYk shuffle RNG")
        for size in range(len(cells), 1, -1):
            sample = rng()
            if type(sample) not in (int, float) or not 0 <= sample < 1:
                raise ValueError("Invalid native eYk shuffle draw")
            index = int(sample * size)
            cells[size - 1], cells[index] = cells[index], cells[size - 1]
    if mode.order in (1, 2):
        x, y, _ = caster_position

        def key(cell):
            dx = (cell[0] - x + 2**31) % 2**32 - 2**31
            dy = (cell[1] - y + 2**31) % 2**32 - 2**31
            absolute = lambda value: value if value == -(2**31) else abs(value)
            distance = (absolute(dx) + absolute(dy) + 2**31) % 2**32 - 2**31
            angle = math.degrees(math.atan2(dy, dx))
            return distance, angle + 360 if angle < 0 else angle

        cells.sort(key=key, reverse=mode.order == 2)
    return CellGroupSelection(
        tuple(cells[: max(0, min(mode.count, len(cells)))]), len(cells)
    )
