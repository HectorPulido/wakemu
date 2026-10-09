"""Pinned bulk original bhe model selection for ordinary owned class sources."""
from wakfu_server import native_catalog as protocol_catalog
from functools import lru_cache
import hashlib
import json
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def _models():
    path = DATA_ROOT / "native-class-copy-appearance.json"
    if not protocol_catalog.exists(path):
        raise ValueError("Missing original class-copy appearance model catalog")
    data = protocol_catalog.load(path)
    seed = DATA_ROOT / "breed-innate-definitions.json"
    seeds = {str(row["breed"]) for row in protocol_catalog.load(seed)["breeds"]}
    rows = data.get("breeds")
    if (
        data.get("schema") != 1
        or data.get("cloth_offset") != -128
        or data.get("class_seed_sha256")
        != hashlib.sha256(protocol_catalog.read_bytes(seed)).hexdigest()
        or not isinstance(rows, dict)
        or set(rows) != seeds
        or len(seeds) != 18
    ):
        raise ValueError("Incomplete original class-copy model source")
    for sex_rows in rows.values():
        if not isinstance(sex_rows, dict) or set(sex_rows) != {"0", "1"}:
            raise ValueError("Missing native class sex model population")
        for models in sex_rows.values():
            if (
                not isinstance(models, list)
                or len(models) != 256
                or any(
                    type(model) is not int or not -32768 <= model <= 32767
                    for model in models
                )
            ):
                raise ValueError("Incomplete native class cloth model population")
    if (
        not isinstance(data.get("jar_sha256"), str)
        or len(data["jar_sha256"]) != 64
        or not isinstance(data.get("bdata_sha256"), str)
        or len(data["bdata_sha256"]) != 64
    ):
        raise ValueError("Missing original model export provenance")
    return rows


def native_class_copy_model(breed, sex, cloth):
    if (
        type(breed) is not int
        or not -32768 <= breed <= 32767
        or type(sex) is not int
        or sex not in (0, 1)
        or type(cloth) is not int
        or not -128 <= cloth <= 127
    ):
        raise ValueError("Uncertified native ordinary class model operands")
    rows = _models().get(str(breed))
    if rows is None:
        raise ValueError("Class outside owned copied appearance source domain")
    return rows[str(sex)][cloth + 128]
