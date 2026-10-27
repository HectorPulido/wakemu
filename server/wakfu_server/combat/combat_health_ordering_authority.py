"""Append-only native faJ identities supplement an unchanged catalog release."""
from functools import lru_cache
import re

SOURCE_DOCUMENTS = (
    "combat-state-definitions.json",
    "native-npc-spell-effect-trees.json",
    "spell-effect-trees.json",
)

CONTRACT = "faJ.PV.a.sgC.PA.aYS.aYU.float32.desc.v1"


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=32)
def _for_revision(revision):
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision):
        raise ValueError("Missing native health-ordering catalog revision")
    with _database().connection() as db:
        version = db.execute(
            "SELECT * FROM native_health_ordering_authority_versions WHERE catalog_revision=%s",
            (revision,),
        ).fetchone()
        candidates = (
            []
            if version is not None
            else db.execute(
                "SELECT * FROM native_health_ordering_authority_versions ORDER BY catalog_revision"
            ).fetchall()
        )
    compatible_lookup = version is None
    source_revision = revision
    if version is None:
        from wakfu_server import native_catalog
        from wakfu_server.native_catalog_compatibility import require_source_revision

        if revision != native_catalog.release() or not candidates:
            return {}
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
                "Native health-ordering source dependencies changed"
            ) from failures[0]
        if len(compatible) != 1:
            raise ValueError("Ambiguous native health-ordering source authority")
        version = compatible[0]
        source_revision = version["catalog_revision"]
    with _database().connection() as db:
        rows = db.execute(
            "SELECT * FROM native_health_ordering_authority_rows WHERE authority_key=%s "
            "ORDER BY effect_reference",
            (version["authority_key"],),
        ).fetchall()
    if (
        set(version)
        != {
            "authority_key",
            "catalog_revision",
            "ordering_contract",
            "source_proof_sha256",
            "definition_count",
        }
        or not isinstance(version["authority_key"], str)
        or not version["authority_key"]
        or version["catalog_revision"] != source_revision
        or version["ordering_contract"] != CONTRACT
        or not isinstance(version["source_proof_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", version["source_proof_sha256"])
        or type(version["definition_count"]) is not int
        or version["definition_count"] <= 0
        or len(rows) != version["definition_count"]
    ):
        raise ValueError("Malformed immutable native health-ordering authority")
    result = {}
    for row in rows:
        flags = row.get("native_effect_flags")
        reference = row.get("effect_reference")
        if (
            set(row)
            != {
                "authority_key",
                "effect_reference",
                "effect_class",
                "native_effect_flags",
                "maximum_targets",
            }
            or row["authority_key"] != version["authority_key"]
            or type(reference) is not int
            or reference <= 0
            or str(reference) in result
            or type(row["effect_class"]) is not int
            or row["effect_class"] <= 0
            or not isinstance(flags, (list, tuple))
            or 25 not in flags
            or any(type(flag) is not int or not 0 <= flag < 128 for flag in flags)
            or len(set(flags)) != len(flags)
            or type(row["maximum_targets"]) is not int
            or not -128 <= row["maximum_targets"] <= 127
        ):
            raise ValueError("Malformed immutable native health-ordering definition")
        result[str(reference)] = dict(
            effect_class=row["effect_class"],
            native_effect_flags=tuple(flags),
            maximum_targets=row["maximum_targets"],
            ordering_contract=CONTRACT,
        )
    if compatible_lookup and native_catalog.release() != revision:
        raise ValueError("Native health-ordering publication changed during lookup")
    return result


def descending_health_target_ordering():
    from wakfu_server import native_catalog

    return _for_revision(native_catalog.release())
