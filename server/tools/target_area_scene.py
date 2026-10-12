"""Plan only genuine empty-cell producer casts; native eligibility stays authoritative."""


def target_area_scene(source, target, validated_cells, *, minimum, maximum):
    from external_owned_area_preparation import adjacent

    cells = set(validated_cells)
    distance = lambda c: abs(c[0] - source[0]) + abs(c[1] - source[1])
    if (
        source not in cells
        or target not in cells
        or source[2] != target[2]
        or not minimum <= distance(target) <= maximum
        or target == source
    ):
        raise ValueError("Target area requires actual validated in-range cell")
    # The producer casts back onto the intended empty target cell from beyond
    # it. It cannot occupy an intermediate source-target LOS probe.
    producer = next(
        (
            c
            for c in sorted(cells)
            if adjacent(target, c) and distance(c) > distance(target)
        ),
        None,
    )
    if producer is None:
        raise ValueError("No validated native producer neighbor beyond target")
    player = next(
        (c for c in sorted(cells) if c not in {source, target, producer}), None
    )
    if player is None:
        raise ValueError("No separate validated player placement")
    return dict(
        producer_cell=producer,
        player_cell=player,
        target_cell=target,
        native_cast_target_id=None,
        requested_target_id=None,
    )
