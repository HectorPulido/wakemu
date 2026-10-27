"""Small native document headers with sealed, external record collections.

No whole-source read or fallback is allowed here. The publisher owns original
JSON order and transformations; the authoritative reader verifies its manifest.
"""
import json
from pathlib import Path

MAX_DOCUMENT_HEADER_BYTES = 64 * 1024


def is_native_json_mapping(value):
    """Recognize legacy dictionaries or authenticated raw publication views."""
    if isinstance(value, dict):
        return True
    from wakfu_server.combat_published_catalogs import static_catalog_descriptor

    return (
        static_catalog_descriptor(value) is not None
        and value.representation == "native_json"
    )


def _document_key(value):
    from wakfu_server import native_catalog

    if isinstance(value, Path) or (
        isinstance(value, str) and Path(value).is_absolute()
    ):
        key = native_catalog._key(value)
        if key is None:
            raise ValueError("Published document must belong to native catalog paths")
    else:
        key = value
    return native_catalog._published_document_name(key)


def _collection(publication, entry):
    from wakfu_server.native_compiled_catalog import descriptor_for
    from wakfu_server.combat_published_catalogs import resolve_static_catalog_descriptor

    if (
        type(entry) is not dict
        or entry.get("kind") != "dict"
        or type(entry.get("count")) is not int
        or entry["count"] < 0
    ):
        raise ValueError("Unsupported published native document collection shape")
    descriptor = descriptor_for(publication, entry["collection"])
    if (
        descriptor["count"] != entry["count"]
        or descriptor["ordered_keys_sha256"] != entry["ordered_keys_sha256"]
    ):
        raise ValueError("Native document collection differs from publication")
    result = resolve_static_catalog_descriptor(descriptor)
    if result.representation != "native_json":
        raise ValueError("Native document requires original JSON value types")
    return result


def load_published_document(path_or_logical_key):
    """Resolve a small root dictionary; original record values stay external.

    Logical transformed outputs and raw originals occupy distinct manifest
    namespaces. Runtime never recomputes a transformation or reads raw JSON.
    """
    from wakfu_server import native_catalog
    from wakfu_server.native_compiled_catalog import resolve_publication

    key = _document_key(path_or_logical_key)
    publication = resolve_publication(source_revision=native_catalog.release())
    matches = [
        rows[key]
        for namespace in ("documents", "raw_documents")
        if type(rows := publication.get(namespace, {})) is dict and key in rows
    ]
    if len(matches) != 1 or type(matches[0]) is not dict:
        raise ValueError("Missing or ambiguous published native document: " + key)
    entry = matches[0]
    if key in publication.get("raw_documents", {}):
        source = publication.get("source_documents", {}).get(key)
        if type(source) is not str or entry.get("source_sha256") != source:
            raise ValueError(
                "Published raw document differs from original source: " + key
            )
    if entry.get("root_kind") == "record_mapping":
        from wakfu_server.native_compiled_catalog import descriptor_for

        collection = entry["root_collection"]
        descriptor = descriptor_for(publication, collection)
        return _collection(
            publication,
            dict(
                kind="dict",
                collection=collection,
                count=descriptor["count"],
                ordered_keys_sha256=descriptor["ordered_keys_sha256"],
            ),
        )
    if entry.get("root_kind") != "dict":
        raise ValueError("Unsupported published native document root: " + key)
    layout, header, collections = (
        entry.get("layout"),
        entry.get("header"),
        entry.get("collections"),
    )
    if (
        type(layout) is not list
        or any(type(name) not in (str, int) for name in layout)
        or len(set(layout)) != len(layout)
        or type(header) is not dict
        or type(collections) is not dict
        or set(header) & set(collections)
        or set(layout) != set(header) | set(collections)
    ):
        raise ValueError("Incomplete published native document layout: " + key)
    ordered_header = entry.get("header_json")
    if type(ordered_header) is not str:
        raise ValueError("Missing original native metadata JSON order")
    header_bytes = ordered_header.encode("utf8")
    if len(header_bytes) > MAX_DOCUMENT_HEADER_BYTES:
        raise ValueError("Published native document metadata exceeds header bound")
    metadata = json.loads(ordered_header)
    if (
        type(metadata) is not dict
        or metadata != header
        or entry.get("header_bytes") != len(header_bytes)
    ):
        raise ValueError("Native metadata differs from original ordered JSON")
    # The manifest's canonical encoding sorts dictionary keys. Decode its
    # authenticated original header JSON to preserve nested source order and
    # private dict/list values without retaining a whole source document.
    return {
        name: (
            _collection(publication, collections[name])
            if name in collections
            else metadata[name]
        )
        for name in layout
    }
