"""eYE.a(PJ): highest present mastery, preserving native enum tie order.

Used by light/stasis arithmetic. Native elemental IDs differ from running
families; the result is a native element ID, or None when none is present.
"""


def highest_mastery_element(stats):
    if not isinstance(stats, dict) or any(
        type(k) is not int or type(v) is not int for k, v in stats.items()
    ):
        raise ValueError("Native elemental characteristic presence required")
    selected = value = None
    # PHYSICAL/SUPPORT have no mastery; STASIS/LIGHT are excluded by eYE.
    for element, characteristic in ((1, 21), (2, 22), (3, 23), (4, 24)):
        if characteristic in stats and (
            selected is None or stats[characteristic] > value
        ):
            selected, value = element, stats[characteristic]
    return selected
