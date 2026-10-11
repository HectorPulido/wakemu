# Frozen evidence normalization, version15

Kokolost141 and Conohos136 receive source-only replacements for their frozen version7 configurations. Their serialized topology, plan, native route and level policy are identical. Only configuration version, its context version and recalculated evidence hashes change. Version7 artifacts remain historical evidence and are not rewritten.

The defect concerns integer keys in offline `stage_by_region` metadata: JSON persists those keys as strings, which can change canonical key ordering. Evidence calculated before persistence therefore did not match the installed JSON representation. The general configuration constructor now normalizes and owns inputs before hashing.

The [version15 report](NATIVE-EVIDENCE-NORMALIZED-CANDIDATES-V15-20261010.json) records source artifact hashes and separate canonical JSON and file hashes. The generic tool `server/tools/normalize_dungeon_configuration_evidence.py` rejects gameplay-field changes, verifies all three frozen evidence hashes and confirms full canonical identity after serialization. The regression test covers both actual routes, unchanged source inputs and mutation isolation; it passed.

No encounters, quantities, native gates, transports, optional exclusions, coordinates or rewards changed. Previously recorded route witnesses still describe the same native paths. Independent lifecycle verification of the replacement artifacts remains separate from this evidence-only preparation. No runtime configuration was installed.
