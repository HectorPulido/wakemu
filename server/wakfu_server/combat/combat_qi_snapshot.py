"""Pure QI mask and explicitly registered QK spatial population snapshot."""
from dataclasses import dataclass


@dataclass(frozen=True)
class RegisteredObstacle:
    obstacle_id: int
    x: int
    y: int
    radius: int


class NativeQISnapshot:
    def __init__(self, arena, *, obstacles=None):
        names = ("x", "y", "width", "height")
        if any(
            type(arena.get(name)) is not int
            or not -(1 << 31) <= arena[name] < (1 << 31)
            for name in names
        ):
            raise ValueError("Missing serialized native QI rectangle")
        self.x, self.y, self.width, self.height = (arena[name] for name in names)
        masks = arena.get("cell_masks")
        if (
            self.width < 1
            or self.height < 1
            or self.width * self.height > 32767
            or not isinstance(masks, (list, tuple))
            or len(masks) != self.width * self.height
            or any(
                type(mask) is not int or not -32768 <= mask <= 32767 for mask in masks
            )
        ):
            raise ValueError("Missing serialized native QI signed-short masks")
        self.masks = tuple(masks)
        self.occupancy = None
        if obstacles is not None:
            if not isinstance(obstacles, (list, tuple)):
                raise ValueError("Missing complete native QK registration population")
            occupancy = {}
            seen = set()
            for obstacle in obstacles:
                if (
                    not isinstance(obstacle, RegisteredObstacle)
                    or any(
                        type(value) is not int
                        for value in (
                            obstacle.obstacle_id,
                            obstacle.x,
                            obstacle.y,
                            obstacle.radius,
                        )
                    )
                    or not 0 <= obstacle.obstacle_id <= 126
                    or not -128 <= obstacle.radius <= 127
                    or any(
                        not -(1 << 31) <= value < (1 << 31)
                        for value in (obstacle.x, obstacle.y)
                    )
                    or obstacle.obstacle_id in seen
                ):
                    raise ValueError("Invalid native registered QK obstacle")
                radius = max(0, obstacle.radius)
                if radius == 0 and not self.aK(obstacle.x, obstacle.y):
                    raise ValueError(
                        "Native radius-zero obstacle is outside QI registration bounds"
                    )
                if (
                    any(
                        not -(1 << 31) <= endpoint < (1 << 31)
                        for endpoint in (
                            obstacle.x - radius,
                            obstacle.x + radius,
                            obstacle.y - radius,
                            obstacle.y + radius,
                        )
                    )
                    or obstacle.x + radius == (1 << 31) - 1
                    or obstacle.y + radius == (1 << 31) - 1
                ):
                    # Native inclusive int loops wrap at MAX and may not terminate.
                    raise ValueError(
                        "Native QK footprint exceeds proven terminating int32 domain"
                    )
                seen.add(obstacle.obstacle_id)
                for x in range(obstacle.x - radius, obstacle.x + radius + 1):
                    for y in range(obstacle.y - radius, obstacle.y + radius + 1):
                        if self.aK(x, y):
                            occupancy.setdefault((x, y), set()).add(
                                obstacle.obstacle_id
                            )
            self.occupancy = {cell: frozenset(ids) for cell, ids in occupancy.items()}

    @staticmethod
    def _int32(value):
        return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)

    def aK(self, x, y):
        if any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in (x, y)
        ):
            raise ValueError("Invalid native QI coordinate")
        return self.x <= x < self._int32(
            self.x + self.width
        ) and self.y <= y < self._int32(self.y + self.height)

    def _mask(self, x, y):
        if not self.aK(x, y):
            return None
        return self.masks[(y - self.y) * self.width + x - self.x]

    def P(self, x, y):
        mask = self._mask(x, y)
        return mask is not None and mask != -257 and bool(mask & 128)

    def Q(self, x, y):
        mask = self._mask(x, y)
        return mask is not None and not bool(mask & 128)

    def R(self, x, y):
        mask = self._mask(x, y)
        return mask is not None and (mask & -257) != -257

    def Z(self, x, y):
        """Native path-option mask lookup uses W/index bounds, not aK."""
        if any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in (x, y)
        ):
            raise ValueError("Invalid native QI coordinate")
        index = self._int32(
            self._int32(self._int32(y - self.y) * self.width) + self._int32(x - self.x)
        )
        return 0 <= index < len(self.masks) and bool(self.masks[index] & 768)

    def U(self, x, y):
        if not self.aK(x, y):
            return frozenset()
        if self.occupancy is None:
            raise ValueError("Missing complete native QK registration population")
        # QL.oY returns null for an absent index, not a synthesized empty set.
        return self.occupancy.get((x, y))
