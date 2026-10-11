# Native dungeon Stasis percentage contracts

The installed client declares exact HP, damage, experience and loot percentages for Stasis difficulties 1–10. These are percentage multipliers of the baseline (difficulty 2 is 100%), not additive bonuses. Extraction is read-only; no server or client asset was changed.

Reproduce with `python3 sniffer/export_native_stasis_percentages.py .runtime/dungeon-stasis-20261011/native-tooltip-percentages.json`. The artifact records archive/member SHA-256 provenance and all 100 numeric templates: 25 keys each in French, English, Spanish and Portuguese. All four locales agree exactly. Rarity variants within each dungeon type agree.

| Dungeon type ID | HP percentages, difficulty 1–10 | Damage percentages, difficulty 1–10 |
| --- | --- | --- |
| 0 | 70,100,160,240,360,520,740,800,1000,1300 | 70,100,130,190,200,210,230,240,260,280 |
| 1 and 2 | 70,100,160,240,400,550,800,900,1150,1400 | 60,100,140,200,210,220,240,250,260,270 |
| 3 and 4 | 70,100,140,210,310,440,600,660,880,1100 | 60,100,130,190,200,210,230,240,250,260 |

All types declare standard XP/loot percentages `60,100,120,160,188,200,205,210,215,220` and competitive percentages `60,100,140,250,400,550,600,650,680,710`.

## Consumer proof and limits

`bqf.getFieldValue("bonusTooltipText")` chooses the localization key using `eQL.dEB()` → `eQM.aIX()` (native dungeon type ID). Its four formatter arguments are selected difficulty, dungeon type, previous best difficulty, and `iUr ? 1 : 0`. The template branch `{[1=4]?…:…}` therefore selects competitive rewards. `bqf.gQ(boolean)` stores `iUr = dungeon.cni() || argument`, and `dFt()` exposes that same flag. Bytecode evidence is retained in `.runtime/dungeon-stasis-20261011/stasis-definition-context.javap.txt` and `scaling-parameters.javap.txt`.

Types 5 and 6 have textual rift descriptions instead of these arrays; they explicitly describe scaling with participant count and participant level. Do not apply dungeon type 0–4 curves to rifts.

These declarations prove the native displayed contract. They do not prove server rounding, modifier stacking, boss exceptions, reward eligibility, or which native state implements it. The state catalog contains several generations of "Características Stasis" and "Bonus de Dificultad Stasis" definitions; names alone do not accredit an active state mapping. In particular, `bpN.cno()` is consumed by dungeon search via `blj.DL(int)` and must not be assumed to be a list of Stasis state IDs.
