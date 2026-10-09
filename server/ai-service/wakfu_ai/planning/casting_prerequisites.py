"""Strict validation for state-bound, one-sided casting availability facts."""


def certified_unavailable_spell_keys(repertoire, state, actor_id):
    """Return only spell keys excluded by explicit, state-bound certificates.

    A malformed, stale, or future-schema certificate fails open. Null table
    metadata alone is not enough: PCs and future actor types may use another
    authoritative cast path.
    """
    spells = repertoire.get("spells") if isinstance(repertoire, dict) else None
    if not isinstance(spells, list) or not isinstance(state, dict):
        return set()
    unavailable = set()
    certificate = repertoire.get("nativeCastingPrerequisites")
    if not isinstance(certificate, dict) or set(certificate) != {
        "schema",
        "sourceState",
        "actorId",
        "stateRevision",
        "complete",
        "unavailable",
    }:
        return unavailable
    if (
        certificate.get("schema") != "native-casting-root-prerequisites-v1"
        or type(certificate.get("sourceState")) is not str
        or certificate.get("sourceState") != state.get("key")
        or type(state.get("key")) is not str
        or type(actor_id) is not int
        or type(certificate.get("actorId")) is not int
        or certificate.get("actorId") != actor_id
        or type(certificate.get("stateRevision")) is not int
        or type(state.get("stateRevision")) is not int
        or certificate["stateRevision"] != state.get("stateRevision")
        or certificate.get("complete") is not True
        or not isinstance(certificate.get("unavailable"), list)
    ):
        return unavailable
    rows = certificate["unavailable"]
    parsed = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"spellId", "level", "reason", "missingRootIds"}
            or type(row.get("spellId")) is not int
            or row["spellId"] <= 0
            or type(row.get("level")) is not int
            or row["level"] <= 0
            or row.get("reason")
            not in {
                "missing_root_metadata",
                "missing_casting_table",
            }
            or not isinstance(row.get("missingRootIds"), list)
            or any(type(root) is not int for root in row["missingRootIds"])
            or len(set(row["missingRootIds"])) != len(row["missingRootIds"])
            or (row["reason"] == "missing_root_metadata" and not row["missingRootIds"])
            or (row["reason"] == "missing_casting_table" and row["missingRootIds"])
        ):
            return unavailable
        key = row["spellId"], row["level"]
        if key in parsed:
            return unavailable
        parsed.add(key)
    owned = set()
    for spell in spells:
        if (
            not isinstance(spell, dict)
            or type(spell.get("spellId")) is not int
            or type(spell.get("level")) is not int
        ):
            return unavailable
        owned.add((spell["spellId"], spell["level"]))
    if not parsed <= owned:
        return unavailable
    unavailable.update(parsed)
    return unavailable


def all_owned_spells_unavailable(repertoire, state, actor_id):
    """Whether every complete native repertoire row has a valid no-cast proof."""
    spells = repertoire.get("spells") if isinstance(repertoire, dict) else None
    if not isinstance(spells, list) or not isinstance(state, dict):
        return False
    keys = set()
    for spell in spells:
        if (
            not isinstance(spell, dict)
            or type(spell.get("spellId")) is not int
            or type(spell.get("level")) is not int
        ):
            return False
        keys.add((spell["spellId"], spell["level"]))
    return not keys or keys <= certified_unavailable_spell_keys(
        repertoire, state, actor_id
    )
