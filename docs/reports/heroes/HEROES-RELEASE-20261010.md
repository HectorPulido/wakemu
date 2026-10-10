# Heroes release candidate — 2026-10-10

The primary acceptance is one selected character plus two actual owned heroes appearing in the same ordinary PvE combat, in separate placement cells, with individual turns and actions from one account session.

## Prepared image

- Image: `wakemu-world:heroes-ready-20261010`
- Image ID: `sha256:3f904524b08eab411fdae5ffa3adc2da60e33890336fe0badc05bc14e7b3e5e3`
- Complete shared server build; 687 source and migration files verified against the image, without mismatches.
- Character limit defaults to 18; `WAKFU_MAX_CHARACTERS` accepts 1–127.
- Migration 098 stores the owned company roster.
- Deployed after explicit user authorization. The existing world container was replaced; migration 098 applied, HTTP health returned OK, and all 687 deployed source/migration files match the validated image. Runtime character capacity is 18. A pre-deploy gameplay database backup excludes immutable native catalog data; a separate full archive was also started.

## Validation

- 73 core combat/hero tests passed, including real PostgreSQL admission, three placement positions, and three characters taking turns and actions under one session.
- 16 capacity/creation/deletion checks passed, including default 18.
- 7 activation/placement checks passed after adding native 12093 activation.
- 4 owned-hero rift/dungeon/deletion lifecycle checks passed.
- Native Java decoder accepted a real Store-created character activation: entity ID 1, build indices [0], aptitude indices [0]. Native company options and hero party identity flags were inspected against actual client consumers.

The native 12093 message activates owned heroes; 13046 only refreshes existing actors. Company/bootstrap publication now uses activation. Hero party rows carry the native hero flag so removal deactivates them correctly.

## Manual acceptance after deployment

1. Log into an account containing three living characters. Open the heroes/company interface and add the other two characters.
2. Start an ordinary monster fight. Before readying, verify that all three characters appear in separate allied cells. This is the primary gate.
3. Ready the account once. On each character’s turn, move and cast one of that character’s own spells. Expect control of all three without logging another account in.
4. Finish or withdraw. Start another ordinary fight and verify that all three still enter. Reconnect and repeat.
5. Remove one hero, start another fight, and expect two allied characters. Add it again and expect three.
6. Enter Tofullero with both heroes, exit using `!exitdungeon`, and reenter without leaving the party. Expect the company to remain together. Repeat in a dimensional rift; entry must not create extra account sessions.

Graphical client acceptance remains pending. Secrets are deferred by user instruction.
