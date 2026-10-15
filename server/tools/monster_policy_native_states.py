"""Preserve the client's flat signed-short initial-state layout in activation policies."""


def native_initial_state_triples(native_record):
    """Return an independent flat copy of the authoritative native cle array."""
    triples = native_record["raw_native"]["cle"]
    if native_record.get("initial_state_triples", triples) != triples:
        raise ValueError("Native initial-state export disagrees with cle")
    validate_initial_state_triples(triples)
    return list(triples)


def validate_initial_state_triples(triples):
    """Reject grouped triples and invalid values before a catalog can be staged."""
    if not isinstance(triples, list) or len(triples) % 3:
        raise ValueError(
            "Initial-state policy requires a flat list of complete triples"
        )
    if any(type(value) is not int or not -32768 <= value <= 32767 for value in triples):
        raise ValueError("Initial-state policy requires flat signed shorts")
