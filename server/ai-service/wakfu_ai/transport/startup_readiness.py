"""Seal the complete bootstrap catalogue before admitting gameplay requests."""
import json
from pathlib import Path
import re
import time


DEFAULT_MANIFEST = "/native/catalog-manifest.json"


def seal_bootstrap_catalog(store, manifest_path=DEFAULT_MANIFEST):
    """Prepare the serving store itself, never a short-lived provisioner.

    Bootstrap and World may have different source manifests. Their immutable
    content hashes can share verified blob references in this store, so World
    subsequently seals only its source delta without repeating the asset copy.
    """
    descriptor = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    if (
        not isinstance(descriptor, dict)
        or set(descriptor) != {"sha256", "entries", "bytes"}
        or not isinstance(descriptor.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", descriptor["sha256"]) is None
        or any(
            type(descriptor.get(field)) is not int or descriptor[field] < 0
            for field in ("entries", "bytes")
        )
    ):
        raise ValueError("Missing complete AI bootstrap catalogue descriptor")
    started = time.monotonic()
    sealed = store.seal_manifest(descriptor["sha256"])
    if (
        not isinstance(sealed, dict)
        or sealed.get("complete") is not True
        or type(sealed.get("entries")) is not int
        or sealed["entries"] != descriptor["entries"]
        or sealed.get("missing") != []
    ):
        raise ValueError("AI bootstrap catalogue is not completely sealed")
    return dict(
        catalogSha256=descriptor["sha256"],
        entries=descriptor["entries"],
        bytes=descriptor["bytes"],
        startupSealMs=(time.monotonic() - started) * 1000,
    )
