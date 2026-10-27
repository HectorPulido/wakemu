"""Publish exact eager combat outputs outside World; PostgreSQL is authority."""
import argparse
from collections.abc import Mapping
from contextlib import contextmanager, redirect_stdout
import gc
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time


RAW_DOCUMENTS = (
    "spell-effect-trees.json",
    "combat-state-definitions.json",
    "spell-costs.json",
    "native-npc-spell-effect-trees.json",
    "native-retained-effect-metadata.json",
    "native-spell-casting.json",
    "native-actor-characteristics.json",
    "native-direct-target-policies.json",
    "native-zone-trigger-policies.json",
    "native-class-casting-roots.json",
    "item-recycling-metadata.json",
    "item-exchange-metadata.json",
    "native-copied-equipment-definitions.json",
    "native-area-effect-trees.json",
)
RECORD_FIELDS = frozenset(
    (
        "effects",
        "states",
        "spells",
        "roots",
        "items",
        "characteristics",
        "baseline_effects",
        "records",
        "definitions",
    )
)


def ordered_bytes(value):
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    ).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def log(event, **values):
    print(json.dumps(dict(event=event, **values)), file=sys.stderr, flush=True)


@contextmanager
def compilation_gc():
    """Avoid repeatedly traversing static source graphs in this offline child."""
    enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()


def raw_value(value, key):
    from wakfu_server.combat_static_catalogs import ImmutableCatalog, DefinitionOverlay

    if type(value) is ImmutableCatalog:
        return value._source[key]
    if type(value) is DefinitionOverlay:
        return raw_value(
            value._overrides if key in value._overrides else value._base, key
        )
    return value[key]


def native_json(value):
    if isinstance(value, Mapping):
        return {key: native_json(raw_value(value, key)) for key in value}
    if isinstance(value, (list, tuple)):
        return [native_json(row) for row in value]
    if value is None or type(value) in (str, int, float, bool):
        return value
    raise ValueError("Unsupported compiled catalog value type: " + type(value).__name__)


class PublicationSpool:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute("PRAGMA cache_size=-8192")
        self.db.execute(
            "CREATE TABLE records(collection TEXT,record_key TEXT,ordinal INTEGER,raw BLOB,sha256 TEXT,PRIMARY KEY(collection,record_key))"
        )
        self.collections = {}
        self.keys = {}

    def collection(self, name, value, *, representation="native_json"):
        if name in self.collections:
            return self.collections[name]
        kind = "dict" if isinstance(value, Mapping) else "list"
        if kind == "list" and not isinstance(value, (tuple, list)):
            raise ValueError("Unsupported collection kind")
        keys = list(value) if kind == "dict" else list(range(len(value)))
        ordered = ordered_bytes(keys)
        content = hashlib.sha256()
        for ordinal, key in enumerate(keys):
            if type(key) not in (str, int):
                raise ValueError(
                    "Published keys must preserve original string/integer types"
                )
            row = raw_value(value, key) if kind == "dict" else value[key]
            raw = ordered_bytes(native_json(row))
            if len(raw) > 16 * 1024 * 1024:
                raise ValueError(
                    "Compiled record exceeds the published reader contract"
                )
            checksum = digest(raw)
            encoded = ordered_bytes(key).decode()
            self.db.execute(
                "INSERT INTO records VALUES(?,?,?,?,?)",
                (name, encoded, ordinal, raw, checksum),
            )
            content.update(ordered_bytes([key, ordinal, checksum]) + b"\n")
        self.db.commit()
        metadata = dict(
            collection=name,
            kind=kind,
            count=len(keys),
            ordered_keys_sha256=digest(ordered),
            records_sha256=content.hexdigest(),
            representation=representation,
        )
        self.collections[name] = metadata
        self.keys[name] = ordered
        log("compiled_collection_spooled", collection=name, records=len(keys))
        return metadata

    def document(self, name, value, *, record_mapping=False, aliases=None):
        if record_mapping:
            collection = "documents." + name + ".$"
            self.collection(collection, value)
            return dict(root_kind="record_mapping", root_collection=collection)
        if not isinstance(value, Mapping):
            raise ValueError("Published document root must be a dictionary: " + name)
        result = dict(root_kind="dict", layout=list(value), header={}, collections={})
        for key in value:
            row = raw_value(value, key)
            if isinstance(row, Mapping):
                if key not in RECORD_FIELDS and key not in (aliases or {}):
                    metadata_value = native_json(row)
                    if len(ordered_bytes(metadata_value)) <= 65536:
                        result["header"][key] = metadata_value
                        continue
                collection = (aliases or {}).get(
                    key, "documents." + name + "." + str(key)
                )
                metadata = self.collection(collection, row)
                result["collections"][key] = {
                    field: metadata[field]
                    for field in ("collection", "kind", "count", "ordered_keys_sha256")
                }
            else:
                # Original metadata arrays remain real JSON lists, never Mapping handles.
                result["header"][key] = native_json(row)
        result["header_bytes"] = len(ordered_bytes(result["header"]))
        if result["header_bytes"] > 65536:
            raise ValueError(
                "Document metadata requires an explicit large-list contract: " + name
            )
        result["header_json"] = ordered_bytes(result["header"]).decode()
        return result


def compile_manifest(spool, identity):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.combat_server_spell import compile_runtime_catalog_eager
    from wakfu_server.combat_npc_attack import compile_npc_runtime_catalog_eager
    from wakfu_server.combat_weapon import compile_weapon_runtime_catalog_eager
    from wakfu_server.combat_original_producer_events import original_output_index
    from wakfu_server.spell_audit import catalog, costs_catalog, states_catalog
    from wakfu_server.combat_casting_context import casting_root_catalog

    player = compile_runtime_catalog_eager()
    state_document = states_catalog()
    spool.collection("shared.states", raw_value(state_document, "states"))
    spool.collection("shared.state_effects", raw_value(state_document, "effects"))
    manifest = dict(
        identity,
        variants={},
        states="shared.states",
        state_effects="shared.state_effects",
        original_output_index={},
        raw_documents={},
        documents={},
    )
    constructors = (
        ("player", lambda: player),
        ("npc_imported", lambda: compile_npc_runtime_catalog_eager(imported=True)),
        ("npc_baseline", lambda: compile_npc_runtime_catalog_eager(imported=False)),
        ("weapon", compile_weapon_runtime_catalog_eager),
    )
    for variant, constructor in constructors:
        compiled = constructor()
        source_name, effect_name = variant + ".source_effects", variant + ".effects"
        spool.collection(source_name, compiled.source_effects)
        spool.collection(effect_name, compiled.effects, representation="frozen_effect")
        manifest["variants"][variant] = dict(
            source_effects=source_name, effects=effect_name
        )
        index = original_output_index(compiled.effects)
        manifest["original_output_index"][variant] = [
            [str(reference), index[reference][0], sorted(index[reference][1])]
            for reference in compiled.effects
            if reference in index
        ]
    for name in RAW_DOCUMENTS:
        value = (
            state_document
            if name == "combat-state-definitions.json"
            else native_catalog.load(DATA_ROOT / name)
        )
        aliases = (
            {"states": "shared.states", "effects": "shared.state_effects"}
            if name == "combat-state-definitions.json"
            else None
        )
        entry = spool.document(name, value, aliases=aliases)
        entry["source_sha256"] = identity["source_documents"][name]
        manifest["raw_documents"][name] = entry
    for name, value, record_mapping in (
        ("spell_audit.catalog", catalog(), False),
        ("spell_audit.costs_catalog", costs_catalog(), True),
        ("combat_casting_context.casting_root_catalog", casting_root_catalog(), False),
    ):
        manifest["documents"][name] = spool.document(
            name, value, record_mapping=record_mapping
        )
    from wakfu_server.prepared_los_compiled import COLLECTION, SCHEMA, CompilerRecords

    spool.collection(COLLECTION, CompilerRecords(identity))
    manifest["prepared_los"] = {"schema": SCHEMA, "collection": COLLECTION}
    manifest["collections"] = spool.collections
    return manifest


def publish(db, spool, manifest, canonical_bytes, *, identity_check=None):
    from psycopg.types.json import Jsonb

    raw = canonical_bytes(manifest)
    generation = digest(raw)
    db.execute(
        "INSERT INTO native_compiled_catalog_releases "
        "(generation,policy,source_revision,source_inventory_sha256,compiler_contract_sha256,config_sha256,manifest_raw,manifest) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            generation,
            manifest["policy"],
            manifest["source_revision"],
            manifest["source_inventory_sha256"],
            manifest["compiler_contract_sha256"],
            manifest["config_sha256"],
            raw,
            Jsonb(manifest),
        ),
    )
    for name, metadata in spool.collections.items():
        db.execute(
            "INSERT INTO native_compiled_catalog_collections "
            "(generation,collection,kind,record_count,ordered_keys_raw,ordered_keys_sha256) VALUES(%s,%s,%s,%s,%s,%s)",
            (
                generation,
                name,
                metadata["kind"],
                metadata["count"],
                spool.keys[name],
                metadata["ordered_keys_sha256"],
            ),
        )
    count = 0
    with db.cursor().copy(
        "COPY native_compiled_catalog_records "
        "(generation,collection,record_key,ordinal,raw,sha256) FROM STDIN (FORMAT BINARY)"
    ) as copy:
        copy.set_types(["text", "text", "text", "int4", "bytea", "text"])
        for row in spool.db.execute(
            "SELECT collection,record_key,ordinal,raw,sha256 FROM records ORDER BY collection,ordinal"
        ):
            copy.write_row((generation, *row))
            count += 1
    expected = sum(row["count"] for row in spool.collections.values())
    actual = db.execute(
        "SELECT count(*) AS n FROM native_compiled_catalog_records WHERE generation=%s",
        (generation,),
    ).fetchone()["n"]
    if count != expected or actual != expected:
        raise ValueError("Compiled catalog record count differs after COPY")
    if identity_check is not None:
        identity_check()
    # New generation/collection statistics must be visible with the seal.
    # Otherwise a one-key lookup can scan an entire collection by ordinal.
    began = time.monotonic()
    db.execute("ANALYZE native_compiled_catalog_records")
    log(
        "compiled_publication_analyzed",
        generation=generation,
        seconds=time.monotonic() - began,
    )
    db.execute(
        "UPDATE native_compiled_catalog_releases SET complete=true,completed_at=now() WHERE generation=%s AND NOT complete",
        (generation,),
    )
    return generation


def ensure_publication(*, warm_redis=False):
    os.environ["WAKFU_COMPILED_CATALOG_BUILD"] = "1"
    from wakfu_server import native_catalog
    from wakfu_server.native_compiled_catalog import (
        expected_publication_identity,
        canonical_bytes,
    )

    identity = expected_publication_identity()
    pins = tuple(
        identity[key]
        for key in (
            "policy",
            "source_revision",
            "source_inventory_sha256",
            "compiler_contract_sha256",
            "config_sha256",
        )
    )
    with native_catalog._database().connection() as db:
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("native_compiled_catalog:" + digest(canonical_bytes(pins)),),
        )
        row = db.execute(
            "SELECT generation,manifest_raw,complete FROM native_compiled_catalog_releases "
            "WHERE policy=%s AND source_revision=%s AND source_inventory_sha256=%s AND compiler_contract_sha256=%s AND config_sha256=%s",
            pins,
        ).fetchone()
        if row is not None:
            if (
                not row["complete"]
                or digest(bytes(row["manifest_raw"])) != row["generation"]
            ):
                raise ValueError(
                    "Existing compiled catalog publication is incomplete or invalid"
                )
            generation = row["generation"]
            log("compiled_publication_reused", generation=generation)
        else:
            with tempfile.TemporaryDirectory(
                prefix="wakemu-compiled-catalog-"
            ) as directory:
                spool = PublicationSpool(str(Path(directory) / "records.sqlite"))
                try:
                    with compilation_gc():
                        manifest = compile_manifest(spool, identity)

                        def check_identity():
                            from wakfu_server.native_compiled_catalog import (
                                _compiler_source_bytes,
                            )

                            _compiler_source_bytes.cache_clear()
                            if expected_publication_identity() != identity:
                                raise ValueError(
                                    "Compiled catalog inputs changed during publication"
                                )

                        check_identity()
                        generation = publish(
                            db,
                            spool,
                            manifest,
                            canonical_bytes,
                            identity_check=check_identity,
                        )
                finally:
                    spool.db.close()
            log("compiled_publication_complete", generation=generation)
    if warm_redis:
        from wakfu_server.native_compiled_catalog import warm_publication

        warm_publication(generation)
    return generation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ensure", action="store_true", required=True)
    parser.add_argument("--print-generation", action="store_true")
    parser.add_argument("--warm-redis", action="store_true")
    args = parser.parse_args()
    began = time.monotonic()
    with redirect_stdout(sys.stderr):
        generation = ensure_publication(warm_redis=args.warm_redis)
    log(
        "compiled_publication_ready",
        generation=generation,
        seconds=time.monotonic() - began,
    )
    print(
        generation
        if args.print_generation
        else json.dumps(dict(generation=generation, complete=True)),
        flush=True,
    )


if __name__ == "__main__":
    main()
