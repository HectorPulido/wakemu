"""Bounded exact-content reuse of static board projections, never native facts."""
from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from types import MappingProxyType

from ..native.native_deadline import check


def _integer_cell(cell):
    return (
        type(cell) is tuple
        and len(cell) == 3
        and type(cell[0]) is int
        and type(cell[1]) is int
        and type(cell[2]) is int
    )


@dataclass(frozen=True)
class GeometryProjection:
    cells: tuple
    indices: object
    edges: tuple
    encoded_edges: tuple
    adjacency: object
    xy_indices: object


class GeometryProjectionCache:
    """Cache only integer XYZ/base-edge values under their complete exact key.

    Actor positions, occupancy, portals, hazards, LOS, tackle and source identity
    are deliberately absent from the value. A live in-place topology mutation
    changes the next content key; object identity and sequence are not trusted.
    The XY index contains each existing dense cell exactly once, including
    every floor, and its retained size is bounded by the same cell population.
    """

    def __init__(self, *, max_entries=8, max_units=250_000):
        if (
            type(max_entries) is not int
            or max_entries < 1
            or type(max_units) is not int
            or max_units < 1
        ):
            raise ValueError("Positive geometry cache bounds required")
        self.max_entries, self.max_units = max_entries, max_units
        self._entries = OrderedDict()
        self._units = 0
        self._lock = RLock()

    @property
    def size(self):
        with self._lock:
            return dict(entries=len(self._entries), units=self._units)

    def get(self, walkable, edges, *, catalog_revision):
        check()
        if not isinstance(catalog_revision, str) or not catalog_revision:
            raise ValueError("Exact catalog scope required for geometry reuse")
        # The actual World constructor stores sets of immutable XYZ/edge
        # tuples. Snapshot content, not these mutable set containers, is keyed.
        cells_key = frozenset(walkable)
        edges_key = tuple(edges or ())
        key = catalog_revision, cells_key, edges_key
        with self._lock:
            existing = self._entries.get(key)
            if existing is not None:
                self._entries.move_to_end(key)
                projection, _, original_edges, verified_cells = existing
                # Identity is only a fast validation proof for these already
                # validated immutable tuples, never the topology cache key.
                # Equal new objects still pass the strict type checks below:
                # Python otherwise equates bool/float coordinates with ints.
                if all(verified_cells[cell] is cell for cell in cells_key) and all(
                    current is original
                    for current, original in zip(edges_key, original_edges)
                ):
                    return projection
        if any(not _integer_cell(cell) for cell in cells_key):
            raise ValueError("Native geometry requires exact integer XYZ cells")
        for edge in edges_key:
            if (
                type(edge) is not tuple
                or len(edge) != 2
                or not _integer_cell(edge[0])
                or not _integer_cell(edge[1])
            ):
                raise ValueError("Native geometry requires exact directed XYZ edges")
        if existing is not None:
            # Fresh native graphs can contain equal, newly allocated tuples.
            # Retain the now-validated objects so subsequent reads of that graph
            # need no repeated Python dtype scan. Strong references prevent ID
            # reuse, and the complete content key remains the authority.
            with self._lock:
                current = self._entries.get(key)
                if current is not None:
                    self._entries[key] = (
                        current[0],
                        current[1],
                        edges_key,
                        {cell: cell for cell in cells_key},
                    )
                    self._entries.move_to_end(key)
            return existing[0]
        cells = tuple(sorted(tuple(cell) for cell in cells_key))
        indices = {cell: index for index, cell in enumerate(cells)}
        xy_indices = {}
        for index, cell in enumerate(cells):
            if index % 512 == 0:
                check()
            xy_indices.setdefault(cell[:2], []).append(index)
        directed = tuple((tuple(start), tuple(end)) for start, end in edges_key)
        adjacency = {}
        encoded_edges = []
        for start, end in directed:
            check()
            encoded_edges.append((indices[start], indices[end]))
            adjacency.setdefault(start, []).append(end)
        projection = GeometryProjection(
            cells,
            MappingProxyType(indices),
            directed,
            tuple(encoded_edges),
            MappingProxyType(
                {cell: tuple(destinations) for cell, destinations in adjacency.items()}
            ),
            MappingProxyType({xy: tuple(values) for xy, values in xy_indices.items()}),
        )
        units = len(cells) + 2 * len(directed)
        if units > self.max_units:
            return projection
        with self._lock:
            # Another owner can publish this same immutable projection while
            # construction is outside the lock. Never retain duplicate units.
            existing = self._entries.get(key)
            if existing is not None:
                self._entries.move_to_end(key)
                return existing[0]
            self._entries[key] = (
                projection,
                units,
                edges_key,
                {cell: cell for cell in cells_key},
            )
            self._units += units
            while len(self._entries) > self.max_entries or self._units > self.max_units:
                _, (_, retired_units, _, _) = self._entries.popitem(last=False)
                self._units -= retired_units
        return projection


_CACHE = GeometryProjectionCache()


def geometry_projection(fight, *, catalog_revision):
    """Project exact current topology without retaining the fight or its actors."""
    return _CACHE.get(fight.walkable, fight.edges, catalog_revision=catalog_revision)


def body_extra_cells(geometry, position, footprint):
    """Read all existing XYZ floors for body XY, preserving dense cell order."""
    position = tuple(position)
    return sorted(
        index
        for xy in footprint
        for index in geometry.xy_indices.get(tuple(xy), ())
        if geometry.cells[index] != position
    )
