"""Shared immutable terrain for previews; exact transient source validation.

Durable checkpoints still serialize every terrain cell and edge. Mutable legacy
fixtures take the complete serialization path, so in-place edits remain visible.
"""
from .fight_checkpoint_store import _plain


class ImmutableTerrainSet(frozenset):
    __slots__ = ()

    def __new__(cls, values):
        values = tuple(values)
        for value in values:
            if not isinstance(value, tuple) or not all(
                type(part) is int
                or (isinstance(part, tuple) and all(type(n) is int for n in part))
                for part in value
            ):
                raise ValueError("Terrain requires immutable integer coordinates")
        return super().__new__(cls, values)

    def __deepcopy__(self, memo):
        memo[id(self)] = self
        return self


def freeze_terrain(fight):
    fight.walkable = ImmutableTerrainSet(fight.walkable)
    if fight.edges is not None:
        fight.edges = ImmutableTerrainSet(fight.edges)


def source_snapshot(fight):
    state = {
        key: (
            value
            if key in ("walkable", "edges") and isinstance(value, ImmutableTerrainSet)
            else _plain(value)
        )
        for key, value in fight.__dict__.items()
        if key not in ("actors", "native_rail_movement_authority")
    }
    state["actors"] = {
        str(identity): _plain(actor.__dict__)
        for identity, actor in fight.actors.items()
    }
    return state
