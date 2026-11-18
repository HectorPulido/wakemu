"""Compile reviewed playable contracts against original native board effects.

The native client opens its own mercenary UI before sending cpF. Its selection
packet supplies no board identity, so only a fresh server-owned board offer
may authorize acceptance. Visibility never supplies earning authority.
"""
from copy import deepcopy

from . import native_effective_eligibility


def compile_contracts(
    sources, descriptors, definitions, manifest, *, floor_proofs=None
):
    if manifest.get("schema") != "reviewed-native-mercenary-boards-v1":
        raise ValueError("Unsupported mercenary board reconstruction")
    sources = {row["id"]: row for row in sources}
    descriptors = {row["descriptor_id"]: row for row in descriptors}
    result = {"schema": manifest["schema"], "boards": [], "definitions": []}
    included, seen = set(), set()
    for declaration in manifest["boards"]:
        identity = declaration["object_id"]
        if type(identity) is not int or identity <= 0 or identity in seen:
            raise ValueError("Invalid or duplicate native board")
        seen.add(identity)
        source = sources[identity]
        if source["type"] != "GenericActivableInteractiveElement" or source["auto"]:
            raise ValueError(
                "Mercenary admission requires an explicit native board action"
            )
        descriptor = descriptors[source["descriptor_id"]]
        matches = []
        for group in descriptor["groups"]:
            for action in group["actions"]:
                for effect in action["effects"]:
                    if effect["effect_type"] == 11:
                        matches.append((group, action, effect))
        if len(matches) != 1:
            raise ValueError("Ambiguous native mercenary board effect")
        group, action, effect = matches[0]
        if (
            action["wire_action"] != 0
            or action["raw_cob"] != 1
            or group["cnd"] != 0
            or group["cod"] != 0
            or group["coe"] != 0
            or len(effect["parameters"]) != 1
            or not effect["parameters"][0].isdigit()
        ):
            raise ValueError("Unsupported native mercenary board action policy")
        category = int(effect["parameters"][0])
        quests = declaration["playable_quests"]
        if not quests or len(set(quests)) != len(quests):
            raise ValueError("A board needs an explicit playable quest whitelist")
        for quest in quests:
            if type(quest) is not int or quest <= 0:
                raise ValueError("Invalid native board quest")
            definition = definitions[quest]
            if (
                definition.get("cjW") is not True
                or definition["cjG"] != category
                or definition.get("aqb") is not False
                or any(definition.get(k) != 0 for k in ("cjU", "cjL", "getDuration"))
            ):
                raise ValueError("Quest does not belong to the native board category")
            native_effective_eligibility.criterion(definition)
            if quest not in included:
                result["definitions"].append(deepcopy(definition))
                included.add(quest)
        anchor = declaration["interaction_anchor"]
        if (
            set(anchor) != {"x", "y", "z"}
            or any(type(v) is not int for v in anchor.values())
            or sum(abs(anchor[k] - source[k]) for k in ("x", "y")) > 4
            or not declaration.get("anchor_evidence")
        ):
            raise ValueError("Board requires a reviewed nearby interaction floor")
        proof = (floor_proofs or {}).get(source["map_id"])
        cell = tuple(anchor[k] for k in ("x", "y", "z"))
        if type(proof) is not dict:
            raise ValueError("Board requires reviewed native floor geometry")
        cells = {tuple(c) for c in proof["cells"]}
        edges = {(tuple(a), tuple(b)) for a, b in proof["edges"]}
        geometry_sha = proof.get("sha256")
        if (
            cell not in cells
            or not any(a == cell and b in cells and (b, a) in edges for a, b in edges)
            or type(geometry_sha) is not str
            or len(geometry_sha) != 64
            or any(c not in "0123456789abcdef" for c in geometry_sha)
        ):
            raise ValueError("Board floor anchor lacks connected native geometry")
        result["boards"].append(
            dict(
                source=deepcopy(source),
                native_group=deepcopy(group),
                native_action=deepcopy(action),
                native_effect=deepcopy(effect),
                category=category,
                playable_quests=sorted(quests),
                interaction_anchor=deepcopy(anchor),
                anchor_evidence=declaration["anchor_evidence"],
                geometry_sha256=geometry_sha,
            )
        )
    return result
