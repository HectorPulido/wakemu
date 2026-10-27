"""Explicit local DEV balancing; native identities do not imply official formulas."""
import hashlib
import random


def validate(policy):
    if (
        not isinstance(policy, dict)
        or policy.get("policy_kind") != "local_dev_not_official"
    ):
        raise ValueError("Rift policy must explicitly identify local DEV balancing")
    for field, minimum, maximum in (
        ("turn_budget", 1, 10000),
        ("max_members", 1, 6),
        ("classic_wave_size", 1, 64),
        ("ultimate_wave_size", 1, 64),
        ("starting_wave", 1, 1000000),
    ):
        value = policy.get(field)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError("Invalid rift policy " + field)
    if (
        policy.get("selection")
        not in (
            "uniform_with_replacement",
            "shuffled_species_cycles",
        )
        or policy.get("scaling") != "native_base_grade"
    ):
        raise ValueError("Unsupported rift selection or scaling policy")
    if policy.get("rewards") != "callback_only":
        raise ValueError("Unsupported rift reward policy")
    if policy.get("quest_requirements") or policy.get("key_requirements"):
        raise ValueError("Native quest/key authority is not yet supported")
    if type(policy.get("ultimate_enabled", False)) is not bool:
        raise ValueError("Invalid ultimate rift enable flag")
    if type(policy.get("enabled")) is not bool:
        raise ValueError("Invalid rift enable flag")
    sizes = policy.get("wave_size_by_company_size")
    if sizes is not None and (
        not isinstance(sizes, dict)
        or set(sizes) != {str(n) for n in range(1, 7)}
        or any(type(n) is not int or not 1 <= n <= 64 for n in sizes.values())
    ):
        raise ValueError("Invalid Rift company wave sizes")
    company_size = policy.get("company_size")
    if company_size is not None and (
        type(company_size) is not int
        or not 1 <= company_size <= policy["max_members"]
        or sizes is None
        or any(
            policy[field] != sizes[str(company_size)]
            for field in ("classic_wave_size", "ultimate_wave_size")
        )
    ):
        raise ValueError("Rift wave size differs from its admitted company")
    interval = policy.get("elite_wave_interval")
    if interval is not None and (
        type(interval) is not int or not 2 <= interval <= 1000000
    ):
        raise ValueError("Invalid Rift elite wave interval")
    return dict(policy)


def bind_company_size(policy, quantity):
    """Freeze the admitted character count, including heroes, for every wave."""
    policy = validate(policy)
    if type(quantity) is not int or not 1 <= quantity <= policy["max_members"]:
        raise ValueError("Invalid Rift company size")
    sizes = policy.get("wave_size_by_company_size")
    if sizes is not None:
        policy.update(
            company_size=quantity,
            classic_wave_size=sizes[str(quantity)],
            ultimate_wave_size=sizes[str(quantity)],
        )
    return validate(policy)


def species_pools(catalog):
    """Keep original random species separate from explicit milestone additions."""
    refs = catalog.get("species_refs")
    if (
        not isinstance(refs, list)
        or not refs
        or any(type(r) is not int or r <= 0 for r in refs)
    ):
        raise ValueError("Invalid native rift species pool")
    additions = catalog.get("additional_species_refs", [])
    if (
        not isinstance(additions, list)
        or any(type(r) is not int or r <= 0 for r in additions)
        or len(set(additions)) != len(additions)
    ):
        raise ValueError("Invalid Rift additional species pool")
    refs = refs + [ref for ref in additions if ref not in refs]
    elites = catalog.get("milestone_species_refs", [])
    if (
        not isinstance(elites, list)
        or any(type(r) is not int or r <= 0 for r in elites)
        or len(set(elites)) != len(elites)
        or bool(set(refs) & set(elites))
    ):
        raise ValueError("Invalid Rift milestone species pool")
    return refs, elites


def select_wave(catalog, policy, seed, wave):
    """Stable local selection, independent from RNG calls elsewhere in combat."""
    validate(policy)
    refs, elites = species_pools(catalog)
    if type(wave) is not int or wave < 1 or not isinstance(seed, str) or not seed:
        raise ValueError("Invalid rift wave seed or counter")
    kind = catalog.get("type")
    if kind not in ("INFINITE_WAVE", "ULTIMATE_INFINITE_WAVE"):
        raise ValueError("Unsupported native rift kind")
    size = policy[
        "ultimate_wave_size"
        if kind == "ULTIMATE_INFINITE_WAVE"
        else "classic_wave_size"
    ]
    digest = hashlib.sha256(f'{catalog["wave_id"]}:{seed}:{wave}'.encode()).digest()
    rng = random.Random(int.from_bytes(digest, "big"))
    if policy["selection"] == "shuffled_species_cycles":
        selected = []
        available = list(dict.fromkeys(refs))
        while len(selected) < size:
            cycle = list(available)
            rng.shuffle(cycle)
            selected.extend(cycle[: size - len(selected)])
    else:
        selected = [rng.choice(refs) for _ in range(size)]
    interval = policy.get("elite_wave_interval")
    if elites and interval is not None and wave % interval == 0:
        # Replace one ordinary slot: company population, ordinal bindings and
        # retry selection all remain fixed for the admitted run.
        elite_seed = hashlib.sha256(
            f'{catalog["wave_id"]}:{seed}:elites'.encode()
        ).digest()
        elite_cycle = list(elites)
        random.Random(int.from_bytes(elite_seed, "big")).shuffle(elite_cycle)
        selected[-1] = elite_cycle[(wave // interval - 1) % len(elite_cycle)]
    return tuple(selected)
