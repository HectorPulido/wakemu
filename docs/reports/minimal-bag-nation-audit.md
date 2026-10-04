# Minimal bag and nation audit

Local SQLite `world.sqlite3` character IDs 1–6 contain model408, only room0 enabled with starting commerce gem4262, eight disabled empty room slots and no furniture. There is no persisted captured set of additional gems in these rows. Nine serialized slots are configuration positions; disabled empty slots are not enabled rooms. Model408 contains native static decoration, so a rendered object alone does not demonstrate an owned furnishing or gem. No personalization was deleted by this audit. The Docker live database has not been inspected here.

`wire.minimal_entity` already replaces nation IDs with0. It previously retained format11 `NATION_SYNCHRO` from the fixture. Native `rk.aF/aG` encode three i64 fields (rank/jobs/voteDate), then three bytes (governmentOpinion/isCandidate/pvpRank). Both constructor and `clear` initialize all fields to0. The adapter now replaces this section with27zero bytes. This removes inherited political state; it does not establish the separate cause of the visible Amakna passport label.

Validation:18 wire tests passed, including captured nonzero political values replaced with exact27byte empty state while surrounding bytes remain unchanged. No service restart or GUI action performed.
