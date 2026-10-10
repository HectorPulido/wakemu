# Native AI source guard deadline enforcement

A live fight 139 diagnostic recorded 12 source-guard calls totaling approximately 32,290 ms wall / 32,239 ms thread CPU, with a single call around 32,119 ms. The sampled stack was complete fingerprint traversal (`_CompletePickler.reducer_override`, dictionary iteration). This is CPU work inside source validation, not evidence of a PostgreSQL checkpoint stall.

## Confirmed defect and narrow correction

The prior fingerprint built a full protocol-5 pickle in `BytesIO` and hashed it afterward. It never checked the cooperative native owner deadline during traversal. Consequently a source guard could continue for roughly 32 seconds even after the AI owner's time budget expired.

The new writer hashes the exact same protocol-5 bytes incrementally. It checks the owner deadline while writing pickle frames, between 64 KiB blocks of raw data, inside native object reducers, and before returning. Expiration raises the existing `TimeoutError`; no partial fingerprint or decision is accepted. All fields, container subclasses, aliases, cycles and future instance data remain included. The change does not cache or skip authority state.

This bounds cooperative work and reduces temporary serialization memory. It does not prove that a normal successful source guard is now cheap, or eliminate the underlying large graph.

## Validation

- Seven fingerprint tests pass, including byte-for-byte legacy digest equality, cycle/alias preservation, mutation detection, deadline expiration during builtin-container serialization, and bounded temporary allocation for an 8 MiB payload.
- Fifteen native turn tests pass. A source-guard timeout rejects the pending cast without spending AP, commits only the native end-turn barrier, and leaves no pending packets or ACK wait.
- An 8 MiB raw payload benchmark produced the identical digest prefix `a393d3ac2ac8`. Legacy buffering peaked at 9,437,785 traced bytes; streaming peaked at 9,010 traced bytes. Single measured elapsed times were 6.664 ms and 9.616 ms respectively. This is a memory/deadline improvement, not a demonstrated CPU speedup.

## Remaining cause investigation

A concrete source-code path can pull static catalogue views into the complete runtime graph:

`runtime.fight.native_rail_movement_authority` → `RegisteredSummonAuthority.ordinary` → `OrdinaryActorAuthority.catalog` → `ImmutableCatalog`.

`ImmutableCatalog` retains raw `_source` and lazily populated `_views`. Its overridden `items()` iterates through `self[key]`, freezing nested catalogue values on access. The complete fingerprint's dictionary-subclass reducer calls `value.items()`, which can therefore populate lazy views while walking a whole catalogue. The fields also include `_source` and `_views`, creating additional complete graph work. This is a plausible contributor to the long first traversal; live field-level attribution has not yet proved that this exact catalogue owns the measured 32 seconds.

No dictionary method bypass, field omission, global immutable cache or mutation-guard weakening was applied. Any subsequent optimization must preserve complete source semantics and test lazy catalogue publication, mutations, aliases and receiver serialization together.

## Follow-up: confirmed lazy dictionary traversal, 01:54 local

Fight 147 confirmed 26.29 seconds of source-guard thread CPU. The continuous capture includes `ImmutableCatalog.items` below the fingerprint reducer. Calling overridden dictionary views eagerly froze large catalog arrays before yielding, defeating cooperative deadline checks inside that method.

Fingerprint and lossless native transport now enumerate actual dictionary storage using `dict.items(value)`. Both still include subclass descriptors, all instance fields (including `_source` and existing `_views`), aliases and cycles. They no longer invoke custom dictionary iteration or mutate lazy views merely to inspect state. Normal dictionaries retain their prior representation; subclass views are intentionally represented by actual stored entries plus complete fields. No authority data is omitted or cached by object identity.

Validation: 95 focused AI tests passed across context, fingerprint, session, turn, catalog, bridge and actor source. Regressions cover hostile dictionary hooks, actual lazy ImmutableCatalog, retained private/slot state and mutation detection. Broader existing oracle fixtures still fail on missing movement authority and `twI` eligibility; these are not claimed green. See LIVE-SLOW-COMBAT-20261010-0654.md for preserved evidence.
