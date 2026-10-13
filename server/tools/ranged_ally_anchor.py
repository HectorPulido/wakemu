"""Bounded native-range placement candidates for real supportive companions."""


def eligible(recipe, source, cell):
    if (
        recipe.get("discovery") != "ordinary_same_species_ally_v1"
        or "native_recipient_range" not in recipe
    ):
        return True
    if (
        recipe.get("kind") != "native_opponent"
        or recipe.get("opponent", {}).get("team") != 1
    ):
        raise ValueError("Ranged ally witness lacks actual allied constructor")
    minimum, maximum = recipe["native_recipient_range"]
    if (
        type(minimum) is not int
        or type(maximum) is not int
        or not 1 <= minimum <= maximum <= 64
    ):
        raise ValueError("Invalid bounded actual ally recipient range")
    return (
        cell[2] == source[2]
        and minimum <= abs(cell[0] - source[0]) + abs(cell[1] - source[1]) <= maximum
    )
