# Native mining surface extraction

The inspection tool reads installed environment and topology archives using the
installed native `aIl` and `VB` decoders. It combines their literal coordinates,
heights and ground IDs with native mineral suitability. It does not change client
assets, launch a client, modify server state or implement gameplay in a sniffer.

## Results

`NATIVE-MINING-SURFACES.json` records961 matched environment/topology map archives,
29798 successfully decoded chunks, and2980 suitable mineral surfaces across47
maps. Each row contains map/x/y/z, native ground, eligible mineral references,
chunk identity and environment chunk SHA256. Per-map environment and topology
archive SHA256 values preserve provenance. The output deliberately says
`official_fixed_spawns_extracted=false` and
`importable_without_distribution_policy=false`.

The scan records1509 unsupported chunks rather than silently treating them as
empty. Of those,1440 throw `BufferUnderflowException`; the others are native
array-bound failures. Their map/chunk identities are in the output. Coverage is
therefore partial. A scoped scan of maps527,1134 and1086 decodes1207 chunks and
finds220 candidate surfaces without errors. That number includes all eligible
mineral species, unlike the earlier resource37-only review.

## What these assets establish

`aIl` decodes ground tables, environmental scalars/timestamps and traversal areas.
Its parent `ach` decodes interactive objects, decorations and effects. None of
these inspected structures supplies a mineral population with species, stage,
spawn identity and respawn deadline. A suitable terrain cell is evidence of where
a mineral is allowed, rather than proof that an official fixed vein exists there.
Some surfaces have one eligible mineral; others may have several. No arbitrary
mineral is selected by this extractor.

This scan does not establish that every script or every other asset format lacks
spawn information. No unverified byte-pattern match is promoted to a placement.
The current dynamic resource publication contract13135 still requires
server-owned resource data.

## Proposed import boundary

Keep these evidence rows separate from gameplay slots. A slot import should
require an explicit distribution policy and preserve `(map,x,y,z,ground)` plus
archive/chunk provenance and the chosen mineral's eligibility proof. Record the
fixed slot independently from its current active/exhausted resource. Configure
respawn in PostgreSQL, restore a slot once transactionally, and exclude minerals
from flora ecology. Do not use native terrain suitability as a claim of official
population density or rare-mineral frequency.

## Reproduction

From the repository root, with existing read access to the native PostgreSQL
catalogs and `JAVA_HOME` pointing to JDK21 or later:

```bash
PYTHONPATH=server .runtime/local/verification-venv/bin/python \
  client-tools/inspection/export-mining-surfaces.py \
  docs/reports/mining/NATIVE-MINING-SURFACES.json
```

The tool uses the existing `WAKFU_DATABASE_URL` and
`WAKFU_DATABASE_PASSWORD_FILE` environment configuration to read catalogs; do not
put credentials in the command or report. Add `--maps 527 1134 1086` for a scoped
scan. Java compilation is confined to an automatically removed temporary folder.

The focused regression `test_mining_surface_inspection` passes and checks that
an explicit resource suitability of zero overrides a positive family rule and
that other professions do not become mineral candidates. Native archive scans
above additionally exercise the real installed decoders.
