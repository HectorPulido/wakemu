# Sparse native descriptor text evidence

Offline review of all 57 HP-base-1/AP-base-0 native definitions. No resources, activation policy, exclusions or runtime behavior were changed. Native text is Spanish; proper names below retain their original language.

**12** definitions have a proven incoming native summon edge. **45** have no incoming summon edge in the audited graphs, which leaves their role unproven; it does not prove they are NPCs, obsolete, or ordinary monsters. Six of those 45 are named racing gobballs. No test/beta keyword occurs in these 57 names. Object and scenario names provide hints only.

Translation namespaces are explicit: monster names `content.7.ref`; spell names/descriptions `content.3.id`/`content.4.id`; state names/descriptions `content.8.id`/`content.9.id`. Namespace 9 is never joined to a monster reference as a monster description. No native monster-description namespace was established.

## Native descriptions linked to actual summon edges

- **1620 Jamajam**: `osamodas_jamajam_companion`. Native edge from spell 7350; `content.4.7350`: El osamodas invoca a su jamajam en combate para que lo ayude. Recupera 1 PW al principio del turno si este está presente.
- **3251 Doble sram**: `sram_controlled_double`. Native edge from spell 4603; `content.4.4603`: Permite al sram invocar un doble de sí mismo controlable que posee otros hechizos. El sram puede tomar el control del doble durante su propio turno. El doble es inmune a los daños de zona del sram.
- **4559 Wauwau**: `uginak_controlled_companion`. Native edge from spell 6286; `content.4.6286`: Permite que el uginak invoque a un compañero controlable que posee otros hechizos.
- **5347 Wonejo**: `osamodas_default_wonejo_when_no_capture_or_empty_jamajam`. Native edge from spell 7348; `content.4.7348`: El osamodas invoca la criatura seleccionada en la interfaz del jamajam. Este hechizo también permite capturar una criatura capturable. Varios osamodas pueden invocar una criatura, pero estas sufrirán un Atracón de Invocación durante un turno. Además, las criaturas duplicadas están prohibidas. Hasta que el osamodas no haya capturado a ninguna criatura o el jamajam esté vacío, puede igualmente invocar un wonejo.

**Reference 5347 is the Osamodas fallback Wonejo**, according to its actual parent spell description, and must not be identified as the Eniripsa Cunejo from a similar animal name. These text-and-edge matches prove intended role, not successful execution or creator-derived resource arithmetic.

## Complete 57-definition inventory

| Ref | Native name | Native summon edge | Owned spells | Name-only hint |
|---:|---|---|---:|---|
| 1422 | Sinistro | Not found | 0 | None |
| 1499 | Imagen | Not found | 0 | None |
| 1620 | Jamajam | Yes | 5 | None |
| 2011 | Torreta | Yes | 0 | name_suggests_object_or_mechanism |
| 3047 | Tótem del Destino | Not found | 0 | name_suggests_object_or_mechanism |
| 3251 | Doble sram | Yes | 4 | None |
| 3602 | Gralarma | Not found | 0 | None |
| 3698 | Tótem | Not found | 0 | name_suggests_object_or_mechanism |
| 3789 | Torre para gatos | Yes | 0 | None |
| 3790 | Rueda Dentada | Not found | 0 | None |
| 3791 | Esfera | Yes | 0 | None |
| 3792 | Bloque steamer | Not found | 0 | None |
| 3793 | Estandarte de valentía | Yes | 0 | name_suggests_object_or_mechanism |
| 3794 | Tonel | Yes | 0 | None |
| 3798 | Baliza de alineamiento | Yes | 0 | name_suggests_object_or_mechanism |
| 3799 | Baliza de contacto | Yes | 0 | name_suggests_object_or_mechanism |
| 3800 | Baliza de destrucción | Yes | 0 | name_suggests_object_or_mechanism |
| 3889 | Caja | Not found | 0 | None |
| 3890 | Ki-Sabi-Nundie | Not found | 0 | None |
| 3913 | Laetitia Jocasta Nuk | Not found | 0 | None |
| 3916 | Yeina Girasolo | Not found | 0 | None |
| 3917 | Tomás Trowindu | Not found | 0 | None |
| 3930 | Gran maestro | Not found | 0 | None |
| 3976 | Jalató de carrera | Not found | 1 | name_suggests_training_or_scenario |
| 3980 | Jalató de carrera | Not found | 1 | name_suggests_training_or_scenario |
| 3981 | Jalató de carrera | Not found | 1 | name_suggests_training_or_scenario |
| 3982 | Jalató de carrera | Not found | 1 | name_suggests_training_or_scenario |
| 3983 | Jalató de carrera | Not found | 1 | name_suggests_training_or_scenario |
| 3984 | Jalató de carrera | Not found | 1 | name_suggests_training_or_scenario |
| 4023 | Embrialma de jalató | Not found | 0 | None |
| 4024 | Embrialma de tofu | Not found | 0 | None |
| 4025 | Embrialma de sadida | Not found | 0 | None |
| 4034 | Embrialma de aniripsa | Not found | 0 | None |
| 4037 | Recolector de Wakfu | Not found | 0 | None |
| 4038 | Recolector de Wakfu | Not found | 0 | None |
| 4112 | Caja | Not found | 0 | None |
| 4169 | Embrialma de yopuka | Not found | 0 | None |
| 4173 | Erizo de mar | Not found | 0 | None |
| 4174 | Corriente marina | Not found | 0 | None |
| 4182 | Corriente marina | Not found | 0 | None |
| 4189 | Mimic rúnico | Not found | 0 | None |
| 4194 | Mimic fragmentado | Not found | 0 | None |
| 4195 | Mimic doméstico | Not found | 0 | None |
| 4196 | Mimic dulce | Not found | 0 | None |
| 4559 | Wauwau | Yes | 4 | None |
| 4566 | Hueso con tuétano | Not found | 0 | None |
| 4645 | Cofre falso | Not found | 0 | None |
| 4721 | Tonel de ñiamzamas | Not found | 0 | None |
| 4797 | Caja | Not found | 0 | None |
| 5029 | Yunque | Not found | 0 | None |
| 5034 | Mimic de nación | Not found | 0 | None |
| 5085 | Tonel de leche de bambú | Not found | 0 | None |
| 5347 | Wonejo | Yes | 3 | None |
| 5444 | Regulador | Not found | 0 | None |
| 5465 | Sapomorros | Not found | 0 | None |
| 5656 | Jinete | Not found | 1 | None |
| 5901 | Bambú | Not found | 0 | None |

The private receipt includes every owned spell name and description, native initial-state name and description, incoming effect provenance, native monster owners of parent spells, descriptor ranges, fight-property symbols and source SHA-256 hashes. Missing text remains null. Duplicate graph edges are preserved as provenance, not counted as additional monsters.

Private receipt: `.runtime/monster-blocker-recovery-20261011/name-description-role-evidence.json`. Reproduce with `python3 .runtime/monster-blocker-recovery-20261011/enrich_sparse_roles.py`. External historical sources are maintained separately and do not override these native reference joins.
