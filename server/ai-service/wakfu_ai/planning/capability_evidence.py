"""Capabilities observed in certified transitions, without spell ID rules."""


def observed(before, after, actor_id):
    friendly = before[actor_id]["team"]
    capabilities = set()
    for identity, source in before.items():
        target = after.get(identity)
        if target is None:
            continue
        ally = source["team"] == friendly
        if not ally and target["hp"] < source["hp"]:
            capabilities.add("damage")
        if ally and target["hp"] > source["hp"]:
            capabilities.add("healing")
        if ally and target["armor"] > source["armor"]:
            capabilities.add("protection")
        if not ally and any(target[name] < source[name] for name in ("ap", "mp", "wp")):
            capabilities.add("control")
        if identity != actor_id and tuple(target["position"]) != tuple(
            source["position"]
        ):
            capabilities.add("displacement")
    if any(
        identity not in before
        and target["team"] == friendly
        and target["hp"] > 0
        and target.get("registeredSummon") is True
        for identity, target in after.items()
    ):
        capabilities.add("summoning")
    return sorted(capabilities)
