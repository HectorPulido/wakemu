# Full cosmetic and Dofus-named item audit

Scope: the installed Wakfu client and the current published Wakemu catalog. No Dofus server data was used. This audit changes no gameplay code, deployed image or runtime database.

Published catalog revision: `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. All 1,234 native `bIt` action IDs match that published catalog. The Spanish locale contains **42 Dofus-named item references**, all present in the published item catalog. The earlier conversational estimate of 43 was corrected by the complete export.

## All native account cosmetic categories

| ID | Native category | Native bIt items | Valid example and exact grant command | Selection status |
| ---: | --- | ---: | --- | --- |
| 1 | MOUNT_SKIN | 175 | Apariencia de dragocorcel dragocorcel de obsidiana: `!item 18708 1` | source_pending_manual |
| 2 | PET_SKIN | 262 | Apariencia de cangrobot: `!item 28561 1` | unsupported_or_other_authority |
| 3 | PLAYER_COSTUME | 562 | Traje de ninja: `!item 12202 1` | manual_accepted_r63 |
| 4 | PLAYER_SPRINT | 51 | Carrera de Ninja: `!item 20820 1` | source_pending_manual |
| 5 | PLAYER_FINISHER | 36 | Golpe de gracia de Evangelyne: `!item 20753 1` | existing_finisher_support |
| 6 | PLAYER_AURA | 127 | Efluvios de Stasis: `!item 18299 1` | source_pending_manual |
| 7 | PLAYER_TITLE | 0 | No bIt item in this native export | unsupported_or_other_authority |
| 8 | PLAYER_HEAD_SKIN | 8 | Diadema del extremo: `!item 32853 1` | unsupported_or_other_authority |
| 9 | PLAYER_CHEST_SKIN | 0 | No bIt item in this native export | unsupported_or_other_authority |
| 10 | PLAYER_SHOULDER_SKIN | 0 | No bIt item in this native export | unsupported_or_other_authority |
| 11 | PLAYER_BACK_SKIN | 7 | Petate definitivo: `!item 32854 1` | unsupported_or_other_authority |
| 12 | PLAYER_BOOTS_SKIN | 6 | Botas desmesuradas: `!item 32855 1` | unsupported_or_other_authority |
| 13 | PLAYER_FIRST_WEAPON_SKIN | 0 | No bIt item in this native export | unsupported_or_other_authority |
| 14 | PLAYER_SECOND_WEAPON_SKIN | 0 | No bIt item in this native export | unsupported_or_other_authority |
| 15 | HAVEN_BAG_SKIN | 0 | No bIt item in this native export | unsupported_or_other_authority |
| 16 | PLAYER_ACCESSORY | 0 | No bIt item in this native export | unsupported_or_other_authority |

Categories with zero bIt items still exist in the native enum. They may use another source, such as title items, direct equipment appearance learning or rewards. Zero does not mean absent from the game.

## Cosmetic-related item actions outside bIt

| Native action class | Purpose | Items | Valid example command | Current route |
| --- | --- | ---: | --- | --- |
| bIs | title_learning | 467 | Título "Pico de oro": `!item 7749 1` | Source implemented through its own native learning route; pending deployment/manual acceptance |
| bIw | emote_learning | 314 | La Buena Educación: `!item 8189 1` | Source implemented through its own native learning route; pending deployment/manual acceptance |
| bIv | haven_bag_custom_learning | 91 | Kit de merkasako tofu: `!item 11426 1` | Separate native action; not implemented by cosmetic bIt learning |
| bHY | play_emote_item | 8 | Pócima pompota: `!item 19023 1` | Separate native action; not implemented by cosmetic bIt learning |
| bHv | learn_target_equipment_appearance | 1 | Transespejo: `!item 31508 1` | Separate native action; not implemented by cosmetic bIt learning |
| bHT | mimibiote_interface | 1 | Mimobionte: `!item 19292 1` | Separate native action; not implemented by cosmetic bIt learning |
| bIb | character_recustomization | 4 | Cambio de sexo y de apariencia: `!item 18292 1` | Separate native action; not implemented by cosmetic bIt learning |

These examples validate item existence, not a functioning action. The shared 12-byte 13220 item-use route now dispatches bIt cosmetics, bIs titles, bIw emotes and bIx furniture to their respective authoritative acquisition services. Title and emote additions are source implemented and pending deployment/manual acceptance; see TITLES-IMPLEMENTATION-20261010.md and EMOTES-IMPLEMENTATION-20261010.md. Bag customizations still require their own native response. Character customization and target-appearance actions also need their distinct native UI/payload contracts.

## Dofus equipment versus learnable aura items

The equipment and aura columns below identify separate installed items by their names and native metadata. This table does **not** prove that equipping the equipment unlocks the listed aura; no such reward/unlock linkage is inferred.

| Theme | Equipment ref / level / native state | Separate learnable aura ref | Exact commands |
| --- | --- | --- | --- |
| Prismatic | 20720 and 24110 / level 200 / state 4570 | 29764, Aura del dofus prismático | `!item 20720 1`, `!item 29764 1` |
| Turquoise | 28417 / level 215 / state 6731 | 29789, Aura del dofus Turquesa | `!item 28417 1`, `!item 29789 1` |
| Ivory | 31361 / level 155 / state 8251 | 31388, Aura del dofus Marfil | `!item 31361 1`, `!item 31388 1` |
| Ebony | 32351 / level 245 / state 8784 | 32355, Aura de dofus Ébano | `!item 32351 1`, `!item 32355 1` |
| Crimson | 33395 / level 170 / state 9364 | 33396, Aura del dofus Púrpura | `!item 33395 1`, `!item 33396 1` |

All five separate aura items use bIt category 6. Their published effect records contain conditional generic 400/eXE roots and presentation instructions. The published field `has_triggers` is not sufficient proof of gameplay triggers: the native fKV/fKW/fKY lists here contain OY/Pt presentation instructions. Their cosmetic acquisition/selection follows the implemented category-6 path. Equipment roots use generic 304/eWu to apply the listed states; the existence of a combat state handler does not establish execution of those equipment effects during exploration.

The separate Traje de los 7 dofus de cristal (26739, category 3) also has a generic-304 root pointing to state 5909 in its native item effects. Successful costume appearance selection does not certify execution of that additional state effect.

The six level-200 Dofus fragments (23994–23999) are equipment in slot 17 and have statistical effects; their current equipment-effect records have no direct generic-304 state root. Other similarly named versions (28392, 31503, 32407, 33397) are not interchangeable with the equipment references above: their current records have no equipment slot/effect entry. The inventory JSON preserves those distinctions.

## Exact current gaps

- `equipment_stats.py` consumes unconditional supported statistic roots and reports unsupported effects. Generic 304 state roots are not converted to invented statistical bonuses; an exploration equipment-state/visual lifecycle is not established by that stat module.
- A generic 400/eXE root has no statistical calculation. Treating an unconditional marker as zero stats is correct, but its visual flag/attachment can still matter to the native client.
- Native research found **172 item-root records** carrying effect flag 35, `IS_RELIC_AURA`: **127 learnable cosmetic aura items plus 45 equippable items**, established by joining the native flags with published equipment-slot rules and the cosmetic category inventory. Native `bge` checks this flag plus the viewer’s all/mine/none relic-aura preference before rendering particles. Examples: Gelanillo 24083 / effect 237492, Solomonk 24090 / 237556, Otomai 24086 / 237516.
- The current published equipment export does not expose that flag or the complete visual attachment contract. This audit does not claim the 172 item aura visuals work, and does not add fake cosmetic-category-6 selections or change combat aura runners 316/338.
- Exact state child effects, visual attachment serialization and exploration apply/remove/reconnect behavior remain under review. A name containing “aura” alone is insufficient evidence of a continuous visual effect.

## Complete machine-readable inventories

- `cosmetic-items.csv`: all 1,234 account cosmetic items with category, name, action ID, published-match result and exact grant command.
- `cosmetic-related-actions.csv`: all 886 other cosmetic-related action items (titles, emotes, bag customizations, target appearance, mimibiote and character customization).
- `inventory.json`: all 16 categories, cosmetic-related native action items, current published effects and state references for every Dofus-named item, plus source hashes and release identity.
- `dofus-named-items.csv`: all 42 references, including furniture, books, title, emotes, cosmetic aura, costume, equipment and otherwise similarly named variants.

Rebuild with `python3 server/tools/build_cosmetic_inventory.py` after generating native action exports and a frozen catalog snapshot. The generator performs no database writes. Offline regression tests are in `test_cosmetic_inventory_audit.py`.

## Native presentation criteria for Dofus aura tests

All five learnable Dofus aura items have the exact native criterion
`GetFightModel() <= 0`. Test them **outside combat**. The native particle references
are 900073 (29764 prismatic), 900126 (29789 turquoise), 900153 (31388 ivory),
900169 (32355 ebony) and 900183 (33396 crimson). Their native presentation strings
use `start|1|end|12|type|2|data|<particle>;true|broadcast|false`.

Example equipped aura: Gelanillo 24083 / effect 237492 uses particle 900033 and
also requires absence of states 3092, 2623, 3220, 3219, 3202, 6237 and 6804 in
addition to `GetFightModel()<=0`. Ignoring those criteria would fabricate always-on
behavior. The native viewer preference (all/mine/none) further controls rendering. See
`NATIVE-EQUIPMENT-AURA-PRESENTATION-20261009.md` for the proven consumer chain.

`native-aura-presentation-effects.json` preserves the native effect fields,
criteria strings, presentation instructions and client SHA256. It contains all
172 flagged roots plus other effects on the specifically inspected Dofus items
(197 rows total). These are presentation instructions, distinct from combat area
auras 316/338 and from generic 304 state application.
