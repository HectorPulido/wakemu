# Feca current catalog and execution audit

## Authoritative scope

Read-only PostgreSQL active revision `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`; breed1FECA.
The class owns21active and18passive spells. Additional granted spells7009
(Armadura de la Paz) and7052(Teletransportación), plus innate6381/4464/7560,
produce44root seeds. Current structural closure contains1620effect nodes,
72states and9areas. Every reached effect family has a current factory binding.
Bindings and source reachability do not establish correct gameplay.

The full metadata snapshot is `feca-catalog-audit-20261010.json`; its
`dynamic_reconciliation` follows current children, all integer parameter levels
0..250, state definitions, granted books, area roots and literal criteria.
Historical edges are comparison evidence only. The independently pinned SQL
snapshot `feca-published-catalog-20261010.json` also includes8commonpassives;
its1634effect/67state counts have a different closure scope and must not be
substituted for the class-only dynamic totals.

The apparent missing `effect:11` is only a `HasEffectWithSpecificId(target,11)`
criterion operand in305228/305240. It is not a missing executable definition.
No native definition is fabricated. No catalog was activated or service changed.

## Root inventory

| Root | Name | Effects | States | Areas |
|---|---|---:|---:|---:|
| spell:6967 | Fecalistófedes | 130 | 6 | 6 |
| spell:6968 | Meteorito | 249 | 21 | 6 |
| spell:6969 | Ataque Natural | 146 | 8 | 6 |
| spell:6970 | Magma | 249 | 21 | 6 |
| spell:6971 | Volcán | 267 | 21 | 6 |
| spell:6972 | Gota | 240 | 17 | 6 |
| spell:6973 | Onda | 125 | 6 | 5 |
| spell:6974 | Avalancha | 153 | 6 | 6 |
| spell:6975 | Tormenta | 140 | 6 | 6 |
| spell:6976 | Filo Abisal | 240 | 17 | 6 |
| spell:6977 | Golpe Telúrico | 299 | 22 | 6 |
| spell:6978 | Orbe Defensivo | 317 | 22 | 6 |
| spell:6979 | Bastión | 147 | 7 | 6 |
| spell:6980 | Muralla | 317 | 22 | 6 |
| spell:6981 | Bastón | 299 | 22 | 6 |
| spell:6982 | Inmune | 6 | 2 | 0 |
| spell:6983 | Tregua | 3 | 0 | 0 |
| spell:6984 | Pacificación | 20 | 2 | 0 |
| spell:6985 | Provocación | 13 | 3 | 0 |
| spell:6986 | Égida | 6 | 2 | 0 |
| spell:6987 | Magnetismo | 8 | 0 | 0 |
| spell:6988 | Glifo Aumentado | 74 | 5 | 4 |
| spell:6989 | Línea | 1 | 0 | 0 |
| spell:6990 | Uno para Todos | 1 | 0 | 0 |
| spell:6991 | Maestro de los Escudos | 20 | 1 | 0 |
| spell:6992 | Quien Quiere la Paz Prepara la Guerra | 3 | 0 | 0 |
| spell:6993 | Trato Pacifista | 13 | 0 | 0 |
| spell:6994 | Conocimiento del Mapa | 1 | 0 | 0 |
| spell:6995 | La Mejor Defensa es el Ataque | 12 | 2 | 0 |
| spell:6996 | Armadura de Combate | 9 | 0 | 0 |
| spell:6997 | Piel Rocosa | 7 | 1 | 0 |
| spell:6998 | Ojo por Ojo | 12 | 3 | 0 |
| spell:6999 | Glifos Persistentes | 1 | 0 | 0 |
| spell:7000 | Pastor | 1 | 0 | 0 |
| spell:7001 | Experiencia del Terreno | 6 | 1 | 0 |
| spell:7002 | Escudos Elementales | 1 | 0 | 0 |
| spell:7003 | Caparazón de Espinas | 88 | 2 | 0 |
| spell:7004 | Comprensión del Wakfu | 7 | 0 | 0 |
| spell:7005 | Protector del Rebaño | 14 | 1 | 0 |
| spell:7009 | Armadura de la Paz | 26 | 2 | 0 |
| spell:7052 | Teletransportación | 13 | 0 | 0 |
| state:6381 | state:6381 | 50 | 4 | 0 |
| state:4464 | state:4464 | 130 | 8 | 0 |
| state:7560 | state:7560 | 1 | 1 | 0 |

## Existing evidence and remaining risks

- `test_combat_feca_start` verifies actual6992Ready initialization and rollback.
- `feca-glyph-manual-readiness-20261008.json` records actual6967glyph creation,
  owned movement and normal expiry on a real map; graphical acceptance remains
  pending. It does not validate all nine glyphs or optional passive variants.
- Shield amounts, damage absorption and removal must be qualified numerically
  on actual self/allied/enemy recipients, including critical casts and lethal
  boundaries. A state icon alone is insufficient.
- Glyph activation must use actual production-enabled turn/movement providers.
  Previous Aniripsa testing demonstrated that default fixture callbacks can
  silently omit area activation. Charge/lifetime, overlapping areas, owner
  removal, grant lifetime and shared turn action ownership need explicit tests.
- Granted7009/7052must follow equipped passives and their native casting rules;
  never seed grants manually.21active baselines are being qualified separately.
- Shared engine changes require parent coordination. Existing Cra/Iop/Sacrier/
  Eniripsa regressions must survive any general mechanism correction.

## Implementation and acceptance status

Inventory completed; current class baseline cast/commit qualification is running.
No Feca-specific gameplay defect has yet been demonstrated by this inventory.
Do not interpret this source report as class acceptance or manual completion.
