"""Import the SQL-declared native Rift producer from its published index."""
from functools import lru_cache
import hashlib
import json

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT


def original_artifact_producer(producer):
    """Return the unchanged original leaf and its pinned publication provenance.

    This is a catalog projection, not an equipped-weapon grant. Execution still
    requires the explicitly scoped Rift controller and its actual SQL policy.
    """
    if (
        not isinstance(producer, dict)
        or producer.get("source_kind") != "native_context_area_ref"
        or type(producer.get("template_effect_reference")) is not int
        or producer["template_effect_reference"] <= 0
    ):
        raise ValueError("Missing SQL-declared native Rift producer")
    reference = producer["template_effect_reference"]
    document = producer.get("source_document")
    if (
        not isinstance(document, str)
        or not document.endswith(".json")
        or "\\" in document
        or document.startswith("/")
        or any(part in ("", ".", "..") for part in document.split("/"))
    ):
        raise ValueError("Rift producer requires its logical published source document")
    hashes = native_catalog.document_hashes()
    document_hash = hashes.get(document)
    if not isinstance(document_hash, str) or len(document_hash) != 64:
        raise ValueError(
            "Rift producer source document is not in the published release"
        )
    effect = native_catalog.record(DATA_ROOT / document, "effects", reference)
    if (
        not isinstance(effect, dict)
        or effect.get("effect_class") != 315
        or effect.get("children")
        or effect.get("criteria", "").strip()
        or not isinstance(document_hash, str)
        or len(document_hash) != 64
    ):
        raise ValueError("Rift producer is missing its original published315 leaf")
    encoded = json.dumps(effect, sort_keys=True, separators=(",", ":")).encode()
    return dict(
        effects={str(reference): effect},
        provenance=dict(
            revision=native_catalog.release(),
            source_document=document,
            document_sha256=document_hash,
            reference=reference,
            record_sha256=hashlib.sha256(encoded).hexdigest(),
        ),
    )


@lru_cache(maxsize=1)
def configured_producer_catalog():
    """Resolve startup configuration once, before the immutable base is built."""
    from wakfu_server.rift_native_gameplay_policy import load

    with native_catalog._database().connection() as db:
        policy = load(db)
    producer = None if policy is None else policy.get("artifacts", {}).get("producer")
    if producer is None:
        return dict(effects={})
    return original_artifact_producer(producer)
