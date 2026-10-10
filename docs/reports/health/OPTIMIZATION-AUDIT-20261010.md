# Cross-system optimization audit — 2026-10-10

## Scope and delivery

Parallel review covered first-party server combat, networking, AI, storage, inventory, characters, maps, dungeons, ecology, profiler, cron, capture tools and repository deployment configuration. This is a ranked audit, not an exhaustive proof of correctness. Native client binaries, third-party libraries, generated assets and localized catalog data were excluded. No gameplay optimization or deployment was performed for this audit.

## Priorities

| Priority | Finding | Evidence and next step |
| --- | --- | --- |
| 1 | Plant growth holds the global combat-group lock across SQL and publication | Source-confirmed contention risk; measure lock hold time before narrowing the atomic boundary. |
| 1 | Shared spell dispatch repeatedly clones and flattens the full fight, including its growing event history | Synthetic growth measured; separate immutable/history state only with rollback and replay regressions. |
| 1 | Native AI searches perform dozens of previews and repeated guards | Live searches around 2.4 seconds; investigate per-query reuse with exact native authority invalidation. |
| 1 | Session health observation takes a write lock | Historical contention amplification confirmed; distinguish observation from renewal with ownership-race tests. |
| 1 | Native surface construction occasionally costs 24.7 CPU seconds | Same map costs 0.641 CPU seconds in a fresh process; root cause unresolved. Preserve longest GC telemetry before changing policy. |
| 1 | Capture hooks synchronously flush disk writes on the client network thread | Source-confirmed risk; prior measurements do not prove it caused minute-long freezes. |
| 2 | Character hydration, catalog cold decoding, geometry reconstruction and profiler artifact/status handling | Concrete source candidates requiring isolated measurements. |

## Detailed reports

- [Combat and networking](OPTIMIZATION-AUDIT-COMBAT-20261010.md)
- [AI service](OPTIMIZATION-AUDIT-AI-20261010.md)
- [Storage and character/inventory reads](OPTIMIZATION-AUDIT-STORAGE-20261010.md)
- [Maps, geometry, dungeons and ecology](OPTIMIZATION-AUDIT-MAPS-20261010.md)
- [Profiler, cron and capture tools](OPTIMIZATION-AUDIT-TOOLS-20261010.md)
- [Repository/client configuration](OPTIMIZATION-AUDIT-REPOSITORY-20261010.md)

## Language cleanup

Translated developer docstrings, scenario labels and CLI diagnostics in `server/tools/name-items.py`, `server/tools/name-monsters.py`, `server/ai-service/scripts/acceptance.py` and `sniffer/authenticate.py`. All four files pass AST parsing. Markdown/text documentation, native identifiers, localized game messages and catalog/fixture data were preserved. SQL/root scripts and first-party client configuration review found no additional developer comments to translate.

## Verification and limitations

- GC monitor/profiler regression bundle: 11 passed.
- Profiler service and capture audit: 18 passed; authentication script syntax passed.
- Additional AI contracts: 114 tests, 1 failure and 3 errors in native oracle eligibility (`twI`).
- Tactical/server AI bundle: reported 2 failures and 4 errors; incomplete owned QI fixtures explain the four authority errors, while failed action expectations remain unresolved. These checks do not constitute a green full suite.
- No manual gameplay acceptance is required for developer-text-only changes. Future performance changes must preserve duel placement, movement/range, native turn ACKs, summons, surrender, spectator replay and transactional rewards.
