# Startup catalog compilation: sampled finding

No runtime optimization was implemented for this finding.

## Follow-up performance audit

The subsequent performance audit compared the current checkout with the running
world container's `/app/wakfu_server/combat/combat_native_area_metadata.py`.
Both use the same implementation. Metadata lookup is already a dictionary lookup
by `str(reference)`. The identity generator compares exactly three fields, rather
than searching the metadata collection. Adding an identity index would therefore
not remove a linear search and is not justified by this sample.

The enclosing operation still visits each supplied effect once and preserves all
identity and offset validation. No runtime change was made: the sample establishes
cold compilation cost, while the current reported multi-minute gameplay stalls
require evidence from ongoing gameplay. This audit does not establish that the
startup function causes those stalls, nor that its validation can be skipped.

## Evidence

Private capture: `.runtime/local/profiler/capture-1791579584453883663.speedscope.json`.
The external sampler ran at 25 Hz for five seconds and reported 123 samples and
one sampling error. Its sampled profile contains 4.92 seconds of MainThread
samples. Leaf attribution includes:

| Leaf | Sample weight |
| --- | ---: |
| `merge_native_point_areas`, line 17 | 1.88 s |
| Identity-comparison generator, line 24 | 1.76 s |
| `merge_native_point_areas`, line 16 | 1.00 s |

These three leaves account for 4.64 of 4.92 sampled seconds (94.3%). They are
sample weights, not directly timed calls or a complete startup measurement.
The stack is `main → prewarm_runtime_catalogs → weapon_runtime_catalog →
CompiledEffects → merge_native_point_areas`.

This is evidence of **startup compilation cost**, not evidence that the same
work delays movement, checkpoints, or every spell cast. The compiled weapon
catalog is cached once per process. Capture normal gameplay separately before
ranking this against recurring latency.

## Source review

`merge_native_point_areas` copies the entire effect mapping, scans every effect,
validates three identity fields for native point areas, compares existing point
offsets, and copies matching effect records to attach the offsets. Complexity is
linear in the number of definitions plus the total compared point-offset data;
space includes the full copied mapping and enriched effect records.

The weapon compiler starts from the base spell catalog's source definitions,
merges weapon definitions, then compiles the combined spell/state definitions
again. Reusing already validated immutable base definitions could reduce repeated
startup work, but only after checking merge conflicts and immutable-value
semantics. Removing validation or skipping definitions would change safeguards.

## Deferred verification proposal

If optimization is authorized later, compare the existing implementation and a
candidate over every shipped effect definition, including weapon and state
merges. Normalize immutable containers for semantic comparison and require exact
point offsets and all retained fields. Add bounded fixtures covering missing
metadata, all three identity conflicts, existing identical/different offsets,
non-point areas, empty inputs, and input non-mutation. Require the same exceptions
and retain separate transaction contexts/RNG. Measure cold compilation time and
peak memory in an isolated process, then prove warm combat paths do not regress.

Until those checks exist, this remains an observation and a future optimization
candidate, not a deployed performance fix.
