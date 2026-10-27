"""Revision-scoped DB authority for missing original fKX/aZF casting roots."""
from functools import lru_cache
import re

from wakfu_server import native_catalog

SOURCE_DOCUMENTS = ("granted-spell-effect-trees.json", "native-spell-casting.json")

_FIELDS = frozenset(
    (
        "native_casting_collision_area",
        "native_selector_present",
        "native_target_selector",
    )
)


def supplemental_root(root, *, spell_reference):
    if (
        type(root) is not int
        or root <= 0
        or type(spell_reference) is not int
        or spell_reference <= 0
    ):
        raise ValueError("Native casting root and owned spell reference required")
    return _supplemental_root(native_catalog.release(), root, spell_reference)


@lru_cache(maxsize=1024)
def _supplemental_root(revision, root, spell_reference):
    with native_catalog._database().connection() as database:
        row = database.execute(
            "SELECT source_jar_sha256,export_sha256,exporter_sha256,metadata "
            "FROM native_casting_root_supplements "
            "WHERE catalog_revision=%s AND root_id=%s AND %s=ANY(source_spell_references)",
            (revision, root, spell_reference),
        ).fetchone()
        candidates = (
            []
            if row is not None
            else database.execute(
                "SELECT catalog_revision,source_jar_sha256,export_sha256,exporter_sha256,metadata "
                "FROM native_casting_root_supplements "
                "WHERE root_id=%s AND %s=ANY(source_spell_references) ORDER BY catalog_revision",
                (root, spell_reference),
            ).fetchall()
        )
    compatible_lookup = row is None
    if row is None:
        if revision != native_catalog.release() or not candidates:
            return None
        from wakfu_server.native_catalog_compatibility import require_source_revision

        compatible = []
        failures = []
        for candidate in candidates:
            try:
                require_source_revision(candidate["catalog_revision"], SOURCE_DOCUMENTS)
            except ValueError as error:
                failures.append(error)
            else:
                compatible.append(candidate)
        if not compatible and failures:
            raise ValueError(
                "Native casting-root source dependencies changed"
            ) from failures[0]
        if len(compatible) != 1:
            raise ValueError("Ambiguous native supplemental casting source")
        row = compatible[0]
    if any(
        type(row[key]) is not str or re.fullmatch(r"[0-9a-f]{64}", row[key]) is None
        for key in ("source_jar_sha256", "export_sha256", "exporter_sha256")
    ):
        raise ValueError("Missing original casting metadata source identity")
    record = row["metadata"]
    if (
        not isinstance(record, dict)
        or set(record) != _FIELDS
        or type(record["native_selector_present"]) is not bool
        or record["native_selector_present"]
        != (record["native_target_selector"] is not None)
        or any(
            value is not None and not isinstance(value, dict)
            for value in (
                record["native_casting_collision_area"],
                record["native_target_selector"],
            )
        )
    ):
        raise ValueError("Invalid original supplemental casting root metadata")
    if compatible_lookup and native_catalog.release() != revision:
        raise ValueError("Native casting-root publication changed during lookup")
    return record
