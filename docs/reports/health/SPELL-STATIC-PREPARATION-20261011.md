# Static spell preparation reuse

## Scope and publication

The change reuses static native LOS columns and exact deck validation results.
It does not change spell execution, targeting, live actor blockers, resources,
movement, placement, the native ray program, or rollback transaction copies.
Code and generated data are pending coordinated publication; measurements below
are offline and do not certify that the live spell latency incident is resolved.

## Deck validation

`characters/spells.py` retains the original validator and adds an LRU of 512
successful validations keyed by exact deck bytes, breed, level, and the identity
of the process-pinned spell catalogue. Values contain immutable tuples; each
caller receives new lists. Changed decks, levels and breeds revalidate. Invalid
inputs retain the original parser path and failures are not cached. Oversized or
non-byte-shaped memoryviews bypass cache normalization, avoiding an unbounded
copy before parsing.

The seven new regressions plus five existing spell tests pass (12/12). A small
10,000-call local benchmark measured approximately 34.44 microseconds per
uncached validation versus 0.59 microseconds cached. This reduces repeated work
but cannot explain a several-second spell stall by itself.

## LOS map data

`storage/prepared_los.py` stores trusted local binary derivatives of the existing
native LOS catalogue. Entries are bound to format version, catalogue revision,
map ID and source SHA-256; manifests and payloads are checksummed. Missing, stale
or damaged artifacts fall back to the original catalogue loader. The runtime
cache holds at most four maps. Static column surface order, altitude, height,
transparency and duplicate-coordinate overwrite semantics remain unchanged.

Map 527 prototype: all 168,804 ordered columns match the original validator.
Source JSON plus column preparation measured 0.62495 seconds; checksum plus
binary loading measured 0.02304 seconds, about 27 times faster. These are cold
local component measurements, not end-to-end combat measurements.

The CLI reuses matching valid artifacts without rewriting them and builds only
missing or invalid derivatives. Existing prepared geometry is not regenerated.
Both preparation CLIs acquire a common build lock. Each map runs sequentially
in an isolated worker with a sampled 512 MiB RSS monitor; this monitor is not a
hard OS memory reservation. Bulk LOS equivalence is in progress; its terminal
receipt must be recorded before claiming full inventory completion.

## Manual acceptance after publication

1. Equip a valid deck, enter a fight and cast a spell requiring line of sight.
   Verify normal range, AP/WP payment and damage.
2. Move a character or summon into that ray. Verify it blocks when the spell's
   rules require blockers; move it away and verify visibility changes immediately.
3. Change the deck and enter another fight. Verify newly selected spells work
   and removed spells are unavailable. Repeat after level modulation.
4. Repeat on a different map and compare the first and later casts. Report map,
   local time and spell if a stall remains; a component speedup is not proof
   that every source of latency has been removed.

## Completed inventory gate

The serial coordinator completed all 934 available native maps with exit 0 and
no memory-monitor failures. All 9,632,196 ordered columns match their original
sources; binary derivatives total 165,883,053 bytes (about 158 MiB). Existing map
527 was reused; 933 missing derivatives were built. An independent streaming
SHA reconciliation verified all 934 manifests without hydrating the maps.
Geometry outputs were untouched. Evidence: private receipts
`prepared-los-all-20261011.jsonl` and `prepared-los-reconciled-20261011.json` under
`.runtime/local/diagnostics/`. Five tiny LOS fixture tests pass, including dynamic
blocker changes and stale/corrupt fallback. Runtime publication is still pending.

Final focused gate: 24/24 tests pass in 0.284 seconds. The two additional CLI
regressions prove matching artifacts retain their bytes and mtimes, corrupt LOS
artifacts rebuild, and neither path invokes geometry regeneration.
