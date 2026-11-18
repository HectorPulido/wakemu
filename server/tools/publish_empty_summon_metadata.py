"""Derive a source-qualified header for additive empty fresh-summon metadata.

No eager compiler runs. The unchanged compiler/configuration and every sealed
collection remain authoritative; only two runtime creation documents may grow.
"""
import hashlib
import json
from psycopg.types.json import Jsonb

DOCUMENTS = frozenset(
    {
        "native-class-summon-abilities.json",
        "native-class-summon-initial-states.json",
    }
)


def qualify(previous, identity, before, after, *, states, effect_ids, properties):
    """Reject anything beyond exact empty books and already compiled states."""
    for name in (
        "policy",
        "compiler_contract_sha256",
        "compiler_sources",
        "config_sha256",
        "config",
    ):
        if previous.get(name) != identity.get(name):
            raise ValueError(
                "Fresh-summon metadata cannot change compiler/configuration"
            )
    old, new = previous["source_documents"], identity["source_documents"]
    if old.keys() != new.keys() or {k for k in old if old[k] != new[k]} != DOCUMENTS:
        raise ValueError("Only the two fresh-summon runtime documents may change")
    additions = None
    for name in DOCUMENTS:
        a, b = before[name], after[name]
        if a.keys() != b.keys():
            raise ValueError("Fresh-summon document metadata shape changed")
        for key in a:
            if key in ("profiles", "npc_dependency_exports"):
                continue
            if a[key] != b[key]:
                raise ValueError("Existing fresh-summon document metadata changed")
        old_profiles, profiles = a["profiles"], b["profiles"]
        if any(profiles.get(k) != v for k, v in old_profiles.items()):
            raise ValueError("Existing fresh-summon profile changed")
        added = set(profiles) - set(old_profiles)
        if not 1 <= len(added) <= 16 or any(
            not k.isdigit() or int(k) <= 0 for k in added
        ):
            raise ValueError("A finite positive fresh-summon addition is required")
        if additions is not None and additions != added:
            raise ValueError("Fresh-summon book and initial-state additions differ")
        additions = added
        old_exports, exports = a.get("npc_dependency_exports", []), b.get(
            "npc_dependency_exports", []
        )
        if exports[: len(old_exports)] != old_exports or any(
            set(row.get("added_profile_ids", [])) != set(map(int, added))
            for row in exports[len(old_exports) :]
        ):
            raise ValueError("Fresh-summon provenance is not additive")
    abilities = after["native-class-summon-abilities.json"]["profiles"]
    initial = after["native-class-summon-initial-states.json"]["profiles"]
    referenced = set()
    for key in additions:
        if abilities[key] != {"abilities": []}:
            raise ValueError("Only exact empty native ability books qualify")
        row = initial[key]
        if set(row) != {"initial_state_triples", "fight_properties"} or row[
            "fight_properties"
        ] != properties.get(key, {}).get("fight_properties"):
            raise ValueError("Fresh-summon properties differ from native source")
        triples = row["initial_state_triples"]
        if (
            not isinstance(triples, list)
            or len(triples) % 3
            or any(type(v) is not int or not -32768 <= v <= 32767 for v in triples)
        ):
            raise ValueError("Malformed original fresh-summon initial states")
        for offset in range(0, len(triples), 3):
            state_id, level, flag = triples[offset : offset + 3]
            if (
                state_id <= 0
                or level < -1
                or flag not in (0, 1)
                or str(state_id) not in states
            ):
                raise ValueError("Fresh-summon state is not already compiled")
            referenced.add(state_id)
            roots = {
                int(e)
                for selected in states[str(state_id)]["levels"]
                for e in selected["effects"]
            }
            if not roots <= effect_ids:
                raise ValueError("Fresh-summon state has a new uncompiled root")
    return dict(profile_ids=sorted(map(int, additions)), state_ids=sorted(referenced))


def _document(db, revision, name, checksum):
    row = db.execute(
        "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s AND sha256=%s",
        (revision, name, checksum),
    ).fetchone()
    if (
        row is None
        or len(row["raw"]) > 2 * 1024 * 1024
        or hashlib.sha256(bytes(row["raw"])).hexdigest() != checksum
    ):
        raise ValueError("Missing or changed bounded fresh-summon source")
    return json.loads(bytes(row["raw"]))


def publish(db, previous_generation, identity, canonical_bytes):
    """Seal a proper new source header referencing verified existing contents."""
    from tools.reuse_unchanged_compiled_catalog import PIN_FIELDS

    db.execute(
        "SELECT pg_advisory_xact_lock_shared(hashtextextended(current_database()||':'||current_schema()||':compiled_catalog_maintenance',0))"
    )
    pins = tuple(identity[key] for key in PIN_FIELDS)
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (
            "native_compiled_catalog:"
            + hashlib.sha256(canonical_bytes(pins)).hexdigest(),
        ),
    )
    prior = db.execute(
        "SELECT manifest_raw,manifest FROM native_compiled_catalog_releases WHERE generation=%s AND complete",
        (previous_generation,),
    ).fetchone()
    if (
        prior is None
        or hashlib.sha256(bytes(prior["manifest_raw"])).hexdigest()
        != previous_generation
        or canonical_bytes(prior["manifest"]) != bytes(prior["manifest_raw"])
    ):
        raise ValueError("Missing or changed sealed prior publication")
    previous = prior["manifest"]
    before = {
        name: _document(
            db, previous["source_revision"], name, previous["source_documents"][name]
        )
        for name in DOCUMENTS
    }
    after = {
        name: _document(
            db, identity["source_revision"], name, identity["source_documents"][name]
        )
        for name in DOCUMENTS
    }
    added = set(after["native-class-summon-initial-states.json"]["profiles"]) - set(
        before["native-class-summon-initial-states.json"]["profiles"]
    )
    initial = after["native-class-summon-initial-states.json"]["profiles"]
    state_ids = {
        str(row[0])
        for key in added
        for row in zip(*[iter(initial[key]["initial_state_triples"])] * 3)
    }
    states = {}
    for key in state_ids:
        row = db.execute(
            "SELECT raw FROM native_compiled_catalog_records WHERE generation=%s AND collection=%s AND record_key=%s",
            (previous_generation, previous["states"], json.dumps(key)),
        ).fetchone()
        if row is not None:
            states[key] = json.loads(bytes(row["raw"]))
    roots = {
        str(e)
        for state in states.values()
        for level in state["levels"]
        for e in level["effects"]
    }
    effect_ids = set(map(int, roots))
    for variant in previous["variants"].values():
        found = db.execute(
            "SELECT record_key FROM native_compiled_catalog_records WHERE generation=%s AND collection=%s AND record_key=ANY(%s)",
            (previous_generation, variant["effects"], [json.dumps(k) for k in roots]),
        ).fetchall()
        effect_ids &= {int(json.loads(row["record_key"])) for row in found}
    properties = {
        row["record_key"]: row["payload"]
        for row in db.execute(
            "SELECT record_key,payload FROM native_catalog_records WHERE revision=%s AND path='native-actor-properties.json' AND collection='npc' AND record_key=ANY(%s)",
            (identity["source_revision"], sorted(added)),
        ).fetchall()
    }
    proof = qualify(
        previous,
        identity,
        before,
        after,
        states=states,
        effect_ids=effect_ids,
        properties=properties,
    )
    rows = db.execute(
        "SELECT c.*,s.complete AS content_complete,s.collection AS content_collection,s.kind AS content_kind,s.representation AS content_representation,s.record_count AS content_count,s.ordered_keys_sha256 AS content_keys_sha256,s.records_sha256 AS content_records_sha256 FROM native_compiled_catalog_collections c LEFT JOIN native_compiled_collection_contents s USING(content_id) WHERE c.generation=%s",
        (previous_generation,),
    ).fetchall()
    declared = previous["collections"]
    if len(rows) != len(declared) or any(
        row["collection"] not in declared
        or not row["content_complete"]
        or row["kind"] != declared[row["collection"]]["kind"]
        or row["record_count"] != declared[row["collection"]]["count"]
        or row["ordered_keys_sha256"]
        != declared[row["collection"]]["ordered_keys_sha256"]
        or row["content_collection"] != row["collection"]
        or row["content_kind"] != row["kind"]
        or row["content_count"] != row["record_count"]
        or row["content_representation"]
        != declared[row["collection"]]["representation"]
        or row["content_keys_sha256"] != row["ordered_keys_sha256"]
        or row["content_records_sha256"]
        != declared[row["collection"]]["records_sha256"]
        or hashlib.sha256(bytes(row["ordered_keys_raw"])).hexdigest()
        != row["ordered_keys_sha256"]
        for row in rows
    ):
        raise ValueError("Prior immutable compiled collections changed")
    manifest = dict(previous)
    manifest.update(identity)
    raw = canonical_bytes(manifest)
    generation = hashlib.sha256(raw).hexdigest()
    existing = db.execute(
        "SELECT manifest_raw,complete FROM native_compiled_catalog_releases WHERE generation=%s",
        (generation,),
    ).fetchone()
    if existing is not None:
        if bytes(existing["manifest_raw"]) != raw or not existing["complete"]:
            raise ValueError("Derived publication identity collision")
        return dict(generation=generation, proof=proof, reused=True)
    db.execute(
        "INSERT INTO native_compiled_catalog_releases(generation,policy,source_revision,source_inventory_sha256,compiler_contract_sha256,config_sha256,manifest_raw,manifest) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
        (generation, *pins, raw, Jsonb(manifest)),
    )
    db.execute(
        "INSERT INTO native_compiled_catalog_collections(generation,collection,kind,record_count,ordered_keys_raw,ordered_keys_sha256,content_id) SELECT %s,collection,kind,record_count,ordered_keys_raw,ordered_keys_sha256,content_id FROM native_compiled_catalog_collections WHERE generation=%s",
        (generation, previous_generation),
    )
    db.execute(
        "UPDATE native_compiled_catalog_releases SET complete=true,completed_at=now() WHERE generation=%s",
        (generation,),
    )
    return dict(
        generation=generation, proof=proof, reused=False, collection_count=len(rows)
    )
