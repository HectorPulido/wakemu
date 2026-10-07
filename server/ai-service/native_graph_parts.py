"""Experimental lossless partitioning of complete native graphs.

Opt-in only in the live transport. Immutable terrain is a complete CAS graph,
with an explicit local-to-global identity map; every other node remains in the
state manifest. restore() materializes the complete flat graph as a reference;
read_parts() exposes all verified nodes through a virtual identity index.
"""
from copy import deepcopy
from collections import OrderedDict
from collections.abc import Sequence
import hashlib
import json
import threading

if __package__:
    from .native_context import NativeGraph
else:
    from native_context import NativeGraph


FORMAT = "wakfu-native-graph-parts-1"
TERRAIN = {
    "module": "wakfu_server.combat_geometry_snapshot",
    "name": "ImmutableTerrainSet",
}
_BLOBS = OrderedDict()
_BLOB_LOCK = threading.RLock()
_READ_BLOBS = OrderedDict()


def _verified_blob(digest, read_blob):
    try:
        body = read_blob(digest)
    except (OSError, KeyError) as error:
        raise ValueError("Missing native fragment content") from error
    if type(body) is not bytes or hashlib.sha256(body).hexdigest() != digest:
        raise ValueError("Native fragment checksum mismatch")
    with _BLOB_LOCK:
        cached = _READ_BLOBS.get(digest)
        if cached is not None and cached[0] == body:
            _READ_BLOBS.move_to_end(digest)
            return cached[1]
    try:
        graph = json.loads(body)
    except (ValueError, UnicodeError) as error:
        raise ValueError("Invalid native fragment graph") from error
    NativeGraph(graph)
    if _bytes(graph) != body:
        raise ValueError("Noncanonical native fragment graph")
    if graph["root"] != {"ref": 0} or _terrain_ids(graph["nodes"], 0) != list(
        range(len(graph["nodes"]))
    ):
        raise ValueError("Incomplete or unsupported native fragment graph")
    with _BLOB_LOCK:
        _READ_BLOBS[digest] = body, graph
        _READ_BLOBS.move_to_end(digest)
        while len(_READ_BLOBS) > 32:
            _READ_BLOBS.popitem(last=False)
    return graph


class _VirtualNodes(Sequence):
    """Complete node index, resolving verified immutable rows on demand."""

    def __init__(self, owners):
        self._owners = owners

    def __len__(self):
        return len(self._owners)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[value] for value in range(*index.indices(len(self)))]
        if type(index) is not int:
            raise TypeError("Native node index must be an integer")
        if index < 0:
            index += len(self)
        if not 0 <= index < len(self):
            raise IndexError(index)
        node, indices = self._owners[index]
        return deepcopy(node) if indices is None else _remap(node, indices)

    def __iter__(self):
        return (self[index] for index in range(len(self)))


def read_parts(manifest, read_blob):
    """Validate every byte and identity, expose full nodes without flattening.

    Fragment cache contents never escape: resolved rows are private copies.
    Dynamic schemas and references use the ordinary NativeGraph validator;
    immutable schemas are validated once per verified complete blob.
    """
    if (
        isinstance(manifest, dict)
        and manifest.get("encoding") == "wakfu-native-graph-1"
    ):
        return NativeGraph(deepcopy(manifest))
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"encoding", "root", "nodeCount", "dynamic", "fragments"}
        or manifest["encoding"] != FORMAT
        or type(manifest["nodeCount"]) is not int
        or manifest["nodeCount"] < 0
        or not isinstance(manifest["dynamic"], list)
        or not isinstance(manifest["fragments"], list)
    ):
        raise ValueError("Invalid native parts manifest")
    count, owners, aliases, dynamic = manifest["nodeCount"], {}, [], []

    def own(identity, node, indices):
        if type(identity) is not int or not 0 <= identity < count or identity in owners:
            raise ValueError("Duplicate or invalid native parts identity")
        owners[identity] = node, indices

    for row in manifest["dynamic"]:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("Invalid native dynamic node")
        node = deepcopy(row[1])
        own(row[0], node, None)
        dynamic.append(node)
    for fragment in manifest["fragments"]:
        if (
            not isinstance(fragment, dict)
            or set(fragment) != {"sha256", "indices", "emitted"}
            or type(fragment["sha256"]) is not str
            or len(fragment["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in fragment["sha256"])
        ):
            raise ValueError("Invalid native fragment descriptor")
        graph = _verified_blob(fragment["sha256"], read_blob)
        length = len(graph["nodes"])
        indices = _unpack(
            fragment["indices"],
            bound=count,
            maximum_count=length,
            expected_count=length,
        )
        emitted = _unpack(fragment["emitted"], bound=length, maximum_count=length)
        if len(set(indices)) != length or len(set(emitted)) != len(emitted):
            raise ValueError("Invalid native fragment identity map")
        emitted = set(emitted)
        for local, node in enumerate(graph["nodes"]):
            if local in emitted:
                own(indices[local], node, indices)
            else:
                aliases.append((indices[local], node, indices))
    if len(owners) != count:
        raise ValueError("Incomplete native parts node ownership")
    nodes = _VirtualNodes(owners)
    for identity, node, indices in aliases:
        if _bytes(nodes[identity]) != _bytes(_remap(node, indices)):
            raise ValueError("Conflicting native fragment alias")
    return NativeGraph(
        dict(
            encoding="wakfu-native-graph-1",
            root=deepcopy(manifest["root"]),
            nodes=nodes,
        ),
        _validation_nodes=dynamic,
    )


def load_graph(store, digest):
    encoded = store.json(digest)
    if isinstance(encoded, dict) and encoded.get("encoding") == FORMAT:
        return read_parts(encoded, store.read)
    return NativeGraph(encoded)


def _fragment_blob(fragment):
    """Cache complete immutable bytes only; global identity maps stay fresh."""
    if __package__:
        from .native_deadline import check
        from .native_geometry_fragments import _locked
    else:
        from native_deadline import check
        from native_geometry_fragments import _locked
    check()
    key = id(fragment)
    with _locked(_BLOB_LOCK):
        cached = _BLOBS.get(key)
        if cached is not None and cached[0] is fragment:
            _BLOBS.move_to_end(key)
            return cached[1:]
    local = tuple(range(len(fragment.objects)))
    rows = []
    for index, template in enumerate(fragment.templates):
        if index % 1024 == 0:
            check()
        rows.append(template.format(local))
    body = (
        '{"encoding":"wakfu-native-graph-1","root":{"ref":0},"nodes":['
        + ",".join(rows)
        + "]}"
    ).encode()
    digest = hashlib.sha256(body).hexdigest()
    check()
    with _locked(_BLOB_LOCK):
        _BLOBS[key] = (fragment, digest, body)
        _BLOBS.move_to_end(key)
        while len(_BLOBS) > 32:
            _BLOBS.popitem(last=False)
    return digest, body


def fragment_descriptor(fragment, identities, next_index, digest):
    """Describe a verified cached terrain blob without rendering global nodes.

    The caller provisions the COMPLETE local blob and its verified digest.
    This helper only assigns identity maps; it neither uploads nor activates
    the experimental wire format. A reserved root must still be emitted.
    """
    if (
        type(digest) is not str
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise ValueError("Invalid native fragment digest")
    indices, following, assignments, emitted = fragment.identity_map(
        identities, next_index
    )
    descriptor = dict(
        sha256=digest,
        indices=_pack(indices),
        emitted=_pack(
            [local for local in range(len(indices)) if local == 0 or local in emitted]
        ),
    )
    return descriptor, following, assignments


def encode_parts(value):
    """Experimental direct encoder; complete local blobs accompany manifest.

    Never constructs global terrain node JSON. Production transport still
    uses encode_bytes; this path exists for differential validation first.
    """
    if __package__:
        from .native_context import _encode
    else:
        from native_context import _encode

    class Parts:
        def __init__(self):
            self.fragments, self.blobs = [], {}

        def add(self, fragment, identities, next_index):
            digest, body = _fragment_blob(fragment)
            self.blobs[digest] = body
            descriptor, following, assignments = fragment_descriptor(
                fragment, identities, next_index, digest
            )
            self.fragments.append(descriptor)
            return following, assignments

        def finish(self, root, nodes):
            if __package__:
                from .native_deadline import check
            else:
                from native_deadline import check
            dynamic = []
            for index, node in enumerate(nodes):
                if index % 1024 == 0:
                    check()
                if node is not None:
                    dynamic.append([index, json.loads(node)])
            if not self.fragments:
                return (
                    dict(
                        encoding="wakfu-native-graph-1",
                        root=root,
                        nodes=[node for _, node in dynamic],
                    ),
                    {},
                )
            return (
                dict(
                    encoding=FORMAT,
                    root=root,
                    nodeCount=len(nodes),
                    dynamic=dynamic,
                    fragments=self.fragments,
                ),
                self.blobs,
            )

    return _encode(value, serialize_nodes=True, _parts=Parts())


def _bytes(value):
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode()


def _pack(values):
    """Encode every identity as consecutive runs, without merging identities."""
    runs = []
    for value in values:
        if runs and runs[-1][0] + runs[-1][1] == value:
            runs[-1][1] += 1
        else:
            runs.append([value, 1])
    return dict(count=len(values), runs=runs)


def _unpack(encoded, *, bound, maximum_count, expected_count=None):
    if (
        not isinstance(encoded, dict)
        or set(encoded) != {"count", "runs"}
        or type(encoded["count"]) is not int
        or not 0 <= encoded["count"] <= maximum_count
        or expected_count is not None
        and encoded["count"] != expected_count
        or not isinstance(encoded["runs"], list)
    ):
        raise ValueError("Invalid native fragment identity map")
    total = 0
    for run in encoded["runs"]:
        if (
            not isinstance(run, list)
            or len(run) != 2
            or any(type(value) is not int for value in run)
            or run[0] < 0
            or run[1] <= 0
            or run[0] + run[1] > bound
        ):
            raise ValueError("Invalid native fragment identity map")
        total += run[1]
        if total > encoded["count"]:
            raise ValueError("Invalid native fragment identity map")
    if total != encoded["count"]:
        raise ValueError("Invalid native fragment identity map")
    return [
        value
        for start, length in encoded["runs"]
        for value in range(start, start + length)
    ]


def _terrain_ids(nodes, root):
    """Return complete identity order only for the known immutable schema."""
    node = nodes[root]
    if (
        set(node) != {"type", "items", "nativeClass", "fields"}
        or node["type"] != "frozenset"
        or node["nativeClass"] != TERRAIN
        or node["fields"] != {}
    ):
        return None
    order, seen, visiting = [root], {root}, set()

    def visit(identity):
        if identity == root:
            return False
        if identity in visiting:
            return False
        if identity in seen:
            return True
        value = nodes[identity]
        if set(value) != {"type", "items"} or value["type"] != "tuple":
            return False
        seen.add(identity)
        visiting.add(identity)
        order.append(identity)
        for child in value["items"]:
            if "ref" in child:
                if not visit(child["ref"]):
                    return False
            elif type(child["value"]) is not int:
                return False
        visiting.remove(identity)
        return True

    try:
        for child in node["items"]:
            if "ref" not in child or not visit(child["ref"]):
                return None
        return order
    finally:
        visit = None


def _remap(node, indices):
    """Translate every reference in an eligible node; preserve field order."""
    result = deepcopy(node)
    result["items"] = [
        {"ref": indices[value["ref"]]} if "ref" in value else deepcopy(value)
        for value in node["items"]
    ]
    return result


def partition(graph):
    """Return a complete manifest and all raw CAS blobs, without mutation."""
    NativeGraph(graph)
    nodes, claimed, fragments, blobs = graph["nodes"], set(), [], {}
    for root, node in enumerate(nodes):
        if root in claimed:
            continue
        identities = _terrain_ids(nodes, root)
        if identities is None:
            continue
        local = {global_id: index for index, global_id in enumerate(identities)}
        body = _bytes(
            dict(
                encoding="wakfu-native-graph-1",
                root={"ref": 0},
                nodes=[_remap(nodes[identity], local) for identity in identities],
            )
        )
        digest = hashlib.sha256(body).hexdigest()
        blobs[digest] = body
        emitted = [
            index
            for index, identity in enumerate(identities)
            if identity not in claimed
        ]
        claimed.update(identities)
        fragments.append(
            dict(sha256=digest, indices=_pack(identities), emitted=_pack(emitted))
        )
    if not fragments:
        return deepcopy(graph), {}
    return (
        dict(
            encoding=FORMAT,
            root=deepcopy(graph["root"]),
            nodeCount=len(nodes),
            dynamic=[
                [index, deepcopy(node)]
                for index, node in enumerate(nodes)
                if index not in claimed
            ],
            fragments=fragments,
        ),
        blobs,
    )


def restore(manifest, read_blob):
    """Verify every blob/identity/alias and reconstruct the complete flat graph."""
    if not isinstance(manifest, dict):
        raise ValueError("Invalid native parts manifest")
    if manifest.get("encoding") == "wakfu-native-graph-1":
        NativeGraph(manifest)
        return deepcopy(manifest)
    if (
        set(manifest) != {"encoding", "root", "nodeCount", "dynamic", "fragments"}
        or manifest["encoding"] != FORMAT
        or type(manifest["nodeCount"]) is not int
        or manifest["nodeCount"] < 0
        or not isinstance(manifest["dynamic"], list)
        or not isinstance(manifest["fragments"], list)
    ):
        raise ValueError("Invalid native parts manifest")
    count, owners, aliases = manifest["nodeCount"], {}, []

    def own(identity, node):
        if type(identity) is not int or not 0 <= identity < count or identity in owners:
            raise ValueError("Duplicate or invalid native parts identity")
        owners[identity] = node

    for row in manifest["dynamic"]:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("Invalid native dynamic node")
        own(row[0], deepcopy(row[1]))
    for fragment in manifest["fragments"]:
        if (
            not isinstance(fragment, dict)
            or set(fragment) != {"sha256", "indices", "emitted"}
            or not isinstance(fragment["sha256"], str)
            or len(fragment["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in fragment["sha256"])
            or not isinstance(fragment["indices"], dict)
            or not isinstance(fragment["emitted"], dict)
        ):
            raise ValueError("Invalid native fragment descriptor")
        try:
            body = read_blob(fragment["sha256"])
        except (OSError, KeyError) as error:
            raise ValueError("Missing native fragment content") from error
        if (
            type(body) is not bytes
            or hashlib.sha256(body).hexdigest() != fragment["sha256"]
        ):
            raise ValueError("Native fragment checksum mismatch")
        try:
            graph = json.loads(body)
        except (ValueError, UnicodeError) as error:
            raise ValueError("Invalid native fragment graph") from error
        NativeGraph(graph)
        fragment_count = len(graph["nodes"])
        indices = _unpack(
            fragment["indices"],
            bound=count,
            maximum_count=fragment_count,
            expected_count=fragment_count,
        )
        emitted = _unpack(
            fragment["emitted"], bound=fragment_count, maximum_count=fragment_count
        )
        if len(set(indices)) != len(indices) or len(set(emitted)) != len(emitted):
            raise ValueError("Invalid native fragment identity map")
        if (
            graph["root"] != {"ref": 0}
            or not indices
            or _terrain_ids(graph["nodes"], 0) != list(range(len(indices)))
        ):
            raise ValueError("Incomplete or unsupported native fragment graph")
        emitted = set(emitted)
        for local, node in enumerate(graph["nodes"]):
            mapped = _remap(node, indices)
            identity = indices[local]
            if local in emitted:
                own(identity, mapped)
            else:
                aliases.append((identity, mapped))
    # Check complete ownership before allocating a declared nodeCount. No
    # field/node is omitted and a forged huge count cannot request that memory.
    if len(owners) != count:
        raise ValueError("Incomplete native parts node ownership")
    for identity, expected in aliases:
        if _bytes(owners.get(identity)) != _bytes(expected):
            raise ValueError("Conflicting native fragment alias")
    graph = dict(
        encoding="wakfu-native-graph-1",
        root=deepcopy(manifest["root"]),
        nodes=[owners[index] for index in range(count)],
    )
    NativeGraph(graph)
    return graph
