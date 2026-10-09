"""Authorize native bEG approach cells and bEm approved path callbacks.

The catalog exports bEG.dST mask/orientation cells with native VA height
selection. Zero-mask objects retain bEm's exact raw X/Y path callback.
All positions come from the bound server Movement or owned character state.
"""


def callback(movement_state, *, map_id, instance_id=0):
    """Bind authoritative movement to one native map and private instance."""

    def allowed(character, source):
        if character.get("instance_id", 0) != instance_id:
            return False
        if character["map_id"] != map_id or source["map_id"] != map_id:
            return False
        approved = tuple(movement_state.approved)
        mask = source.get("approach_mask", 0)
        if type(mask) is not int or not 0 <= mask <= 32767:
            return False
        if mask:
            orientation = source.get("approach_orientation")
            if type(orientation) is not int or not 0 <= orientation < 8:
                return False
            positions = source.get("approach_positions", ())
            candidates = set()
            for point in positions:
                values = tuple(point.get(axis) for axis in ("x", "y", "z"))
                if any(
                    type(value) not in (int, float) or value != int(value)
                    for value in values
                ):
                    return False
                candidates.add(tuple(int(value) for value in values))
            if any(tuple(point) in candidates for point in approved):
                return True
            # Native bEk invokes directly when no animated path is running.
            # The dispatcher supplies an owned persisted character, never the
            # coordinates from the client teleporter request.
            if not approved and all(axis in character for axis in ("x", "y", "z")):
                return tuple(character[axis] for axis in ("x", "y", "z")) in candidates
            return False
        sx, sy = source["x"], source["y"]
        if sx != int(sx) or sy != int(sy):
            return False
        if any(x == int(sx) and y == int(sy) for x, y, z in approved):
            return True
        return (
            not approved
            and character.get("x") == int(sx)
            and character.get("y") == int(sy)
        )

    return allowed
