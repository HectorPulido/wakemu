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
        policy.get("selection") != "uniform_with_replacement"
        or policy.get("scaling") != "native_base_grade"
    ):
        raise ValueError("Unsupported rift selection or scaling policy")
    if policy.get("rewards") != "callback_only":
        raise ValueError("Unsupported rift reward policy")
    if policy.get("quest_requirements") or policy.get("key_requirements"):
        raise ValueError("Native quest/key authority is not yet supported")
    if policy.get("ultimate_enabled", False) is not False:
        raise ValueError("Ultimate rift key authority is unavailable")
    if type(policy.get("enabled")) is not bool:
        raise ValueError("Invalid rift enable flag")
    return dict(policy)


def select_wave(catalog, policy, seed, wave):
    """Stable local selection, independent from RNG calls elsewhere in combat."""
    validate(policy)
    refs = catalog.get("species_refs")
    if (
        not isinstance(refs, list)
        or not refs
        or any(type(r) is not int or r <= 0 for r in refs)
    ):
        raise ValueError("Invalid native rift species pool")
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
    return tuple(rng.choice(refs) for _ in range(size))
