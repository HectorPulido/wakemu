"""Reuse the combat variants when only unrelated native item data changed.

All variants share retained effect definitions, so they are reused as one
unit. An unknown change, configuration or incomplete publication is a miss.
"""

import hashlib
import json

# These two documents are consumed by item recycling/exchange, not by any of
# the four eager effect compilers. They are still published as raw documents.
INDEPENDENT_DOCUMENTS = frozenset(
    {
        "item-recycling-metadata.json",
        "item-exchange-metadata.json",
    }
)


def _safe_config(value, changed):
    if value is None or isinstance(value, (bool, int, float)):
        return True
    if isinstance(value, str):
        if any(name in value for name in changed):
            return False
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            # Plain identifiers and labels cannot name an independent source
            # unless its complete document name occurs in the value.
            return True
        return parsed != value and _safe_config(parsed, changed)
    if isinstance(value, list):
        return all(_safe_config(item, changed) for item in value)
    if isinstance(value, dict):
        return all(_safe_config(item, changed) for item in value.values())
    return False


def compatible(previous, current):
    """Allow only known item-only changes with identical compiler/config."""
    if any(
        previous.get(key) != current.get(key)
        for key in ("policy", "compiler_contract_sha256", "config_sha256", "config")
    ):
        return False
    old, new = previous.get("source_documents"), current.get("source_documents")
    if (
        not isinstance(old, dict)
        or not isinstance(new, dict)
        or old.keys() != new.keys()
    ):
        return False
    changed = {name for name in old if old[name] != new[name]}
    return (
        bool(changed)
        and changed <= INDEPENDENT_DOCUMENTS
        and _safe_config(current.get("config"), changed)
    )


def reuse(spool, identity):
    """Attach sealed variants without reading their individual records."""
    from wakfu_server import native_catalog
    from wakfu_server.native_compiled_catalog import canonical_bytes

    with native_catalog._database().connection() as db:
        view = db.execute(
            "SELECT relkind FROM pg_class WHERE oid=to_regclass('native_compiled_catalog_records')"
        ).fetchone()
        if not view or view["relkind"] != "v":
            return None
        candidates = db.execute(
            "SELECT generation,manifest_raw,manifest FROM native_compiled_catalog_releases "
            "WHERE complete AND policy=%s AND compiler_contract_sha256=%s AND config_sha256=%s "
            "ORDER BY completed_at DESC LIMIT 5",
            (
                identity["policy"],
                identity["compiler_contract_sha256"],
                identity["config_sha256"],
            ),
        ).fetchall()
        for candidate in candidates:
            raw, manifest = bytes(candidate["manifest_raw"]), candidate["manifest"]
            if (
                hashlib.sha256(raw).hexdigest() != candidate["generation"]
                or canonical_bytes(manifest) != raw
                or not compatible(manifest, identity)
            ):
                continue
            variants, output = manifest.get("variants"), manifest.get(
                "original_output_index"
            )
            if (
                not isinstance(variants, dict)
                or set(variants) != {"player", "npc_imported", "npc_baseline", "weapon"}
                or not isinstance(output, dict)
                or set(output) != set(variants)
            ):
                continue
            names = {manifest.get("states"), manifest.get("state_effects")}
            if any(not isinstance(value, str) for value in names):
                continue
            if any(
                not isinstance(row, dict)
                or set(row) != {"source_effects", "effects", "entry_effects"}
                or any(not isinstance(value, str) for value in row.values())
                for row in variants.values()
            ):
                continue
            names.update(value for row in variants.values() for value in row.values())
            rows = db.execute(
                "SELECT c.collection,c.kind,c.record_count,c.ordered_keys_raw,c.ordered_keys_sha256, "
                "s.complete,s.collection AS content_collection,s.kind AS content_kind,s.representation, "
                "s.record_count AS content_count,s.ordered_keys_sha256 AS content_keys_sha256,s.records_sha256 "
                "FROM native_compiled_catalog_collections c JOIN native_compiled_collection_contents s USING(content_id) "
                "WHERE c.generation=%s AND c.collection=ANY(%s)",
                (candidate["generation"], list(names)),
            ).fetchall()
            if len(rows) != len(names):
                continue
            declared = manifest.get("collections", {})
            resolved = {}
            for row in rows:
                name, keys = row["collection"], bytes(row["ordered_keys_raw"])
                metadata = declared.get(name)
                if (
                    not isinstance(metadata, dict)
                    or not row["complete"]
                    or metadata.get("collection") != name
                    or row["content_collection"] != name
                    or metadata.get("kind") != row["kind"]
                    or row["content_kind"] != row["kind"]
                    or metadata.get("count") != row["record_count"]
                    or row["content_count"] != row["record_count"]
                    or metadata.get("representation") != row["representation"]
                    or metadata.get("ordered_keys_sha256") != row["ordered_keys_sha256"]
                    or row["content_keys_sha256"] != row["ordered_keys_sha256"]
                    or metadata.get("records_sha256") != row["records_sha256"]
                    or hashlib.sha256(keys).hexdigest() != row["ordered_keys_sha256"]
                    or (
                        name in spool.collections
                        and spool.collections[name] != metadata
                    )
                ):
                    break
                resolved[name] = (metadata, keys)
            if set(resolved) != names:
                continue
            for name, (metadata, keys) in resolved.items():
                spool.collections[name], spool.keys[name] = metadata, keys
            return {
                "variants": variants,
                "original_output_index": output,
                "states": manifest["states"],
                "state_effects": manifest["state_effects"],
            }
    return None
