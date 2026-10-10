# Exact boss identity expansion — 2026-10-10

Eight previously blocked physical routes now pass offline preparation, six-player combat formation, directed engagement and gate progression, and native exterior exit validation. PostgreSQL lifecycle verification and activation are owned by the main agent. No runtime changes were made by this extraction.

## Identity authority

The extractor accepts only an archived section heading of the form `2.4 – Exact Native Name (Boss)`. The name must match exactly one species in the native dungeon pool. Each identity retains the article URL, local archive path, SHA-256, line number and literal heading. It rejects prose, substring matches, names outside the pool, duplicate names, and multiple distinct boss headings. It never selects bosses by level.

The guide client-version match remains unverified; these headings establish identity, not boss mechanics or official encounter quantities. Missing roster quantities remain explicit local policy.

| Dungeon | Native boss | Rooms |
|---|---|---|
| Compost del Gran Calabaciflor | Potofeu, Grand maître culinaire (`5471`) | 2 |
| Mazmorra del Clan de Bworkana | Zulnara, cheffe de guerre (`5644`) | 2 |
| Mazmorra Abrakna | Abraknelle (`4107`) | 3 |
| Mazmorra de los Primacizos | Imagori (`5632`) | 2 |
| Mazmorra de los Sabanastrales | Timö le possédé (`5638`) | 2 |
| Dique Eskuálido | Royal Skouale (`4244`) | 3 |
| Panteón Viviente | Morfor (`3216`) | 3 |
| Pío Lajop | Piou Royal (`1187`) | 3 |

## Remaining blockers

The physical composition audit still has 23 routes lacking an explicit reviewed boss identity. No archived exact heading tied to their native species pool was found. Names suggesting royalty, higher levels, or final position in the pool were deliberately not treated as evidence. The corresponding records remain blocked pending additional guide/native script evidence. This is an evidence gap, not an established engine limitation.

Full candidate and path witnesses: `BOSS-IDENTITY-CANDIDATES-20261010.json`. Identity evidence: `EXACT-BOSS-IDENTITY-EVIDENCE-20261010.json`.

## Validation

`PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_dungeon_boss_identity_extraction.py`: 5/5 passed. All eight candidates passed the existing formation validator and `validate_prepared_physical_flows.validate` without adapting geometry or changing combat/spells. Boss spells, immunities, scripted phases and special rewards remain unverified.
