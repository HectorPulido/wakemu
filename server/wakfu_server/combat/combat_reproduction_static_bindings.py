"""Diagnostic-only provenance for existing canonical immutable projections.

Observe already materialized published rows/lazy views by identity. Never search
for equal content, mutate a cache, or freeze an unobserved child during capture.
Resolvers use the existing pinned publication descriptor and verified reader.
"""

import json

POLICY = "wakemu.published-projection.v1"


class StaticProjectionBindings:
    def __init__(self):
        from . import combat_published_catalogs as published
        from . import combat_static_catalogs as static

        with published._LOCK:
            roots = {
                key: reference() for key, reference in published._LIVE_ROWS.items()
            }
            for key, entry in published._HOT_ROWS.items():
                roots.setdefault(key, entry[0])
        with static._VIEW_CACHE_LOCK:
            views = {
                identity: (entry[0](), dict(entry[1]))
                for identity, entry in static._VIEW_CACHE.items()
            }
        self._bindings = {}
        self._descriptors = {}
        self._verified_records = {}
        self._internals = {}
        pending = [
            (value, identity, ())
            for identity, value in sorted(roots.items())
            if value is not None
        ]
        while pending:
            value, identity, path = pending.pop()
            kind = type(value)
            if kind is not tuple and kind is not static.ImmutableCatalog:
                continue
            previous = self._bindings.get(id(value))
            if previous is not None:
                if previous[0] is not value:
                    raise ValueError(
                        "Immutable projection identity reused during capture"
                    )
                continue
            if kind is static.ImmutableCatalog:
                attrs = vars(value)
                if (
                    set(attrs) != {"_source", "_views"}
                    or type(attrs["_source"]) is not dict
                    or type(attrs["_views"]) is not dict
                    or attrs["_views"]
                ):
                    continue  # Extended/custom owners do not acquire provenance.
                self._mark_internals(attrs)
            self._bindings[id(value)] = (value, identity, path)
            if kind is tuple:
                pending.extend(
                    (child, identity, path + (("item", index),))
                    for index, child in enumerate(value)
                )
            else:
                materialized = views.get(id(value))
                if materialized is not None and materialized[0] is value:
                    pending.extend(
                        (child, identity, path + (("key", key),))
                        for key, child in materialized[1].items()
                        if type(key) in (str, int)
                    )

    def _mark_internals(self, attrs):
        pending = [attrs]
        while pending:
            value = pending.pop()
            if type(value) not in (dict, list):
                continue
            previous = self._internals.get(id(value))
            if previous is value:
                continue
            self._internals[id(value)] = value
            pending.extend(dict.values(value) if type(value) is dict else value)

    def descriptor(self, value):
        if self._internals.get(id(value)) is value:
            raise ValueError(
                "External alias into immutable catalog internals is unsupported"
            )
        binding = self._bindings.get(id(value))
        if binding is None or binding[0] is not value:
            return None
        _, identity, path = binding
        generation, collection, key = identity
        if type(key) is not str:
            raise ValueError("Unknown immutable published record key")
        pair = (generation, collection)
        catalog = self._descriptors.get(pair)
        if catalog is None:
            from wakfu_server import native_catalog
            from wakfu_server.native_compiled_catalog import (
                resolve_publication,
                descriptor_for,
            )

            header = resolve_publication(source_revision=native_catalog.release())
            if header["generation"] != generation:
                raise ValueError(
                    "Captured immutable source belongs to another publication"
                )
            catalog = descriptor_for(header, collection)
            self._descriptors[pair] = catalog
        expected = self._verified_records.get(identity)
        if expected is None:
            from wakfu_server.native_compiled_catalog import published_collection

            reader = published_collection(catalog)
            if reader.representation != "frozen_effect":
                raise ValueError("Projection lacks immutable published authority")
            # This reader verifies record bytes against the publication's SHA.
            expected = json.loads(reader.record_bytes(key))
            self._verified_records[identity] = expected
        for kind, part in path:
            if kind == "key" and type(expected) is dict and part in expected:
                expected = expected[part]
            elif (
                kind == "item" and type(expected) is list and 0 <= part < len(expected)
            ):
                expected = expected[part]
            else:
                raise ValueError("Captured immutable projection path differs")
        if not _matches_published(value, expected):
            raise ValueError("Canonical immutable projection was modified")
        return {
            "policy": POLICY,
            "catalog": dict(catalog),
            "record": key,
            "path": [list(step) for step in path],
        }


def _matches_published(value, expected):
    """Validate content and order, never use value equality to assign identity."""
    from .combat_static_catalogs import ImmutableCatalog

    pending = [(value, expected)]
    while pending:
        value, expected = pending.pop()
        if type(value) is ImmutableCatalog:
            attrs = vars(value)
            if (
                set(attrs) != {"_source", "_views"}
                or type(attrs["_source"]) is not dict
                or type(attrs["_views"]) is not dict
                or attrs["_views"]
            ):
                return False
            # Both actual backing dictionaries matter to full-state capture.
            pending.append((attrs["_source"], expected))
            value = dict(dict.items(value))
        if type(expected) is dict:
            if type(value) is not dict or any(type(key) is not str for key in value):
                return False
            if list(value) != list(expected):
                return False
            pending.extend((value[key], expected[key]) for key in expected)
        elif type(expected) is list:
            if type(value) not in (list, tuple) or len(value) != len(expected):
                return False
            pending.extend(zip(value, expected))
        elif type(value) is not type(expected) or type(value) not in (
            str,
            int,
            bool,
            float,
            type(None),
        ):
            return False
        elif value != expected:
            return False
    return True


def resolve_static_projection(descriptor):
    from .combat_published_catalogs import resolve_static_catalog_descriptor
    from .combat_static_catalogs import ImmutableCatalog

    if (
        type(descriptor) is not dict
        or set(descriptor) != {"policy", "catalog", "record", "path"}
        or descriptor["policy"] != POLICY
        or type(descriptor["record"]) is not str
        or type(descriptor["path"]) is not list
    ):
        raise ValueError("Invalid immutable projection descriptor")
    catalog = resolve_static_catalog_descriptor(descriptor["catalog"])
    if catalog.representation != "frozen_effect":
        raise ValueError("Only canonical frozen records have projection identity")
    value = catalog[descriptor["record"]]
    expected = json.loads(catalog._reader.record_bytes(descriptor["record"]))
    for step in descriptor["path"]:
        if type(step) is not list or len(step) != 2:
            raise ValueError("Invalid immutable projection step")
        kind, key = step
        if (
            kind == "key"
            and type(value) is ImmutableCatalog
            and type(key) in (str, int)
        ):
            value = value[key]
            if type(expected) is not dict or key not in expected:
                raise ValueError("Published immutable key path differs")
            expected = expected[key]
        elif (
            kind == "item"
            and type(value) is tuple
            and type(key) is int
            and 0 <= key < len(value)
        ):
            value = value[key]
            if type(expected) is not list or key >= len(expected):
                raise ValueError("Published immutable item path differs")
            expected = expected[key]
        else:
            raise ValueError("Immutable projection path differs")
    if type(value) not in (ImmutableCatalog, tuple):
        raise ValueError("Projection is not a canonical immutable owner")
    if not _matches_published(value, expected):
        raise ValueError("Resolved immutable projection was modified")
    return value
