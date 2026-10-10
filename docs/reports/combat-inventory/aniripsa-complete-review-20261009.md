# Aniripsa complete inventory — 2026-10-09

Scope: inventory and offline baseline verification only. No gameplay implementation, database writes, deployment or restart. Class acceptance remains Cra + Iop2/18; this inventory does not accept Aniripsa or certify Sacrier manually.

## Current authoritative scope

Native breed7, published catalog revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

- 21 owned active spells and20 passives.
- 3 granted actions: Contra Natura7977, Cunejo7978 and Repulsión7979.
- 2 innate seed states3911/4464; these are separate from the owned spell count.
- The expanded current closure includes974 effects,51 states,82 effect families,2 areas and4 summon profiles. It also contains52 spell references, including dependent summon abilities and three criterion-only Sacrier references5054/5193/7218;52 is not the number of player-owned spells.
- No missing effect/state definitions or missing factory family registrations were found in this closure. Registered handlers and complete catalogs do not prove every branch is implemented.

[Full current catalog and per-root dependencies](aniripsa-catalog-audit-20261009.json), [catalog findings](aniripsa-catalog-audit-20261009.md), [runtime risks](aniripsa-runtime-risk-audit-20261009.md), [baseline verification and exact commands](aniripsa-validation-current-20261009.md).

## Measured baseline

- 4/4 legal Ready decks at levels20/200;14/21 available actives respectively.
- 32/35 ordinary spell-level pairs prepared and committed;60/60 prepared attempts committed. No transaction rejection among these attempts. This is cast-path coverage, not a92% gameplay completion estimate.
- The remaining3 pairs are Anisurrección1535 at both levels and Vínculo de Amistad781 at200. Their actual allied/off-play prerequisites were not supplied by the enemy-only baseline; they must not be labeled failed casts or working mechanics.
- 20/20 passive installation/turn/ACK/expiry cycles completed, but only Cura Única1415, Punción5454 and Presencia7990 activated in this scenario. The other17 specific passive mechanics remain unverified.
- Healing regressions:34 passed,1 optional skip. This is separate from an actual injured ally or resurrection acceptance scenario.

## Complete owned register

Every row below is covered by the current catalog inventory. Unlock levels are native values. Baseline status intentionally does not certify damage, healing, marks or trigger semantics individually.

| ID | Native Spanish label | Kind | Unlock | Current evidence |
|---|---|---|---:|---|
| 623 | Colimador | active | 13 | Baseline cast committed; conditional mechanics unverified |
| 625 | Reconstitución | active | 23 | Baseline cast committed; conditional mechanics unverified |
| 627 | Desfase | active | 45 | Baseline cast committed; conditional mechanics unverified |
| 628 | Médico sin Barreras | passive | 40 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 630 | Anatomía | active | 1 | Baseline cast committed; conditional mechanics unverified |
| 636 | Corrosana | active | 15 | Baseline cast committed; conditional mechanics unverified |
| 638 | Fuego Guardián | active | 9 | Baseline cast committed; conditional mechanics unverified |
| 644 | Marcaje Preciso | passive | 20 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 645 | Explosana | active | 1 | Baseline cast committed; conditional mechanics unverified |
| 779 | Palabra Sanadora | active | 5 | Baseline cast committed; conditional mechanics unverified |
| 780 | Revitalización | active | 17 | Baseline cast committed; conditional mechanics unverified |
| 781 | Vínculo de Amistad | active | 30 | Required ally without3864 not exercised by baseline |
| 782 | Juventud | active | 15 | Baseline cast committed; conditional mechanics unverified |
| 1415 | Cura Única | passive | 45 | Passive activation observed; full conditional mechanics unverified |
| 1532 | Infusión | active | 11 | Baseline cast committed; conditional mechanics unverified |
| 1533 | Vivificación | active | 1 | Baseline cast committed; conditional mechanics unverified |
| 1534 | Llama Purificadora | active | 21 | Baseline cast committed; conditional mechanics unverified |
| 1535 | Anisurrección | active | 3 | Required ally/KO context not exercised by baseline |
| 1536 | Paroxismo Vital | passive | 10 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 1537 | Marcador de Serie | passive | 10 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 1538 | Prohibición | active | 60 | Baseline cast committed; conditional mechanics unverified |
| 1539 | Cura Alternativa | active | 3 | Baseline cast committed; conditional mechanics unverified |
| 1540 | Psicosis | active | 7 | Baseline cast committed; conditional mechanics unverified |
| 1541 | Aletargamiento | active | 25 | Baseline cast committed; conditional mechanics unverified |
| 1542 | Matraz Infectado | active | 19 | Baseline cast committed; conditional mechanics unverified |
| 5451 | Retraso | passive | 60 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 5453 | Todos para Mí | passive | 85 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 5454 | Punción | passive | 15 | Passive activation observed; full conditional mechanics unverified |
| 5455 | Naturaleza Muerta | passive | 100 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 5463 | Vampiripsa | passive | 25 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 7985 | Fuente salvadora | active | 90 | Baseline cast committed; conditional mechanics unverified |
| 7987 | Resplandor | passive | 30 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 7990 | Presencia | passive | 35 | Passive activation observed; full conditional mechanics unverified |
| 7991 | Súper Cunejo II | passive | 50 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 7992 | Transgresión | passive | 55 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 7993 | Elixir de Viento | passive | 65 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 7994 | Aprendiz Alquimista | passive | 70 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 7995 | Secreto de Producción | passive | 75 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 7996 | Marca Anbareul | passive | 80 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 7997 | Paradoja Contra Natura | passive | 90 | Ready/turn/expiry cycle observed; specific trigger unverified |
| 7998 | Ambivalencia | passive | 95 | Ready/turn/expiry cycle observed; specific trigger unverified |

## Granted actions and dependent entities

Contra Natura must be granted through its actual owner/innate path, change the correct branches and expire or toggle through native rules. Cunejo must preserve ownership, selected profile, level scaling, costs, summon count and book identity. Repulsión requires actual displacement/occupancy/LOS checks.

Summon profiles182 Cunejo,1775 SúperCunejo,5528 Darkcunejo and5533 Súperdarkcunejo are present in the published ability, initial-state/property and characteristic catalogs. Their ability books reference5457/5458/5459/986/7988, with profile-specific subsets. Profile availability is not proof that every branch is selectable, controllable or active. The eight extra action references are the three grants plus these five unique summon abilities; none is an additional owned passive.

## Ranked implementation/validation backlog

| ID | Priority | Finding | Required next evidence |
|---|---|---|---|
| ANI-01 | P1 | Resurrection lifecycle is not certified. Actual1535 chain restores HP through196 then25 and applies1144; HP restoration alone does not prove native off-play/death/QI/timeline restoration. | Real owned ally becomes KO in an ongoing fight, actual1535, restored fighter state, occupancy, timeline and12727 state1 delivery, then legitimate next action. Distinguish revivable KO from final removal. |
| ANI-02 | P1 | Allied healing and Vínculo de Amistad target branches lack class-specific acceptance. | Injured self/ally/enemy, fullHP, area edges, overheal/virtualHP, heal resistance, modifiers and exact cost once. Verify781 against eligible ally without3864. |
| ANI-03 | P1 | Contra Natura conversion and conditional books/grants are catalogued but not exhaustively played. | Natural grant, toggle, correct heal/damage target/element branches, rollback on invalid casts and expiration/reconnect cleanup. Separate native definition branches from the generic property20 undead-healing conversion guard. |
| ANI-04 | P1 | Marks and death-trigger chains require semantic coverage. | Marked target dies from caster/ally/summon/indirect effect; correct recipient/area once, lethal reaction ordering, no corpse occupancy and no duplicated deaths. |
| ANI-05 | P1 | Cunejo and all four dependent profiles are structurally complete, lifecycle unverified. | Real summon/granted book, owner/count/level/passive variants, healing target, AP/MP, AI/control, death, resummon, cell reuse and cleanup. |
| ANI-06 | P1 | Most passive-specific triggers are not exercised by a completed cycle. | Legal rotating decks for all20 passives; trigger each actual condition, verify values, durations, stack caps, mutual effects and consumption. |
| ANI-07 | P1 | Delayed/retained effects, source amounts and linked areas are not certified by ordinary casts. | Triggering-runner value mutation430 (not delayed execution), native delayed containers/timers and source-value/group reaction publishers, delayed turns/expiry, area1812/1814 entry/removal, source ownership, damage/healing changes and disconnection. |
| ANI-08 | P1 | Shared multiplayer/end lifecycle remains manual acceptance. | Two clients PvP/PvM, first turn, reconnect, surrender, revival, normal finish, UI/book cleanup and dungeon continuation. Track the separately observed duplicate interactive objects on map return. |
| ANI-09 | P2 | Numeric and boundary combinations need acceptance beyond a baseline cast. | Critical/heal resistance/masteries, life steal, null/full/lowHP, multiple targets, LOS/height/large actors/stabilization and rejected-cost rollback. |

## Existing shared work applicable without class-specific copying

- Current fresh-group area selection fixes from Cra and relationship selection from Sacrier apply to ally heals, marks and summon areas. Preserve explicit point targets and retained replay identity.
- Granted action ownership, retained managers and book cleanup cover the infrastructure for7977/7978/7979; never copy another class's prerequisite IDs.
- Paid-cost events, preview/commit isolation, RNG rollback and primitive checkpoints protect nested heal/damage/mark chains.
- Actual healing arithmetic, aptitude modifiers and resistance are shared foundations, not proof of each Aniripsa formula.
- Death/occupancy/LOS, forced movement and summon retirement apply broadly. Resurrection needs its own native inverse lifecycle; merely increasingHP must not be treated as revival.

## Planned complete manual acceptance after implementation

Use an Aniripsa with an allied player and enemies in the same fight. Use `!nivel 250` for all unlocks and rotate legal decks; do not silently put every passive in one impossible deck. First verify normal and Contra Natura branches of every active on injured/full allies and enemies, then marks/deaths, Cunejo variants, actual allied KO/resurrection, passive triggers, delayed effects and areas. Finally repeat two-client start/reconnect/surrender/finish and dungeon progression. Record spell, passive deck, target, state/value before and after, combat ID and expected tooltip behavior. No part of this manual acceptance is claimed complete here.

No overall gameplay completion percentage is assigned: structural coverage is complete for the catalogued scope, while the class-specific conditional acceptance above remains open.
