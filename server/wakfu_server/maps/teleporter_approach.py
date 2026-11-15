"""Authorize native bEG approach cells and bEm approved path callbacks.

The catalog exports bEG.dST mask/orientation cells with native VA height
selection. Zero-mask objects retain bEm's exact raw X/Y path callback.
All positions come from the bound server Movement or owned character state.
"""


def callback(movement_state, *, map_id, instance_id=0):
    """Bind authoritative movement to one native map and private instance."""

    def allowed(character, source):
        projected_source = {
            key: source[key]
            for key in ("map_id", "x", "y", "approach_mask", "approach_orientation")
            if key in source
        }
        if "approach_positions" in source:
            positions = source["approach_positions"]
            projected_source["approach_positions"] = (
                [
                    (
                        {key: row[key] for key in ("x", "y", "z") if key in row}
                        if isinstance(row, dict)
                        else {}
                    )
                    for row in positions
                ]
                if isinstance(positions, (list, tuple))
                else None
            )
        return movement_state._spatial.call(
            "navigation.approach",
            handle=movement_state._handle,
            map_id=map_id,
            instance_id=instance_id,
            character={
                key: character[key]
                for key in ("map_id", "instance_id", "x", "y", "z")
                if key in character
            },
            source=projected_source,
        )

    return allowed
