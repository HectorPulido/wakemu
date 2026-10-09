"""Profile complete CAS graph loading without importing native game catalogs.

Run against a preserved private context digest. Only sizes, timings, schema
counts and profiler statistics are emitted; context fields remain private.
"""
import argparse
import cProfile
import gzip
import hashlib
import json
from pathlib import Path
import pstats
import time

from wakfu_ai.context.native_context import NativeGraph
from wakfu_ai.planning.query_search import _fight, _sequence
from wakfu_ai.planning.topology_distance import directed_adjacencies


def measure(result, name, operation):
    started = time.perf_counter()
    value = operation()
    result[name + "Seconds"] = time.perf_counter() - started
    return value


def exact_integer_tuple(node):
    return (
        type(node) is dict
        and len(node) == 2
        and node.get("type") == "tuple"
        and type(node.get("items")) is list
        and all(
            type(item) is dict and len(item) == 1 and type(item.get("value")) is int
            for item in node["items"]
        )
    )


def generic_tuple_check(node):
    if set(node) != {"type", "items"} or not isinstance(node["items"], list):
        raise ValueError("Invalid native sequence")
    for item in node["items"]:
        if not isinstance(item, dict) or len(item) != 1:
            raise ValueError("Invalid native graph reference")
        value = item["value"]
        if value is not None and type(value) not in (str, int, float, bool):
            raise ValueError("Invalid native primitive")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/var/lib/wakfu-ai-context")
    parser.add_argument("--digest", required=True)
    parser.add_argument("--profile")
    args = parser.parse_args()
    if len(args.digest) != 64 or any(c not in "0123456789abcdef" for c in args.digest):
        raise ValueError("Invalid private context digest")
    result = dict(digest=args.digest)
    body = measure(result, "read", lambda: (Path(args.root) / args.digest).read_bytes())
    digest = measure(result, "sha", lambda: hashlib.sha256(body).hexdigest())
    if digest != args.digest:
        raise ValueError("Private context checksum changed")
    result["storedBytes"] = len(body)
    raw = measure(
        result,
        "decompress",
        lambda: gzip.decompress(body) if body.startswith(b"\x1f\x8b") else body,
    )
    result["rawBytes"] = len(raw)
    encoded = measure(result, "json", lambda: json.loads(raw))
    result["nodeCount"] = len(encoded["nodes"])
    profile = cProfile.Profile() if args.profile else None
    if profile:
        profile.enable()
    graph = measure(result, "validate", lambda: NativeGraph(encoded))
    if profile:
        profile.disable()
        profile.dump_stats(args.profile)
    tuple_nodes = [node for node in graph.nodes if exact_integer_tuple(node)]
    result["exactIntegerTupleNodes"] = len(tuple_nodes)
    measure(
        result,
        "genericTupleChecks",
        lambda: [generic_tuple_check(n) for n in tuple_nodes],
    )
    valid = measure(
        result,
        "fastTupleChecks",
        lambda: all(exact_integer_tuple(n) for n in tuple_nodes),
    )
    if not valid:
        raise AssertionError("Complete primitive tuple validation failed")
    fight = measure(result, "fightNavigation", lambda: _fight(graph))
    memo = {}
    cells = measure(
        result,
        "walkableDecode",
        lambda: _sequence(graph, graph.field(fight, "walkable"), memo),
    )
    edges_ref = graph.field(fight, "edges")
    edges = measure(result, "edgesDecode", lambda: _sequence(graph, edges_ref, memo))
    result.update(cells=len(cells), edges=len(edges))
    measure(
        result, "adjacencies", lambda: directed_adjacencies(edges, cells=set(cells))
    )
    print(json.dumps(result, sort_keys=True))
    if profile:
        pstats.Stats(profile).strip_dirs().sort_stats("cumulative").print_stats(15)


if __name__ == "__main__":
    main()
