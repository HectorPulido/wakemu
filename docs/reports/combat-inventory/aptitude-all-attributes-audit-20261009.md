# All aptitude attributes audit

Pinned published catalog: `7071a8d8c8664e9e0d5fe8f44bf2a948d4138060fc1353ea70f65f2dcf00b568`. All **31 native bonus identities** are listed below. The same category grants and reducers serve all18classes; this is not an18class gameplay pass claim.

## Current delivery checkpoint

The table below was generated from7071; r54 now runs complete revision
`b0ed79766ae57e6ef26aa9321d05642522cf4c3d9baf7a22a4ea9d3cefc6f219`.
Its aptitude definitions are unchanged; native execution-count metadata was
enriched from178337original definitions. Selected-build and merged-save
validation, actual tackle/dodge movement and scaled listener budgets are
deployed. World and matching rebuilt AI are healthy.

Real two-player Barrier acceptance proves one-hit reduction/exhaustion and
next-owner-turn renewal without duplication. The renewal source passes35
regressions across initialization, actual Cra/Iop casting and retained
lifecycles, but awaits the next complete coordinated deployment. Received
healing now passes actual allied-heal acceptance after a general group
transmitted-target correction (tested, not deployed); HP-as-armor produces
52armor for2points and650maximumHP at real initialization.
The following investigation sections retain earlier checkpoints; their
no-deployment statements and missing-consumer descriptions are historical.
See [current consumer evidence](aptitude-damage-healing-armor-consumers-20261009.md)
and [manual31attribute acceptance](aptitude-manual-acceptance-20261009.md).

|Category|Attribute / bonus ID|Cap|Native production route|
|---|---|---|---|
|Intelligence|HP percent /1|category budget|root136429; flat/percentage reducer → equipment_stats → world/actor snapshot; stat|
|Intelligence|Elemental resistance /16|10|root136451; flat/percentage reducer → equipment_stats → world/actor snapshot; stat27|
|Intelligence|Barrier /17|10|root165201; native eQr runtime initialization; stat-1, -1|
|Intelligence|Healing received /27|5|root136594; native eQr runtime initialization; stat-1, -1|
|Intelligence|HP as armor /36|10|root303745; native eQr runtime initialization; stat-1, -1, -1|
|Strength|Elemental mastery /23|category budget|root137957; flat/percentage reducer → equipment_stats → world/actor snapshot; stat20|
|Strength|Melee mastery /26|40|root137965; flat/percentage reducer → equipment_stats → world/actor snapshot; stat103|
|Strength|Distance mastery /30|40|root137977; flat/percentage reducer → equipment_stats → world/actor snapshot; stat104|
|Strength|Flat HP /31|category budget|root137974; flat/percentage reducer → equipment_stats → world/actor snapshot; stat1|
|Agility|Lock /18|category budget|root136467; flat/percentage reducer → equipment_stats → world/actor snapshot; stat7|
|Agility|Dodge /19|category budget|root136468; flat/percentage reducer → equipment_stats → world/actor snapshot; stat8|
|Agility|Initiative /20|20|root136469; flat/percentage reducer → equipment_stats → world/actor snapshot; stat35|
|Agility|Lock and dodge /21|category budget|root136470; flat/percentage reducer → equipment_stats → world/actor snapshot; stat8, 7|
|Agility|Willpower /37|20|root243129; flat/percentage reducer → equipment_stats → world/actor snapshot; stat86|
|Luck|Critical chance /9|20|root136444; flat/percentage reducer → equipment_stats → world/actor snapshot; stat9|
|Luck|Block /10|20|root136445; flat/percentage reducer → equipment_stats → world/actor snapshot; stat87|
|Luck|Critical mastery /11|category budget|root136446; flat/percentage reducer → equipment_stats → world/actor snapshot; stat52|
|Luck|Rear mastery /12|category budget|root136447; flat/percentage reducer → equipment_stats → world/actor snapshot; stat16|
|Luck|Berserk mastery /13|category budget|root136448; flat/percentage reducer → equipment_stats → world/actor snapshot; stat107|
|Luck|Healing mastery /14|category budget|root136449; flat/percentage reducer → equipment_stats → world/actor snapshot; stat18|
|Luck|Rear resistance /15|20|root136450; flat/percentage reducer → equipment_stats → world/actor snapshot; stat17|
|Luck|Critical resistance /34|20|root137557; flat/percentage reducer → equipment_stats → world/actor snapshot; stat95|
|Major|AP /2|1|root136428; flat/percentage reducer → equipment_stats → world/actor snapshot; stat2|
|Major|MP and mastery /3|1|root136430; flat/percentage reducer → equipment_stats → world/actor snapshot; stat3, 20|
|Major|Range and mastery /4|1|root136433; flat/percentage reducer → equipment_stats → world/actor snapshot; stat11, 20|
|Major|WP /5|1|root136436; flat/percentage reducer → equipment_stats → world/actor snapshot; stat4|
|Major|Armor given percent /6|1|root410102; flat/percentage reducer → equipment_stats → world/actor snapshot; stat120|
|Major|Damage inflicted percent /8|1|root137558; flat/percentage reducer → equipment_stats → world/actor snapshot; stat48|
|Major|Elemental resistance /35|1|root137559; flat/percentage reducer → equipment_stats → world/actor snapshot; stat27|
|Major|Healing performed percent /38|1|root410101; flat/percentage reducer → equipment_stats → world/actor snapshot; stat114|
|Major|Indirect damage and mastery /39|1|root410103; flat/percentage reducer → equipment_stats → world/actor snapshot; stat-1, 20|

## Budgets and ownership

Category points count native grant thresholds at the effective sheet level. Intelligence starts2 then every4levels; Strength3; Agility4; Luck5. Major grants25/75/125/175/225. At200:50/50/50/49/4; at250:62/62/62/62/5. Per-bonus caps apply independently. Dormant category references24/25/32/33 have no native bonus objects and remain rejected; they must not be invented from historical UI categories.

## Concrete corrected defect

Build saving already validates against the selected build cap. Flat and runtime aptitude readers previously validated against character real level. A valid explicit capped sheet could reject during combat, while an automatic-level sheet could consume an excessive real-level budget. Both readers now share `validate_owned_sheet`, which resolves existing saved build metadata before validation. Three regression cases cover explicit cap, overbudget automatic sheet and alternate selected build. Production source files are frozen for deployment coordination.

## Persistence, reset and consumers

`builds.validate` validates all four blobs before saving; storage saves/loads aptitude blobs in character builds; `aptitude_registry` emits each owned sheet for reconnect. Flat additions flow through `equipment_stats.bonuses`; HP applies flat maximum plus percentage with Java truncation; resources apply AP/MP/WP and initiative; actor snapshots consume all stat keys and reject unsupported effects. Build response canonicalizes missing default sheets with empty aptitudes. No dedicated unrestricted respec operation was established by this review; replacing a validated saved blob is the observed boundary.

The three reactive bonuses17/27/36 use eQr container36 at allocated point level, after class initialization, exactly once. Their full exported criteria, events and children are preserved in JSON. They are not flat healreceived/barrier guesses:Barrier17 has reverse damage2→999→430; current execution-count slope export is incomplete and can leave its base0 listener inactive (event owner is fixing the general count contract). Received healing27 installs state3205 at6*points from external1003; state3205 applies family1093 only for qualifying other allied heal sources. HP-as-armor36 selects HP<80000/≥80000 branches1047→1013 and excludes summons. Lock/Dodge7/8 and combined bonus21 currently reach snapshots but lack production disengagement consumption; the separate movement owner is implementing that contract.

## Verification and remaining gates

Current-catalog tests:14 run,10PASS,4 database-mutating integration tests skipped. Catalog coverage exercises budgets at all250levels and every legal allocated point, grouped reducers and fail-closed partial children. These checks establish producer/reducer contracts, not healing, armor, barrier or combat outcomes. Damage/heal/armor consumer audit belongs to the parallel event owner; reactive start/damage/turn counters and state3205 require actual initialized combat tests. All18classes share the code, but all18saved-build/combat combinations were not executed. No service restart, deployment or database writes.

## Follow-up arithmetic and partial-save review

Critical chance reads live PC9, clamps its owned percentage roll threshold to0..100, and preserves unavailable native critical branches. Block reads PC87 through the exact inclusive1..100 boundary; Willpower86 enters float32 AP/MP loss calculation with source/target and self/ignore flags. The additional focused source-contract suite passed28tests; random server roll policy is explicitly distinguished from original client arithmetic. No additional missing consumer is established for these three statistics.

A second concrete defect was found in partial build persistence: empty request blobs retained previous data only after validating the incoming request. Lowering the build level could therefore retain overbudget old aptitudes. The new shared `validated_saved_blobs` merges first and validates exactly what the transaction will persist; the Store inserts that same payload. Regression cases cover rejected lowered cap with source unchanged, valid partial retention and explicit reset in the same update. Luna validated all3partial-save regressions plus all3selected-build-level regressions against the current published catalog:6PASS, no gameplay database mutation.
