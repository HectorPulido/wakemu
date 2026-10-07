"""Validated multi-role hints from world; never a cast legality authority."""
import re


def validate_capabilities(raw):
    if not isinstance(raw, list) or len(raw) > 256:
        raise ValueError("Invalid capability repertoire")
    result, seen = [], set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise ValueError("Invalid spell capability")
        for field, lower, upper in (
            ("spellId", 1, 2**31 - 1),
            ("level", 1, 32767),
            ("minimum", 0, 32767),
            ("maximum", 0, 32767),
        ):
            if type(entry.get(field)) is not int or not lower <= entry[field] <= upper:
                raise ValueError("Invalid capability " + field)
        key = entry["spellId"], entry["level"]
        if key in seen or entry["minimum"] > entry["maximum"]:
            raise ValueError("Duplicate capability or invalid range envelope")
        seen.add(key)
        tags = entry.get("tags")
        if (
            not isinstance(tags, list)
            or not 1 <= len(tags) <= 32
            or any(
                not isinstance(tag, str)
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", tag)
                for tag in tags
            )
        ):
            raise ValueError("Invalid capability tags")
        if type(entry.get("conditional", False)) is not bool:
            raise ValueError("Invalid conditional capability")
        unknown = entry.get("unknownDependencies", [])
        if (
            not isinstance(unknown, list)
            or len(unknown) > 128
            or any(
                not isinstance(reason, str) or not 1 <= len(reason) <= 160
                for reason in unknown
            )
        ):
            raise ValueError("Invalid capability dependencies")
        result.append(dict(entry, tags=sorted(set(tags))))
    return result


def affinities(capabilities):
    result = dict(melee=0, ranged=0, support=0, controller=0, summoner=0, unknown=0)
    for capability in capabilities:
        tags = set(capability["tags"])
        if "damage" in tags:
            result["ranged" if capability["maximum"] >= 2 else "melee"] += 1
        if tags & {"heal", "armor", "buff"}:
            result["support"] += 1
        if tags & {"control", "debuff", "displacement"}:
            result["controller"] += 1
        if "summon" in tags:
            result["summoner"] += 1
        if "unknown" in tags:
            result["unknown"] += 1
    return result
