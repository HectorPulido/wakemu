# Limitations and useful next steps

[Wiki home](README.md) · Related: [Contributing](contributing.md)

Wakemu is an experiment, not a complete replacement for the official game. Source implementation, automated verification, deployed images, and manual acceptance are separate milestones. This page describes broad gaps rather than keeping a release-by-release issue ledger.

## Areas that need work

- **Reproducible installation:** world still depends on ordered bootstrap records and separately prepared runtime inputs; current source loads those records from PostgreSQL, while older image/configuration paths use a private capture file.
- **Combat completeness:** shared effects, class mechanics, summons, and monster abilities need broader end-to-end validation; unsupported behavior must remain explicit.
- **Performance:** fight startup, tactical search, spell handling, and client synchronization still need measurement and refinement.
- **Dungeons and rewards:** supported encounter and reward paths do not establish complete dungeon, boss, difficulty, or loot coverage.
- **NPCs and quests:** many definitions lack the placement, dialogue transitions, objectives, or reward integration needed for a complete playable story.
- **Social and item systems:** specialized channels, duels, personal spaces, and advanced item behavior have uneven coverage and remaining acceptance work.
- **Client compatibility:** only Wakfu 1.93.1+79 is targeted; another installation version may have incompatible protocol or resource layouts.
- **Portable testing:** some historical integration and research checks still require private inputs or an explicitly configured test database.

## High-value contributions

A reliable first-run path, synthetic protocol fixtures, reusable missing combat operations, and complete gameplay regression journeys would make the project easier for others to use. Bug reports are most useful when they include the client version, reproduction steps, expected behavior, and sanitized logs.

Internal issue records and detailed evidence remain in `agents_docs/`; they may include historical or source-only work. Check current code and image contents before treating an old report as a description of the running server.
