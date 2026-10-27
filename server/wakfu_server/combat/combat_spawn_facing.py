"""Choose fresh NPC facing with the same cardinal sectors as ordinary casts."""


def toward_nearest(position, targets, *, default=3):
    from .combat_cast_facing import cast_direction

    targets = [
        (identity, point)
        for identity, point in targets
        if tuple(point[:2]) != tuple(position[:2])
    ]
    if not targets:
        return default
    _, target = min(
        targets,
        key=lambda row: (
            abs(row[1][0] - position[0]) + abs(row[1][1] - position[1]),
            abs(row[1][2] - position[2]),
            row[0],
        ),
    )
    return cast_direction(
        target[0] - position[0], target[1] - position[1], diagonals=False
    )
