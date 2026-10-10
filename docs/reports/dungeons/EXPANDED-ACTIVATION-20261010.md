# Expanded native dungeon activation — 2026-10-10

Eighteen additional configurations were activated in `wakemu_runtime`: ten native teleport flows and eight physical flows. Eight existing physical configurations, including manually accepted Tofullero, were preserved. Readback verifies all **26 routes**, their immutable version 3 configuration and matching context-policy pointers: **16 physical, 10 teleport, 67 rooms**.

No world restart, client modification or combat/spell deployment was required. Six deployed dungeon core module hashes match the tested shared checkout. Existing runs keep their pinned configuration; exit an old run before starting acceptance. Other pre-existing generic dungeon configurations are not counted as these 26 validated native flows and were not removed.

## Added routes

Physical: Cañón de los Plaguepardos, Kaníbola, Kanívoras, Plantiguardias, Cresta Helada, Fuente del Mal, Tumba de Pandala and Volcán Or'Hodruin.

Teleport: Castillo de los Cangwejos, Arakna, Crustariscos, Cocodrails Delnilo, Trópikos, Gerbilinda, Güinos, Vandalienados, Torre Helada and Fábrica Buhatrás.

The eight physical additions adapt guide compositions to proved native physical regions under an explicit local playable policy. Species and reviewed final bosses are retained; official room quantities/order are not certified. Boss spells, special AI, phases, invulnerability and balance remain incomplete across this activation.

## Validation and activation evidence

- Independent isolated PostgreSQL lifecycle tests cover all 26 frozen configurations, 67 room victories and 201 reward receipts for three players. They verify progression/reward rollback, replay, native exits, member rejoin and fresh reentry using authoritative terminal-fight fixtures; they do not simulate boss combat.
- Twelve focused activation/readiness/native-teleport tests pass, including preservation of existing physical and teleport configurations.
- Lifecycle evidence embeds the exact candidate file SHA-256 values; activation rejects changed source/configuration evidence.
- [Physical lifecycle evidence](EXPANDED-PHYSICAL-PG-LIFECYCLE-ECONOMY.json), [teleport lifecycle evidence](AUTOMATIC-TELEPORT-PG-LIFECYCLE-ECONOMY.json).
- [Physical activation](EXPANDED-PHYSICAL-ACTIVATION-20261010.json), [teleport activation](TELEPORT-ACTIVATION-20261010.json), [post-commit database readback](ACTIVATION-READBACK-20261010.json).

Private pre-change settings/context backups are `.runtime/local/backups/expanded-physical-activation-20261010.json` and `.runtime/local/backups/teleport-activation-20261010.json`. They preserve prior pointers and immutable configurations. No destructive schema migration occurred.

## Concrete blockers

[The per-definition audit](EXPANSION-BLOCKERS-20261010.md) records the first failed gate for all remaining inventory entries, with [machine-readable evidence](EXPANSION-BLOCKERS-20261010.json). Its preparation statuses describe extraction; activation/readback above supersede pending labels for the 26 successful configurations. The 156-entry denominator includes variants, legacy guide records and rifts; a dungeon-extractor failure is not a regression of the separately implemented rift system.

- **Kaskarlusca:** room 3 anchor `[-37,-11,4]` cannot provide safe reachable combat terrain for its encounter and six-player formation. Need a verified same-room alternative; do not move an encounter behind a gate or outside its room.
- **Sliptorium:** the three-room transport chain is proved, but no unique free native exterior exit is bound to the final room. Need the literal exit source, approach and destination, or a proved backtracking contract.
- **Hacienda de la Balinería, Neohacienda de la Balinería, Montaña Conohos and Escarantera Abandonada:** mixed physical doors/internal transports may bypass the walking sequence. Need combined transport/door reachability and victory-unlock validation.
- Remaining first failures include missing reviewed final boss identity, unresolved native species, malformed/oversized guide quantities, ambiguous physical flow, open geometry without proved encounter order, and missing usable exterior entry.

## Manual acceptance order

Test **Fuente del Mal**, **Plaguepardos**, **Or'Hodruin**, **Castillo de los Cangwejos**, then **Torre Helada** first. The first three have adapted encounter stages; Cangwejos has stacked heights; Torre Helada has a distinct exterior-return landing. Continue through the other newly activated routes afterward.

[Exact teleport commands, entrance positions and the complete acceptance sequence](ACTIVATION-MANUAL-RISK-20261010.md) cover ordinary three-player parties, each locked/unlocked transition, nonleader exit/rejoin, final exit, fresh reentry and a subsequent heroes pass. Tofullero remains accepted and does not need its basic solo test repeated.
