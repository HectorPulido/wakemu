# Ultimate Boss audit — 2026-10-09

## Conclusion

Ultimate Bosses are not correct as a complete system. The native client catalog contains **15 Ultimate Boss definitions: 13 classic encounters and two Neo variants**. The installed bundle covers **11 classic encounters**. **Ten installed encounters contain eight duplicate copies of their boss in each generated room**; Magmog has two such rooms. Ombrage alone has a single boss reference, which establishes composition identity/count only, not correct mechanics or access.

These are confirmed installed database configurations, not merely speculative generated artifacts. No code, database, runtime, image or service was changed during this audit. `docker compose ps` showed the single world on `wakemu-world:performance-20261009-r61`, healthy. Ongoing runs pin their configuration; this audit did not enumerate every active run or inspect every live fight.

## Evidence and interpretation

- Native catalog: `.runtime/local/methodwakfu-dungeons/native-dungeon-index.json`, `native_dungeons`, filtered by `type == ULTIMATE_BOSS`; 15 definitions. `raw_aWb` is the entry-level field used in the local catalog, **not the monster's level**. `raw_aHA` contains interior maps and `raw_cno` contains species references, not authoritative room composition.
- Installed data: read-only PostgreSQL queries of `settings`, `dungeon_runtime_active:*` and `dungeon_runtime_config:*:v2`; all 11 installed UB active selectors resolve to v2. Missing selectors for definitions 111, 194, 213, 219.
- Generated artifact: `.runtime/local/methodwakfu-dungeons/local-policy-configs-all87/configurations.json`; agrees with the inspected installed UB configurations.
- Guide evidence: `.runtime/local/methodwakfu-dungeons/composition-catalog.json` and `guides/boss-ultimes-*/article.txt`. Eleven reviewed guide documents do not constitute thirteen classic UBs or fifteen native definitions.
- Public sanitized data and source hashes: [ultimate-boss-evidence-20261009.json](ultimate-boss-evidence-20261009.json). Credentials, database dumps and client captures are excluded.

## Complete native inventory

“Missing” means no active configuration under the native route key in the inspected database, not absence of all client assets. Every installed row still requires normal-entry and mechanics acceptance.

| Boss / native venue | Definition | Minimum entry level / native boss level | Interior map | Boss reference | Installed v2 composition |
| --- | --- | --- | --- | --- | --- |
| Excarnus / Antre d'Excarnus | 4 | 66 / 80 | 360 | 1986 | 1 room, **8 Excarnus** |
| Milkar / Antre du Meulou | 3 | 81 / 95 | 358 | 1987 | 1 room, **8 Milkar** |
| Black Crow / Antre du Corbeau Noir | 5 | 96 / 110 | 363 | 1988 | 1 room, **8 Black Crow** |
| Magmog / Antre du Boufrog | 6 | 96 / 110 | 365 | 42 | **2 rooms, 8 Magmog in each** |
| Neo Black Crow / Néo-Antre du Corbeau Noir | 213 | 96 / not inspected | 1447 | 5797 | Missing; Neo variant, not an additional classic boss |
| Dragon Pig / Antre du Dragon-Cochon | 57 | 111 / 125 | 545 | 2430 | 1 room, **8 Dragon Pig** |
| Tal Kasha / Tombeau de Tal Kasha | 194 | 141 / not inspected | 1400 | 5500 | **Missing classic UB** |
| Steel Beak / Plateau des Haut-Vents | 100 | 156 / 170 | 959 | 3582 | 1 room, **8 Steel Beak** |
| Sham Moon / Cime du Grand Totem | 111 | 171 / not inspected | 1056 | 3870 | **Missing classic UB** |
| Nogord / Antre de Nogord l'Ezarélé | 117 | 186 / 200 | 1092 | 3433 | 1 room, **8 Nogord** |
| Ogrest / Pointe du Mont Zinit | 131 | 186 / 230 | 1156 | 4378 | 1 room, **8 Ogrest** |
| Neo Ogrest / Néo-Pointe du Mont Zinit | 219 | 186 / not inspected | 1446 | 5806 | Missing; Neo variant |
| Shadofang / Dimension-Objet d'Ombrage | 135 | 200 / 200 | 1229 | 4770 | 1 room, **1 Ombrage**; mechanics unverified |
| Rushu / Palais de Rushu | 181 | 216 / 230 | 1332 | 5306 | 1 room, **8 Rushu** |
| Nox / Cœur de l'horloge de Nox | 203 | 231 / 245 | 1435 | 5664 | 1 room, **8 Nox** |

The official WAKFU publisher announcement confirms Nox is an Ultimate Boss released with update 1.89 and tied to the conclusion of the Misty Isle story: [publisher announcement on Steam](https://store.steampowered.com/news/posts/?appids=215080&enddate=1758042002), September 9, 2025. Native local IDs remain the authoritative inventory for this checkout; current online lists must not silently replace its client version.

## Access, keys and content besides the boss

The following are guide-author observations, with exact local article locators. A route's criterion alone does not establish the complete access contract; requirements can live on exterior travel, interactions, items, achievements or quest states. Blank criterion does **not** establish free access.

| Boss | Observed guide access/content | Local evidence / gap |
| --- | --- | --- |
| Excarnus, Milkar, Black Crow, Magmog, Dragon Pig | Key per attempt; crafted from four fragments. First weekly successful fight is eligible for drops; token vendor rewards also documented. | Article lines 18–33 and reward sections; installed route criteria are blank except Black Crow's non-beta/non-Neo condition. Key consumption and weekly eligibility unverified. |
| Magmog | An intermediate Boufrog fight before Magmog; later summons and heat/cooling mechanics. | [Guide](https://methodwakfu.com/pvm/boss-ultimes/antre-du-boufrog/), article lines 39–44, 93–134. The unresolved intermediate species was replaced with reference 42 and filled to eight; it is not evidence for an eight-Magmog preliminary fight. |
| Steel Beak | Crafted access item from four fragments; phase-specific boss behavior; first weekly successful drop and token rewards. | [Guide](https://methodwakfu.com/pvm/boss-ultimes/plateau-des-hauts-vents/), article lines 20–22, 147. Local route only checks non-beta. |
| Sham Moon | Native venue/species known. | Guide missing from the 87-document bundle. Quest, key, map interactions, composition and phase requirements not reviewed; do not infer absence. |
| Tal Kasha | Native venue/species known. | Guide missing from bundle. Full access, puzzles, quest relation, key and rewards require dedicated extraction. A quest pyramid and the UB tomb must not be conflated without route evidence. |
| Nogord | Intro quest; Divine Dimensions main quest and victories over Steel Beak/Sham Moon; competitive modulation and crafted key. | [Guide](https://methodwakfu.com/pvm/boss-ultimes/antre-de-nogord-l-ezarele/), article lines 15–34. Installed criterion checks non-beta and a past release date; complete prerequisites are not certified. |
| Ogrest | Summit access through Zinit quest, cannon plus artifacts, or level 194 unlock; crafted key from four Zinit dungeon fragments. Score encounter and quest-dependent rewards. | [Guide](https://methodwakfu.com/pvm/boss-ultimes/pointe-du-mont-zinit/), article lines 30–56, 168–200. Route checks non-beta/non-Neo, not the complete exterior access chain. |
| Ombrage | Intro UB quest, competitive modulation, crafted key using five dimensional-rift fragments; four phases. | [Guide](https://methodwakfu.com/pvm/boss-ultimes/dimension-objet-dombrage/), article lines 15–36. Route checks non-beta and past release date. Correct single boss count does not validate these requirements. |
| Rushu | Key using five Shustuft Crust fragments; renewed key after failure; timed score encounter. | [Guide](https://methodwakfu.com/pvm/boss-ultimes/palais-de-rushu/), article lines 18–38. Local route checks non-beta; key and timed score not certified. |
| Nox | Key using six Misty Isle dungeon fragments; story quest supplies a free key; renewed key after failure. Timed score fight with three phases, batteries, weapons and difficulty steles. | [Guide](https://methodwakfu.com/pvm/boss-ultimes/coeur-de-lhorloge-de-nox/), article lines 18–98. Blank installed criterion; no evidence of this full contract functioning locally. |
| Neo variants | Separate native maps/species; classic routes explicitly exclude Neo mode. | No installed Neo configurations. Treat as separate server-mode variants, not duplicates to merge into classic encounters. |

The reviewed older-guide weekly rule concerns **drop eligibility after the first weekly victory**. Do not replace it with “one combat attempt per week”; current key-based retries and weekly rewards are distinct contracts. Their exact current reset timezone, account/character scope and behavior on losses remain unknown locally.

## Why duplicate bosses appeared

`server/wakfu_server/maps/dungeon_local_roster_policy.py` repairs missing references from the whole native species pool and then fills incomplete rooms to the generation target (currently eight). A pool containing only the boss produces eight bosses. `is_boss` only assigns metadata; it does not prevent duplicates. Missing boss classification can label authentic bosses as ordinary monsters. Even the otherwise complete Ogrest guide is expanded by the current local policy.

The same mechanism affects ordinary dungeons, as documented in [the Tofullero review](PARALLEL-DUNGEON-REVIEW-20261009.md). Fix the general policy and preserve verified encounter composition; do not patch eleven rows independently or trust catalog flags alone.

## Mechanics and reward correctness

A read-only search of `server/wakfu_server/combat` and `server/ai-service` found no named UB controllers for these bosses or an explicit UB weekly-reward authority. This is a gap in evidence, not proof that no native spell/effect can execute. Native monster spells, statistics and generic AI can exist without reproducing the encounter's phase machine, arena entities, invulnerability, summons, score win condition or loot eligibility.

**No UB is certified mechanically correct by this review.** Nox, Rushu and Ogrest especially require score/timer termination instead of merely exhausting ordinary monster HP. The Nox guide describes a ten-turn base encounter and a base minimum score of 3,000,000 with difficulty increments; those current-guide values require client/version compatibility checks before implementation. All boss-specific phase, threshold, arena-object and reward claims need automated fixtures plus one normal-entry complete acceptance, rather than spawning a species with an admin command.

## Recommended order

1. Freeze a documented native-version inventory including the two missing classic UBs and separate Neo rows; extract the missing guides and exact access interactions.
2. Correct encounter compilation generally: preserve trusted counts, distinguish intermediate species from final boss, refuse guessed UB pools, and record unknown compositions explicitly.
3. Verify native key/quest contracts and weekly loot eligibility independently of ordinary route criteria; never bypass authority to claim an encounter works.
4. Audit boss spells/effect handlers and phase controllers against reviewed evidence, including score victories and arena objects. Correct roster alone is not completion.
5. Version new configurations without mutating ongoing pinned runs. Automated tests should reject eight copies of a singleton boss, early final-boss substitution and unverified score fights falsely declared complete.
6. Only after validated implementation and a user-authorized later deployment, perform normal-entry complete runs. Do not ask Hector to test these known-invalid rosters now.
