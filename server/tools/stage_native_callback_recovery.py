"""Prepare/verify an additive callback catalog package; stage only explicitly.

Preparation and verification are read-only. Staging uses the existing immutable
release builder and never updates native_catalog_active or restarts a service.
"""
import argparse
import gc
import hashlib
import json
import mmap
from pathlib import Path
import shutil

NPC = "native-npc-spell-effect-trees.json"
CELLS = "native-class-cell-group-metadata.json"
PROFILES = (
    "native-class-summon-abilities.json",
    "native-class-summon-initial-states.json",
)
PATHS = (NPC, CELLS, *PROFILES)


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def object_start(path, key):
    """Find an actual top-level JSON object without decoding the large document."""
    with Path(path).open("rb") as source, mmap.mmap(
        source.fileno(), 0, access=mmap.ACCESS_READ
    ) as raw:
        depth, position = 0, 0
        while position < len(raw):
            value = raw[position]
            if value == 34:
                start = position
                position += 1
                while position < len(raw):
                    if raw[position] == 92:
                        position += 2
                    elif raw[position] == 34:
                        position += 1
                        break
                    else:
                        position += 1
                if depth == 1 and json.loads(raw[start:position]) == key:
                    while raw[position] in b" \r\n\t":
                        position += 1
                    if raw[position] != 58:
                        continue
                    position += 1
                    while raw[position] in b" \r\n\t":
                        position += 1
                    if raw[position] != 123:
                        raise ValueError("Expected top-level object: " + key)
                    return position + 1
                continue
            if value in (123, 91):
                depth += 1
            elif value in (125, 93):
                depth -= 1
            position += 1
    raise ValueError("Missing top-level object: " + key)


def insert_effects(base, target, additions):
    offset = object_start(base, "effects")
    encoded = json.dumps(additions, separators=(",", ":")).encode()[1:-1]
    with Path(base).open("rb") as source, Path(target).open("wb") as output:
        remaining = offset
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                raise ValueError("Truncated native base document")
            output.write(chunk)
            remaining -= len(chunk)
        peek = source.read(1)
        if peek not in (b'"', b"}"):
            raise ValueError("Native base effects must use compact JSON layout")
        injection = encoded + (b"," if peek != b"}" else b"")
        output.write(injection)
        output.write(peek)
        shutil.copyfileobj(source, output, 1024 * 1024)
    return dict(
        offset=offset,
        length=len(injection),
        sha256=hashlib.sha256(injection).hexdigest(),
    )


def export_raw(connection, revision, name, path, expected_hash, size):
    if path.exists() and digest(path) == expected_hash:
        return
    temporary = path.with_suffix(path.suffix + ".partial")
    with temporary.open("wb") as output:
        chunk_size = 8 * 1024 * 1024
        for offset in range(0, size, chunk_size):
            row = connection.execute(
                "SELECT substring(raw FROM %s FOR %s) FROM native_catalog_documents "
                "WHERE revision=%s AND path=%s",
                (offset + 1, min(chunk_size, size - offset), revision, name),
            ).fetchone()
            if row is None:
                raise ValueError("Missing immutable base document")
            output.write(bytes(row[0]))
    if temporary.stat().st_size != size or digest(temporary) != expected_hash:
        raise ValueError("Base export SHA256 differs from indexed authority")
    temporary.replace(path)


def prepare(connection, candidate, output):
    candidate, output = Path(candidate), Path(output)
    provenance = json.loads((candidate / "provenance.json").read_text())
    revision = provenance["active_revision"]
    integrity = candidate / "integrity-validation.json"
    if json.loads(integrity.read_text()).get("result") != "PASS":
        raise ValueError("Missing successful candidate integrity receipt")
    candidate_hashes = json.loads((candidate / "candidate-sha256.json").read_text())
    for name, checksum in candidate_hashes.items():
        if digest(candidate / name) != checksum:
            raise ValueError("Recovered candidate changed after validation")
    output.mkdir(parents=True, exist_ok=True)
    (output / "base").mkdir(exist_ok=True)
    with connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        active = connection.execute(
            "SELECT revision FROM native_catalog_active WHERE id=1"
        ).fetchone()[0]
        if active != revision:
            raise ValueError(
                "Active revision changed; recovery package must be rebuilt"
            )
        published = connection.execute(
            "SELECT path,sha256,source_bytes FROM native_catalog_documents WHERE revision=%s ORDER BY path",
            (revision,),
        ).fetchall()
        indexed = {name: (checksum, size) for name, checksum, size in published}
        for name in PATHS:
            checksum, size = indexed[name]
            export_raw(
                connection, revision, name, output / "base" / name, checksum, size
            )
        additions = json.loads((candidate / "effect-additions.json").read_text())[
            "effects"
        ]
        # Each execution namespace is indexed by immutable revision/path/key.
        for name in (
            "spell-effect-trees.json",
            "granted-spell-effect-trees.json",
            "native-area-effect-trees.json",
            NPC,
            "combat-state-definitions.json",
        ):
            duplicate = connection.execute(
                "SELECT record_key FROM native_catalog_records WHERE revision=%s AND path=%s "
                "AND collection='effects' AND record_key=ANY(%s)",
                (revision, name, list(additions)),
            ).fetchall()
            if duplicate:
                raise ValueError(
                    "Recovery would shadow an existing execution definition"
                )
    injection = insert_effects(output / "base" / NPC, output / NPC, additions)
    shutil.copyfile(candidate / "cell-group-export" / CELLS, output / CELLS)
    for name in PROFILES:
        shutil.copyfile(candidate / name, output / name)
    shutil.copyfile(
        candidate / "effect-additions.json", output / "effect-additions.json"
    )
    shutil.copyfile(integrity, output / "integrity-validation.json")
    shutil.copyfile(candidate / "provenance.json", output / "provenance.json")
    entries = [
        (name, digest(output / name), (output / name).stat().st_size) for name in PATHS
    ]
    from stage_spell_resource_cost_catalog import full_manifest
    from import_native_catalogs import release_revision

    replacement = [dict(path=n, sha256=h, source_bytes=s) for n, h, s in entries]
    combined = full_manifest(published, replacement)
    manifest = dict(
        schema="native-callback-recovery-package-v1",
        base_revision=revision,
        candidate_revision=release_revision(combined),
        activated=False,
        base_documents=published,
        candidate_documents=combined,
        changed_documents={n: h for n, h, _ in entries},
        insertion=injection,
        effect_ids=sorted(map(int, additions)),
        integrity_sha256=digest(output / "integrity-validation.json"),
        effects_sha256=digest(output / "effect-additions.json"),
        provenance_sha256=digest(output / "provenance.json"),
        expected_enabled_count=1883,
        delta=dict(executable_effects=721, summon_profiles=18, cell_groups=125),
    )
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return verify(connection, output)


def verify_preserved_bytes(base, candidate, injection):
    # Removing the exact addition must reproduce every byte of the base,
    # including activation policy, initial CLE, baseline effects and exclusions.
    calculated = hashlib.sha256()
    with Path(candidate).open("rb") as source:
        remaining = injection["offset"]
        while remaining:
            block = source.read(min(1024 * 1024, remaining))
            if not block:
                raise ValueError("Truncated candidate prefix")
            calculated.update(block)
            remaining -= len(block)
        inserted = source.read(injection["length"])
        if hashlib.sha256(inserted).hexdigest() != injection["sha256"]:
            raise ValueError("Callback insertion changed")
        for block in iter(lambda: source.read(1024 * 1024), b""):
            calculated.update(block)
    if calculated.hexdigest() != digest(base):
        raise ValueError("Existing NPC document bytes were changed")


def verify(connection, directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    if (
        manifest.get("schema") != "native-callback-recovery-package-v1"
        or manifest.get("activated") is not False
    ):
        raise ValueError("Invalid inactive recovery package")
    if set(manifest["changed_documents"]) != set(PATHS):
        raise ValueError("Recovery cannot change unrelated catalog documents")
    for name, expected in manifest["changed_documents"].items():
        if digest(directory / name) != expected:
            raise ValueError("Candidate document changed: " + name)
    for name, field in (
        ("integrity-validation.json", "integrity_sha256"),
        ("effect-additions.json", "effects_sha256"),
        ("provenance.json", "provenance_sha256"),
    ):
        if digest(directory / name) != manifest[field]:
            raise ValueError("Candidate validation artifact changed")
    if (
        json.loads((directory / "integrity-validation.json").read_text()).get("result")
        != "PASS"
    ):
        raise ValueError("Candidate integrity did not pass")
    with connection.transaction():
        connection.execute("SET TRANSACTION READ ONLY")
        active = connection.execute(
            "SELECT revision FROM native_catalog_active WHERE id=1"
        ).fetchone()[0]
        if active != manifest["base_revision"]:
            raise ValueError("Active catalog differs from pinned package base")
        indexed = connection.execute(
            "SELECT path,sha256,source_bytes FROM native_catalog_documents WHERE revision=%s ORDER BY path",
            (active,),
        ).fetchall()
        if [list(row) for row in indexed] != manifest["base_documents"]:
            raise ValueError("Pinned base document inventory changed")
        enabled = connection.execute(
            "SELECT count(*) FROM native_catalog_records r, LATERAL jsonb_object_keys(r.payload) k "
            "WHERE r.revision=%s AND r.path=%s AND r.collection='activation_policy' "
            "AND r.record_key='enabled_monsters'",
            (active, NPC),
        ).fetchone()[0]
        if enabled != manifest["expected_enabled_count"]:
            raise ValueError("Enabled monster policy differs from reviewed count")
    bases = {name: checksum for name, checksum, _ in indexed}
    for name in PATHS:
        if digest(directory / "base" / name) != bases[name]:
            raise ValueError("Rollback base differs from indexed catalog")
    from stage_spell_resource_cost_catalog import full_manifest
    from import_native_catalogs import release_revision

    combined = full_manifest(indexed, entries(directory))
    if [list(row) for row in combined] != manifest[
        "candidate_documents"
    ] or release_revision(combined) != manifest["candidate_revision"]:
        raise ValueError("Candidate full revision inventory differs")
    additions = json.loads((directory / "effect-additions.json").read_text())["effects"]
    if sorted(map(int, additions)) != manifest["effect_ids"]:
        raise ValueError("Exact recovered effect identity delta changed")
    expected_insertion = (
        json.dumps(additions, separators=(",", ":")).encode()[1:-1] + b","
    )
    if (
        object_start(directory / "base" / NPC, "effects")
        != manifest["insertion"]["offset"]
        or hashlib.sha256(expected_insertion).hexdigest()
        != manifest["insertion"]["sha256"]
    ):
        raise ValueError("NPC insertion is not the exact reviewed effect addition set")
    verify_preserved_bytes(
        directory / "base" / NPC, directory / NPC, manifest["insertion"]
    )
    from export_monster_cell_groups import assert_preserved as cells_preserved
    from export_monster_summon_dependencies import (
        assert_preserved as profiles_preserved,
    )

    for name in (CELLS, *PROFILES):
        base = json.loads((directory / "base" / name).read_text())
        candidate = json.loads((directory / name).read_text())
        if name == CELLS:
            cells_preserved(base, candidate)
            if (
                len(candidate["effects"]) - len(base["effects"])
                != manifest["delta"]["cell_groups"]
            ):
                raise ValueError("Cell-group delta differs")
        else:
            profiles_preserved(name, base, candidate)
            if (
                len(candidate["profiles"]) - len(base["profiles"])
                != manifest["delta"]["summon_profiles"]
            ):
                raise ValueError("Summon profile delta differs")
    if len(manifest["effect_ids"]) != manifest["delta"]["executable_effects"]:
        raise ValueError("Effect addition delta differs")
    return dict(
        result="PASS",
        base_revision=active,
        candidate_revision=manifest["candidate_revision"],
        delta=manifest["delta"],
        npc_original_bytes_preserved=True,
        activation_policy_unchanged=True,
        enabled_monsters=enabled,
        staged=False,
        activated=False,
    )


def entries(directory):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    return [
        dict(
            path=name,
            source=directory / name,
            sha256=checksum,
            source_bytes=(directory / name).stat().st_size,
        )
        for name, checksum in manifest["changed_documents"].items()
    ]


def stage(connection, directory):
    verified = verify(connection, directory)
    from stage_spell_resource_cost_catalog import stage as stage_release

    with connection.transaction():
        result = stage_release(
            connection,
            directory,
            verified["base_revision"],
            dry_run=False,
            document_provider=entries,
        )
        if result["revision"] != verified["candidate_revision"]:
            raise ValueError("Staged revision differs from reviewed package")
        result["indexed_validation"] = verify_staged(connection, directory)
    return result


def verify_staged(connection, directory):
    """Check indexed base preservation and exact additions before stage commits."""
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    base, candidate = manifest["base_revision"], manifest["candidate_revision"]
    rows = connection.execute(
        "SELECT path,sha256,source_bytes FROM native_catalog_documents WHERE revision=%s ORDER BY path",
        (candidate,),
    ).fetchall()
    if [list(row) for row in rows] != manifest["candidate_documents"]:
        raise ValueError("Staged indexed document inventory mismatch")
    for name in PATHS:
        changed = connection.execute(
            "SELECT count(*) FROM native_catalog_records b LEFT JOIN native_catalog_records c "
            "ON c.revision=%s AND c.path=b.path AND c.collection=b.collection AND c.record_key=b.record_key "
            "WHERE b.revision=%s AND b.path=%s AND c.payload IS DISTINCT FROM b.payload",
            (candidate, base, name),
        ).fetchone()[0]
        if changed:
            raise ValueError("Staged catalog changed existing indexed rows: " + name)
    expected = {NPC: ("effects", set(map(str, manifest["effect_ids"])))}
    for name in (CELLS, *PROFILES):
        collection = "effects" if name == CELLS else "profiles"
        previous = json.loads((directory / "base" / name).read_text())[collection]
        current = json.loads((directory / name).read_text())[collection]
        expected[name] = (collection, set(current) - set(previous))
    for name, (collection, identities) in expected.items():
        added = connection.execute(
            "SELECT c.record_key FROM native_catalog_records c LEFT JOIN native_catalog_records b "
            "ON b.revision=%s AND b.path=c.path AND b.collection=c.collection AND b.record_key=c.record_key "
            "WHERE c.revision=%s AND c.path=%s AND c.collection=%s AND b.record_key IS NULL",
            (base, candidate, name, collection),
        ).fetchall()
        if {row[0] for row in added} != identities:
            raise ValueError("Staged indexed identity delta mismatch: " + name)
    enabled = connection.execute(
        "SELECT count(*) FROM native_catalog_records r, LATERAL jsonb_object_keys(r.payload) k "
        "WHERE r.revision=%s AND r.path=%s AND r.collection='activation_policy' "
        "AND r.record_key='enabled_monsters'",
        (candidate, NPC),
    ).fetchone()[0]
    if enabled != manifest["expected_enabled_count"]:
        raise ValueError("Staged enabled monster policy changed")
    return dict(
        result="PASS",
        enabled_monsters=enabled,
        exact_deltas=True,
        existing_indexed_rows_preserved=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--candidate", type=Path, help="Prepare package from sealed recovery artifacts"
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="Write inactive immutable revision; never activate",
    )
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--password-file", required=True, type=Path)
    args = parser.parse_args()
    if args.stage and args.candidate:
        parser.error("Preparation and staging are separate operations")
    import psycopg

    gc.disable()
    with psycopg.connect(
        args.dsn, password=args.password_file.read_text().strip()
    ) as connection:
        result = (
            prepare(connection, args.candidate, args.directory)
            if args.candidate
            else stage(connection, args.directory)
            if args.stage
            else verify(connection, args.directory)
        )
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
