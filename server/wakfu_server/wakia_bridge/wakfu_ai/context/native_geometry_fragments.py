"""Byte-identical cached fragments for the canonical immutable terrain type."""
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
import importlib
import json
import threading

try:
    from ..native.native_deadline import check, remaining
except ImportError:
    from ..native.native_deadline import check, remaining


_CACHE_LIMIT = 32
_TERRAIN_MODULE = "wakfu_server.combat_geometry_snapshot"
_TERRAIN_QUALNAME = "ImmutableTerrainSet"
_CACHE_LOCK = threading.RLock()
_CACHE = OrderedDict()
_BUILD_LOCKS = {}


@contextmanager
def _locked(lock, *, cleanup=False):
    """Acquire a lock without waiting beyond the current owner deadline."""
    if not cleanup:
        check()
    try:
        available = remaining() if not cleanup else None
    except TimeoutError:
        if not cleanup:
            raise
        available = None
    if available is None:
        lock.acquire()
    elif not lock.acquire(timeout=available):
        if not cleanup:
            check()
        raise TimeoutError(
            "Native AI turn deadline reached while waiting for geometry cache"
        )
    try:
        if not cleanup:
            check()
        yield
    finally:
        lock.release()


def _canonical_terrain_type(item):
    if _descriptor(item) != (_TERRAIN_MODULE, _TERRAIN_QUALNAME):
        return None
    try:
        module = importlib.import_module(_TERRAIN_MODULE)
        return getattr(module, _TERRAIN_QUALNAME)
    except (ImportError, AttributeError):
        return None


@dataclass(frozen=True)
class _RefToken:
    index: int


@dataclass(frozen=True)
class _NodeTemplate:
    prefix: str = ""
    items: tuple = ()
    suffix: str = ""
    literal: str = ""

    def format(self, refmap):
        if self.literal:
            return self.literal
        check()
        encoded = []
        for index, value in enumerate(self.items):
            if index % 1024 == 0:
                check()
            if isinstance(value, _RefToken):
                try:
                    target = refmap[value.index]
                except (IndexError, KeyError, TypeError) as error:
                    raise ValueError(
                        "Incomplete native geometry fragment reference map"
                    ) from error
                if type(target) is not int or target < 0:
                    raise ValueError("Invalid native geometry fragment target")
                encoded.append('{"ref":' + str(target) + "}")
            elif type(value) is int:
                encoded.append('{"value":' + str(value) + "}")
            else:
                raise ValueError("Invalid native geometry fragment token")
        return self.prefix + ",".join(encoded) + self.suffix


@dataclass(frozen=True)
class GeometryFragment:
    root: object
    descriptor: tuple
    objects: tuple
    templates: tuple
    _encoded_size: int | None

    @property
    def encoded_size(self):
        if self._encoded_size is not None:
            return self._encoded_size
        # Size is diagnostic metadata. Production has already verified every
        # emitted row, so it need not serialize an independent graph again
        # merely to count bytes while constructing a cold cache entry.
        refmap = tuple(range(len(self.objects)))
        body = (
            '{"encoding":"wakfu-native-graph-1","root":{"ref":0},"nodes":['
            + ",".join(template.format(refmap) for template in self.templates)
            + "]}"
        )
        return len(body.encode())

    @property
    def root_index(self):
        return 0

    def identity_map(self, identities, next_index):
        """Assign complete DFS identities without rendering terrain nodes."""
        if (
            not isinstance(identities, dict)
            or type(next_index) is not int
            or next_index < 0
        ):
            raise ValueError("Invalid native geometry rebase inputs")
        refmap, new_pairs, new_local = [], [], set()
        following = next_index
        for local, item in enumerate(self.objects):
            if local % 1024 == 0:
                check()
            identity = id(item)
            if identity in identities:
                global_index = identities[identity]
                if type(global_index) is not int or not 0 <= global_index < next_index:
                    raise ValueError("Invalid existing native graph identity")
            else:
                global_index = following
                following += 1
                new_pairs.append((identity, global_index))
                new_local.add(local)
            refmap.append(global_index)
        check()
        return tuple(refmap), following, tuple(new_pairs), frozenset(new_local)

    def rebase(self, identities, next_index):
        """Rebase DFS identities without merging equal-but-distinct objects."""
        refmap, following, new_pairs, new_local = self.identity_map(
            identities, next_index
        )
        rendered = []
        for local, template in enumerate(self.templates):
            if local % 1024 == 0:
                check()
            if local == 0 or local in new_local:
                rendered.append((refmap[local], template.format(refmap)))
        check()
        return refmap[0], following, tuple(new_pairs), tuple(rendered)


def _descriptor(item):
    kind = type(item)
    return kind.__module__, kind.__qualname__


@lru_cache(maxsize=16384)
def _int_tuple_literal(values):
    """Canonical JSON for an exact tuple of ints; bytes never encode identity."""
    check()
    if type(values) is not tuple:
        raise ValueError("Expected an exact integer tuple")
    items = []
    for index, value in enumerate(values):
        if index % 1024 == 0:
            check()
        if type(value) is not int:
            raise ValueError("Expected an exact integer tuple")
        items.append('{"value":' + str(value) + "}")
    return '{"type":"tuple","items":[' + ",".join(items) + "]}"


def cached_int_tuple_values(item):
    """Return canonical node bytes for exact-int tuples, validating before LRU lookup."""
    check()
    if type(item) is not tuple:
        return None
    for index, value in enumerate(item):
        if index % 1024 == 0:
            check()
        if type(value) is not int:
            return None
    # functools.lru_cache can return without entering _int_tuple_literal;
    # still enforce the current owner's deadline immediately before lookup.
    check()
    return _int_tuple_literal(item)


def cached_int_tuple_node(item, node):
    """Return known-schema tuple bytes only when node fully matches item."""
    check()
    if (
        type(item) is not tuple
        or type(node) is not dict
        or list(node.keys()) != ["type", "items"]
        or type(node.get("type")) is not str
        or node["type"] != "tuple"
        or type(node.get("items")) is not list
        or len(node["items"]) != len(item)
    ):
        return None
    for index, child in enumerate(node["items"]):
        if index % 1024 == 0:
            check()
        if type(child) is not dict or list(child.keys()) != ["value"]:
            return None
    for index, child in enumerate(node["items"]):
        if index % 1024 == 0:
            check()
        if (
            type(item[index]) is not int
            or type(child["value"]) is not int
            or child["value"] != item[index]
        ):
            return None
    # Eligibility must precede the LRU lookup: arbitrary complete tuples can
    # contain mutable values or objects with custom hash implementations.
    return _int_tuple_literal(item)


def _eligible_root(item, terrain_type, instance_fields):
    if type(item) is not terrain_type:
        return False
    if terrain_type.__iter__ is not frozenset.__iter__:
        return False
    if type(iter(item)) is not type(iter(frozenset())):
        return False
    fields = instance_fields(item)
    return isinstance(fields, dict) and not fields


def _members(item):
    try:
        check()
        # Exact frozenset iteration is the canonical serializer's ordering
        # source; sorting here is required to reproduce that wire order.
        members = sorted(item)
        check()
        return tuple(members)
    except (TypeError, ValueError):
        return None


def _build_objects(item, members):
    objects = [item]
    identities = {id(item): 0}
    visits = 0

    def visit(value):
        nonlocal visits
        visits += 1
        if visits % 1024 == 0:
            check()
        if type(value) is int:
            return
        if type(value) is not tuple:
            raise ValueError("Native terrain contains a non-tuple value")
        identity = id(value)
        if identity in identities:
            return
        identities[identity] = len(objects)
        objects.append(value)
        for child in value:
            visit(child)

    try:
        for index, member in enumerate(members):
            if index % 1024 == 0:
                check()
            visit(member)
    except ValueError:
        return None
    finally:
        # Break visit's self-closure so the temporary id map and object list
        # are released promptly instead of waiting for cyclic GC.
        visit = None
    return tuple(objects), identities


def _node_template(
    index, item, identities, encoded_node, descriptor, members, node_encoder
):
    if index == 0:
        expected = {"type", "items", "nativeClass", "fields"}
        if (
            not isinstance(encoded_node, dict)
            or set(encoded_node) != expected
            or encoded_node.get("type") != "frozenset"
            or encoded_node.get("nativeClass")
            != {"module": descriptor[0], "name": descriptor[1]}
            or encoded_node.get("fields") != {}
        ):
            return None
        children_list = []
        for offset, value in enumerate(members):
            if offset % 1024 == 0:
                check()
            if type(value) is not tuple:
                return None
            children_list.append(_RefToken(identities[id(value)]))
        children = tuple(children_list)
        prefix = '{"type":"frozenset","items":['
        suffix = (
            '],"nativeClass":'
            + node_encoder.encode({"module": descriptor[0], "name": descriptor[1]})
            + ',"fields":{}}'
        )
        template = _NodeTemplate(prefix, children, suffix)
    else:
        if (
            type(item) is not tuple
            or not isinstance(encoded_node, dict)
            or set(encoded_node) != {"type", "items"}
            or encoded_node.get("type") != "tuple"
        ):
            return None
        children = []
        for offset, value in enumerate(item):
            if offset % 1024 == 0:
                check()
            if type(value) is int:
                children.append(value)
            elif type(value) is tuple:
                children.append(_RefToken(identities[id(value)]))
            else:
                return None
    refs = encoded_node.get("items")
    if not isinstance(refs, list) or len(refs) != len(children):
        return None
    for offset, (ref, expected_child) in enumerate(zip(refs, children)):
        if offset % 1024 == 0:
            check()
        if isinstance(expected_child, _RefToken):
            if ref != {"ref": expected_child.index}:
                return None
        elif ref != {"value": expected_child}:
            return None
    if index != 0 and all(type(value) is int for value in item):
        # Coordinate leaf nodes are immutable and their complete bytes do not
        # depend on rebased references. Reuse the validated wire node.
        literal = node_encoder.encode(encoded_node)
        return _NodeTemplate(literal=literal)
    if index != 0:
        template = _NodeTemplate('{"type":"tuple","items":[', tuple(children), "]}")
    return template


def _make_fragment(item, descriptor, encode_complete, members):
    check()
    built = _build_objects(item, members)
    if built is None:
        return None
    objects, identities = built
    encoded = encode_complete(item)
    check()
    if type(encoded) is not bytes:
        return None
    try:
        graph = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if (
        not isinstance(graph, dict)
        or set(graph) != {"encoding", "root", "nodes"}
        or graph.get("encoding") != "wakfu-native-graph-1"
        or graph.get("root") != {"ref": 0}
        or not isinstance(graph.get("nodes"), list)
        or len(graph["nodes"]) != len(objects)
    ):
        return None
    node_encoder = json.JSONEncoder(separators=(",", ":"), allow_nan=False)
    templates = []
    for index, obj in enumerate(objects):
        if index % 1024 == 0:
            check()
        template = _node_template(
            index,
            obj,
            identities,
            graph["nodes"][index],
            descriptor,
            members,
            node_encoder,
        )
        if template is None:
            return None
        templates.append(template)
    fragment = GeometryFragment(
        item, descriptor, objects, tuple(templates), len(encoded)
    )
    # Rebase once to verify the exact wrapper, key order and serialized node
    # bytes. This accepts only the complete canonical form without re-dumping
    # the entire parsed graph.
    _, following, _, rows = fragment.rebase({}, 0)
    if following != len(objects) or len(rows) != len(objects):
        return None
    if any(index != expected for expected, (index, _) in enumerate(rows)):
        return None
    rebuilt = (
        '{"encoding":"wakfu-native-graph-1","root":{"ref":0},"nodes":['
        + ",".join(node for _, node in rows)
        + "]}"
    ).encode()
    if rebuilt != encoded:
        return None
    return fragment


def _lookup(item, descriptor):
    key = (id(item), descriptor)
    with _locked(_CACHE_LOCK):
        cached = _CACHE.get(key)
        if (
            cached is not None
            and cached.root is item
            and cached.descriptor == descriptor
        ):
            _CACHE.move_to_end(key)
            return cached
    return None


def _build_record(key):
    with _locked(_CACHE_LOCK):
        lock_record = _BUILD_LOCKS.get(key)
        if lock_record is None:
            lock_record = [threading.Lock(), 0]
            _BUILD_LOCKS[key] = lock_record
        lock_record[1] += 1
    return lock_record


def _release_build_record(key, lock_record):
    # Cleanup must complete even after the owner deadline expired.
    with _locked(_CACHE_LOCK, cleanup=True):
        lock_record[1] -= 1
        if lock_record[1] == 0 and _BUILD_LOCKS.get(key) is lock_record:
            del _BUILD_LOCKS[key]


def _publish(key, fragment):
    check()
    with _locked(_CACHE_LOCK):
        cached = _CACHE.get(key)
        if (
            cached is not None
            and cached.root is fragment.root
            and cached.descriptor == fragment.descriptor
        ):
            _CACHE.move_to_end(key)
            return cached
        _CACHE[key] = fragment
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_LIMIT:
            check()
            _CACHE.popitem(last=False)
        return fragment


def _template_from_native_nodes(
    item, descriptor, objects, local_identities, members, global_indices, nodes
):
    """Build and verify templates against nodes emitted by the main encoder."""
    node_encoder = json.JSONEncoder(separators=(",", ":"), allow_nan=False)
    templates = []
    for local, obj in enumerate(objects):
        if local % 1024 == 0:
            check()
        global_index = global_indices[local]
        if global_index >= len(nodes) or type(nodes[global_index]) is not str:
            return None
        if local:
            # Coordinate leaves have no reference tokens. Validate their
            # complete canonical bytes before building a template that would
            # immediately be discarded. Nested tuples keep the reference
            # path, without throwing a ValueError for every directed edge.
            literal = cached_int_tuple_values(obj)
            if literal is not None:
                if literal != nodes[global_index]:
                    return None
                templates.append(_NodeTemplate(literal=nodes[global_index]))
                continue
        if local == 0:
            if any(type(value) is not tuple for value in members):
                return None
            children = tuple(
                _RefToken(local_identities[id(value)]) for value in members
            )
            template = _NodeTemplate(
                '{"type":"frozenset","items":[',
                children,
                '],"nativeClass":'
                + node_encoder.encode({"module": descriptor[0], "name": descriptor[1]})
                + ',"fields":{}}',
            )
        else:
            if type(obj) is not tuple:
                return None
            children = []
            for offset, value in enumerate(obj):
                if offset % 1024 == 0:
                    check()
                if type(value) is int:
                    children.append(value)
                elif type(value) is tuple and id(value) in local_identities:
                    children.append(_RefToken(local_identities[id(value)]))
                else:
                    return None
            template = _NodeTemplate('{"type":"tuple","items":[', tuple(children), "]}")

        # Exact rendered-byte comparison checks known schema and key order;
        # new fields or encoder changes safely fall back to ordinary encoding.
        if template.format(global_indices) != nodes[global_index]:
            return None
        templates.append(template)

    return GeometryFragment(item, descriptor, objects, tuple(templates), None)


def cache_fragment_from_encoded(item, identities, nodes, instance_fields):
    """Cache an eligible fragment from nodes the complete encoder just wrote.

    This cold path performs no second terrain serialization and no whole-graph
    JSON parse. The node templates are accepted only if they reproduce the
    original encoder rows byte for byte using current graph identities.
    """
    check()
    terrain_type = _canonical_terrain_type(item)
    if terrain_type is None or not _eligible_root(item, terrain_type, instance_fields):
        return None
    if not isinstance(identities, dict) or not isinstance(nodes, list):
        return None
    descriptor = _descriptor(item)
    key = (id(item), descriptor)
    cached = _lookup(item, descriptor)
    if cached is not None:
        return cached
    lock_record = _build_record(key)
    try:
        with _locked(lock_record[0]):
            check()
            if not _eligible_root(item, terrain_type, instance_fields):
                return None
            cached = _lookup(item, descriptor)
            if cached is not None:
                return cached
            members = _members(item)
            if members is None:
                return None
            built = _build_objects(item, members)
            if built is None:
                return None
            objects, local_identities = built
            global_indices = []
            for index, obj in enumerate(objects):
                if index % 1024 == 0:
                    check()
                global_index = identities.get(id(obj))
                if (
                    type(global_index) is not int
                    or global_index < 0
                    or global_index >= len(nodes)
                ):
                    return None
                global_indices.append(global_index)
            if len(set(global_indices)) != len(global_indices):
                return None
            fragment = _template_from_native_nodes(
                item,
                descriptor,
                objects,
                local_identities,
                members,
                global_indices,
                nodes,
            )
            if fragment is None:
                return None
            return _publish(key, fragment)
    finally:
        _release_build_record(key, lock_record)


def get_fragment(item, encode_complete, instance_fields, *, build=True):
    """Return an exact cached terrain fragment, or None for fallback encoding.

    Unknown/future graph schemas and terrain fields deliberately take the full
    encoder path. The encoder callback must be uncached and return complete
    canonical graph bytes.
    """
    if type(build) is not bool:
        raise ValueError("Invalid native geometry fragment build mode")
    check()
    terrain_type = _canonical_terrain_type(item)
    if terrain_type is None:
        return None
    if not _eligible_root(item, terrain_type, instance_fields):
        return None
    descriptor = _descriptor(item)
    key = (id(item), descriptor)
    cached = _lookup(item, descriptor)
    if cached is not None or not build:
        return cached
    lock_record = _build_record(key)
    try:
        with _locked(lock_record[0]):
            check()
            if not _eligible_root(item, terrain_type, instance_fields):
                return None
            cached = _lookup(item, descriptor)
            if cached is not None:
                return cached
            members = _members(item)
            if members is None:
                return None
            fragment = _make_fragment(item, descriptor, encode_complete, members)
            if fragment is None:
                return None
            check()
            return _publish(key, fragment)
    finally:
        _release_build_record(key, lock_record)
