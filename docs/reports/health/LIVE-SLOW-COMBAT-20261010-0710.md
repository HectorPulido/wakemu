# Live repertoire metadata encoding stall, 07:10 UTC

Read-only investigation of r68. Evidence retained under `.runtime/local/diagnostics/slow-combat-20261010-0710/`. No service restart or runtime change.

Fight 150 event 07:10:53.577198 UTC reports 16,416.258 ms decision elapsed, 15,820.996 ms search, and one failed `repertoire` query consuming **15,703.049 ms wall / 15,547.897 ms thread CPU**. Casting prerequisites take 1,067.771 ms wall / 931.582 ms CPU inclusively. Source guards are only 7.805 ms wall / 7.268 ms CPU over three calls. Context inventory takes 166.860 ms. The immediately following tactical event duplicates these metrics; do not count it as another query.

Capture `capture-1791616182464572124`: session thread 268 has 94 identical recursive encoder samples. Following `capture-1791616242705288963`: 259/1445 identical samples. Path:

`run_turn → decide:1197 → query:1218 → _query:1261 → _measure_native_query:1238 → _query_unmeasured:1373 → native_context.encode:264 → _encode:243 → visit:164 / visit:182`.

Line 1373 encodes **repertoire metadata**, via `result = dict(nativeMetadata=self.transport.instance(encode(metadata)))`. This is not the prior root-state fingerprint bottleneck. Dictionary/list graph encoding is the dominant sampled computation, corroborated by the 15.55 seconds of measured thread CPU. The precise metadata branch responsible for exceptional size remains to be identified.

Transport reports 3,672,673 sent bytes, 733 received bytes, and 0.357 seconds of request time. Network waiting does not explain the 15-second query. The other socket thread is predominantly in SSL receive, with smaller health-query waits; those are not CPU work.

Candidate corrective boundary: bounded/cooperative encoding with the existing deadline and inspect repertoire metadata shape/size to avoid repeatedly exporting oversized immutable native data while preserving complete native authority. Do not weaken source guard or omit required metadata. No corrective code was implemented here.

## Offline shape and allocation probes

Read-only isolated Python subprocesses in the existing world container loaded native catalogs through their normal read API. These did not introspect or mutate live process objects. Casting has 4,143 records; its largest single JSON record is spell 753 at 120,403 bytes. Class effect metadata has 730 records, maximum 24,472 bytes. The failed live query has no target-envelope timing, excluding that measured provider from its slow path. Prerequisite output is a compact unavailable-spell list, not the root catalog itself.

A synthetic repertoire holding the largest casting record, its optional class definition and no class inventory encoded to 11,007 nodes / 903,021 JSON bytes. First encoding consumed 1,197.52 ms thread CPU, subsequent encodings 27.19 and 17.98 ms. A separate isolated run with local GC callbacks measured first encoding 1,374.81 ms CPU and a generation-1 collection of 629.35 ms, collecting zero objects. This **proves allocation-triggered GC can account for substantial encoder time without an intrinsically huge metadata field**; it does not prove the exact live 15-second stall was GC because that process lacked GC callback evidence. Avoid asserting that a specific repertoire field is enormous merely from sampled Python allocation frames.

Post-r68 aggregate (boot `12266a9c5cb94dcfb753857809140eb8`) has only four distinct completed decision metric sets so far, with identical duplicate logs deduplicated. Repertoire: four calls, 15,733.869 ms wall / 15,568.776 ms CPU, one failure. Prerequisites: four calls, 1,068.310 ms wall / 932.105 ms CPU. Guards: 33 calls, 97.822 ms wall / 87.390 ms CPU, maximum 5.688 ms. Small sample size; inclusive query metrics overlap and must not be summed into process CPU. Aggregate saved as `aggregate-post-r68.json` beside raw evidence.
