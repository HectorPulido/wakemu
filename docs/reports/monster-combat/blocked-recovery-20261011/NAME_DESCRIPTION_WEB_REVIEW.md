# Native names, descriptions and external role context

The full offline text inventory now covers all808 blocked references.801 have a localized monster name;917 owned spell entries have native localized descriptions. Names and descriptions enrich diagnosis; they never enable, exclude or rewrite a monster. Evidence: `.runtime/monster-blocker-recovery-20261011/all-blocked-text-evidence.json`, with namespace-qualified source keys and hashes.

## Native description conclusions

| Reference | Native evidence | Role conclusion |
|---|---|---|
|1620 Jamajam|307 edge from7350; `content.4.7350` explicitly describes Osamodas summoning its companion|Osamodas companion, creator-dependent setup|
|3251 Doble sram|307 edge from4603; `content.4.4603` describes a controllable Sram double with its own spells|Sram double, creator-dependent setup|
|4559 Wauwau|307 edge from6286; `content.4.6286` explicitly describes Uginak summoning a controllable companion|Uginak companion, creator-dependent setup|
|5347 Wonejo|307 edge from7348; `content.4.7348` explicitly provides a Wonejo while the Osamodas has no captured creature or an empty Jamajam|Osamodas fallback summon; do not identify this reference as Eniripsa Cunejo|

Monster names use namespace7. Spell names/descriptions use3/4; state names/descriptions use8/9. No separate monster-description namespace has been established. Joining `content.9.<monster_ref>` would attach an unrelated state description and is forbidden by the evidence format.

The57 HP1/AP0 descriptors include12 explicit summon targets and45 with no role proved by the supplied summon graph. Examples such as Bloque steamer, Sinistro, balizas, cajas and racing gobballs suggest heterogeneous objects or encounter actors, not one common missing-resource bug. Negative graph evidence is limited to supplied catalogs. Generic summon edges do not establish that a creature has no ordinary world role.

## External contextual sources consulted

External pages are supporting role context only. Their mechanics can describe another game version and their translated names do not identify a native reference by themselves. The implementation source remains the installed native bytecode, sealed records and exact text keys.

- [Bow Wow spell — Wakfu Wiki](https://wakfu.wiki.gg/wiki/Bow_Wow_%28spell%29): identifies the Ouginak companion as controllable and owning a spell set. This agrees with native4559/6286 role evidence; external resource numbers are not imported.
- [Sram — Wakfu Wiki](https://wakfu.fandom.com/es/wiki/Sram): describes the Double as an invocation, consistent with native3251/4603.
- [Sinistro — Wakfu Wiki](https://wakfu.fandom.com/wiki/Sinistro): identifies a Xelor summon. Historical charge-based mechanics illustrate why HP1 is insufficient to infer a broken ordinary monster.
- [Steamer — Wakfu Wiki](https://wakfu.fandom.com/es/wiki/Steamer): describes blocks and machines as class combat tools. This is contextual support for inspecting object lifecycle, not proof that3792 is an autonomous monster.
- [Cunejo — Wakfu Wiki](https://wakfu.fandom.com/es/wiki/Cunejo): describes the Eniripsa healing summon. It must not be used to classify Osamodas Wonejo5347 despite superficially similar creatures.

Seven blocked native references have no localized monster name.5419 and5588 own spells explicitly named `Mode testeur curieux`, `Mode testeur méticuleux` and/or `Modo testeador de características`; these are strong QA-role candidates, not confirmed exclusions. Other unnamed references contain boss-specific text, so missing names alone cannot identify test actors.

No published inventory membership, resources, catalog, services or activation policy changed during this review.

## Multilingual identity cross-check

All808 blocked references were matched against installed Spanish, English, French and Portuguese translation keys with jar hashes pinned in `multilingual-blocked-names.json`. Seven lack names in all four languages. Spell-name QA candidates5419/5588 remain metadata hints rather than exclusions.

Reference5112 maps Miluba / Boowolfine / Muloune / Miloba. [Boowolfine](https://wakfu.wiki.gg/wiki/Boowolfine) and [Boowolf Clearing](https://wakfu.wiki.gg/wiki/Boowolf_Clearing) identify an ordinary monster in the Sadida Kingdom. This supports retaining it for normal-monster investigation. Its native sealed base descriptor has0WP while owned7386 costs1WP; web identity cannot justify changing that resource rule.

The broader static base-cost audit finds42 blocked references with a possible native base-resource deficit,35 involvingWP. This is an observation before initialization, conditional cost branches, creator effects or encounter preparation. Full evidence and source hashes are in `static-resource-deficit-audit.json`; no resource values or casting guards were changed.

## Encounter-mechanism lead: Electric Crystal5661

The multilingual identity is Cristal eléctrico / Electric Crystal / Cristal électrique / Cristal Elétrico. Native reference5661 has levels248–253, HP999999, AP0 and MP0. Its explicit fight property1 is `SKIP_TURN`; other properties include hidden health bar and stabilization. Owned spells8298/8299 are División and Castigo Celestial, and initial states are8649/8640/8650/8773 (Tormenta). These are direct installed-data observations, not inferred missing resources.

The search-index excerpt for [MethodWakfu's Ferociraptors dungeon guide](https://methodwakfu.com/pvm/donjons/donjon-ferociraptors/) describes Cristal électrique casting Châtiment céleste from turn2 around wing stones. The matching spell translation is a useful encounter-role lead. Full-page retrieval returned403, so the exact trigger, timing, version and native-reference identity remain unqualified. Audit the actual initial-state subscriptions and encounter lifecycle before changing execution eligibility. Ordinary AI turn casting is not an adequate sole qualification for a native `SKIP_TURN` actor. No exclusion, resource modification or activation follows from this evidence.

Titanohuevo4872 maps to Gigantegg / Titanoeuf / Gigantovo. It has native HP2000, AP0, MP0, level80 and owned6638 Explosión, with push/pull and carry prohibitions. A matching wiki title was found, but full-page retrieval also returned403; no external mechanics or role are asserted for this reference.

### Native trigger confirmation

Installed initial state8649 resolves root389435, with subscription mask index5 containing event1001 (start turn). Child389437 is family426 and requests spell8299 only when `GetFightCurrentTableTurn()>1`; sibling389436 requests8298 when the WP characteristic is positive. This directly confirms an automatic owned-spell route rather than an ordinary AI decision for8299. Initial8640 also includes event1003 subscriptions and family194 WP effects. The external guide was the lead; these native IDs and predicates provide the implementation authority. Trigger support and an executed end-to-end fight remain separate qualification requirements.
