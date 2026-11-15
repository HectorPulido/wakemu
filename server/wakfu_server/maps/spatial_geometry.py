"""Pinned source loading and Python views of native immutable spatial indexes.

All path, footprint, proximity and occupancy calculations run in Rust. These
adapters only shape compact inputs and refill evicted immutable source indexes.
"""

from functools import lru_cache

from wakfu_server.spatial_native import get_spatial


def actor_position(actor, *, identity=False):
    value = {key: actor[key] for key in ("x", "y", "z")}
    if identity and "id" in actor:
        value["id"] = actor["id"]
    return value


def member_rows(members):
    return [actor_position(member, identity=True) for member in members]


def group_rows(groups):
    return [
        dict(status=group.get("status"), members=member_rows(group["members"]))
        for group in groups
    ]


class ImmutableIndex:
    def __init__(self, operation, payload):
        self.native = get_spatial()
        self.operation = operation
        self.payload = payload
        self.key = None
        self.reload()

    def reload(self):
        self.key = self.native.call(self.operation, **self.payload())["key"]

    def call(self, operation, **kwargs):
        try:
            return self.native.call(operation, key=self.key, **kwargs)
        except ValueError as error:
            if str(error) != "Spatial geometry handle expired":
                raise
            self.reload()
            return self.native.call(operation, key=self.key, **kwargs)


class NativeEdges:
    def __init__(self, index):
        self.index = index

    def __contains__(self, edge):
        origin, destination = edge
        return self.index.call(
            "geometry.edge_contains", origin=origin, destination=destination
        )


class NativeAdjacency:
    def __init__(self, index):
        self.index = index

    def get(self, origin, default=()):
        rows = self.index.call("geometry.adjacent", origin=origin)
        return tuple(map(tuple, rows)) if rows else default


class NativeEdgeIndex(tuple):
    def __new__(cls, index):
        value = super().__new__(cls, (NativeEdges(index), NativeAdjacency(index)))
        value.native_index = index
        return value


def edge_index(edges):
    # Fixture/dynamic graphs are immutable inputs, never a Python adjacency index.
    edges = tuple(edges)
    return NativeEdgeIndex(
        ImmutableIndex("geometry.index_edges", lambda: dict(edges=edges))
    )


@lru_cache(maxsize=16)
def catalog_edges(map_id):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    def source():
        if map_id == 2_000_000_000:
            # The combat domain owns the explicit authored interior projection.
            from wakfu_server.combat_terrain import map_geometry

            graph = map_geometry(map_id)
            return dict(
                cells=graph["cells"],
                edges=graph["edges"],
                authority=native_catalog.release(),
            )
        return dict(
            map_id=map_id,
            authority=native_catalog.release(),
            raw=native_catalog.read_bytes(
                DATA_ROOT / f"combat-maps/{map_id}.json"
            ).decode("utf-8"),
        )

    op = "geometry.index_graph" if map_id == 2_000_000_000 else "geometry.load"
    return NativeEdgeIndex(ImmutableIndex(op, source))


class NativeNeighbors:
    def __init__(self, groups):
        rows = group_rows(groups)
        self.index = ImmutableIndex(
            "geometry.neighbor_index", lambda: dict(groups=rows)
        )


@lru_cache(maxsize=1)
def habitats():
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    return ImmutableIndex(
        "geometry.load_habitats",
        lambda: dict(
            authority=native_catalog.release(),
            raw=native_catalog.read_bytes(DATA_ROOT / "ecology-regions.json").decode(
                "utf-8"
            ),
        ),
    )


@lru_cache(maxsize=16)
def surfaces(map_id):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    return ImmutableIndex(
        "geometry.load_surfaces",
        lambda: dict(
            authority=native_catalog.release(),
            raw=native_catalog.read_bytes(
                DATA_ROOT / f"planting-maps/{map_id}.json"
            ).decode("utf-8"),
        ),
    )
