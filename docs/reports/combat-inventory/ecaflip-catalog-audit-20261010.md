# Ecaflip current native inventory — 2026-10-10

Status: implementation and actual-pipeline validation in progress. Structural availability is not functional acceptance.

## Authority

PostgreSQL complete active revision `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`. Read-only extraction tool: `server/tools/audit_ecaflip_catalog.py`. The adjacent JSON preserves full native effect metadata, including probabilities, sampled parameters, event masks and native criteria.

## Scope

Breed 6; 21 actives and 20 class passives, plus 8 common passives. Conservative transitive closure currently contains 1723 effects, 80 states, 1 area, 18 additional spells, and 3 summon profiles. No absent direct record was found. This includes all exported root levels, class innates, nested casts, state applications, grants, areas and class summon abilities. Native reference families outside the reader map and conditional-only dependencies require explicit semantic review.

## Owned spells

| ID | Kind | Native display name | Unlock |
|---|---|---|---|
| 2041 | active | Cara o Cruz | 1 |
| 2042 | active | Dado Seis | 9 |
| 2043 | active | Todo o Nada | 19 |
| 2044 | active | Tres Cartas | 25 |
| 2045 | active | Craps | 1 |
| 2046 | active | Bufido | 21 |
| 2047 | active | All In | 7 |
| 2048 | active | Ruleta de Dados | 15 |
| 2049 | active | Batalla | 13 |
| 2050 | active | Dado Gatuno | 3 |
| 2059 | passive | Tarot Suertudo | 25 |
| 2060 | active | Doble o Nada | 3 |
| 2061 | active | Felintuición | 30 |
| 2062 | passive | Pulgación | 10 |
| 2065 | active | Lengua Raspadora | 1 |
| 2066 | active | Laceraciones | 5 |
| 2067 | active | Pulga Arcito | 11 |
| 2068 | passive | Desventura | 10 |
| 2072 | active | ¡Zarpas Quietas! | 17 |
| 2073 | active | Pulguita | 23 |
| 2075 | active | Topkaj | 15 |
| 2076 | passive | En Racha | 15 |
| 2078 | active | Ficha de Vida | 45 |
| 2079 | active | Mala Suerte | 60 |
| 2080 | passive | Desdicha | 20 |
| 5246 | passive | Tarot Profético | 30 |
| 5249 | passive | Impacto Felino | 40 |
| 5250 | passive | Destino de Zurcarák | 35 |
| 5251 | passive | Trampas | 45 |
| 7225 | active | Trébol | 90 |
| 7954 | passive | Racha Sanadora | 50 |
| 7955 | passive | Tarot Felino | 55 |
| 7956 | passive | La Fortuna Sonríe a los Audaces | 60 |
| 7957 | passive | Cruz, Gano | 65 |
| 7958 | passive | Dados Generosos | 70 |
| 7959 | passive | Felino Supremo | 75 |
| 7960 | passive | Black Jack | 80 |
| 7961 | passive | Triunfos Periódicos | 85 |
| 7999 | passive | Siete Fetiche | 95 |
| 8000 | passive | El Universo | 100 |
| 8001 | passive | Racha de Cartas | 90 |

## Summons

| Profile | Owned ability references |
|---|---|
| 1482 | 5231 |
| 3789 | No owned abilities in authoritative book |
| 5535 | 7986 |

## Native mechanics and required runtime evidence

- Tarot: innate 6892 installs hand counter 7941; repeated group 949 draws temporary 7978, weighted group341 selects eligible card states 7961–7973, and grants 7938–7950. Verify no duplicates, hand cap, casting consumption, turn refresh, passive parity restrictions, and actual grant retirement.
- Active control: 7227 and derived7989/7953 require real owned grants and costs, rather than injecting spellbook entries.
- Fleas: 2067/2073 and passive2062 require ally/enemy numeric and spread/expiry branches.
- Dice/random damage: deterministic seeds and native conditional draws must qualify both positive and negative outcomes, critical variants and repeated-cast boundaries.
- Summons 1482/5535/3789: verify legal cell, owned ability books, actual ability casts, QI/timeline registration, destruction/removal and resummon. Empty3789 ability book is catalog evidence, not an absent-handler conclusion.
- Area1798: verify actual placement, occupant providers, ownership and removal.
- Streak and passive conditions: preserve current names from source; state7941 is **cards in hand**, not streak. Counter/formula meanings must be derived from effects rather than inferred from reference numbers.
- Preserve multiplayer roster, finite capped state replacement, turn-triggered retained source-cost descriptor, transaction rollback and preview isolation fixes qualified for previous classes.

## Acceptance boundary

The normal-cast matrix and semantic modules are executed by Luna. A shared state-variant policy correction was required and validated for multi-pair normal/critical flea trees; see `ecaflip-runtime-qualification-20261010.md`. No service operations or catalog activation were performed by this class workstream. Passive coverage and the complete manual battery are recorded in adjacent `ecaflip-passive-semantic-matrix-20261010.md` and `ecaflip-manual-acceptance-20261010.md`.
