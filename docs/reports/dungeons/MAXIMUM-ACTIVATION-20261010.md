# Further dungeon activation — current 2026-10-10

The first 26 routes were not the maximum. Further automatic extraction and validation activated **21 more**, giving **47 verified native flows: 37 physical/open arenas and 10 teleport flows, covering 102 encounter stages**. All configuration and context-policy pointers were read back from `wakemu_runtime` at immutable version 3. Existing generic configurations remain untouched and are not counted as validated native flows. No world restart or client change occurred.

## Added after the first pass

- Ten one-boss arenas: Excarnus, Nogord, Cuervo Negro, Dragocerdo, Maxilubo, Nox, Sombría, Rushu, Garras de Acero and Ogrest. Native singleton identity, directed arrival/engagement/exit and six-player formation are verified. Their previous generated eight-boss duplicates are replaced by an explicit local one-boss initial roster.
- Eight formerly unresolved boss identities: Compost del Gran Calabaciflor, Clan de Bworkana, Abrakna, Primacizos, Sabanastrales, Dique Eskuálido, Panteón Viviente and Pío Lajop. Archived explicit boss headings are joined to exact native species names, with source URL, line and hashes.
- Kaskarlusca: the one-cell stair region is contracted into the next encounter stage without removing any gate. Both stair gates open after room two; three full encounters remain.
- Torre Mineral and Guarida de Kali: one reviewed encounter each, preserving three known accompanying monsters and one identified boss. Kali's two equivalent native exit objects share the exact same exterior destination; the binding is canonicalized with alias evidence.

These are playable local configurations, not certification of official room quantities, special boss mechanics or balance. Nox, Rushu and Ogrest still need score/timer/phase implementation; none is certified mechanically complete.

## Validation and release evidence

Independent isolated PostgreSQL lifecycle gates cover the 47 active configurations, **102 room victories and 306 reward receipts** for three players. They check reward/progression rollback, receipt replay, entry/exit, partial rejoin and fresh reentry using authoritative terminal-fight fixtures, not simulated boss AI. The combined focused source regression suite passes **47/47 tests**, covering activation, geometry, boss identity, transit contraction, exit proof and object states.

[Database readback](MAXIMUM-ACTIVATION-READBACK-20261010.json) contains every active route, version, configuration hash and exact exterior command. Each activation batch has a corresponding immutable configuration/hash lifecycle audit and private pre-change settings/context backup in `.runtime/local/backups/`. New batches are `OPEN-BOSS`, `ADDITIONAL-PHYSICAL`, `BOSS-IDENTITY` and `REVIEWED-OPEN-ARENA`; their activation reports and lifecycle evidence are in this directory.

## Remaining activation limits

Sliptorium is prepared and its actual backward native exit passed isolated PostgreSQL validation. It is **not active**: the running object-state module rejects intermediate-room exterior exits. The necessary narrow source change and tests are ready, but a complete shared server build/deployment is required before activation. [Exact source/deployed hashes, native exit chain and blocker](SLIPTORIUM-BACKWARD-EXIT-20261010.md).

Four mixed walking/teleport routes still have proven bypasses or unassigned annexes; [counterexamples](MIXED-NATIVE-TRANSPORT-BLOCKERS-20261010.md) identify literal source and destination IDs. Other remaining entries need reviewed initial composition, boss identity, safe native route ordering or compiled/registered route bases. These are missing evidence or implementation, not proof they can never work.

[Current per-definition blockers](MAXIMUM-ACTIVATION-BLOCKERS-20261010.md) supersede the earlier 26-route snapshot. The 156-entry inventory includes legacy records, variants and rifts: 47 validated active flows, one deployment-blocked prepared candidate, and 108 other blocked preparations. Separately implemented rifts are not invalidated by this dungeon extraction audit.

## Manual handoff

Prioritize Kaskarlusca, Pío Lajop, Torre Mineral and Kali, then the earlier Cangwejos/Torre Helada transport cases. [All 47 exterior commands and the complete party/hero acceptance sequence](MAXIMUM-ACTIVATION-MANUAL-20261010.md). Leave old instances before testing so the new run selects version 3; Tofullero's accepted solo basics need not be repeated.
