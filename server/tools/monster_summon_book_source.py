"""Explicit native empty summon books are dependencies, not wild activation."""
import hashlib
import json

SOURCE = "sealed_installed_aMb.csd_empty_v1"


def _digest(document):
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def empty_book_source(reference, profile):
    """Attest both exported abilities and raw native csd; absence is unknown."""
    if not isinstance(profile, dict) or not isinstance(
        profile.get("native_abilities"), list
    ):
        raise ValueError("Missing original native summon ability source")
    if profile["native_abilities"]:
        return None
    raw = profile.get("raw_native")
    if (
        type(reference) is not int
        or reference <= 0
        or profile.get("ref") != reference
        or not isinstance(raw, dict)
        or raw.get("d") != reference
        or not isinstance(raw.get("csd"), list)
        or raw["csd"] != []
    ):
        raise ValueError("Missing source-qualified empty native summon book")
    operands = dict(profile_reference=reference, native_abilities=[], raw_csd=[])
    return dict(
        producer=SOURCE,
        **operands,
        operands_sha256=_digest(operands),
        raw_profile_sha256=_digest(raw)
    )


def qualified_empty_book(reference, source):
    if not isinstance(source, dict):
        return False
    operands = dict(profile_reference=reference, native_abilities=[], raw_csd=[])
    digest = source.get("raw_profile_sha256")
    return (
        source.get("producer") == SOURCE
        and source.get("profile_reference") == reference
        and type(reference) is int
        and reference > 0
        and source.get("native_abilities") == []
        and isinstance(source.get("native_abilities"), list)
        and source.get("raw_csd") == []
        and isinstance(source.get("raw_csd"), list)
        and source.get("operands_sha256") == _digest(operands)
        and isinstance(digest, str)
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest)
    )
