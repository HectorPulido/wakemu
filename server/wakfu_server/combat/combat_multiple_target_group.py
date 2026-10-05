"""eYC345: criterion-per-PV, shuffle, stable spiral sort, count."""
import math


def multiple_target_spec(values):
    parameters = values["parameters"]
    if (
        not parameters
        or len(parameters) > 4
        or any(type(x) is not int for x in parameters)
    ):
        raise ValueError("Missing native eYC parameter interpretation")
    return (
        parameters[0],
        len(parameters) > 1 and parameters[1] == 1,
        len(parameters) < 3 or parameters[2] == 1,
        parameters[3] if len(parameters) > 3 else 0,
    )


def select_multiple_targets(
    values, candidates, *, caster_position, position, condition, rng
):
    count, filtered, shuffled, order = multiple_target_spec(values)
    candidates = list(candidates)
    identities = [item.target_id for item in candidates]
    if None in identities or len(identities) != len(set(identities)):
        raise ValueError("Invalid native eYC candidate identities")
    if filtered:
        candidates = [item for item in candidates if condition(item)]
    if shuffled:
        if not callable(rng):
            raise ValueError("Missing transaction-owned eYC shuffle RNG")
        for size in range(len(candidates), 1, -1):
            sample = rng()
            if type(sample) not in (int, float) or not 0 <= sample < 1:
                raise ValueError("Invalid native eYC shuffle sample")
            index = int(sample * size)
            candidates[size - 1], candidates[index] = (
                candidates[index],
                candidates[size - 1],
            )
    if order in (1, 2):
        x, y, _ = caster_position

        def key(item):
            tx, ty, _ = position(item.target_id)
            # Java signed int subtraction and Manhattan overflow semantics.
            dx = (tx - x + 2**31) % 2**32 - 2**31
            dy = (ty - y + 2**31) % 2**32 - 2**31
            abs_java = lambda v: v if v == -(2**31) else abs(v)
            distance = (abs_java(dx) + abs_java(dy) + 2**31) % 2**32 - 2**31
            angle = math.degrees(math.atan2(dy, dx))
            if angle < 0:
                angle += 360
            return distance, angle

        candidates.sort(key=key, reverse=order == 2)
    return tuple(candidates[: max(0, min(count, len(candidates)))])
