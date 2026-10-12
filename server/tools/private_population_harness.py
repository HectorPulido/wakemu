"""Private harness additions reuse actual owned_instance and initialization."""
from population_witness import required_enemy_population
from zero_range_ally import propose


def private_recipes(reference, level, capability, criterion, roots):
    from wakfu_server.monsters import reference as native_reference

    profile = native_reference(reference)
    recipes = []
    ally = propose(reference, level, capability, roots, {str(reference): profile})
    if ally:
        recipes.append(ally)
    from allied_population_witness import allied_population_recipe

    allied = allied_population_recipe(reference, level, capability, criterion, profile)
    if allied is not None:
        recipes.insert(0, allied)
    population = required_enemy_population(criterion)
    # Existing native_opponent adds one monster and retains the real player:
    # exactly two actual enemies. Larger populations need another constructor.
    if population and population["minimum_enemies"] == 2:
        if (
            type(level) is not int
            or not profile["min_level"] <= level <= profile["max_level"]
        ):
            raise ValueError("Missing actual population descriptor authority")
        recipes.append(
            dict(
                kind="native_opponent",
                opponent=dict(reference=reference, level=level, team=0),
                discovery="native_two_enemy_population_private_v1",
                population=population,
            )
        )
    return recipes


def private_spare_eligible(scenario, source, enemy, spare):
    if scenario.get("discovery") == "native_two_allied_population_v1":
        from allied_population_witness import allied_spare_eligible

        return allied_spare_eligible(scenario, source, enemy, spare)
    if scenario.get("discovery") != "native_two_enemy_population_private_v1":
        return True
    p = scenario["population"]
    if p["minimum_enemies"] != 2:
        raise ValueError("Unsupported native population size")
    close = (
        lambda c: c[2] == source[2]
        and 0 < abs(c[0] - source[0]) + abs(c[1] - source[1]) <= p["radius"]
    )
    return close(enemy) and close(spare) and tuple(enemy) != tuple(spare)
