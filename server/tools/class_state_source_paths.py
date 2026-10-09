"""Memory-bounded scoped native graph path extraction; never executes effects."""
import gzip
from collections import defaultdict, deque
import json
import re


def graph_edges(path):
    decoder = json.JSONDecoder()
    buffer = ""
    with gzip.open(path, "rt") if path.suffix == ".gz" else open(path, "rt") as stream:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                raise ValueError("Native graph edges section absent")
            buffer += chunk
            marker = re.search(r'"edges"\s*:\s*\[', buffer)
            if marker:
                buffer = buffer[marker.end() :]
                break
            buffer = buffer[-128:]
        while True:
            buffer = buffer.lstrip(" \r\n\t,")
            if buffer.startswith("]"):
                return
            try:
                edge, end = decoder.raw_decode(buffer)
            except json.JSONDecodeError:
                chunk = stream.read(65536)
                if not chunk:
                    raise ValueError("Truncated native graph edge")
                buffer += chunk
                continue
            if (
                not isinstance(edge, dict)
                or not isinstance(edge.get("source"), str)
                or not isinstance(edge.get("target"), str)
            ):
                raise ValueError("Invalid scoped native dependency edge")
            yield edge
            buffer = buffer[end:]


def reverse_edges(path):
    parents = defaultdict(list)
    for edge in graph_edges(path):
        parents[edge["target"]].append((edge["source"], edge["kind"]))
    return parents


def shortest_source_path(parents, source, target, maximum_nodes=4096):
    pending = deque([(target, [target], [])])
    seen = set()
    while pending and len(seen) < maximum_nodes:
        node, nodes, kinds = pending.popleft()
        if node == source:
            return dict(
                status="shortest_native_dependency_candidate",
                nodes=nodes[::-1],
                edge_kinds=kinds[::-1],
                executable_verified=False,
                alternative_paths_complete=False,
            )
        if node in seen:
            continue
        seen.add(node)
        for parent, kind in parents.get(node, []):
            pending.append((parent, nodes + [parent], kinds + [kind]))
    return dict(
        status="bounded_source_path_unresolved"
        if pending
        else "no_path_in_current_scoped_graph",
        visited_nodes=len(seen),
        executable_verified=False,
    )


def graph_nodes(path, keys):
    pending = set(keys)
    patterns = {
        key: re.compile(r'"' + re.escape(key) + r'"\s*:\s*\{') for key in pending
    }
    found, buffer = {}, ""
    with gzip.open(path, "rt") if path.suffix == ".gz" else open(path, "rt") as stream:
        while pending:
            chunk = stream.read(65536)
            if not chunk:
                break
            buffer += chunk
            for key in list(pending):
                match = patterns[key].search(buffer)
                if match is None:
                    continue
                try:
                    node, _ = json.JSONDecoder().raw_decode(buffer[match.end() - 1 :])
                except json.JSONDecodeError:
                    continue
                found[key] = {
                    field: node.get(field)
                    for field in (
                        "kind",
                        "reference",
                        "family",
                        "native_runner_class",
                        "criterion_raw",
                        "raw_parameters",
                    )
                }
                pending.remove(key)
            buffer = buffer[-131072:]
    return found
