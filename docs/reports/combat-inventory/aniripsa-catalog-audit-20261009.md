# Aniripsa current native catalog audit — 2026-10-09

Inventory only: no gameplay code edits, database writes, services, restart or deployment. Current metadata and static routes are evidence of availability, not gameplay acceptance.

## Authority and exact scope

Published native catalog revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`. Current `spells.json` proves breed7 owns41 spells; current `breed-innate-definitions.json` identifies breed7 as **ENIRIPSA** and innates3911/4464. Neither identity nor innate ownership relies only on the historical class graph.

- **21 owned active spells,20 owned passives,3 granted actions,2 innate seeds**:46 seed roots.
- Expanded current closure: **974 effects,51 states,82 effect families,52 spell references,4 summon profiles,2 areas**.
- **Zero missing effect/state/spell/area/summon definitions and zero absent family registrations** in this scoped current closure. No missing759 definition is reported:759 is not reached by this closure.
- Eight additional class actions comprise3grants plus5unique summon abilities. The52spell references also include3cross-class criterion dependencies; this is not a52spell player inventory.

## Complete owned spell register

Labels below are historical native localization labels, not newly translated names. Ownership, kind, unlock level, current roots, dependencies and metadata are current. The JSON retains full current definitions, masks, conditions, native flags and per-root closure.

|ID|Label|Kind|Unlock|Selected native roots at200|
|---:|---|---|---:|---|
|623|Colimador|active|13|167363, 167675, 167676, 167365|
|625|Reconstitución|active|23|367697, 367703|
|627|Desfase|active|45|167716|
|628|Médico sin Barreras|passive|40|369979|
|630|Anatomía|active|1|367522, 367525|
|636|Corrosana|active|15|167704, 167598, 167600, 167706|
|638|Fuego Guardián|active|9|167594, 367444, 167596, 367445|
|644|Marcaje Preciso|passive|20|368117, 371713|
|645|Explosana|active|1|367430, 167592|
|779|Palabra Sanadora|active|5|367668, 367674|
|780|Revitalización|active|17|367646, 367647|
|781|Vínculo de Amistad|active|30|166867, 167529, 166868|
|782|Juventud|active|15|367737|
|1415|Cura Única|passive|45|143554|
|1532|Infusión|active|11|367687, 367681|
|1533|Vivificación|active|1|367641, 367662|
|1534|Llama Purificadora|active|21|367650, 367649|
|1535|Anisurrección|active|3|166893|
|1536|Paroxismo Vital|passive|10|167898|
|1537|Marcador de Serie|passive|10|368107|
|1538|Prohibición|active|60|367731, 367730|
|1539|Cura Alternativa|active|3|167611, 367436, 367437, 168320|
|1540|Psicosis|active|7|166967, 167686, 367528, 367530, 367529, 367531|
|1541|Aletargamiento|active|25|367638, 367639|
|1542|Matraz Infectado|active|19|367536, 367539, 168407, 367542|
|5451|Retraso|passive|60|369980|
|5453|Todos para Mí|passive|85|368102|
|5454|Punción|passive|15|378748, 368147, 370032, 368150|
|5455|Naturaleza Muerta|passive|100|168401|
|5463|Vampiripsa|passive|25|368130|
|7985|Fuente salvadora|active|90|367761, 367759, 367760, 367762|
|7987|Resplandor|passive|30|368131|
|7990|Presencia|passive|35|371754|
|7991|Súper Cunejo II|passive|50|371816|
|7992|Transgresión|passive|55|371817|
|7993|Elixir de Viento|passive|65|371831|
|7994|Aprendiz Alquimista|passive|70|371838|
|7995|Secreto de Producción|passive|75|371890|
|7996|Marca Anbareul|passive|80|371972|
|7997|Paradoja Contra Natura|passive|90|371928|
|7998|Ambivalencia|passive|95|371983|

## Grants and complete summon books

Native649 effects367635/367636/367637 grant7977Contra Natura,7978Cunejo and7979Repulsión. Each requires actual real level>=6, no active933effect and instance<>862. These actions are not ordinary equipped player-deck slots. Grant books, owner identities, condition contexts, usage costs and retained cleanup still require runtime acceptance.

|Profile|Current native monster name|Complete ability references|Initial states|Fight properties|
|---:|---|---|---|---|
|182|Cunejo|986|[]|[28, 15, 69]|
|1775|Súper Cunejo|5457, 5459, 5458, 986|[]|[28, 15, 69]|
|5528|Dark cunejo|7988|[]|[28, 15, 69]|
|5533|Súper dark cunejo|5457, 5458, 5459, 7988|[]|[28, 15, 69]|

All four current merged ability profiles, initial-state/property plans and characteristic profiles exist. All ability descriptors have raw UID=reference, inherited descriptor level (`override_level=-1`) and maximum245. The five unique summon actions are986/5457/5458/5459/7988. Cross-class spells5054/5193/7218 are criterion dependencies, not equip permissions or summon book entries. No execution or controllability of a particular profile is certified here.

## State and mark register

Every current state definition is present. Names are those available in the native localization snapshot; unnamed internal states remain unnamed rather than guessed. Reachability includes criterion-only references and false branches.

|State|Native label|Native effect roots|
|---:|---|---|
|756|Incurable|177975|
|1144|Convaleciente|149448, 163833|
|3230|Constitución|143553|
|3863|Cunejo|166762, 166764, 166781, 166761, 311943, 368080, 371989, 414079|
|3864|Vínculo de Amistad|166869, 167516, 268609|
|3867|Contra Natura|166896, 367571|
|3868|Palabra Revigorizante|166925|
|3869|Propagador|167934, 368126, 371834, 373487|
|3870|Juventud|178122, 367740, 367741, 367742|
|3876|Gangrena|167251, 313578|
|3878|Propagador|371761, 371764, 371773, 373491|
|3882|Marca Sdesade|367422, 367426, 367423, 367427, 371932, 371936|
|3884|Marca Ting|367443, 367451, 367438, 367446, 371946, 371955|
|3885|Marca Hmill|167494, 298416|
|3886|Propagador Retrasado|371893|
|3887|(internal; no label)|371058, 371060, 371062, 371064, 371070, 372008|
|3888|Marca del Reintegro|367478, 367474, 367479, 367475, 371962, 371967|
|3890|Recuperador|167524, 167525, 167527|
|3892|Súper Cunejo|168335, 168337, 168354, 168380, 311956, 371994, 414080|
|3894|(internal; no label)|371921|
|3896|Desfasado|167719, 167722, 167717, 167721, 367746, 367747, 367748|
|3897|(internal; no label)|167720|
|3899|Retraso|371828|
|3901|Palabra Sanadora|167879|
|3902|(internal; no label)|167892|
|3903|Elixir de Viento|371833|
|3907|Propagador Retrasado|371901|
|3911|Sanador|367634, 168092, 367604, 367718, 371778, 371072, 371562, 398460|
|3912|Bonus de gracia|178118|
|3917|Disminución de la resist. a las curas|168288, 345700|
|3918|Naturaleza Muerta|371982|
|3919|Marca Breo|168295, 367433, 371940|
|4464|Golpe de gracia|185234, 302260, 327548, 416581, 416965|
|6009|Crítico Berserker|283386|
|6012|Placaje Berserker|283401|
|6018|Esquiva Berserker|283439|
|6024|Anticipación Berserker|283469|
|6500|Pacificado|303900, 303909, 303917|
|6624|Frágil|348522|
|7885|Reavivar la Llama - Contador|353202, 353199|
|8019|Colisiones dolorosas|367532, 367534|
|8020|(internal; no label)|367561, 367567|
|8023|Generador|367744|
|8024|(internal; no label)|367755, 367757|
|8029|Dark cunejo|367993, 367995, 368012, 368036, 368037, 368090, 371999, 414062|
|8030|Murmullos de debilitamiento|368052|
|8032|Bonus de vitalidad|368101|
|8055|Propagador Retrasado|371908|
|8056|Propagador Retrasado|371913|
|9315|Berserker|416587, 416583, 416588, 416962|
|9331|(internal; no label)|416967, 417051, 416968, 417511, 418269|

The named marks include3882Marca Sdesade,3884Marca Ting,3885Marca Hmill,3888Marca del Reintegro and3919Marca Breo. Their meaning must be validated through their actual current subscribers, effect values and death recipients, not inferred from a label. Contra Natura3867, Cunejo3863/Súper Cunejo3892/Dark cunejo8029, Friendship3864, Desfasado3896, Propagator3869/3878 and delayed8055/8056/3907/3886 are distinct native states.

## Structural routes and concrete uncertainty

|Family|Current binding source|Static requirement / limit|
|---:|---|---|
|28|`server/wakfu_server/combat/combat_effect_runtime.py:484`|Registered unconditionally; semantic correctness unproven|
|196|`server/wakfu_server/combat/combat_effect_runtime.py:519`|Registered unconditionally; semantic correctness unproven|
|430|`server/wakfu_server/combat/combat_effect_runtime.py:873`|Registered unconditionally; semantic correctness unproven|
|307|`server/wakfu_server/combat/combat_effect_runtime.py:591`|self.summon_authority is not None|
|332|`server/wakfu_server/combat/combat_effect_runtime.py:507`|Registered unconditionally; semantic correctness unproven|
|649|`server/wakfu_server/combat/combat_effect_runtime.py:715`|Registered unconditionally; semantic correctness unproven|
|315|`server/wakfu_server/combat/combat_effect_runtime.py:666`|retention is not None|
|421|`server/wakfu_server/combat/combat_effect_runtime.py:1709`|retention is not None|
|1099|`server/wakfu_server/combat/combat_effect_runtime.py:456`|Registered unconditionally; semantic correctness unproven|

Historical claims that28/196/430 are absent are obsolete: all three have current bindings.196 maps to `NativeCurrentHPRestoreHandler`;28 is kill;430 mutates the live triggering runner amount. That does not establish an inverse death lifecycle. Anisurrección1535 current root166893 requires `IsOffPlay(target) and not IsEnnemy()` and executes196ref166894, heal25ref167897 and state1144ref166895. Nativeflags15 on the root/restore require actual off-play targeting. An enemy-only ordinary cast probe cannot certify or refute resurrection.

Summon307 is constructed only with an actual summon authority. Areas315 and linked removal421 need actual retention. Finding a binding does not prove providers supply correct source/target identity, event IDs, channels, registered geometry, ownership, turn timing or wire publication.

Areas1812 and1814 have current complete definitions and executable roots367753/371986. Area1812 entry mask10000; area1814 entry masks10000/10001/10008/10006. Exit masks are empty in both. Entry delivery, ownership, retained callback timing and retirement are behavior risks, not missing catalog data.

## Condition and mask scope

The JSON contains full conditions and seven-channel target-mask arrays for every974effect definition. Counts of effects with nonempty mask channels (channel index, not event ID): 3:43, 6:48, 2:10, 1:12, 5:44, 0:7.

Actual function names seen include `GetActiveCosmeticId`, `GetActiveSpellId`, `GetAlliesCount`, `GetAlliesCountInRange`, `GetCharac`, `GetCharacMax`, `GetCharacPct`, `GetCharacteristic`, `GetCharacteristicMax`, `GetCurrentFighterId`, `GetDate`, `GetEffectCaster`, `GetEffectTarget`, `GetEnnemyCountInRange`, `GetFightCurrentTableTurn`, `GetFightModel`, `GetInstanceId`, `GetItemQuantity`, `GetLevel`, `GetRandomNumber`, `GetRealLevel`, `GetStateLevel`, `GetTeamId`, `GetTotalHpInPercent`, `GetTriggeringContainerStateId`, `GetTriggeringContainerType`, `GetTriggeringEffectActionId`, `GetTriggeringEffectCaster`, `GetTriggeringEffectCasterIsSameAsCaster`, `GetTriggeringEffectId`, `GetTriggeringEffectTarget`, `GetTriggeringEffectValue`, `HasActiveCosmeticId`, `HasEffectWithActionId`, `HasEffectWithSpecificId`, `HasFightProperty`, `HasState`, `HasStateFromUser`, `HasWorldProperty`, `IsBreed`, `IsBreedId`, `IsCarried`, `IsChallenger`, `IsEnnemy`, `IsInFight`, `IsOffPlay`, `IsOwnSpecificArea`, `IsOwnSummon`, `IsPvp`, `IsSpellInDeck`, `IsTargetCellFree`, `IsTriggeredByIndirectEffect`, `IsTriggeredByZoneEffect`, `NbSummons`.

These names are inventory evidence, not a claim of complete authoritative context coverage. Priority cases include off-play/ally selection; own summons/areas; current real level, instance and morph exclusions for grants; carried/stabilized/movement contexts; heal resistance/virtual HP; triggering caster/target/value/container/action; death timing and indirect/zone provenance. Native condition classes/mask-bit labels retained from the historical graph are comparison evidence only.

## Current closure method and limitations

Current edges are recomputed from selected casting roots, morph level0 roots when published, raw state roots and levels, child arrays, native parameters at every integer0..250, state apply304/remove321, grants649, morph933profiles, summon307 ability+initial-state+characteristic catalogs, areas315/339/314/338, linked421effects and literal criterion references. Current dependencies are compared with the historical20261007graph per root; old graph edges are not used as executable child/spell/state truth.

This remains structural closure: impossible branches and criterion references can appear; no new native definitions are fabricated. Generic finisher1099 is presentation assignment, not an invented executable spell dependency. Runtime baseline/test results belong in the separate validation report. Manual class acceptance remains pending.

## Artifacts

- `aniripsa-catalog-audit-20261009.json`: full scoped current metadata, current breed row, current owned spells, exact current factory bindings, per-root historical/current reconciliation, areas and summon profiles.
- Temporary audit scripts `/tmp/aniripsa_inventory.py`, `/tmp/aniripsa_enrich.py`, `/tmp/aniripsa_markdown.py` read current published catalogs and write only these report artifacts.
- No gameplay implementation or deployment was performed.
