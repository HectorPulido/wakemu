"""Exact observed continuation edges, bound to their original capture identity."""
from functools import lru_cache
import gzip
import json
from pathlib import Path

from .npc_capture_contracts import authorized_identity
from .npc_protectors import speaker


@lru_cache(maxsize=1)
def ledger():
    path = (
        Path(__file__).resolve().parents[2]
        / "protocol/npc-observed-dialogue-edges.json.gz"
    )
    with gzip.open(path, "rt", encoding="utf-8") as source:
        value = json.load(source)
    if value.get("schema") != "native-observed-dialogue-edges-v1":
        raise ValueError("Unsupported observed dialogue ledger")
    return value


def graph(row, nodes, evidence=None):
    """Select exact speaker/root/source edges; never infer roots from node order."""
    if not authorized_identity(row):
        return {}
    evidence = ledger() if evidence is None else evidence
    if row["native_capture_contract"]["source_sha256"] != evidence["source_sha256"]:
        return {}
    kind, identity = speaker(row)
    result = {}
    for edge in evidence["edges"]:
        if (edge["speaker_type"], edge["speaker_id"], edge["initial_root"]) != (
            kind,
            identity,
            row["dialogue_root"],
        ):
            continue
        node, choice, target = (
            edge[key] for key in ("node_id", "choice_id", "target_node_id")
        )
        if (
            any(type(value) is not int for value in (node, choice, target))
            or node not in nodes
            or choice not in {value["id"] for value in nodes[node]["choices"]}
            or target < 0
            or (target != 0 and target not in nodes)
        ):
            raise ValueError("Invalid observed native dialogue edge")
        key = node, choice
        if key in result and result[key] != target:
            raise ValueError("Conflicting observed native dialogue edge")
        result[key] = target
    # Disconnected observations cannot authorize a later node in this scene.
    reached = {row["dialogue_root"]}
    while True:
        following = {
            target for (node, _), target in result.items() if node in reached and target
        }
        if following <= reached:
            break
        reached.update(following)
    return {key: target for key, target in result.items() if key[0] in reached}
