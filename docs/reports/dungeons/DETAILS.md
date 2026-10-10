# Per-dungeon evidence

Native Spanish names retain French aliases. Read [inventory scope and limitations](INVENTORY.md). Reference pools are not encounter rosters. Official order, collision and quest authority need verification; native object presence is independently proven.

## Factor Trool (native:13)

French alias: Académie Trool. Type: DUNGEON_3_PLAYERS. Native level: 81. Maps: [483].

Species pool: Troolk Hoogan [2440] level 89-93, The Undertroolker [2441] level 85-89, Rey Mystroolrio [2442] level 83-87, Trool del Río [2443] level 98-103

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 337, object 18969, destination 1167, template 16. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 8, 'ZoneTrigger': 1, 'GenericActivableInteractiveElement': 5}.

- Internal transport object 18807 on map 483: map 483 (-41,-33,0), criterion=empty, item=0
- Internal transport object 18808 on map 483: map 483 (-41,-61,0), criterion=empty, item=0
- Internal transport object 18809 on map 483: map 483 (-61,-74,0), criterion=empty, item=0
- Internal transport object 18810 on map 483: map 483 (-42,-6,-4), criterion=empty, item=0
- Internal transport object 18811 on map 483: map 483 (-41,-45,0), criterion=empty, item=0
- Internal transport object 18812 on map 483: map 483 (-47,-74,0), criterion=empty, item=0
- ZoneTrigger: 19116 at map 483 (-65.0,-68.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Ala de la Embajadora (native:9)

French alias: Aile de l'Ambassadrice. Type: DUNGEON_2_ROOMS. Native level: 111. Maps: [515].

Species pool: Bárbaro norteño [2344] level 115-119, Guarda norteño [2345] level 115-119, Arquero norteño [2346] level 113-117, Rastreador norteño [2347] level 125-129, Kya, Mizz Frizz [2348] level 128-133

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 521, object 18068, destination 1105, template 12. Criterion:

```text
not IsNeoServer()
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 2}.

- Door: 18071 at map 515 (19.0,-36.0,-12.0); 18072 at map 515 (32.0,-36.0,-12.0); 18070 at map 515 (19.0,-37.0,-12.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Antro de Excarnus (native:4)

French alias: Antre d'Excarnus. Type: ULTIMATE_BOSS. Native level: 66. Maps: [360].

Species pool: Excarnus [1986] level 80-80

### Guide composition

[boss-ultimes-antre-dexcarnus](https://methodwakfu.com/pvm/boss-ultimes/antre-dexcarnus/); extraction=partial; version=1.64; client version match=unverified.

- Room 1 (unknown): Unknown composition

### Native entrance and interiors

Entry map 711, object 20704, destination 878, template 8. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 1, 'Door': 5, 'GenericActivableInteractiveElement': 2}.

- Door: 33387 at map 360 (-4.0,-4.0,0.0); 33386 at map 360 (-4.0,-3.0,0.0); 33385 at map 360 (-6.0,-3.0,0.0); 33389 at map 360 (-4.0,-7.0,0.0); 33388 at map 360 (-4.0,-6.0,0.0)

### Local implementation

boss-ultimes-antre-dexcarnus v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Excarnus [1986], 1 × Excarnus [1986], 1 × Excarnus [1986], 1 × Excarnus [1986], 1 × Excarnus [1986], 1 × Excarnus [1986], 1 × Excarnus [1986], 1 × Excarnus [1986]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Antro de Nogord, el Alado (native:117)

French alias: Antre de Nogord l'Ezarélé. Type: ULTIMATE_BOSS. Native level: 186. Maps: [1092].

Species pool: Nogord, el Alado [3433] level 200-200

### Guide composition

[antre-de-nogord-l-ezarele](https://methodwakfu.com/pvm/boss-ultimes/antre-de-nogord-l-ezarele/); extraction=unknown; version=None; client version match=unverified.


### Native entrance and interiors

Entry map 1093, object 27294, destination 2563, template 120. Criterion:

```text
not GetBooleanSystemConfiguration("beta.mode") and IsAfter(13,12,2016,20,00,00)
```

Object counts: {'Teleporter': 1, 'GenericActivableInteractiveElement': 2}.


### Local implementation

antre-de-nogord-l-ezarele v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Nogord, el Alado [3433], 1 × Nogord, el Alado [3433], 1 × Nogord, el Alado [3433], 1 × Nogord, el Alado [3433], 1 × Nogord, el Alado [3433], 1 × Nogord, el Alado [3433], 1 × Nogord, el Alado [3433], 1 × Nogord, el Alado [3433]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Antro de Jálrog (native:6)

French alias: Antre du Boufrog. Type: ULTIMATE_BOSS. Native level: 96. Maps: [365].

Species pool: Magmog, el Jálrog [42] level 110-110

### Guide composition

[boss-ultimes-antre-du-boufrog](https://methodwakfu.com/pvm/boss-ultimes/antre-du-boufrog/); extraction=partial; version=1.64; client version match=unverified.

- Room 1 (partial): 1 × Boufrog [ref None, unknown]
- Room 2 (partial): 1 × Magmog le Boufrog [ref 42, boss]

### Native entrance and interiors

Entry map 1137, object 18074, destination 1107, template 10. Criterion:

```text
(empty on this entry)
```

Object counts: {'GenericActivableInteractiveElement': 2, 'AudioMarker': 1, 'Teleporter': 1}.


### Local implementation

boss-ultimes-antre-du-boufrog v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42]
- Configured room 2: 1 × Magmog le Boufrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42], 1 × Magmog, el Jálrog [42]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Antro del Cuervo Negro (native:5)

French alias: Antre du Corbeau Noir. Type: ULTIMATE_BOSS. Native level: 96. Maps: [363].

Species pool: Cuervo Negro [1988] level 110-110

### Guide composition

[antre-du-corbeau-noir](https://methodwakfu.com/pvm/boss-ultimes/antre-du-corbeau-noir/); extraction=unknown; version=1.64; client version match=unverified.


### Native entrance and interiors

Entry map 962, object 25245, destination 886, template 9. Criterion:

```text
not GetBooleanSystemConfiguration("beta.mode") and not IsNeoServer()
```

Object counts: {'Teleporter': 1}.


### Local implementation

antre-du-corbeau-noir v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Cuervo Negro [1988], 1 × Cuervo Negro [1988], 1 × Cuervo Negro [1988], 1 × Cuervo Negro [1988], 1 × Cuervo Negro [1988], 1 × Cuervo Negro [1988], 1 × Cuervo Negro [1988], 1 × Cuervo Negro [1988]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Antro del Dragocerdo (native:57)

French alias: Antre du Dragon-Cochon. Type: ULTIMATE_BOSS. Native level: 111. Maps: [545].

Species pool: Dragocerdo [2430] level 125-125

### Guide composition

[boss-ultimes-antre-du-dragon-cochon](https://methodwakfu.com/pvm/boss-ultimes/antre-du-dragon-cochon/); extraction=partial; version=1.70; client version match=unverified.

- Room 1 (partial): None × Dragon-Cochon [ref 2430, boss]

### Native entrance and interiors

Entry map 1222, object 19060, destination 1223, template 58. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 4, 'GenericActivableInteractiveElement': 1, 'AudioMarker': 1, 'Teleporter': 1}.

- Door: 33392 at map 545 (-2.0,-32.0,0.0); 33391 at map 545 (-3.0,-32.0,0.0); 33394 at map 545 (1.0,-32.0,0.0); 33393 at map 545 (0.0,-32.0,0.0)

### Local implementation

boss-ultimes-antre-du-dragon-cochon v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Dragon-Cochon [2430], 1 × Dragocerdo [2430], 1 × Dragocerdo [2430], 1 × Dragocerdo [2430], 1 × Dragocerdo [2430], 1 × Dragocerdo [2430], 1 × Dragocerdo [2430], 1 × Dragocerdo [2430]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Antro de Maxilubo (native:3)

French alias: Antre du Meulou. Type: ULTIMATE_BOSS. Native level: 81. Maps: [358].

Species pool: Milkar, el Maxilubo [1987] level 95-95

### Guide composition

[boss-ultimes-antre-du-meulou](https://methodwakfu.com/pvm/boss-ultimes/antre-du-meulou/); extraction=unknown; version=1.64; client version match=unverified.


### Native entrance and interiors

Entry map 1264, object 18061, destination 882, template 7. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 1}.


### Local implementation

boss-ultimes-antre-du-meulou v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Milkar, el Maxilubo [1987], 1 × Milkar, el Maxilubo [1987], 1 × Milkar, el Maxilubo [1987], 1 × Milkar, el Maxilubo [1987], 1 × Milkar, el Maxilubo [1987], 1 × Milkar, el Maxilubo [1987], 1 × Milkar, el Maxilubo [1987], 1 × Milkar, el Maxilubo [1987]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## antre-de-la-sorciere (legacy-guide:antre-de-la-sorciere)

French alias: unmapped legacy guide. Type: legacy. Native level: unknown. Maps: see configured entry.

Species pool: Unknown native pool

### Guide composition

[antre-de-la-sorciere](https://methodwakfu.com/pvm/donjons-evenementiels/antre-de-la-sorciere/); extraction=complete; version=1.66; client version match=unverified.

- Room 1 (complete): 4 × Bouftou d’Halouine [ref None, monster], 2 × Boufette d’Halouine [ref 2047, monster], 1 × Chef Bouftou d’Halouine [ref 2046, monster]
- Room 2 (complete): 1 × Sorcière [ref 2096, boss]

### Native entrance and interiors

Entry map 527, object 20179, destination 955, template 1000443. Criterion:

```text
@("event.halouine.date.expired") (IsAfter(16,10,2026,10,00,00) and IsBefore(03,11,2026,10,00,00))@ and #HasState(1536)#
```

Object counts: {'GenericActivableInteractiveElement': 1, 'Door': 1, 'ZoneTrigger': 1, 'Teleporter': 2}.

- Door: 16459 at map 443 (-19.0,0.0,0.0)
- ZoneTrigger: 16626 at map 443 (-23.0,0.0,0.0)

### Local implementation

antre-de-la-sorciere v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 4 × Jefe jalató de Haluín [2046], 2 × Jalalínea de Haluín [2047], 1 × Bruja [2096], 1 × Jefe jalató de Haluín [2046]
- Configured room 2: 1 × Sorcière [2096]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Blópera (native:152)

French alias: Blopéra. Type: DUNGEON_2_ROOMS. Native level: 141. Maps: [1223].

Species pool: Blop flautista [4777] level 143-147, Blop Dylan [4778] level 145-149, Blop tamborrudo [4779] level 149-153, Blopgang Amadeus Blopzart [4780] level 158-163

### Guide composition

[blopera](https://methodwakfu.com/pvm/blopera/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Blop Tompettiste [ref None, monster], 2 × Blop Dylan [ref 4778, monster], 2 × Blop Tambourrin [ref 4779, monster]
- Room 2 (complete): 2 × Blop Tompettiste [ref None, monster], 2 × Blop Dylan [ref 4778, monster], 3 × Blop Tambourrin [ref 4779, monster]
- Room 3 (complete): 3 × Blop Tompettiste [ref None, monster], 2 × Blop Dylan [ref 4778, monster], 3 × Blop Tambourrin [ref 4779, monster]
- Room 4 (complete): 1 × Blopang Amadeus Blopzart [ref None, boss], 2 × Blop Tompettiste [ref None, monster], 2 × Blop Dylan [ref 4778, monster], 2 × Blop Tambourrin [ref 4779, monster]

### Native entrance and interiors

Entry map 1137, object 31680, destination 4019, template 155. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Stele': 1, 'GenericActivableInteractiveElement': 1, 'Door': 8}.

- Door: 31654 at map 1223 (-32.0,-26.0,18.0); 31653 at map 1223 (-33.0,-26.0,18.0); 31649 at map 1223 (-31.0,-36.0,28.0); 31648 at map 1223 (-31.0,-35.0,28.0); 31647 at map 1223 (-31.0,-34.0,28.0); 31652 at map 1223 (-37.0,-33.0,28.0); 31650 at map 1223 (-37.0,-31.0,28.0); 31651 at map 1223 (-37.0,-32.0,28.0)
- Stele: 34863 at map 1223 (-36.0,-14.0,0.0)

### Local implementation

blopera v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Blop flautista [4777], 2 × Blop Dylan [4778], 2 × Blop Tambourrin [4779], 1 × Blopgang Amadeus Blopzart [4780], 1 × Blop flautista [4777]
- Configured room 2: 2 × Blop Dylan [4778], 2 × Blop Dylan [4778], 3 × Blop Tambourrin [4779], 1 × Blop flautista [4777]
- Configured room 3: 3 × Blop tamborrudo [4779], 2 × Blop Dylan [4778], 3 × Blop Tambourrin [4779]
- Configured room 4: 1 × Blopgang Amadeus Blopzart [4780], 2 × Blop flautista [4777], 2 × Blop Dylan [4778], 2 × Blop Tambourrin [4779], 1 × Blopgang Amadeus Blopzart [4780]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Brecha dimensional de Amakna (native:174)

French alias: Brèche dimensionnelle d'Amakna. Type: INFINITE_WAVE. Native level: 111. Maps: [1329].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'GenericActivableInteractiveElement': 1, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Brecha dimensional de Osamosa (native:175)

French alias: Brèche dimensionnelle d'Osamosa. Type: INFINITE_WAVE. Native level: 201. Maps: [1330].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'GenericActivableInteractiveElement': 1, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Brecha dimensional de Bonta (native:171)

French alias: Brèche dimensionnelle de Bonta. Type: INFINITE_WAVE. Native level: 141. Maps: [1320].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'GenericActivableInteractiveElement': 1, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Brecha dimensional de Frigost (native:170)

French alias: Brèche dimensionnelle de Frigost. Type: ULTIMATE_INFINITE_WAVE. Native level: 111. Maps: [1318].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'Teleporter': 1, 'GenericActivableInteractiveElement': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Brecha dimensional de la Fab'hugruta (native:182)

French alias: Brèche dimensionnelle de la Shukrute. Type: INFINITE_WAVE. Native level: 216. Maps: [1345].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'GenericActivableInteractiveElement': 1, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Brecha dimensional de Moon (native:172)

French alias: Brèche dimensionnelle de Moon. Type: INFINITE_WAVE. Native level: 171. Maps: [1322].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'Teleporter': 1, 'GenericActivableInteractiveElement': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Brecha dimensional de Sufokia (native:169)

French alias: Brèche dimensionnelle de Sufokia. Type: INFINITE_WAVE. Native level: 66. Maps: [1316].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'Teleporter': 1, 'GenericActivableInteractiveElement': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Brecha dimensional de Tainela (native:168)

French alias: Brèche dimensionnelle de Tainéla. Type: INFINITE_WAVE. Native level: 21. Maps: [1314].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'GenericActivableInteractiveElement': 1, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Brecha dimensional del Monte Zinit (native:173)

French alias: Brèche dimensionnelle du Mont Zinit. Type: ULTIMATE_INFINITE_WAVE. Native level: 201. Maps: [1324].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'GenericActivableInteractiveElement': 1, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Brecha dimensional definitiva de la Fab'hugruta (native:183)

French alias: Brèche dimensionnelle ultime de la Shukrute. Type: ULTIMATE_INFINITE_WAVE. Native level: 216. Maps: [1347].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'GenericActivableInteractiveElement': 1, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Cañón de los Plaguepardos (native:156)

French alias: Canyon des Fléopards. Type: DUNGEON_3_ROOMS. Native level: 186. Maps: [1257].

Species pool: Plagueroz [5047] level 194-198, Plagandul [5048] level 190-194, Plaguétido [5049] level 188-192, Plagogro [5052] level 203-208

### Guide composition

[canyon-des-fleopards](https://methodwakfu.com/pvm/canyon-des-fleopards/); extraction=partial; version=1.66; client version match=unverified.

- Room 1 (complete): 2 × Flémard [ref 5048, monster], 2 × Fléroce [ref 5047, monster], 2 × Flétide [ref 5049, monster]
- Room 2 (complete): 2 × Flémard [ref 5048, monster], 2 × Fléroce [ref 5047, monster], 3 × Flétide [ref 5049, monster]
- Room 3 (partial): 8 × Fléopard [ref None, unknown]
- Room 4 (complete): 1 × Fléogre [ref 5052, boss], 2 × Flémard [ref 5048, monster], 3 × Fléroce [ref 5047, monster], 2 × Flétide [ref 5049, monster]

### Native entrance and interiors

Entry map 1252, object 31867, destination 4035, template 159. Criterion:

```text
(empty on this entry)
```

Object counts: {'GenericActivableInteractiveElement': 8, 'Teleporter': 2, 'Door': 3, 'Stele': 1}.

- Door: 31866 at map 1257 (-35.0,1.0,11.0); 31865 at map 1257 (-48.0,-9.0,11.0); 31864 at map 1257 (-77.0,-2.0,1.0)
- Stele: 34879 at map 1257 (-92.0,0.0,49.0)

### Local implementation

canyon-des-fleopards v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Flémard [5048], 2 × Fléroce [5047], 2 × Flétide [5049]
- Configured room 2: 2 × Flémard [5048], 2 × Fléroce [5047], 3 × Flétide [5049]
- Configured room 3: 8 × Plaguétido [5049]
- Configured room 4: 1 × Fléogre [5052], 2 × Flémard [5048], 3 × Fléroce [5047], 2 × Flétide [5049]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Caverna Brizlónica (native:122)

French alias: Caverne des Slekymoses. Type: DUNGEON_2_ROOMS. Native level: 81. Maps: [1126].

Species pool: Brizlón mágico [4246] level 89-93, Long Brizlón [4247] level 85-89, Brizlochino [4248] level 83-87, Reina Brizlona [4251] level 98-103

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1119, object 27745, destination 2610, template 125. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 3, 'Teleporter': 2, 'GenericActivableInteractiveElement': 1}.

- Door: 27720 at map 1126 (-14.0,-48.0,-11.0); 27719 at map 1126 (-15.0,-48.0,-11.0); 27721 at map 1126 (-28.0,-66.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Caverna Samaraciosa (native:123)

French alias: Caverne Smarrante. Type: DUNGEON_3_ROOMS. Native level: 111. Maps: [1127].

Species pool: Samaracito [4228] level 113-117, Sámara gordinflón [4229] level 119-123, Sámara cuático [4230] level 115-119, Samarilion [4231] level 128-133

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1120, object 27784, destination 2612, template 126. Criterion:

```text
(empty on this entry)
```

Object counts: {'GenericActivableInteractiveElement': 16, 'Teleporter': 2, 'Door': 3}.

- Door: 27785 at map 1127 (6.0,-43.0,-10.0); 27776 at map 1127 (10.0,-40.0,-10.0); 27777 at map 1127 (13.0,-68.0,15.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## chez-la-mere-michou (legacy-guide:chez-la-mere-michou)

French alias: unmapped legacy guide. Type: legacy. Native level: unknown. Maps: see configured entry.

Species pool: Unknown native pool

### Guide composition

[chez-la-mere-michou](https://methodwakfu.com/pvm/chez-la-mere-michou/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 3 × Chacha [ref 2616, monster]
- Room 2 (complete): 2 × Chacha [ref 2616, monster], 1 × Chacha Blanc [ref 2617, monster]
- Room 3 (complete): 1 × Maine Cooyne [ref 1816, boss], 1 × Chacha [ref 2616, monster], 1 × Chacha Blanc [ref 2617, monster]

### Native entrance and interiors

Entry map 527, object 18736, destination 713, template 1000312. Criterion:

```text
not (IsAchievementRunning(5568)
and IsAchievementObjectiveComplete(11513)
and not IsAchievementObjectiveComplete(11515))
```

Object counts: {'Teleporter': 4, 'Door': 2}.

- Internal transport object 14513 on map 312: map 312 (148,125,0), criterion=(IsAchievementRunning(5568)
and IsAchievementObjectiveComplete(11513)
and not IsAchievementObjectiveComplete(11515)), item=0
- Internal transport object 35383 on map 312: map 312 (8,-45,0), criterion=empty, item=0
- Internal transport object 35385 on map 312: map 312 (17,-9,-11), criterion=empty, item=0
- Internal transport object 14514 on map 312: map 312 (148,125,0), criterion=(IsAchievementRunning(5568)
and IsAchievementObjectiveComplete(11513)
and not IsAchievementObjectiveComplete(11515)), item=0
- Door: 14511 at map 312 (9.0,-3.0,0.0); 14512 at map 312 (16.0,-10.0,0.0)

### Local implementation

chez-la-mere-michou v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 3 × Chacha [2616]
- Configured room 2: 2 × Chacha [2616], 1 × Chacha Blanc [2617]
- Configured room 3: 1 × Maine Cooyne [1816], 1 × Chacha [2616], 1 × Chacha Blanc [2617]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Base del Susurro (native:53)

French alias: Chuchobase. Type: DUNGEON_4_ROOMS. Native level: 96. Maps: [448].

Species pool: Susurrador abanderado [2076] level 100-104, Crujidor susurrado [2078] level 100-104, Crujibola susurrado [2083] level 98-102, Gran crujidor susurrado [2084] level 104-108, Susurrón I [2100] level 120-120

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1295, object 32889, destination 940, template 51. Criterion:

```text
(empty on this entry)
```

Object counts: {'ZoneTrigger': 5, 'Door': 4, 'AudioMarker': 2, 'GenericActivableInteractiveElement': 1, 'Teleporter': 2}.

- Door: 16509 at map 448 (-1.0,-60.0,8.0); 16262 at map 448 (1.0,-22.0,8.0); 16508 at map 448 (0.0,-22.0,8.0); 16263 at map 448 (0.0,-60.0,8.0)
- ZoneTrigger: 16538 at map 448 (-2.0,-43.0,8.0); 16511 at map 448 (-3.0,-93.0,10.0); 16512 at map 448 (-2.0,-93.0,10.0); 16514 at map 448 (0.0,-93.0,10.0); 16513 at map 448 (1.0,-93.0,10.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Castillo de Wagnar (native:49)

French alias: Château de Wagnar. Type: DUNGEON_3_ROOMS. Native level: 81. Maps: [330].

Species pool: Murciego rechoncho [1825] level 85-89, Ghul [1827] level 85-89, Ghulotony [1828] level 89-93, Vampyro [1836] level 95-95

### Guide composition

[chateau-wagnar](https://methodwakfu.com/pvm/chateau-wagnar/); extraction=partial; version=1.59; client version match=unverified.

- Room 1 (complete): 6 × Goule [ref 1827, monster]
- Room 2 (complete): 4 × Chauffe-Souris Dodue [ref 1825, monster], 3 × Gouloutony [ref 1828, monster]
- Room 3 (partial): None × Vampyro [ref 1836, boss], 6 × Goule [ref 1827, monster]

### Native entrance and interiors

Entry map 1232, object 30694, destination 720, template 47. Criterion:

```text
not HasState(5724) and not IsNeoServer()
```

Object counts: {'Teleporter': 9, 'ZoneTrigger': 2, 'GenericActivableInteractiveElement': 1, 'BackgroundDisplay': 1, 'AudioMarker': 2}.

- Internal transport object 14676 on map 330: map 330 (72,-90,37), criterion=not IsNeoServer(), item=0
- Internal transport object 14674 on map 330: map 330 (72,-90,37), criterion=not IsNeoServer(), item=0
- Internal transport object 14675 on map 330: map 330 (0,-19,16), criterion=empty, item=0
- Internal transport object 14679 on map 330: map 330 (79,-97,37), criterion=not IsNeoServer(), item=0
- Internal transport object 16172 on map 330: map 330 (3,-18,16), criterion=empty, item=0
- Internal transport object 14678 on map 330: map 330 (0,-117,0), criterion=not IsNeoServer(), item=0
- Internal transport object 14677 on map 330: map 330 (0,-19,16), criterion=not IsNeoServer(), item=0
- ZoneTrigger: 14701 at map 330 (0.0,-2.0,0.0); 14756 at map 330 (0.0,-123.0,0.0)

### Local implementation

chateau-wagnar v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 6 × Murciego rechoncho [1825], 1 × Ghul [1827], 1 × Ghulotony [1828]
- Configured room 2: 4 × Chauffe-Souris Dodue [1825], 3 × Gouloutony [1828]
- Configured room 3: 1 × Ghulotony [1828], 6 × Vampyro [1836], 1 × Murciego rechoncho [1825]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Castillo de los Cangwejos (native:140)

French alias: Château des Cwabes. Type: DUNGEON_3_ROOMS. Native level: 51. Maps: [496].

Species pool: Don Kangwejus [4749] level 51-55, Kangwejator [4750] level 61-64, Albatroz [4751] level 56-60, Cangwejo Real [4754] level 68-73

### Guide composition

[donjons-chateau-des-cwabes](https://methodwakfu.com/pvm/donjons/chateau-des-cwabes/); extraction=complete; version=1.70; client version match=unverified.

- Room 1 (complete): 3 × Cwalbator [ref 4749, monster], 2 × Père Cwabtor [ref 4750, monster], 1 × Salbatroce [ref 4751, monster]
- Room 2 (complete): 4 × Cwalbator [ref 4749, monster], 2 × Père Cwabtor [ref 4750, monster], 2 × Salbatroce [ref 4751, monster]
- Room 3 (complete): 1 × Cwabe Royal [ref 4754, boss], 2 × Cwalbator [ref 4749, monster], 3 × Père Cwabtor [ref 4750, monster], 2 × Salbatroce [ref 4751, monster]

### Native entrance and interiors

Entry map 1135, object 18015, destination 1030, template 143. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 8, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 17745 on map 496: map 496 (-16,-27,20), criterion=empty, item=0
- Internal transport object 18016 on map 496: map 496 (-4,63,0), criterion=empty, item=0
- Internal transport object 31596 on map 496: map 496 (-17,-35,72), criterion=empty, item=0
- Internal transport object 31597 on map 496: map 496 (-15,-34,40), criterion=empty, item=0
- Internal transport object 31595 on map 496: map 496 (-17,-32,40), criterion=empty, item=0
- Internal transport object 31594 on map 496: map 496 (-8,-24,0), criterion=empty, item=0

### Local implementation

donjons-chateau-des-cwabes v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 3 × Cwalbator [4749], 2 × Kangwejator [4750], 1 × Albatroz [4751], 1 × Cangwejo Real [4754], 1 × Don Kangwejus [4749]
- Configured room 2: 4 × Cwalbator [4749], 2 × Albatroz [4751], 2 × Cangwejo Real [4754]
- Configured room 3: 1 × Cwabe Royal [4754], 2 × Cwalbator [4749], 3 × Don Kangwejus [4749], 2 × Kangwejator [4750]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Castillo del Wey Wabbit (native:72)

French alias: Château du Wa Wabbit. Type: DUNGEON_3_PLAYERS. Native level: 141. Maps: [1399].

Species pool: Tiwadow wabbit [2577] level 149-153, Caballewo wabbit [2578] level 147-151, Guawdia wabbit [2579] level 143-147, Wobot [2580] level 147-151, Jefe wobot [2581] level 147-151, Wey Wabbit [2582] level 158-163

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1393, object 34667, destination 4578, template 183. Criterion:

```text
not IsNeoServer()
and not (IsAchievementRunning(5182)
and IsAchievementObjectiveComplete(10854)
and not IsAchievementObjectiveComplete(10855))
and not (IsAchievementRunning(5187)
and IsAchievementObjectiveComplete(10774)
and not IsAchievementObjectiveComplete(10775))
```

Object counts: {'Teleporter': 1, 'GenericActivableInteractiveElement': 6, 'Stele': 1}.

- Stele: 34864 at map 1399 (-11.0,-105.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Cima del Gran Tótem (native:111)

French alias: Cime du Grand Totem. Type: ULTIMATE_BOSS. Native level: 171. Maps: [1056].

Species pool: Ful Moon [3870] level 185-185

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 999, object 26474, destination 2468, template 114. Criterion:

```text
not GetBooleanSystemConfiguration("beta.mode")
```

Object counts: {'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Cire Momore (native:221)

French alias: Cire Momore. Type: DUNGEON_ARCADE. Native level: 51. Maps: [1477].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 346, object 35958, destination 4789, template 213. Criterion:

```text
(empty on this entry)
```

Object counts: {'GenericActivableInteractiveElement': 1, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Ciudad Prohibida (native:155)

French alias: Cité Interdite. Type: DUNGEON_3_PLAYERS. Native level: 171. Maps: [1256].

Species pool: Pandikaze [5041] level 175-179, Pandido [5042] level 179-183, Pandócil [5043] level 173-177, Pandora [5046] level 188-193

### Guide composition

[cite-interdite](https://methodwakfu.com/pvm/cite-interdite/); extraction=complete; version=1.66; client version match=unverified.

- Room 1 (complete): 1 × Pandore [ref 5046, boss], 1 × Pandou [ref 5043, monster], 1 × Pandikaze [ref 5041, monster], 1 × Pandit [ref 5042, monster]

### Native entrance and interiors

Entry map 1252, object 31868, destination 4033, template 158. Criterion:

```text
not IsNeoServer()
```

Object counts: {'Door': 3, 'GenericActivableInteractiveElement': 6, 'Teleporter': 1}.

- Door: 33363 at map 1256 (-1.0,1.0,0.0); 33365 at map 1256 (1.0,1.0,0.0); 33364 at map 1256 (0.0,1.0,0.0)

### Local implementation

cite-interdite v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Pandore [5046], 1 × Pandou [5043], 1 × Pandikaze [5041], 1 × Pandit [5042]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Compost del Gran Calabaciflor (native:193)

French alias: Compost du grand Potofeu. Type: DUNGEON_2_ROOMS. Native level: 126. Maps: [1394].

Species pool: Puerroculto [5468] level 130-134, Mazorcapo [5469] level 132-136, Cegalobolla [5470] level 128-132, Calabaciflor, Gran maestro culinario [5471] level 143-148, Zanahowia zombi [5474] level 134-138

### Guide composition

[compost-du-grand-potofeu](https://methodwakfu.com/pvm/donjons/compost-du-grand-potofeu/); extraction=unknown; version=None; client version match=unverified.

- Room 1 (unknown): Unknown composition
- Room 2 (unknown): Unknown composition

### Native entrance and interiors

Entry map 1384, object 34735, destination 4624, template 186. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 2, 'GenericActivableInteractiveElement': 1, 'Stele': 1}.

- Door: 35022 at map 1394 (-11.0,-34.0,23.0); 34733 at map 1394 (0.0,-22.0,24.0)
- Stele: 34856 at map 1394 (-20.0,-27.0,23.0)

### Local implementation

compost-du-grand-potofeu v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 1 × Puerroculto [5468], 1 × Mazorcapo [5469], 1 × Cegalobolla [5470], 1 × Calabaciflor, Gran maestro culinario [5471], 1 × Zanahowia zombi [5474], 1 × Puerroculto [5468], 1 × Mazorcapo [5469], 1 × Cegalobolla [5470]
- Configured room 2: 1 × Mazorcapo [5469], 1 × Cegalobolla [5470], 1 × Calabaciflor, Gran maestro culinario [5471], 1 × Zanahowia zombi [5474], 1 × Puerroculto [5468], 1 × Mazorcapo [5469], 1 × Cegalobolla [5470], 1 × Calabaciflor, Gran maestro culinario [5471]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Corazón del Reloj de Nox (native:203)

French alias: Cœur de l'horloge de Nox. Type: ULTIMATE_BOSS. Native level: 231. Maps: [1435].

Species pool: Nox [5664] level 245-245

### Guide composition

[boss-ultimes-coeur-de-lhorloge-de-nox](https://methodwakfu.com/pvm/boss-ultimes/coeur-de-lhorloge-de-nox/); extraction=unknown; version=1.92; client version match=unverified.


### Native entrance and interiors

Entry map 1430, object 35050, destination 4716, template 195. Criterion:

```text
(empty on this entry)
```

Object counts: {'GenericActivableInteractiveElement': 2, 'Stele': 1, 'Teleporter': 1}.

- Stele: 35254 at map 1435 (-2.0,-15.0,0.0)

### Local implementation

boss-ultimes-coeur-de-lhorloge-de-nox v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Nox [5664], 1 × Nox [5664], 1 × Nox [5664], 1 × Nox [5664], 1 × Nox [5664], 1 × Nox [5664], 1 × Nox [5664], 1 × Nox [5664]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Dimensión-Objeto de Sombría (native:135)

French alias: Dimension-Objet d'Ombrage. Type: ULTIMATE_BOSS. Native level: 200. Maps: [1229].

Species pool: Sombría [4770] level 200-200

### Guide composition

[boss-ultimes-dimension-objet-dombrage](https://methodwakfu.com/pvm/boss-ultimes/dimension-objet-dombrage/); extraction=complete; version=1.85; client version match=unverified.

- Room 1 (complete): 1 × Ombrage [ref 4770, boss]

### Native entrance and interiors

Entry map 1233, object 30692, destination 3674, template 138. Criterion:

```text
not GetBooleanSystemConfiguration("beta.mode")
and IsAfter(26,09,2018,16,00,00)
```

Object counts: {'Teleporter': 1}.


### Local implementation

boss-ultimes-dimension-objet-dombrage v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Ombrage [4770]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Hacienda de la Topera Oculta (native:124)

French alias: Domaine de la Trouffe Salée. Type: DUNGEON_3_ROOMS. Native level: 126. Maps: [1128].

Species pool: Perforatroz doméstico [4221] level 130-134, Perforatroz entrenado [4222] level 134-138, Bebé perforatroz [4223] level 128-132, Perfowarrior [4254] level 143-148

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1120, object 27783, destination 2617, template 127. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 4, 'Door': 2, 'AudioMarker': 2, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 27786 on map 1128: map 1128 (32,-39,-16), criterion=empty, item=0
- Internal transport object 27989 on map 1128: map 1128 (22,-18,-24), criterion=empty, item=0
- Door: 27771 at map 1128 (12.0,0.0,0.0); 27770 at map 1128 (31.0,-53.0,0.0)
- Stele: 34854 at map 1128 (25.0,-61.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Hacienda de la Balinería (native:145)

French alias: Domaine du Petit Groin. Type: DUNGEON_3_ROOMS. Native level: 66. Maps: [911].

Species pool: Jabatillo [4760] level 66-68, Jabalina [4761] level 70-74, Balí agresivo [4762] level 74-78, Balí Real [4763] level 83-88, Balí [4766] level 68-72

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1136, object 14578, destination 2076, template 148. Criterion:

```text
not IsNeoServer()
```

Object counts: {'Teleporter': 4, 'Door': 3, 'Collector': 1, 'LootChest': 1, 'BackgroundDisplay': 1, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 24175 on map 911: map 911 (-62,-96,0), criterion=not IsNeoServer(), item=0
- Internal transport object 24177 on map 911: map 911 (-17,18,-24), criterion=not IsNeoServer(), item=0
- Door: 24179 at map 911 (-12.0,27.0,-24.0); 24180 at map 911 (-8.0,35.0,-36.0); 24178 at map 911 (4.0,14.0,-12.0)
- LootChest: 26427 at map 911 (-64.0,-99.0,0.0)
- Collector: 24174 at map 911 (-21.0,19.0,-24.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Mazmorra Abráknida (native:148)

French alias: Donjon Abraknyde. Type: DUNGEON_3_ROOMS. Native level: 126. Maps: [202].

Species pool: Roble Blando [4874] level 143-148, Abráknido Ancestral [4886] level 134-138, Tronkónido oscuro [4887] level 130-134, Abráknido oscuro [4888] level 128-132

### Guide composition

[donjon-abraknyde](https://methodwakfu.com/pvm/donjon-abraknyde/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Tronknyde Sombre [ref 4887, monster], 2 × Abraknyde Ancestral [ref 4886, monster], 2 × Abraknyde Sombre [ref 4888, monster]
- Room 2 (complete): 3 × Abraknyde Ancestral [ref 4886, monster], 2 × Tronknyde Sombre [ref 4887, monster], 2 × Abraknyde Sombre [ref 4888, monster]
- Room 3 (complete): 3 × Tronknyde Sombre [ref 4887, monster], 3 × Abraknyde Ancestral [ref 4886, monster], 2 × Abraknyde Sombre [ref 4888, monster]
- Room 4 (complete): 1 × Chêne Mou [ref 4874, boss]

### Native entrance and interiors

Entry map 1136, object 16936, destination 964, template 151. Criterion:

```text
not IsNeoServer()
```

Object counts: {'Door': 18, 'GenericActivableInteractiveElement': 1, 'Teleporter': 2, 'Stele': 1}.

- Door: 31618 at map 202 (-14.0,-35.0,-28.0); 31628 at map 202 (-14.0,-43.0,-28.0); 31627 at map 202 (-14.0,-41.0,-28.0); 31626 at map 202 (-15.0,-41.0,-28.0); 31624 at map 202 (-15.0,-40.0,-28.0); 31623 at map 202 (-15.0,-39.0,-28.0); 31622 at map 202 (-14.0,-38.0,-28.0); 31621 at map 202 (-13.0,-39.0,-28.0); 31616 at map 202 (-12.0,-43.0,-28.0); 31615 at map 202 (-13.0,-38.0,-28.0); 31620 at map 202 (-14.0,-38.0,-29.0); 31629 at map 202 (-14.0,-46.0,-28.0); 31614 at map 202 (-13.0,-37.0,-28.0); 31617 at map 202 (-13.0,-43.0,-28.0); 31625 at map 202 (-14.0,-40.0,-28.0); 16849 at map 202 (16.0,-38.0,-14.0); 16847 at map 202 (19.0,-15.0,-14.0); 16848 at map 202 (24.0,-21.0,-14.0)
- Stele: 34855 at map 202 (5.0,-40.0,-28.0)

### Local implementation

donjon-abraknyde v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Tronknyde Sombre [4887], 2 × Abraknyde Ancestral [4886], 2 × Abraknyde Sombre [4888]
- Configured room 2: 3 × Abraknyde Ancestral [4886], 2 × Tronknyde Sombre [4887], 2 × Abraknyde Sombre [4888]
- Configured room 3: 3 × Tronknyde Sombre [4887], 3 × Abraknyde Ancestral [4886], 2 × Abraknyde Sombre [4888]
- Configured room 4: 1 × Abráknido oscuro [4888], 1 × Roble Blando [4874], 1 × Abráknido Ancestral [4886], 1 × Tronkónido oscuro [4887], 1 × Abráknido oscuro [4888], 1 × Roble Blando [4874], 1 × Abráknido Ancestral [4886], 1 × Tronkónido oscuro [4887]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Arakna (native:46)

French alias: Donjon Arakne. Type: DUNGEON_3_ROOMS. Native level: 66. Maps: [1268].

Species pool: Arakna peluda [5104] level 70-74, Arakna mayor [5105] level 74-78, Arakna menor [5106] level 72-72, Viuda Negra [5107] level 83-88

### Guide composition

[donjon-arakne](https://methodwakfu.com/pvm/donjon-arakne/); extraction=complete; version=None; client version match=unverified.

- Room 1 (complete): 2 × Arakne Poilue [ref 5104, monster], 2 × Arakne Mineure [ref 5106, monster], 2 × Arakne Majeure [ref 5105, monster]
- Room 2 (complete): 3 × Arakne Poilue [ref 5104, monster], 2 × Arakne Mineure [ref 5106, monster], 3 × Arakne Majeure [ref 5105, monster]
- Room 3 (complete): 2 × Arakne Poilue [ref 5104, monster], 2 × Arakne Mineure [ref 5106, monster], 3 × Arakne Majeure [ref 5105, monster], 1 × Veuve Noire [ref 5107, boss]

### Native entrance and interiors

Entry map 1264, object 32241, destination 4181, template 44. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 6, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 32263 on map 1268: map 1268 (175,-12,2), criterion=empty, item=0
- Internal transport object 32267 on map 1268: map 1268 (98,91,0), criterion=empty, item=0
- Internal transport object 32268 on map 1268: map 1268 (185,2,-3), criterion=empty, item=0
- Internal transport object 32266 on map 1268: map 1268 (-9,-16,5), criterion=empty, item=0

### Local implementation

donjon-arakne v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 2 × Arakna peluda [5104], 2 × Arakna mayor [5105], 2 × Arakna menor [5106], 1 × Viuda Negra [5107], 1 × Arakna peluda [5104]
- Configured room 2: 3 × Arakna mayor [5105], 2 × Arakna menor [5106], 3 × Viuda Negra [5107]
- Configured room 3: 2 × Arakna menor [5106], 2 × Viuda Negra [5107], 3 × Arakna peluda [5104], 1 × Veuve Noire [5107]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Trinchera de Huelguerreros (native:80)

French alias: Donjon Bwork. Type: DUNGEON_3_ROOMS. Native level: 51. Maps: [716].

Species pool: Minero bwork [2770] level 55-55, Bomber bwork [2771] level 57-57, Guerrero bwork [2772] level 59-59, Cybwork [2773] level 61-61, Throll [2774] level 70-70

### Guide composition

[donjons-donjon-bwork](https://methodwakfu.com/pvm/donjons/donjon-bwork/); extraction=complete; version=1.70; client version match=unverified.

- Room 1 (complete): 2 × Mineur Bwork [ref 2770, monster], 4 × Bomber Bwork [ref 2771, monster], 2 × Guerrier Bwork [ref 2772, monster]
- Room 2 (complete): 2 × Mineur Bwork [ref 2770, monster], 2 × Bomber Bwork [ref 2771, monster], 3 × Guerrier Bwork [ref 2772, monster], 1 × Cybwork [ref 2773, monster]
- Room 3 (complete): 1 × Throll [ref 2774, boss], 2 × Mineur Bwork [ref 2770, monster], 1 × Bomber Bwork [ref 2771, monster], 3 × Guerrier Bwork [ref 2772, monster], 1 × Cybwork [ref 2773, monster]

### Native entrance and interiors

Entry map 711, object 20422, destination 1410, template 81. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 3, 'Teleporter': 2, 'AudioMarker': 1}.

- Door: 20415 at map 716 (-10.0,32.0,0.0); 20413 at map 716 (14.0,6.0,0.0); 20414 at map 716 (5.0,29.0,0.0)

### Local implementation

donjons-donjon-bwork v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 2 × Minero bwork [2770], 4 × Bomber bwork [2771], 2 × Guerrero bwork [2772]
- Configured room 2: 2 × Bomber bwork [2771], 2 × Guerrero bwork [2772], 3 × Cybwork [2773], 1 × Cybwork [2773]
- Configured room 3: 1 × Throll [2774], 2 × Cybwork [2773], 1 × Throll [2774], 3 × Minero bwork [2770], 1 × Cybwork [2773]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Meseta Pikapik (native:83)

French alias: Donjon Cacterre. Type: DUNGEON_2_ROOMS. Native level: 111. Maps: [798].

Species pool: Escorpico [2967] level 115-115, Slashand [2968] level 117-117, Cactifloro [2969] level 119-119, Pampactus [2970] level 121-121, Cactoblongo [2971] level 123-123, Piktus [2972] level 135-135

### Guide composition

[donjon-cacterre](https://methodwakfu.com/pvm/donjon-cacterre/); extraction=partial; version=1.59; client version match=unverified.

- Room 1 (partial): 1 × Sorpique [ref None, monster], 1 × Tartanque [ref 2968, monster], 2 × Cactiflore [ref 2969, monster], 2 × Pampactus [ref 2970, monster], 2 × Cactoblong [ref 2971, monster]
- Room 2 (complete): 1 × Sorpique [ref None, monster], 1 × Tartanque [ref 2968, monster], 1 × Cactiflore [ref 2969, monster], 1 × Pampactus [ref 2970, monster], 1 × Cactoblong [ref 2971, monster], 1 × Piktus [ref 2972, monster]

### Native entrance and interiors

Entry map 792, object 21800, destination 1500, template 84. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 1, 'AudioMarker': 1, 'Door': 3}.

- Door: 21687 at map 798 (20.0,-31.0,-8.0); 21688 at map 798 (20.0,-32.0,-8.0); 21689 at map 798 (18.0,-42.0,-8.0)

### Local implementation

donjon-cacterre v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 1 × Escorpico [2967], 1 × Slashand [2968], 2 × Cactifloro [2969], 2 × Pampactus [2970], 2 × Cactoblongo [2971]
- Configured room 2: 1 × Slashand [2968], 1 × Cactifloro [2969], 1 × Pampactus [2970], 1 × Cactoblongo [2971], 1 × Piktus [2972], 1 × Piktus [2972], 1 × Slashand [2968], 1 × Cactifloro [2969]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Solgazanes (native:161)

French alias: Donjon Cagnardeurs. Type: DUNGEON_2_ROOMS. Native level: 201. Maps: [1281].

Species pool: Castorbital [5173] level 209-213, Tatorbellino [5174] level 205-209, Caparrabias [5175] level 203-207, Escorpisoteador [5176] level 218-223

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1276, object 32628, destination 4290, template 164. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 4, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 32555 on map 1281: map 1281 (101,-120,4), criterion=empty, item=0
- Internal transport object 32554 on map 1281: map 1281 (188,-170,0), criterion=empty, item=0
- Stele: 34882 at map 1281 (187.0,-173.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Mazmorra de los Escapatarazones (native:165)

French alias: Donjon Carapattes. Type: DUNGEON_2_ROOMS. Native level: 201. Maps: [1301].

Species pool: Dragolfo [5232] level 209-213, Camalehombre [5233] level 205-209, Torturbulento [5234] level 203-207, Tortumulto [5235] level 218-223

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1298, object 32767, destination 4425, template 168. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 2, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Door: 32794 at map 1301 (-35.0,23.0,-12.0); 32795 at map 1301 (-31.0,34.0,-12.0)
- Stele: 34886 at map 1301 (-33.0,45.0,-24.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Mazmorra del Clan de Bworkana (native:200)

French alias: Donjon Clan de Bworkana. Type: DUNGEON_2_ROOMS. Native level: 231. Maps: [1419].

Species pool: Mamá bwork [5641] level 239-243, Gran mamá bwork [5642] level 235-239, Vieja bwork [5643] level 233-237, Zulnara, jefa de guerra [5644] level 248-253

### Guide composition

[donjons-donjon-clan-de-bworkana](https://methodwakfu.com/pvm/donjons/donjon-clan-de-bworkana/); extraction=unknown; version=1.91; client version match=unverified.

- Room 1 (unknown): Unknown composition
- Room 2 (unknown): Unknown composition

### Native entrance and interiors

Entry map 1401, object 34979, destination 4686, template 192. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 3, 'Teleporter': 2}.

- Door: 35024 at map 1419 (-4.0,-23.0,0.0); 35025 at map 1419 (11.0,-12.0,15.0); 35021 at map 1419 (0.0,-25.0,0.0)

### Local implementation

donjons-donjon-clan-de-bworkana v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 1 × Mamá bwork [5641], 1 × Gran mamá bwork [5642], 1 × Vieja bwork [5643], 1 × Zulnara, jefa de guerra [5644], 1 × Mamá bwork [5641], 1 × Gran mamá bwork [5642], 1 × Vieja bwork [5643], 1 × Zulnara, jefa de guerra [5644]
- Configured room 2: 1 × Gran mamá bwork [5642], 1 × Vieja bwork [5643], 1 × Zulnara, jefa de guerra [5644], 1 × Mamá bwork [5641], 1 × Gran mamá bwork [5642], 1 × Vieja bwork [5643], 1 × Zulnara, jefa de guerra [5644], 1 × Mamá bwork [5641]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Crustariscos (native:162)

French alias: Donjon Crustargneux. Type: DUNGEON_2_ROOMS. Native level: 201. Maps: [1282].

Species pool: Cangwepillo [5179] level 203-207, Pincisión [5180] level 209-213, Pinsular [5181] level 205-209, Crustacerebro [5182] level 218-223

### Guide composition

[donjon-crustargneux](https://methodwakfu.com/pvm/donjons/donjon-crustargneux/); extraction=complete; version=1.72; client version match=unverified.

- Room 1 (complete): 2 × Cwabotteur [ref 5179, monster], 2 × Pinsulaire [ref 5181, monster], 3 × Pincision [ref 5180, monster]
- Room 2 (complete): 2 × Cwabotteur [ref 5179, monster], 3 × Pinsulaire [ref 5181, monster], 3 × Pincision [ref 5180, monster]
- Room 3 (complete): 1 × Crustacérébro [ref 5182, boss], 2 × Cwabotteur [ref 5179, monster], 2 × Pinsulaire [ref 5181, monster], 2 × Pincision [ref 5180, monster]

### Native entrance and interiors

Entry map 1276, object 32601, destination 4296, template 165. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 4, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 32560 on map 1282: map 1282 (179,-167,4), criterion=empty, item=0
- Internal transport object 32561 on map 1282: map 1282 (99,-99,0), criterion=empty, item=0
- Stele: 34881 at map 1282 (172.0,-174.0,4.0)

### Local implementation

donjon-crustargneux v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 2 × Cwabotteur [5179], 2 × Pinsulaire [5181], 3 × Pinsular [5181], 1 × Crustacerebro [5182]
- Configured room 2: 2 × Cwabotteur [5179], 3 × Pinsulaire [5181], 3 × Crustacerebro [5182]
- Configured room 3: 1 × Crustacérébro [5182], 2 × Cwabotteur [5179], 2 × Pinsulaire [5181], 2 × Pincisión [5180], 1 × Pinsular [5181]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Abrakna (native:125)

French alias: Donjon des Abraknes. Type: DUNGEON_3_ROOMS. Native level: 21. Maps: [1091].

Species pool: Abráknido [4076] level 29-33, Abrakllota [4077] level 23-27, Arakna tejedora [4078] level 25-29, Arakna [4079] level 19-23, Abraknela [4107] level 38-43

### Guide composition

[donjon-des-abraknes](https://methodwakfu.com/pvm/donjon-des-abraknes/); extraction=unknown; version=1.87; client version match=unverified.

- Room 1 (unknown): Unknown composition
- Room 2 (unknown): Unknown composition
- Room 3 (unknown): Unknown composition

### Native entrance and interiors

Entry map 527, object 27097, destination 2560, template 128. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 2, 'Teleporter': 2, 'GenericActivableInteractiveElement': 1}.

- Door: 27914 at map 1091 (3.0,-15.0,0.0); 27915 at map 1091 (27.0,-12.0,0.0)

### Local implementation

donjon-des-abraknes v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Abráknido [4076], 1 × Abrakllota [4077], 1 × Arakna tejedora [4078], 1 × Arakna [4079], 1 × Abraknela [4107], 1 × Abráknido [4076], 1 × Abrakllota [4077], 1 × Arakna tejedora [4078]
- Configured room 2: 1 × Abrakllota [4077], 1 × Arakna tejedora [4078], 1 × Arakna [4079], 1 × Abraknela [4107], 1 × Abráknido [4076], 1 × Abrakllota [4077], 1 × Arakna tejedora [4078], 1 × Arakna [4079]
- Configured room 3: 1 × Arakna tejedora [4078], 1 × Arakna [4079], 1 × Abraknela [4107], 1 × Abráknido [4076], 1 × Abrakllota [4077], 1 × Arakna tejedora [4078], 1 × Arakna [4079], 1 × Abraknela [4107]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Cocodrails Delnilo (native:110)

French alias: Donjon des Crocodailles. Type: DUNGEON_2_ROOMS. Native level: 171. Maps: [1054].

Species pool: Cazador Delnilo [3968] level 173-177, Destripador Delnilo [3969] level 179-183, Shamán Delnilo [3970] level 175-179, Rey Delnilo [3971] level 188-193

### Guide composition

[donjon-des-crocodailles](https://methodwakfu.com/pvm/donjon-des-crocodailles/); extraction=complete; version=1.66; client version match=unverified.

- Room 1 (complete): 2 × Chasseur Dunîl [ref 3968, monster], 2 × Shaman Dunîl [ref 3970, monster], 2 × Eventreur Dunîl [ref 3969, monster]
- Room 2 (complete): 2 × Chasseur Dunîl [ref 3968, monster], 2 × Shaman Dunîl [ref 3970, monster], 3 × Eventreur Dunîl [ref 3969, monster]
- Room 3 (complete): 2 × Chasseur Dunîl [ref 3968, monster], 3 × Shaman Dunîl [ref 3970, monster], 3 × Eventreur Dunîl [ref 3969, monster]
- Room 4 (complete): 1 × Roi Dunîl [ref 3971, boss], 3 × Chasseur Dunîl [ref 3968, monster], 2 × Shaman Dunîl [ref 3970, monster], 2 × Eventreur Dunîl [ref 3969, monster]

### Native entrance and interiors

Entry map 999, object 26364, destination 2428, template 113. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 6, 'Door': 2, 'Stele': 1, 'GenericActivableInteractiveElement': 3, 'StoppingPositionZoneTrigger': 1}.

- Internal transport object 26359 on map 1054: map 1054 (74,-82,0), criterion=empty, item=0
- Internal transport object 26357 on map 1054: map 1054 (0,-81,0), criterion=empty, item=0
- Internal transport object 26358 on map 1054: map 1054 (9,-30,-17), criterion=empty, item=0
- Internal transport object 26362 on map 1054: map 1054 (-1,-99,4), criterion=empty, item=0
- Door: 27722 at map 1054 (-32.0,-106.0,0.0); 26365 at map 1054 (8.0,-30.0,-17.0)
- Stele: 34870 at map 1054 (65.0,-92.0,0.0)

### Local implementation

donjon-des-crocodailles v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Chasseur Dunîl [3968], 2 × Shaman Dunîl [3970], 2 × Eventreur Dunîl [3969]
- Configured room 2: 2 × Chasseur Dunîl [3968], 2 × Shaman Dunîl [3970], 3 × Eventreur Dunîl [3969]
- Configured room 3: 2 × Chasseur Dunîl [3968], 3 × Shaman Dunîl [3970], 3 × Eventreur Dunîl [3969]
- Configured room 4: 1 × Roi Dunîl [3971], 3 × Chasseur Dunîl [3968], 2 × Shaman Dunîl [3970], 2 × Eventreur Dunîl [3969]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Kaníbola (native:106)

French alias: Donjon des Kannibouls. Type: DUNGEON_2_ROOMS. Native level: 171. Maps: [1007].

Species pool: Kaníbola lug [3855] level 179-183, Kaníbola zeprot [3856] level 175-179, Kaníbola vudú [3857] level 173-177, Kanibolístero [3864] level 188-193

### Guide composition

[kannibouls](https://methodwakfu.com/pvm/kannibouls/); extraction=complete; version=None; client version match=unverified.

- Room 1 (complete): 2 × Kanniboul Lymi [ref 3855, monster], 2 × Kanniboul Ette [ref 3856, monster], 2 × Kanniboul Voodoo [ref 3857, monster]
- Room 2 (complete): 2 × Kanniboul Lymi [ref 3855, monster], 2 × Kanniboul Ette [ref 3856, monster], 3 × Kanniboul Voodoo [ref 3857, monster]
- Room 3 (complete): 3 × Kanniboul Lymi [ref 3855, monster], 3 × Kanniboul Ette [ref 3856, monster], 2 × Kanniboul Voodoo [ref 3857, monster]
- Room 4 (complete): 1 × Kannistère [ref 3864, boss], 2 × Kanniboul Lymi [ref 3855, monster], 2 × Kanniboul Ette [ref 3856, monster], 3 × Kanniboul Voodoo [ref 3857, monster]

### Native entrance and interiors

Entry map 999, object 25568, destination 2269, template 109. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 3, 'Stele': 1}.

- Door: 25570 at map 1007 (-40.0,-1.0,0.0); 25571 at map 1007 (-41.0,-1.0,0.0); 25569 at map 1007 (-54.0,1.0,0.0)
- Stele: 34871 at map 1007 (-70.0,9.0,8.0)

### Local implementation

kannibouls v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Kanniboul Lymi [3855], 2 × Kanniboul Ette [3856], 2 × Kanniboul Voodoo [3857]
- Configured room 2: 2 × Kanniboul Lymi [3855], 2 × Kanniboul Ette [3856], 3 × Kanniboul Voodoo [3857]
- Configured room 3: 3 × Kanniboul Lymi [3855], 3 × Kanniboul Ette [3856], 2 × Kanniboul Voodoo [3857]
- Configured room 4: 1 × Kannistère [3864], 2 × Kanniboul Lymi [3855], 2 × Kanniboul Ette [3856], 3 × Kanniboul Voodoo [3857]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de las Kanívoras (native:109)

French alias: Donjon des Kannivores. Type: DUNGEON_2_ROOMS. Native level: 171. Maps: [1006].

Species pool: Feramona [3861] level 179-183, Dionatrapa [3862] level 173-177, Tropiliana [3863] level 175-179, Espinanta [3866] level 188-193

### Guide composition

[donjon-des-kannivores](https://methodwakfu.com/pvm/donjon-des-kannivores/); extraction=complete; version=1.70; client version match=unverified.

- Room 1 (complete): 2 × Phéromane [ref 3861, monster], 2 × Tropiliane [ref 3863, monster], 2 × Dionatrape [ref 3862, monster]
- Room 2 (complete): 3 × Phéromane [ref 3861, monster], 2 × Tropiliane [ref 3863, monster], 2 × Dionatrape [ref 3862, monster]
- Room 3 (complete): 3 × Phéromane [ref 3861, monster], 2 × Tropiliane [ref 3863, monster], 3 × Dionatrape [ref 3862, monster]
- Room 4 (complete): 1 × Grozépine [ref 3866, boss], 3 × Phéromane [ref 3861, monster], 2 × Tropiliane [ref 3863, monster], 3 × Dionatrape [ref 3862, monster]

### Native entrance and interiors

Entry map 1053, object 26470, destination 2427, template 112. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'Stele': 1, 'GenericActivableInteractiveElement': 3}.

- Door: 26373 at map 1006 (49.0,-2.0,-29.0); 26372 at map 1006 (36.0,-5.0,-29.0); 26371 at map 1006 (36.0,-6.0,-29.0)
- Stele: 34872 at map 1006 (63.0,1.0,-29.0)

### Local implementation

donjon-des-kannivores v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Feramona [3861], 2 × Dionatrapa [3862], 2 × Dionatrape [3862], 1 × Espinanta [3866], 1 × Feramona [3861]
- Configured room 2: 3 × Dionatrapa [3862], 2 × Tropiliana [3863], 2 × Dionatrape [3862], 1 × Feramona [3861]
- Configured room 3: 3 × Tropiliana [3863], 2 × Espinanta [3866], 3 × Dionatrape [3862]
- Configured room 4: 1 × Grozépine [3866], 3 × Feramona [3861], 2 × Dionatrapa [3862], 3 × Dionatrape [3862]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Trópikos (native:104)

French alias: Donjon des Tropikes. Type: DUNGEON_2_ROOMS. Native level: 171. Maps: [1000].

Species pool: Psikokópata [3858] level 173-177, Kokolériko [3859] level 179-183, Kokoloso [3860] level 175-179, Koko, el Kolgado [3865] level 188-193

### Guide composition

[donjon-des-tropikes](https://methodwakfu.com/pvm/donjon-des-tropikes/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Kokolosse [ref 3860, monster], 2 × Kokolérik [ref 3859, monster], 2 × Psykoko [ref 3858, monster]
- Room 2 (complete): 3 × Psykoko [ref 3858, monster], 2 × Kokolosse [ref 3860, monster], 2 × Kokolérik [ref 3859, monster]
- Room 3 (complete): 3 × Kokolosse [ref 3860, monster], 3 × Kokolérik [ref 3859, monster], 2 × Psykoko [ref 3858, monster]
- Room 4 (complete): 1 × Koko le Nutt [ref 3865, boss], 3 × Kokolérik [ref 3859, monster], 2 × Kokolosse [ref 3860, monster], 2 × Psykoko [ref 3858, monster]

### Native entrance and interiors

Entry map 999, object 25562, destination 2265, template 107. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 2, 'Teleporter': 4, 'GenericActivableInteractiveElement': 3, 'Stele': 1}.

- Internal transport object 25563 on map 1000: map 1000 (-31,-91,0), criterion=empty, item=0
- Internal transport object 25560 on map 1000: map 1000 (-14,4,-2), criterion=empty, item=0
- Door: 25558 at map 1000 (-9.0,-1.0,-2.0); 25559 at map 1000 (-13.0,5.0,-2.0)
- Stele: 34869 at map 1000 (-39.0,-99.0,2.0)

### Local implementation

donjon-des-tropikes v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Kokolosse [3860], 2 × Kokolérik [3859], 2 × Psykoko [3858]
- Configured room 2: 3 × Psykoko [3858], 2 × Kokolosse [3860], 2 × Kokolérik [3859]
- Configured room 3: 3 × Kokolosse [3860], 3 × Kokolérik [3859], 2 × Psykoko [3858]
- Configured room 4: 1 × Koko le Nutt [3865], 3 × Kokolérik [3859], 2 × Kokolosse [3860], 2 × Psykoko [3858]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Demorribles (native:178)

French alias: Donjon Démhorribles. Type: DUNGEON_2_ROOMS. Native level: 216. Maps: [1328].

Species pool: Saguijueveto [5286] level 224-228, Rapaz despedazador [5287] level 220-224, Condenador [5288] level 218-222, Crateros, verdugo del fin [5289] level 233-238, Anathar [5305] level 230-230

### Guide composition

[donjons-donjon-demhorribles](https://methodwakfu.com/pvm/donjons/donjon-demhorribles/); extraction=complete; version=1.74; client version match=unverified.

- Room 1 (complete): 2 × Sangsure [ref 5286, monster], 2 × Condamnateur [ref 5288, monster], 2 × Rapace dépeceur [ref 5287, monster]
- Room 2 (complete): 1 × Cratéros, Bourreau de la fin [ref 5289, boss], 1 × Sangsure [ref 5286, monster], 1 × Condamnateur [ref 5288, monster], 1 × Rapace dépeceur [ref 5287, monster]

### Native entrance and interiors

Entry map 1326, object 33146, destination 4463, template 173. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 1, 'Teleporter': 2, 'GenericActivableInteractiveElement': 2}.

- Door: 33144 at map 1328 (-26.0,0.0,0.0)

### Local implementation

donjons-donjon-demhorribles v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 2 × Sangsure [5286], 2 × Condamnateur [5288], 2 × Rapace dépeceur [5287]
- Configured room 2: 1 × Cratéros, Bourreau de la fin [5289], 1 × Sangsure [5286], 1 × Condamnateur [5288], 1 × Rapace dépeceur [5287]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra iBúho (native:96)

French alias: Donjon E-Bou. Type: DUNGEON_2_ROOMS. Native level: 156. Maps: [917].

Species pool: Mento [3392] level 158-162, Loradante [3393] level 160-164, Siclick [3394] level 164-168, Rapyodo, el Infrecuenciable [3399] level 173-178

### Guide composition

[donjon-e-bou](https://methodwakfu.com/pvm/donjon-e-bou/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Lairdavan [ref 3393, monster], 2 × Poz [ref 3392, monster], 2 × Syclick [ref 3394, monster]
- Room 2 (complete): 3 × Lairdavan [ref 3393, monster], 2 × Poz [ref 3392, monster], 2 × Syclick [ref 3394, monster]
- Room 3 (complete): 3 × Poz [ref 3392, monster], 3 × Syclick [ref 3394, monster], 2 × Lairdavan [ref 3393, monster]
- Room 4 (complete): 1 × Raipiode L’Infréquençable [ref 3399, boss], 2 × Lairdavan [ref 3393, monster], 2 × Poz [ref 3392, monster], 2 × Syclick [ref 3394, monster]

### Native entrance and interiors

Entry map 923, object 24794, destination 2100, template 98. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 15, 'GenericActivableInteractiveElement': 4, 'Stele': 1}.

- Door: 24837 at map 917 (-27.0,-42.0,0.0); 24836 at map 917 (-26.0,-42.0,0.0); 24835 at map 917 (-25.0,-42.0,0.0); 24838 at map 917 (-28.0,-42.0,0.0); 24839 at map 917 (-29.0,-44.0,0.0); 24842 at map 917 (-28.0,-44.0,0.0); 24841 at map 917 (-27.0,-44.0,0.0); 24840 at map 917 (-26.0,-44.0,0.0); 24846 at map 917 (-30.0,-48.0,0.0); 24843 at map 917 (-31.0,-48.0,0.0); 24844 at map 917 (-32.0,-48.0,0.0); 24845 at map 917 (-33.0,-48.0,0.0); 25009 at map 917 (-33.0,-79.0,0.0); 25010 at map 917 (-32.0,-79.0,0.0); 25011 at map 917 (-31.0,-79.0,0.0)
- Stele: 34866 at map 917 (-39.0,-70.0,0.0)

### Local implementation

donjon-e-bou v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Mento [3392], 2 × Loradante [3393], 2 × Siclick [3394], 1 × Rapyodo, el Infrecuenciable [3399], 1 × Mento [3392]
- Configured room 2: 3 × Loradante [3393], 2 × Siclick [3394], 2 × Rapyodo, el Infrecuenciable [3399], 1 × Mento [3392]
- Configured room 3: 3 × Siclick [3394], 3 × Rapyodo, el Infrecuenciable [3399], 2 × Mento [3392]
- Configured room 4: 1 × Rapyodo, el Infrecuenciable [3399], 2 × Mento [3392], 2 × Loradante [3393], 2 × Siclick [3394], 1 × Rapyodo, el Infrecuenciable [3399]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de Anutropía (native:87)

French alias: Donjon Enutrosor. Type: DUNGEON_2_ROOMS. Native level: 141. Maps: [854].

Species pool: Cofrosaurio [3090] level 143-147, Caballanza [3091] level 145-149, Anucofre [3092] level 147-151, Kamarácnido [3093] level 149-153, Andy Sonesto, el Llavero [3094] level 158-163

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 853, object 22735, destination 1785, template 88. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 10, 'GenericActivableInteractiveElement': 1, 'Stele': 1}.

- Door: 22564 at map 854 (-23.0,-32.0,12.0); 22565 at map 854 (-25.0,-32.0,12.0); 22566 at map 854 (-25.0,-31.0,12.0); 22567 at map 854 (-25.0,-30.0,12.0); 22570 at map 854 (-23.0,-30.0,12.0); 22568 at map 854 (-23.0,-31.0,12.0); 22569 at map 854 (-23.0,-32.0,12.0); 22573 at map 854 (-25.0,-35.0,12.0); 22571 at map 854 (-23.0,-35.0,12.0); 22572 at map 854 (-24.0,-35.0,12.0)
- Stele: 34862 at map 854 (-31.0,-56.0,12.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Mazmorra del Charcoso Real (native:142)

French alias: Donjon Flaqueux. Type: DUNGEON_2_ROOMS. Native level: 111. Maps: [460].

Species pool: Jefe charcoso [4717] level 119-123, Guerrero charcoso [4718] level 113-117, Mamá charcosa [4719] level 115-119, Charcoso Real [4720] level 128-133

### Guide composition

[donjon-flaqueux](https://methodwakfu.com/pvm/donjon-flaqueux/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 3 × Guerrier Flaqueux [ref 4718, monster], 3 × Mama Flaqueuse [ref 4719, monster], 2 × Chef Flaqueux [ref 4717, monster]
- Room 2 (complete): 3 × Guerrier Flaqueux [ref 4718, monster], 2 × Mama Flaqueuse [ref 4719, monster], 2 × Chef Flaqueux [ref 4717, monster], 1 × Flaque Royale [ref 4720, boss]

### Native entrance and interiors

Entry map 1135, object 18060, destination 1026, template 145. Criterion:

```text
(empty on this entry)
```

Object counts: {'AudioMarker': 3, 'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 1}.

- Door: 17730 at map 460 (-46.0,-8.0,0.0); 17728 at map 460 (-46.0,8.0,0.0); 17729 at map 460 (-45.0,8.0,0.0)

### Local implementation

donjon-flaqueux v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 3 × Guerrier Flaqueux [4718], 3 × Mama Flaqueuse [4719], 2 × Chef Flaqueux [4717]
- Configured room 2: 3 × Guerrier Flaqueux [4718], 2 × Mama Flaqueuse [4719], 2 × Chef Flaqueux [4717], 1 × Flaque Royale [4720]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Ferocirraptores (native:197)

French alias: Donjon Férociraptors. Type: DUNGEON_2_ROOMS. Native level: 231. Maps: [1416].

Species pool: Velocisesino [5623] level 233-237, Nabucodonosaurio [5624] level 235-239, Tragalodón [5625] level 239-243, Fulgurosaurio [5626] level 248-253

### Guide composition

[donjons-donjon-ferociraptors](https://methodwakfu.com/pvm/donjons/donjon-ferociraptors/); extraction=unknown; version=1.87; client version match=unverified.

- Room 1 (unknown): Unknown composition
- Room 2 (unknown): Unknown composition

### Native entrance and interiors

Entry map 1401, object 34978, destination 4682, template 189. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 3, 'GenericActivableInteractiveElement': 2, 'Door': 3}.

- Door: 35095 at map 1416 (-15.0,17.0,-80.0); 35093 at map 1416 (-15.0,18.0,-80.0); 35094 at map 1416 (-15.0,19.0,-80.0)

### Local implementation

donjons-donjon-ferociraptors v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 1 × Velocisesino [5623], 1 × Nabucodonosaurio [5624], 1 × Tragalodón [5625], 1 × Fulgurosaurio [5626], 1 × Velocisesino [5623], 1 × Nabucodonosaurio [5624], 1 × Tragalodón [5625], 1 × Fulgurosaurio [5626]
- Configured room 2: 1 × Nabucodonosaurio [5624], 1 × Tragalodón [5625], 1 × Fulgurosaurio [5626], 1 × Velocisesino [5623], 1 × Nabucodonosaurio [5624], 1 × Tragalodón [5625], 1 × Fulgurosaurio [5626], 1 × Velocisesino [5623]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Gelatinada (native:69)

French alias: Donjon Gelée. Type: DUNGEON_3_ROOMS. Native level: 96. Maps: [559].

Species pool: Gelatina de frambuesa [1339] level 100-104, Gelatina de menta [1340] level 100-104, Gelatina de fresa [1341] level 100-104, Emperador Gelax [1345] level 118-123, Gelatina de limón [1358] level 100-104

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 553, object 19630, destination 1235, template 70. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 3, 'Teleporter': 2, 'GenericActivableInteractiveElement': 5}.

- Door: 19161 at map 559 (-4.0,-16.0,8.0); 19162 at map 559 (0.0,-24.0,8.0); 19163 at map 559 (0.0,-39.0,16.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Mazmorra Gerbilinda (native:158)

French alias: Donjon Gerbouille. Type: DUNGEON_3_ROOMS. Native level: 171. Maps: [1270].

Species pool: Bebé gerbilinda [5128] level 173-177, Gerbilinda [5129] level 175-179, Abuelito gerbilinda [5130] level 179-183, Mamá Gerbilinda [5131] level 188-193, Conde Kontatrás [5155] level 200-200

### Guide composition

[donjon-gerbouille](https://methodwakfu.com/pvm/donjon-gerbouille/); extraction=complete; version=None; client version match=unverified.

- Room 1 (complete): 2 × Bébé Gerbouille [ref 5128, monster], 2 × Gerbouille [ref 5129, monster], 2 × Pépé Gerbouille [ref 5130, monster]
- Room 2 (complete): 3 × Bébé Gerbouille [ref 5128, monster], 2 × Gerbouille [ref 5129, monster], 2 × Pépé Gerbouille [ref 5130, monster]
- Room 3 (complete): 2 × Bébé Gerbouille [ref 5128, monster], 3 × Gerbouille [ref 5129, monster], 3 × Pépé Gerbouille [ref 5130, monster]
- Room 4 (complete): 1 × Maman Gerbouille [ref 5131, boss], 2 × Bébé Gerbouille [ref 5128, monster], 3 × Gerbouille [ref 5129, monster], 2 × Pépé Gerbouille [ref 5130, monster]

### Native entrance and interiors

Entry map 1264, object 32342, destination 4198, template 161. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 6, 'GenericActivableInteractiveElement': 2}.

- Internal transport object 32316 on map 1270: map 1270 (91,103,0), criterion=empty, item=0
- Internal transport object 32313 on map 1270: map 1270 (97,84,8), criterion=empty, item=0
- Internal transport object 32314 on map 1270: map 1270 (83,-85,0), criterion=empty, item=0
- Internal transport object 32315 on map 1270: map 1270 (210,6,15), criterion=empty, item=0

### Local implementation

donjon-gerbouille v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Bébé Gerbouille [5128], 2 × Gerbilinda [5129], 2 × Pépé Gerbouille [5130], 1 × Mamá Gerbilinda [5131], 1 × Conde Kontatrás [5155]
- Configured room 2: 3 × Bébé Gerbouille [5128], 2 × Abuelito gerbilinda [5130], 2 × Pépé Gerbouille [5130], 1 × Conde Kontatrás [5155]
- Configured room 3: 2 × Bébé Gerbouille [5128], 3 × Mamá Gerbilinda [5131], 3 × Pépé Gerbouille [5130]
- Configured room 4: 1 × Maman Gerbouille [5131], 2 × Bébé Gerbouille [5128], 3 × Bebé gerbilinda [5128], 2 × Pépé Gerbouille [5130]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Máquinas de Nox (native:201)

French alias: Donjon Machines de Nox. Type: DUNGEON_2_ROOMS. Native level: 231. Maps: [1418].

Species pool: Noxus IV [5647] level 239-242, Noxaraña [5648] level 233-237, Noxbriz [5649] level 235-239, Nox [5718] level 248-253

### Guide composition

[donjon-machines-de-nox](https://methodwakfu.com/pvm/donjons/donjon-machines-de-nox/); extraction=partial; version=None; client version match=unverified.

- Room 1 (partial): 3 × Noxelanste [ref 5649, monster]
- Room 2 (unknown): Unknown composition

### Native entrance and interiors

Entry map 1401, object 34980, destination 4688, template 193. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 1, 'Teleporter': 2}.

- Door: 35006 at map 1418 (-28.0,3.0,0.0)

### Local implementation

donjon-machines-de-nox v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 3 × Noxus IV [5647], 1 × Noxaraña [5648], 1 × Noxbriz [5649], 1 × Nox [5718], 1 × Noxus IV [5647], 1 × Noxaraña [5648]
- Configured room 2: 1 × Noxaraña [5648], 1 × Noxbriz [5649], 1 × Nox [5718], 1 × Noxus IV [5647], 1 × Noxaraña [5648], 1 × Noxbriz [5649], 1 × Nox [5718], 1 × Noxus IV [5647]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Güinos (native:167)

French alias: Donjon Mansots. Type: DUNGEON_2_ROOMS. Native level: 201. Maps: [1300].

Species pool: Desemplegüino [5244] level 209-213, Botelligüino [5245] level 205-209, Chocogüino [5246] level 203-207, Sumorsa [5247] level 218-223

### Guide composition

[donjons-donjon-mansots](https://methodwakfu.com/pvm/donjons/donjon-mansots/); extraction=partial; version=1.75; client version match=unverified.

- Room 1 (unknown): Unknown composition
- Room 2 (unknown): Unknown composition
- Room 3 (complete): 1 × Sumorse [ref 5247, boss], 2 × Manchômage [ref 5244, monster], 2 × Manchot Kola [ref 5246, monster], 2 × Manchopine [ref 5245, monster]

### Native entrance and interiors

Entry map 1297, object 32775, destination 4427, template 170. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 4, 'GenericActivableInteractiveElement': 1, 'Stele': 1}.

- Internal transport object 32785 on map 1300: map 1300 (136,-164,1), criterion=empty, item=0
- Internal transport object 32788 on map 1300: map 1300 (65,-93,0), criterion=empty, item=0
- Stele: 34885 at map 1300 (135.0,-159.0,0.0)

### Local implementation

donjons-donjon-mansots v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Desemplegüino [5244], 1 × Botelligüino [5245], 1 × Chocogüino [5246], 1 × Sumorsa [5247], 1 × Desemplegüino [5244], 1 × Botelligüino [5245], 1 × Chocogüino [5246], 1 × Sumorsa [5247]
- Configured room 2: 1 × Botelligüino [5245], 1 × Chocogüino [5246], 1 × Sumorsa [5247], 1 × Desemplegüino [5244], 1 × Botelligüino [5245], 1 × Chocogüino [5246], 1 × Sumorsa [5247], 1 × Desemplegüino [5244]
- Configured room 3: 1 × Sumorse [5247], 2 × Manchômage [5244], 2 × Desemplegüino [5244], 2 × Manchopine [5245], 1 × Chocogüino [5246]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Martilloseco (native:186)

French alias: Donjon Marteaux-Aigris. Type: DUNGEON_3_ROOMS. Native level: 51. Maps: [1371].

Species pool: Marthos [5385] level 55-59, Parraguás [5386] level 53-57, Escudacha [5387] level 59-63, Goel el Gólem [5388] level 68-73, Cire Momore [5417] level 68-73

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1364, object 33645, destination 4532, template 179. Criterion:

```text
not IsNeoServer()
```

Object counts: {'Door': 2, 'GenericActivableInteractiveElement': 1, 'Teleporter': 2}.

- Door: 33636 at map 1371 (0.0,-25.0,0.0); 33637 at map 1371 (12.0,-51.0,-24.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Mazmorra Kaskarlusca (native:34)

French alias: Donjon Mollusky. Type: DUNGEON_3_ROOMS. Native level: 51. Maps: [466].

Species pool: Dark Maulusco [4237] level 55-59, Kasrakol [4238] level 59-63, Kralamar [4239] level 53-57, Kralaboss [4240] level 68-73

### Guide composition

[donjons-donjon-mollusky](https://methodwakfu.com/pvm/donjons/donjon-mollusky/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Kaskargo [ref 4238, monster], 2 × Dark Moule [ref 4237, monster], 3 × Kralamour [ref 4239, monster]
- Room 2 (complete): 3 × Kaskargo [ref 4238, monster], 3 × Dark Moule [ref 4237, monster], 2 × Kralamour [ref 4239, monster]
- Room 3 (complete): 1 × Kralaboss [ref 4240, boss], 2 × Kaskargo [ref 4238, monster], 3 × Dark Moule [ref 4237, monster], 2 × Kralamour [ref 4239, monster]

### Native entrance and interiors

Entry map 1118, object 27739, destination 974, template 56. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'AudioMarker': 5, 'Door': 5, 'GenericActivableInteractiveElement': 1}.

- Door: 17284 at map 466 (-36.0,-11.0,1.0); 17286 at map 466 (-22.0,12.0,0.0); 17287 at map 466 (-19.0,29.0,0.0); 17288 at map 466 (-19.0,28.0,0.0); 17283 at map 466 (-38.0,-11.0,8.0)

### Local implementation

donjons-donjon-mollusky v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 2 × Kaskargo [4238], 2 × Kasrakol [4238], 3 × Kralamar [4239], 1 × Kralaboss [4240]
- Configured room 2: 3 × Kaskargo [4238], 3 × Kralamar [4239], 2 × Kralaboss [4240]
- Configured room 3: 1 × Kralaboss [4240], 2 × Kaskargo [4238], 3 × Dark Maulusco [4237], 2 × Kasrakol [4238]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Fallecinerados (native:185)

French alias: Donjon Morts-brûlés. Type: DUNGEON_3_ROOMS. Native level: 36. Maps: [1372].

Species pool: Bwork incinerado [5379] level 40-44, Taponcendio [5380] level 40-44, Difunerario [5381] level 44-48, Hark Saniss, Último gigante [5382] level 53-58, Cire Momore [5416] level 53-58

### Guide composition

[donjon-morts-brules](https://methodwakfu.com/pvm/donjon-morts-brules/); extraction=partial; version=1.87; client version match=unverified.

- Room 1 (partial): None × Nimbrasier [ref 5380, monster]
- Room 2 (partial): None × Défunéraire [ref 5381, monster]
- Room 3 (partial): None × Hark Saniss, Dernier géant [ref 5382, boss]

### Native entrance and interiors

Entry map 1359, object 33644, destination 4531, template 178. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 2, 'Teleporter': 2, 'GenericActivableInteractiveElement': 1}.

- Door: 33638 at map 1372 (0.0,-29.0,0.0); 33639 at map 1372 (28.0,-54.0,-16.0)

### Local implementation

donjon-morts-brules v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Nimbrasier [5380], 1 × Taponcendio [5380], 1 × Difunerario [5381], 1 × Hark Saniss, Último gigante [5382], 1 × Cire Momore [5416], 1 × Bwork incinerado [5379], 1 × Taponcendio [5380], 1 × Difunerario [5381]
- Configured room 2: 1 × Défunéraire [5381], 1 × Difunerario [5381], 1 × Hark Saniss, Último gigante [5382], 1 × Cire Momore [5416], 1 × Bwork incinerado [5379], 1 × Taponcendio [5380], 1 × Difunerario [5381], 1 × Hark Saniss, Último gigante [5382]
- Configured room 3: 1 × Hark Saniss, Dernier géant [5382], 1 × Hark Saniss, Último gigante [5382], 1 × Cire Momore [5416], 1 × Bwork incinerado [5379], 1 × Taponcendio [5380], 1 × Difunerario [5381], 1 × Hark Saniss, Último gigante [5382], 1 × Cire Momore [5416]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Milubo (native:47)

French alias: Donjon Mulou. Type: DUNGEON_4_ROOMS. Native level: 66. Maps: [1266].

Species pool: Milubo [5111] level 70-74, Miluba [5112] level 74-78, Minilubo [5113] level 68-72, Luna Gigante [5114] level 83-88

### Guide composition

[autel-de-la-lune](https://methodwakfu.com/pvm/autel-de-la-lune/); extraction=complete; version=1.70; client version match=unverified.

- Room 1 (complete): 2 × Milimulou [ref 5113, monster], 2 × Mulou [ref 5111, monster], 2 × Muloune [ref 5112, monster]
- Room 2 (complete): 2 × Milimulou [ref 5113, monster], 3 × Mulou [ref 5111, monster], 2 × Muloune [ref 5112, monster]
- Room 3 (complete): 3 × Milimulou [ref 5113, monster], 3 × Mulou [ref 5111, monster], 2 × Muloune [ref 5112, monster]
- Room 4 (complete): 3 × Milimulou [ref 5113, monster], 2 × Mulou [ref 5111, monster], 2 × Muloune [ref 5112, monster], 1 × Lune géante [ref 5114, boss]

### Native entrance and interiors

Entry map 1264, object 32240, destination 4159, template 45. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 10, 'GenericActivableInteractiveElement': 1, 'Door': 2}.

- Internal transport object 32214 on map 1266: map 1266 (18,-11,-8), criterion=empty, item=0
- Internal transport object 32206 on map 1266: map 1266 (-15,-81,0), criterion=empty, item=0
- Internal transport object 32215 on map 1266: map 1266 (29,-15,-8), criterion=empty, item=0
- Internal transport object 32207 on map 1266: map 1266 (2,-87,0), criterion=empty, item=0
- Internal transport object 32209 on map 1266: map 1266 (46,111,0), criterion=empty, item=0
- Internal transport object 32213 on map 1266: map 1266 (35,-15,-8), criterion=empty, item=0
- Internal transport object 32208 on map 1266: map 1266 (35,-14,-27), criterion=empty, item=0
- Internal transport object 32210 on map 1266: map 1266 (25,2,-27), criterion=empty, item=0
- Door: 32205 at map 1266 (13.0,1.0,0.0); 32212 at map 1266 (36.0,117.0,0.0)

### Local implementation

autel-de-la-lune v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Milubo [5111], 2 × Miluba [5112], 2 × Muloune [5112], 1 × Luna Gigante [5114], 1 × Milubo [5111]
- Configured room 2: 2 × Miluba [5112], 3 × Minilubo [5113], 2 × Muloune [5112], 1 × Milubo [5111]
- Configured room 3: 3 × Minilubo [5113], 3 × Luna Gigante [5114], 2 × Muloune [5112]
- Configured room 4: 3 × Luna Gigante [5114], 2 × Milubo [5111], 2 × Muloune [5112], 1 × Minilubo [5113]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Negraspora (native:84)

French alias: Donjon Noirespore. Type: DUNGEON_2_ROOMS. Native level: 126. Maps: [806].

Species pool: Haploide esporulador [2973] level 131-131, Amenita bicéfala [2974] level 128-128, Matacando saltarín [2975] level 125-125, Ates, el Challampano [2977] level 145-145, Caniofaro aplastante [2988] level 134-134

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 796, object 21779, destination 1502, template 85. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Door: 21697 at map 806 (-57.0,-5.0,0.0); 21698 at map 806 (-56.0,-5.0,0.0); 21699 at map 806 (-63.0,-1.0,0.0)
- Stele: 34853 at map 806 (-70.0,-2.0,8.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Mazmorra de los Fitoformes (native:176)

French alias: Donjon Phytomorphes. Type: DUNGEON_2_ROOMS. Native level: 216. Maps: [1308].

Species pool: Meristodio [5274] level 224-228, Champidiablo [5275] level 220-224, Virescente [5276] level 218-222, Vaal'Enthia, reina demonio [5277] level 233-238, Anathar [5305] level 230-230

### Guide composition

[donjon-phytomorphes](https://methodwakfu.com/pvm/donjons/donjon-phytomorphes/); extraction=complete; version=1.74; client version match=unverified.

- Room 1 (complete): 3 × Virescent [ref 5276, monster], 2 × Champidiable [ref 5275, monster], 3 × Méristhaine [ref 5274, monster]
- Room 2 (complete): 1 × Vaal’Enthia, Reine-démone [ref 5277, boss], 3 × Virescent [ref 5276, monster], 2 × Champidiable [ref 5275, monster], 2 × Méristhaine [ref 5274, monster]

### Native entrance and interiors

Entry map 1305, object 33138, destination 4459, template 171. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 1, 'Teleporter': 2, 'GenericActivableInteractiveElement': 2}.

- Door: 33150 at map 1308 (-11.0,-45.0,12.0)

### Local implementation

donjon-phytomorphes v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 3 × Virescent [5276], 2 × Champidiable [5275], 3 × Méristhaine [5274]
- Configured room 2: 1 × Champidiablo [5275], 3 × Virescent [5276], 2 × Champidiable [5275], 2 × Méristhaine [5274]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Plantiguardias (native:166)

French alias: Donjon Plantigardes. Type: DUNGEON_2_ROOMS. Native level: 201. Maps: [1296].

Species pool: Osuezño [5238] level 209-213, Abosotargado [5239] level 205-209, Kungfoso [5240] level 203-207, Temerarioso [5241] level 218-223

### Guide composition

[donjon-plantigardes](https://methodwakfu.com/pvm/donjon-plantigardes/); extraction=partial; version=1.70; client version match=unverified.

- Room 1 (unknown): Unknown composition
- Room 2 (unknown): Unknown composition
- Room 3 (complete): 1 × Casse-Cours [ref 5241, boss], 3 × Oursonge [ref 5238, monster], 2 × Boursouflé [ref 5239, monster], 2 × Koung Fours [ref 5240, monster]

### Native entrance and interiors

Entry map 1295, object 32869, destination 4435, template 169. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 2, 'Stele': 1, 'GenericActivableInteractiveElement': 1, 'PositionTrigger': 1}.

- Door: 32777 at map 1296 (-4.0,-41.0,8.0); 32778 at map 1296 (-17.0,-47.0,8.0)
- Stele: 34884 at map 1296 (-18.0,-58.0,16.0)
- PositionTrigger: 32865 at map 1296 (-21.0,-62.0,16.0)

### Local implementation

donjon-plantigardes v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Osuezño [5238], 1 × Abosotargado [5239], 1 × Kungfoso [5240], 1 × Temerarioso [5241], 1 × Osuezño [5238], 1 × Abosotargado [5239], 1 × Kungfoso [5240], 1 × Temerarioso [5241]
- Configured room 2: 1 × Abosotargado [5239], 1 × Kungfoso [5240], 1 × Temerarioso [5241], 1 × Osuezño [5238], 1 × Abosotargado [5239], 1 × Kungfoso [5240], 1 × Temerarioso [5241], 1 × Osuezño [5238]
- Configured room 3: 1 × Casse-Cours [5241], 3 × Oursonge [5238], 2 × Osuezño [5238], 2 × Abosotargado [5239]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Pezgajosos Abisales (native:187)

French alias: Donjon Poisseux abyssaux. Type: DUNGEON_3_ROOMS. Native level: 216. Maps: [1370].

Species pool: Pequeño pezgajoso [5391] level 218-222, Golpeador abisal [5392] level 224-228, Asesirena [5393] level 220-224, Raeliss [5394] level 233-238, Cire Momore [5418] level 228-233

### Guide composition

[donjons-donjon-poisseux-abyssaux](https://methodwakfu.com/pvm/donjons/donjon-poisseux-abyssaux/); extraction=partial; version=1.87; client version match=unverified.

- Room 1 (complete): 2 × Assassirène [ref 5393, monster], 3 × Petit-poisseux [ref 5391, monster], 2 × Cogneur abyssal [ref 5392, monster]
- Room 2 (complete): 2 × Assassirène [ref 5393, monster], 3 × Petit-poisseux [ref 5391, monster], 3 × Cogneur abyssal [ref 5392, monster]
- Room 3 (partial): None × Raeliss [ref 5394, boss], 2 × Assassirène [ref 5393, monster], 3 × Petit-poisseux [ref 5391, monster], 2 × Cogneur abyssal [ref 5392, monster]

### Native entrance and interiors

Entry map 1368, object 33622, destination 4500, template 180. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 26, 'Teleporter': 2, 'GenericActivableInteractiveElement': 2}.

- Door: 33565 at map 1370 (-29.0,0.0,0.0); 33576 at map 1370 (-55.0,-9.0,12.0); 33600 at map 1370 (-72.0,-2.0,-1.0); 33601 at map 1370 (-71.0,-2.0,-1.0); 33602 at map 1370 (-71.0,-1.0,-1.0); 33603 at map 1370 (-71.0,0.0,-1.0); 33604 at map 1370 (-72.0,0.0,-1.0); 33587 at map 1370 (-85.0,-1.0,-1.0); 33588 at map 1370 (-85.0,-2.0,-1.0); 33589 at map 1370 (-86.0,-2.0,-1.0); 33590 at map 1370 (-87.0,-2.0,-1.0); 33595 at map 1370 (-87.0,-1.0,-1.0); 33598 at map 1370 (-73.0,-1.0,-1.0); 33599 at map 1370 (-73.0,-2.0,-1.0); 33577 at map 1370 (-85.0,8.0,-1.0); 33578 at map 1370 (-86.0,8.0,-1.0); 33579 at map 1370 (-87.0,8.0,-1.0); 33580 at map 1370 (-87.0,7.0,-1.0); 33581 at map 1370 (-87.0,6.0,-1.0); 33582 at map 1370 (-86.0,6.0,-1.0); 33583 at map 1370 (-85.0,6.0,-1.0); 33584 at map 1370 (-85.0,7.0,-1.0); 33586 at map 1370 (-85.0,0.0,-1.0); 33593 at map 1370 (-87.0,0.0,-1.0); 33594 at map 1370 (-86.0,0.0,-1.0); 33597 at map 1370 (-73.0,0.0,-1.0)

### Local implementation

donjons-donjon-poisseux-abyssaux v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 2 × Assassirène [5393], 3 × Petit-poisseux [5391], 2 × Cogneur abyssal [5392]
- Configured room 2: 2 × Assassirène [5393], 3 × Petit-poisseux [5391], 3 × Cogneur abyssal [5392]
- Configured room 3: 1 × Raeliss [5394], 2 × Assassirène [5393], 3 × Petit-poisseux [5391], 2 × Cogneur abyssal [5392]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Primacizos (native:198)

French alias: Donjon Primassifs. Type: DUNGEON_2_ROOMS. Native level: 231. Maps: [1415].

Species pool: Teralónix [5629] level 235-239, Terronita [5630] level 233-237, Rocaceronte [5631] level 239-242, Imagori [5632] level 248-253

### Guide composition

[donjons-donjon-primassifs](https://methodwakfu.com/pvm/donjons/donjon-primassifs/); extraction=unknown; version=1.87; client version match=unverified.


### Native entrance and interiors

Entry map 1401, object 34977, destination 4684, template 190. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 1, 'Teleporter': 2}.

- Door: 34971 at map 1415 (-2.0,-26.0,0.0)

### Local implementation

donjons-donjon-primassifs v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 1 × Teralónix [5629], 1 × Terronita [5630], 1 × Rocaceronte [5631], 1 × Imagori [5632], 1 × Teralónix [5629], 1 × Terronita [5630], 1 × Rocaceronte [5631], 1 × Imagori [5632]
- Configured room 2: 1 × Terronita [5630], 1 × Rocaceronte [5631], 1 × Imagori [5632], 1 × Teralónix [5629], 1 × Terronita [5630], 1 × Rocaceronte [5631], 1 × Imagori [5632], 1 × Teralónix [5629]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Devastadores (native:180)

French alias: Donjon Ravageurs. Type: DUNGEON_2_ROOMS. Native level: 216. Maps: [1341].

Species pool: Zamparrón [5298] level 224-228, Druidra [5299] level 220-224, Maestro de las tinieblas [5300] level 218-222, K'abah'al, guardián del camino de los muertos [5301] level 233-238, Anathar [5305] level 230-230

### Guide composition

[donjons-donjon-ravageurs](https://methodwakfu.com/pvm/donjons/donjon-ravageurs/); extraction=partial; version=1.74; client version match=unverified.

- Room 1 (partial): 3 × Ravageur [ref None, monster], 3 × Ravageur [ref None, monster], 2 × Ravageur [ref None, monster]
- Room 2 (complete): 1 × K’abah’al, Gardien de la route des morts [ref 5301, boss], 2 × Druidre [ref 5299, monster], 2 × Maître des ténèbres [ref 5300, monster], 2 × Glouto [ref 5298, monster]

### Native entrance and interiors

Entry map 1338, object 33155, destination 4467, template 175. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 1, 'GenericActivableInteractiveElement': 2, 'Teleporter': 2}.

- Door: 33156 at map 1341 (-27.0,0.0,0.0)

### Local implementation

donjons-donjon-ravageurs v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 3 × Zamparrón [5298], 3 × Druidra [5299], 2 × Maestro de las tinieblas [5300]
- Configured room 2: 1 × Druidra [5299], 2 × Druidre [5299], 2 × Maître des ténèbres [5300], 2 × Glouto [5298], 1 × Zamparrón [5298]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Riktus de Élite (native:139)

French alias: Donjon Riktus Elite. Type: DUNGEON_4_ROOMS. Native level: 156. Maps: [301].

Species pool: Elitiro [4534] level 157-165, Elitespada [4535] level 157-165, Elitandarte [4536] level 157-165, Elitechizo [4537] level 157-165, Riktus Enmascarado [4538] level 173-178

### Guide composition

[donjons-donjon-riktus-elite](https://methodwakfu.com/pvm/donjons/donjon-riktus-elite/); extraction=complete; version=1.72; client version match=unverified.

- Room 1 (complete): 2 × Elitendard [ref 4536, monster], 2 × Magilite [ref 4537, monster], 1 × Elitir [ref 4534, monster], 1 × Epélite [ref 4535, monster]
- Room 2 (complete): 2 × Elitendard [ref 4536, monster], 2 × Magilite [ref 4537, monster], 2 × Elitir [ref 4534, monster], 1 × Epélite [ref 4535, monster]
- Room 3 (complete): 2 × Elitendard [ref 4536, monster], 2 × Magilite [ref 4537, monster], 2 × Elitir [ref 4534, monster], 2 × Epélite [ref 4535, monster]
- Room 4 (complete): 1 × Le Riktus Masqué [ref 4538, boss], 2 × Elitendard [ref 4536, monster], 2 × Magilite [ref 4537, monster], 1 × Elitir [ref 4534, monster], 2 × Epélite [ref 4535, monster]

### Native entrance and interiors

Entry map 1207, object 14568, destination 745, template 142. Criterion:

```text
(empty on this entry)
```

Object counts: {'CraftTable': 1, 'Door': 6, 'Teleporter': 2, 'PositionTrigger': 1, 'GenericActivableInteractiveElement': 2, 'LootChest': 5}.

- Door: 13937 at map 301 (-8.0,-36.0,0.0); 13942 at map 301 (-8.0,-59.0,0.0); 13939 at map 301 (-23.0,-43.0,0.0); 13938 at map 301 (13.0,-36.0,0.0); 13941 at map 301 (9.0,-59.0,0.0); 13940 at map 301 (19.0,-43.0,0.0)
- LootChest: 13559 at map 301 (-1.0,-87.0,0.0); 13556 at map 301 (-27.0,-11.0,0.0); 13560 at map 301 (-27.0,-80.0,0.0); 13557 at map 301 (15.0,-17.0,0.0); 13558 at map 301 (21.0,-87.0,0.0)
- CraftTable: 31797 at map 301 (-5.0,-15.0,0.0)
- PositionTrigger: 31790 at map 301 (-2.0,-65.0,0.0)

### Local implementation

donjons-donjon-riktus-elite v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Elitendard [4536], 2 × Magilite [4537], 1 × Elitir [4534], 1 × Epélite [4535]
- Configured room 2: 2 × Elitendard [4536], 2 × Magilite [4537], 2 × Elitir [4534], 1 × Epélite [4535]
- Configured room 3: 2 × Elitendard [4536], 2 × Magilite [4537], 2 × Elitir [4534], 2 × Epélite [4535]
- Configured room 4: 1 × Le Riktus Masqué [4538], 2 × Elitendard [4536], 2 × Magilite [4537], 1 × Elitir [4534], 2 × Epélite [4535]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Sabanastrales (native:199)

French alias: Donjon Savanastraux. Type: DUNGEON_2_ROOMS. Native level: 231. Maps: [1422].

Species pool: Machumorado [5635] level 239-243, Astrompa [5636] level 235-239, Quimera vigilante [5637] level 233-237, Timó el Poseído [5638] level 248-253

### Guide composition

[donjon-savanastraux](https://methodwakfu.com/pvm/donjons/donjon-savanastraux/); extraction=unknown; version=None; client version match=unverified.

- Room 1 (unknown): Unknown composition
- Room 2 (unknown): Unknown composition

### Native entrance and interiors

Entry map 1401, object 34976, destination 4689, template 191. Criterion:

```text
not (IsAchievementRunning(5335) and IsAchievementObjectiveComplete(11278) and not IsAchievementObjectiveComplete(11279))
```

Object counts: {'Door': 1, 'Teleporter': 2}.

- Door: 35036 at map 1422 (-21.0,2.0,0.0)

### Local implementation

donjon-savanastraux v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 1 × Machumorado [5635], 1 × Astrompa [5636], 1 × Quimera vigilante [5637], 1 × Timó el Poseído [5638], 1 × Machumorado [5635], 1 × Astrompa [5636], 1 × Quimera vigilante [5637], 1 × Timó el Poseído [5638]
- Configured room 2: 1 × Astrompa [5636], 1 × Quimera vigilante [5637], 1 × Timó el Poseído [5638], 1 × Machumorado [5635], 1 × Astrompa [5636], 1 × Quimera vigilante [5637], 1 × Timó el Poseído [5638], 1 × Machumorado [5635]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Sramvil (native:86)

French alias: Donjon Srambad. Type: DUNGEON_2_ROOMS. Native level: 141. Maps: [851].

Species pool: Bulldaga enano [3076] level 143-147, Adiestrador hojalarga [3077] level 145-149, Apotecario macabrasivo [3078] level 147-151, Sramva [3079] level 149-153, Venonusto, el Devorasombras [3080] level 158-163

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 843, object 24490, destination 1703, template 87. Criterion:

```text
(empty on this entry)
```

Object counts: {'Stele': 1, 'Teleporter': 2, 'GenericActivableInteractiveElement': 1, 'Door': 3}.

- Door: 22352 at map 851 (-27.0,-34.0,0.0); 22353 at map 851 (-27.0,-35.0,0.0); 22354 at map 851 (-22.0,-35.0,0.0)
- Stele: 34861 at map 851 (-13.0,-33.0,-16.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Mazmorra Steamers (native:188)

French alias: Donjon Steamers. Type: DUNGEON_4_ROOMS. Native level: 216. Maps: [1373].

Species pool: Mekano [5397] level 218-222, Artillero de élite [5398] level 224-228, Unidad stasificadora [5399] level 220-224, Sir Kurn Flex [5400] level 233-238, Cire Momore [5418] level 228-233

### Guide composition

[donjons-donjon-steamers](https://methodwakfu.com/pvm/donjons/donjon-steamers/); extraction=partial; version=1.87; client version match=unverified.

- Room 1 (unknown): Unknown composition
- Room 2 (unknown): Unknown composition
- Room 3 (unknown): Unknown composition
- Room 4 (unknown): Unknown composition

### Native entrance and interiors

Entry map 1365, object 33633, destination 4525, template 181. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 10, 'GenericActivableInteractiveElement': 5, 'Door': 30}.

- Internal transport object 33627 on map 1373: map 1373 (8,-5,4), criterion=empty, item=0
- Internal transport object 33626 on map 1373: map 1373 (2,-5,4), criterion=empty, item=0
- Internal transport object 33623 on map 1373: map 1373 (-86,-88,0), criterion=empty, item=0
- Internal transport object 33625 on map 1373: map 1373 (72,-87,0), criterion=empty, item=0
- Internal transport object 33624 on map 1373: map 1373 (-5,-89,0), criterion=empty, item=0
- Internal transport object 33634 on map 1373: map 1373 (154,43,0), criterion=empty, item=0
- Internal transport object 33628 on map 1373: map 1373 (14,-5,4), criterion=empty, item=0
- Internal transport object 33635 on map 1373: map 1373 (8,6,0), criterion=empty, item=0
- Door: 33706 at map 1373 (-102.0,-108.0,-1.0); 33709 at map 1373 (-101.0,-108.0,-1.0); 33712 at map 1373 (-100.0,-108.0,-1.0); 33697 at map 1373 (-111.0,-97.0,-1.0); 33700 at map 1373 (-111.0,-98.0,-1.0); 33703 at map 1373 (-111.0,-99.0,-1.0); 33823 at map 1373 (121.0,45.0,-1.0); 33824 at map 1373 (121.0,44.0,-1.0); 33825 at map 1373 (121.0,43.0,-1.0); 33826 at map 1373 (118.0,43.0,-1.0); 33827 at map 1373 (118.0,44.0,-1.0); 33828 at map 1373 (118.0,45.0,-1.0); 33829 at map 1373 (123.0,41.0,-1.0); 33830 at map 1373 (124.0,41.0,-1.0); 33831 at map 1373 (125.0,41.0,-1.0); 33832 at map 1373 (123.0,38.0,-1.0); 33833 at map 1373 (124.0,38.0,-1.0); 33834 at map 1373 (125.0,38.0,-1.0); 33817 at map 1373 (121.0,55.0,-1.0); 33818 at map 1373 (121.0,56.0,-1.0); 33819 at map 1373 (121.0,57.0,-1.0); 33820 at map 1373 (118.0,57.0,-1.0); 33821 at map 1373 (118.0,56.0,-1.0); 33822 at map 1373 (118.0,55.0,-1.0); 33837 at map 1373 (137.0,38.0,-1.0); 33838 at map 1373 (137.0,41.0,-1.0); 33835 at map 1373 (135.0,38.0,-1.0); 33836 at map 1373 (136.0,38.0,-1.0); 33839 at map 1373 (136.0,41.0,-1.0); 33840 at map 1373 (135.0,41.0,-1.0)

### Local implementation

donjons-donjon-steamers v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 1 × Mekano [5397], 1 × Artillero de élite [5398], 1 × Unidad stasificadora [5399], 1 × Sir Kurn Flex [5400], 1 × Cire Momore [5418], 1 × Mekano [5397], 1 × Artillero de élite [5398], 1 × Unidad stasificadora [5399]
- Configured room 2: 1 × Artillero de élite [5398], 1 × Unidad stasificadora [5399], 1 × Sir Kurn Flex [5400], 1 × Cire Momore [5418], 1 × Mekano [5397], 1 × Artillero de élite [5398], 1 × Unidad stasificadora [5399], 1 × Sir Kurn Flex [5400]
- Configured room 3: 1 × Unidad stasificadora [5399], 1 × Sir Kurn Flex [5400], 1 × Cire Momore [5418], 1 × Mekano [5397], 1 × Artillero de élite [5398], 1 × Unidad stasificadora [5399], 1 × Sir Kurn Flex [5400], 1 × Cire Momore [5418]
- Configured room 4: 1 × Sir Kurn Flex [5400], 1 × Cire Momore [5418], 1 × Mekano [5397], 1 × Artillero de élite [5398], 1 × Unidad stasificadora [5399], 1 × Sir Kurn Flex [5400], 1 × Cire Momore [5418], 1 × Mekano [5397]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Nievajas (native:163)

French alias: Donjon Toundrasoirs. Type: DUNGEON_2_ROOMS. Native level: 201. Maps: [1283].

Species pool: Tigris [5185] level 209-213, Lobín [5186] level 205-209, Zorrofrénico [5187] level 203-207, Bufaluciente [5188] level 218-223

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1276, object 32606, destination 4302, template 166. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 4, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 32577 on map 1283: map 1283 (170,-170,16), criterion=empty, item=0
- Internal transport object 32575 on map 1283: map 1283 (78,-98,0), criterion=empty, item=0
- Stele: 34880 at map 1283 (173.0,-177.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Mazmorra Vandalienados (native:160)

French alias: Donjon Vandaliénés. Type: DUNGEON_2_ROOMS. Native level: 201. Maps: [1284].

Species pool: Ciervofante [5167] level 209-213, Pinchusorio [5168] level 203-207, Asesimio [5169] level 205-209, Jabalirio [5170] level 218-223

### Guide composition

[donjons-donjon-vandalienes](https://methodwakfu.com/pvm/donjons/donjon-vandalienes/); extraction=partial; version=1.70; client version match=unverified.

- Room 1 (partial): 7 × Vandaliénés (species unspecified) [ref None, unknown]
- Room 2 (partial): 8 × Vandaliénés (species unspecified) [ref None, unknown]
- Room 3 (complete): 1 × Phacochemar [ref 5170, boss], 2 × Assassinge [ref 5169, monster], 2 × Uto-pic [ref 5168, monster], 2 × Boiseux [ref 5167, monster]

### Native entrance and interiors

Entry map 1285, object 32603, destination 4308, template 163. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 4, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 32581 on map 1284: map 1284 (161,-167,20), criterion=empty, item=0
- Internal transport object 32582 on map 1284: map 1284 (113,-101,-4), criterion=empty, item=0
- Stele: 34883 at map 1284 (160.0,-171.0,20.0)

### Local implementation

donjons-donjon-vandalienes v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 7 × Ciervofante [5167], 1 × Pinchusorio [5168]
- Configured room 2: 8 × Pinchusorio [5168]
- Configured room 3: 1 × Phacochemar [5170], 2 × Assassinge [5169], 2 × Uto-pic [5168], 2 × Pinchusorio [5168], 1 × Asesimio [5169]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Vaciantes (native:177)

French alias: Donjon Vidéants. Type: DUNGEON_2_ROOMS. Native level: 216. Maps: [1313].

Species pool: Vaciequinoideo [5280] level 224-228, Inanido [5281] level 220-224, Crisálivacío [5282] level 218-222, Ar'Nan, augurio del vacío [5283] level 233-238, Anathar [5305] level 230-230

### Guide composition

[donjon-videants](https://methodwakfu.com/pvm/donjons/donjon-videants/); extraction=complete; version=1.74; client version match=unverified.

- Room 1 (complete): 3 × Echinoidéant [ref 5280, monster], 3 × Inanite [ref 5281, monster], 2 × Chrysavide [ref 5282, monster]
- Room 2 (complete): 1 × Ar’Nan, Augure du néant [ref 5283, boss], 3 × Echinoidéant [ref 5280, monster], 2 × Inanite [ref 5281, monster], 2 × Chrysavide [ref 5282, monster]

### Native entrance and interiors

Entry map 1309, object 33149, destination 4461, template 172. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 1, 'GenericActivableInteractiveElement': 2}.

- Door: 33152 at map 1313 (-32.0,-27.0,8.0)

### Local implementation

donjon-videants v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 3 × Echinoidéant [5280], 3 × Inanite [5281], 2 × Chrysavide [5282]
- Configured room 2: 1 × Inanido [5281], 3 × Echinoidéant [5280], 2 × Inanite [5281], 2 × Chrysavide [5282]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra de los Idos (native:179)

French alias: Donjon Égarés ?. Type: DUNGEON_2_ROOMS. Native level: 216. Maps: [1336].

Species pool: Remanagobiante [5292] level 224-228, Oditrevni [5293] level 220-224, CeEvroaint [5294] level 218-222, !@#dh`~ [5295] level 233-238, Anathar [5305] level 230-230

### Guide composition

[donjons-donjon-egares](https://methodwakfu.com/pvm/donjons/donjon-egares/); extraction=partial; version=1.74; client version match=unverified.

- Room 1 (partial): 3 × Égarés [ref None, monster], 3 × Égarés [ref None, monster], 2 × Égarés [ref None, monster]
- Room 2 (partial): 1 × !@#dh`~ [ref 5295, boss], 3 × Égarés [ref None, monster], 2 × Égarés [ref None, monster], 2 × Égarés [ref None, monster]

### Native entrance and interiors

Entry map 1333, object 33141, destination 4465, template 174. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 4, 'GenericActivableInteractiveElement': 2, 'Teleporter': 2}.

- Door: 33168 at map 1336 (-1.0,-23.0,0.0); 33169 at map 1336 (0.0,-23.0,0.0); 33170 at map 1336 (1.0,-23.0,0.0); 33380 at map 1336 (2.0,-23.0,0.0)

### Local implementation

donjons-donjon-egares v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 3 × Remanagobiante [5292], 3 × Oditrevni [5293], 2 × CeEvroaint [5294]
- Configured room 2: 1 × !@#dh`~ [5295], 3 × CeEvroaint [5294], 2 × !@#dh`~ [5295], 2 × Anathar [5305]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Mazmorra Tripulación del Pulpo (native:184)

French alias: Donjon Équipage du poulpe. Type: DUNGEON_2_ROOMS. Native level: 36. Maps: [1369].

Species pool: Hermana de la costa [5373] level 40-44, Filibustero de Rano [5374] level 38-42, Batallante de los mares [5375] level 44-48, Pohl el Pulpo [5376] level 53-58, Cire Momore [5416] level 53-58

### Guide composition

[donjons-donjon-equipage-du-poulpe](https://methodwakfu.com/pvm/donjons/donjon-equipage-du-poulpe/); extraction=unknown; version=1.91; client version match=unverified.


### Native entrance and interiors

Entry map 1358, object 33426, destination 4498, template 177. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 43, 'GenericActivableInteractiveElement': 5, 'Teleporter': 2}.

- Door: 33435 at map 1369 (-6.0,-10.0,-2.0); 33436 at map 1369 (-6.0,-11.0,-2.0); 33437 at map 1369 (-5.0,-11.0,-2.0); 33443 at map 1369 (-7.0,-16.0,-2.0); 33444 at map 1369 (-8.0,-16.0,-2.0); 33445 at map 1369 (-8.0,-17.0,-2.0); 33563 at map 1369 (-5.0,-10.0,-2.0); 33431 at map 1369 (-1.0,-32.0,0.0); 33446 at map 1369 (-7.0,-24.0,-2.0); 33447 at map 1369 (-8.0,-24.0,-2.0); 33448 at map 1369 (-3.0,-27.0,-2.0); 33449 at map 1369 (-3.0,-28.0,-2.0); 33450 at map 1369 (-4.0,-28.0,-2.0); 33460 at map 1369 (-9.0,-52.0,-17.0); 33461 at map 1369 (-9.0,-53.0,-17.0); 33477 at map 1369 (-8.0,-53.0,-17.0); 33463 at map 1369 (-4.0,-55.0,-17.0); 33466 at map 1369 (-8.0,-57.0,-17.0); 33467 at map 1369 (-4.0,-62.0,-17.0); 33468 at map 1369 (-4.0,-61.0,-17.0); 33469 at map 1369 (-7.0,-61.0,-17.0); 33470 at map 1369 (-7.0,-62.0,-17.0); 33471 at map 1369 (-8.0,-62.0,-17.0); 33472 at map 1369 (-8.0,-65.0,-17.0); 33473 at map 1369 (-9.0,-65.0,-17.0); 33474 at map 1369 (-2.0,-58.0,-17.0); 33475 at map 1369 (-2.0,-64.0,-17.0); 33476 at map 1369 (-3.0,-65.0,-17.0); 33860 at map 1369 (-5.0,-67.0,-17.0); 33861 at map 1369 (-6.0,-67.0,-17.0); 33862 at map 1369 (-7.0,-67.0,-17.0); 33438 at map 1369 (1.0,-18.0,-2.0); 33439 at map 1369 (2.0,-18.0,-2.0); 33440 at map 1369 (2.0,-17.0,-2.0); 33441 at map 1369 (1.0,-11.0,-2.0); 33442 at map 1369 (1.0,-10.0,-2.0); 33451 at map 1369 (2.0,-24.0,-2.0); 33453 at map 1369 (3.0,-25.0,-2.0); 33455 at map 1369 (3.0,-25.0,-2.0); 33456 at map 1369 (3.0,-24.0,-2.0); 33457 at map 1369 (2.0,-25.0,-2.0); 33458 at map 1369 (5.0,-21.0,-2.0); 33459 at map 1369 (4.0,-21.0,-2.0)

### Local implementation

donjons-donjon-equipage-du-poulpe v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 1 × Hermana de la costa [5373], 1 × Filibustero de Rano [5374], 1 × Batallante de los mares [5375], 1 × Pohl el Pulpo [5376], 1 × Cire Momore [5416], 1 × Hermana de la costa [5373], 1 × Filibustero de Rano [5374], 1 × Batallante de los mares [5375]
- Configured room 2: 1 × Filibustero de Rano [5374], 1 × Batallante de los mares [5375], 1 × Pohl el Pulpo [5376], 1 × Cire Momore [5416], 1 × Hermana de la costa [5373], 1 × Filibustero de Rano [5374], 1 × Batallante de los mares [5375], 1 × Pohl el Pulpo [5376]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## donjons-evenementiels-atelier-du-pere-nowel (legacy-guide:donjons-evenementiels-atelier-du-pere-nowel)

French alias: unmapped legacy guide. Type: legacy. Native level: unknown. Maps: see configured entry.

Species pool: Unknown native pool

### Guide composition

[donjons-evenementiels-atelier-du-pere-nowel](https://methodwakfu.com/pvm/donjons-evenementiels/atelier-du-pere-nowel/); extraction=complete; version=1.66; client version match=unverified.

- Room 1 (complete): 2 × Rennes’Abat [ref None, monster], 2 × Paquets Cadeaux I [ref None, monster], 2 × Paquets Cadeaux II [ref None, monster]
- Room 2 (complete): 1 × Renne’Calcitrant [ref 2225, boss], 1 × Renne’Abat [ref 2200, monster], 2 × Paquets Cadeaux I [ref None, monster], 2 × Paquets Cadeaux II [ref None, monster]
- Room 3 (complete): 1 × Grinch [ref 2868, boss], 2 × Paquets Cadeaux I [ref None, monster], 2 × Paquets Cadeaux II [ref None, monster]

### Native entrance and interiors

Entry map 472, object 27425, destination 977, template 1000474. Criterion:

```text
IsAchievementComplete(836)
```

Object counts: {'Door': 2, 'Teleporter': 4, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 17344 on map 474: map 474 (-29,0,1), criterion=empty, item=0
- Internal transport object 17342 on map 474: map 474 (-34,-110,8), criterion=empty, item=0
- Door: 17345 at map 474 (-10.0,1.0,0.0); 21357 at map 474 (-24.0,-5.0,0.0)

### Local implementation

donjons-evenementiels-atelier-du-pere-nowel v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 2 × Reno Joso [2200], 2 × Reno Civo [2225], 2 × Grinch [2868], 1 × Reno Joso [2200], 1 × Reno Civo [2225]
- Configured room 2: 1 × Reno Civo [2225], 1 × Grinch [2868], 2 × Reno Joso [2200], 2 × Reno Civo [2225], 1 × Grinch [2868], 1 × Reno Joso [2200]
- Configured room 3: 1 × Grinch [2868], 2 × Reno Joso [2200], 2 × Reno Civo [2225], 1 × Grinch [2868], 1 × Reno Joso [2200], 1 × Reno Civo [2225]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## donjons-evenementiels-maison-du-pere-nowel (legacy-guide:donjons-evenementiels-maison-du-pere-nowel)

French alias: unmapped legacy guide. Type: legacy. Native level: unknown. Maps: see configured entry.

Species pool: Unknown native pool

### Guide composition

[donjons-evenementiels-maison-du-pere-nowel](https://methodwakfu.com/pvm/donjons-evenementiels/maison-du-pere-nowel/); extraction=complete; version=1.66; client version match=unverified.

- Room 1 (complete): 1 × Père Nowel [ref None, boss], 1 × Renne’Abat [ref 2200, monster], 2 × Paquets Cadeaux II [ref None, monster], 2 × Paquets Cadeaux I [ref None, monster]

### Native entrance and interiors

Entry map 472, object 17452, destination 1004, template 1000476. Criterion:

```text
(empty on this entry)
```

Object counts: {'AudioMarker': 1, 'Teleporter': 1}.


### Local implementation

donjons-evenementiels-maison-du-pere-nowel v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Reno Joso [2200], 1 × Reno Joso [2200], 2 × Reno Joso [2200], 2 × Reno Joso [2200], 1 × Reno Joso [2200], 1 × Reno Joso [2200]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## donjons-evenementiels-palais-marin (legacy-guide:donjons-evenementiels-palais-marin)

French alias: unmapped legacy guide. Type: legacy. Native level: unknown. Maps: see configured entry.

Species pool: Unknown native pool

### Guide composition

[donjons-evenementiels-palais-marin](https://methodwakfu.com/pvm/donjons-evenementiels/palais-marin/); extraction=complete; version=1.66; client version match=unverified.

- Room 1 (complete): 2 × Mimis Pâtis [ref None, monster], 1 × Pâtis Impériâls [ref None, monster]
- Room 2 (complete): 2 × Mimis Pâtis [ref None, monster], 2 × Pâtis Impériâls [ref None, monster], 1 × Pâtis Bulleurs [ref None, monster]
- Room 3 (complete): 3 × Pâtis Bulleurs [ref None, monster], 2 × Pâtis Impériâls [ref None, monster], 1 × Mimis Pâtis [ref None, monster]
- Room 4 (complete): 1 × Château de Sâble [ref 4021, boss], 2 × Mimis Pâtis [ref None, monster], 2 × Pâtis Bulleurs [ref None, monster]
- Room 5 (complete): 1 × Pâti Noir [ref 4022, monster]

### Native entrance and interiors

Entry map 458, object 26727, destination 2482, template 1001075. Criterion:

```text
@("quest.Madrague.event.termine") (IsAfter(27,07,2027,10,00,00) and IsBefore(31,08,2027,10,00,00))@ and @("quest.Madrague.boussole") GetItemQuantity(20389) > 0@
```

Object counts: {'Door': 4, 'ZoneTrigger': 6, 'Teleporter': 3, 'GenericActivableInteractiveElement': 3}.

- Internal transport object 26690 on map 1075: map 1075 (7,-85,5), criterion=empty, item=0
- Internal transport object 26689 on map 1075: map 1075 (-72,-118,0), criterion=empty, item=0
- Door: 26635 at map 1075 (-5.0,-25.0,9.0); 26638 at map 1075 (-19.0,-50.0,17.0); 26636 at map 1075 (10.0,-25.0,9.0); 26637 at map 1075 (10.0,-50.0,17.0)
- ZoneTrigger: 26653 at map 1075 (-4.0,-61.0,22.0); 26655 at map 1075 (-2.0,-58.0,22.0); 26657 at map 1075 (0.0,-61.0,22.0); 26652 at map 1075 (2.0,-58.0,22.0); 26656 at map 1075 (0.0,-55.0,22.0); 26654 at map 1075 (4.0,-61.0,22.0)

### Local implementation

donjons-evenementiels-palais-marin v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=4.

- Configured room 1: 2 × Cästillo Enhärenädo [4021], 1 × Pätinojäldre [4022], 1 × Cästillo Enhärenädo [4021], 1 × Pätinojäldre [4022], 1 × Cästillo Enhärenädo [4021], 1 × Pätinojäldre [4022], 1 × Cästillo Enhärenädo [4021]
- Configured room 2: 2 × Pätinojäldre [4022], 2 × Cästillo Enhärenädo [4021], 1 × Pätinojäldre [4022], 1 × Cästillo Enhärenädo [4021], 1 × Pätinojäldre [4022], 1 × Cästillo Enhärenädo [4021]
- Configured room 3: 3 × Cästillo Enhärenädo [4021], 2 × Pätinojäldre [4022], 1 × Cästillo Enhärenädo [4021], 1 × Pätinojäldre [4022], 1 × Cästillo Enhärenädo [4021]
- Configured room 4: 1 × Château de Sâble [4021], 2 × Cästillo Enhärenädo [4021], 2 × Pätinojäldre [4022], 1 × Cästillo Enhärenädo [4021], 1 × Pätinojäldre [4022], 1 × Cästillo Enhärenädo [4021]
- Configured room 5: 1 × Pâti Noir [4022]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Espíritu vengativo (native:220)

French alias: Esprit vengeur. Type: DUNGEON_ARCADE. Native level: 96. Maps: [1476].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Mekafábrica (native:95)

French alias: Fabrique Méka. Type: DUNGEON_2_ROOMS. Native level: 156. Maps: [916].

Species pool: Ordagova [3395] level 158-162, Lapso [3396] level 164-168, Goreloj [3397] level 160-164, Vertox, el Intemporal [3398] level 173-178

### Guide composition

[donjons-fabrique-meka](https://methodwakfu.com/pvm/donjons/fabrique-meka/); extraction=complete; version=1.72; client version match=unverified.

- Room 1 (complete): 2 × Laps [ref 3396, monster], 2 × Orda Gova [ref 3395, monster], 2 × Grorlog [ref 3397, monster]
- Room 2 (complete): 2 × Laps [ref 3396, monster], 2 × Orda Gova [ref 3395, monster], 3 × Grorlog [ref 3397, monster]
- Room 3 (complete): 3 × Laps [ref 3396, monster], 3 × Orda Gova [ref 3395, monster], 2 × Grorlog [ref 3397, monster]
- Room 4 (complete): 1 × Vertox l’Intemporel [ref 3398, boss], 2 × Laps [ref 3396, monster], 2 × Orda Gova [ref 3395, monster], 2 × Grorlog [ref 3397, monster]

### Native entrance and interiors

Entry map 922, object 24795, destination 2102, template 97. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 13, 'Stele': 1, 'Teleporter': 2, 'GenericActivableInteractiveElement': 4}.

- Door: 24810 at map 916 (-4.0,-71.0,8.0); 24811 at map 916 (-4.0,-70.0,8.0); 24812 at map 916 (-4.0,-69.0,8.0); 24813 at map 916 (-4.0,-68.0,8.0); 24817 at map 916 (-3.0,-71.0,8.0); 24816 at map 916 (-3.0,-70.0,8.0); 24815 at map 916 (-3.0,-69.0,8.0); 24814 at map 916 (-3.0,-68.0,8.0); 24821 at map 916 (-2.0,-86.0,8.0); 24820 at map 916 (-1.0,-86.0,8.0); 24822 at map 916 (-1.0,-122.0,8.0); 24819 at map 916 (0.0,-86.0,8.0); 24818 at map 916 (1.0,-86.0,8.0)
- Stele: 34867 at map 916 (-9.0,-113.0,8.0)

### Local implementation

donjons-fabrique-meka v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Ordagova [3395], 2 × Lapso [3396], 2 × Goreloj [3397], 1 × Vertox, el Intemporal [3398], 1 × Ordagova [3395]
- Configured room 2: 2 × Lapso [3396], 2 × Goreloj [3397], 3 × Vertox, el Intemporal [3398], 1 × Ordagova [3395]
- Configured room 3: 3 × Goreloj [3397], 3 × Vertox, el Intemporal [3398], 2 × Ordagova [3395]
- Configured room 4: 1 × Vertox, el Intemporal [3398], 2 × Ordagova [3395], 2 × Lapso [3396], 2 × Goreloj [3397], 1 × Vertox, el Intemporal [3398]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Fosa del Atormentador (native:82)

French alias: Fosse du Tourmenteur. Type: DUNGEON_3_PLAYERS. Native level: 111. Maps: [795].

Species pool: Espectrex, el Atormentador [2827] level 128-133, Jyman [3007] level 113-117, Okhlar [3008] level 115-119, Kiryuk [3009] level 113-117

### Guide composition

[fosse-du-tourmenteur](https://methodwakfu.com/pvm/fosse-du-tourmenteur/); extraction=unknown; version=1.87; client version match=unverified.

- Room 1 (unknown): Unknown composition

### Native entrance and interiors

Entry map 793, object 27324, destination 1498, template 83. Criterion:

```text
(empty on this entry)
```

Object counts: {'GenericActivableInteractiveElement': 6, 'Teleporter': 1}.


### Local implementation

fosse-du-tourmenteur v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Espectrex, el Atormentador [2827], 1 × Jyman [3007], 1 × Okhlar [3008], 1 × Kiryuk [3009], 1 × Espectrex, el Atormentador [2827], 1 × Jyman [3007], 1 × Okhlar [3008], 1 × Kiryuk [3009]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Relojeros (native:224)

French alias: Horlogers. Type: DUNGEON_ARCADE. Native level: 51. Maps: [1439].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 346, object 35961, destination 4792, template 216. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Jawdín de la Weina (native:67)

French alias: Jawdin de la Weine. Type: DUNGEON_3_ROOMS. Native level: 126. Maps: [1398].

Species pool: Pekewabbit [2565] level 128-132, Wabbit [2566] level 130-134, Wabbit wodo [2567] level 132-136, Awelito wabbit [2568] level 134-138, Gwan Visiw Wabbit [2570] level 143-148

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1384, object 34682, destination 4588, template 68. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 2, 'Teleporter': 2, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Door: 34716 at map 1398 (-14.0,12.0,0.0); 34715 at map 1398 (-4.0,6.0,0.0)
- Stele: 34851 at map 1398 (-27.0,3.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Kokolost Island (native:141)

French alias: Kokokolantha. Type: DUNGEON_4_ROOMS. Native level: 51. Maps: [295].

Species pool: Gorkoko [4728] level 59-63, Kokoko [4729] level 55-59, Pekekoko [4730] level 53-57, Gorkokolost [4731] level 68-73

### Guide composition

[donjons-kokokolantha](https://methodwakfu.com/pvm/donjons/kokokolantha/); extraction=complete; version=1.70; client version match=unverified.

- Room 1 (complete): 2 × Tikoko [ref 4730, monster], 2 × Kokoko [ref 4729, monster], 2 × Grokoko [ref 4728, monster]
- Room 2 (complete): 2 × Tikoko [ref 4730, monster], 3 × Kokoko [ref 4729, monster], 2 × Grokoko [ref 4728, monster]
- Room 3 (complete): 3 × Tikoko [ref 4730, monster], 3 × Kokoko [ref 4729, monster], 2 × Grokoko [ref 4728, monster]
- Room 4 (complete): 1 × Vieux Binson [ref None, monster], 1 × Viendredi [ref None, monster], 2 × Grokoko [ref 4728, monster]
- Room 5 (complete): 1 × Grokokolantha [ref 4731, boss], 3 × Tikoko [ref 4730, monster], 2 × Kokoko [ref 4729, monster], 2 × Grokoko [ref 4728, monster]

### Native entrance and interiors

Entry map 1135, object 14590, destination 744, template 144. Criterion:

```text
(empty on this entry)
```

Object counts: {'AudioMarker': 4, 'Door': 5, 'GenericActivableInteractiveElement': 5, 'Stool': 7, 'Teleporter': 4, 'LootChest': 1, 'StreetLight': 1}.

- Internal transport object 13346 on map 295: map 295 (-39,-30,0), criterion=empty, item=0
- Internal transport object 13345 on map 295: map 295 (-18,-74,0), criterion=empty, item=0
- Door: 13340 at map 295 (-12.0,-1.0,0.0); 13341 at map 295 (-31.0,-6.0,0.0); 13347 at map 295 (-24.0,-81.0,0.0); 13348 at map 295 (-21.0,-86.0,0.0); 13342 at map 295 (-46.0,-24.0,0.0)
- LootChest: 13817 at map 295 (-31.0,-74.0,0.0)

### Local implementation

donjons-kokokolantha v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=4.

- Configured room 1: 2 × Tikoko [4730], 2 × Kokoko [4729], 2 × Pekekoko [4730], 1 × Gorkokolost [4731], 1 × Gorkoko [4728]
- Configured room 2: 2 × Tikoko [4730], 3 × Pekekoko [4730], 2 × Gorkokolost [4731], 1 × Gorkoko [4728]
- Configured room 3: 3 × Tikoko [4730], 3 × Gorkokolost [4731], 2 × Gorkoko [4728]
- Configured room 4: 1 × Gorkokolost [4731], 1 × Gorkoko [4728], 2 × Kokoko [4729], 1 × Pekekoko [4730], 1 × Gorkokolost [4731], 1 × Gorkoko [4728], 1 × Kokoko [4729]
- Configured room 5: 1 × Grokokolantha [4731], 3 × Tikoko [4730], 2 × Pekekoko [4730], 2 × Gorkokolost [4731]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Antro Olvidado (native:81)

French alias: L'Antre oubliée. Type: DUNGEON_2_ROOMS. Native level: 51. Maps: [712].

Species pool: Jefe de guerra salvaje [2764] level 55-55, Jalató salvaje [2765] level 50-50, Jalalínea chamana [2766] level 52-52, Jalatín salvaje [2767] level 54-54, Gran Jalató Salvaje [2768] level 65-65

### Guide composition

[antre-oublie](https://methodwakfu.com/pvm/antre-oublie/); extraction=complete; version=1.59; client version match=unverified.

- Room 1 (complete): 2 × Bouftou Sauvage [ref 2765, monster], 2 × Boufette Chamane [ref None, monster], 1 × Boufton Sauvage [ref 2767, monster], 2 × Chef de Guerre Sauvage [ref 2764, monster]
- Room 2 (complete): 1 × Bouftou Sauvage [ref 2765, monster], 1 × Boufette Chamane [ref None, monster], 2 × Chef de Guerre Sauvage [ref 2764, monster], 1 × Grand Bouftou Sauvage [ref 2768, boss]

### Native entrance and interiors

Entry map 711, object 20421, destination 1408, template 82. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 1, 'Door': 3}.

- Door: 20417 at map 712 (18.0,-49.0,-16.0); 20416 at map 712 (18.0,-48.0,-16.0); 20418 at map 712 (23.0,-59.0,-16.0)

### Local implementation

antre-oublie v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 2 × Bouftou Sauvage [2765], 2 × Jalató salvaje [2765], 1 × Jalalínea chamana [2766], 2 × Chef de Guerre Sauvage [2764], 1 × Gran Jalató Salvaje [2768]
- Configured room 2: 1 × Bouftou Sauvage [2765], 1 × Jalalínea chamana [2766], 2 × Chef de Guerre Sauvage [2764], 1 × Grand Bouftou Sauvage [2768], 1 × Jefe de guerra salvaje [2764], 1 × Jalató salvaje [2765], 1 × Jalalínea chamana [2766]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Arena Danzante (native:11)

French alias: L'Arène Dansante. Type: DUNGEON_3_ROOMS. Native level: 96. Maps: [549].

Species pool: Bilbyboy de frambuesa [2465] level 100-104, Bilbygirl de menta [2466] level 100-104, Bilbyboy de fresa [2467] level 100-104, Bilbygirl de limón [2468] level 100-104, Bilby Queen [2469] level 113-118

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 458, object 18988, destination 1196, template 14. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Cuerbokueva (native:88)

French alias: La Corbeau-Cave. Type: DUNGEON_3_ROOMS. Native level: 66. Maps: [153].

Species pool: Cuerbok [1152] level 69-69, Cuerbik [1153] level 72-72, Jefe cuerbok [1155] level 75-75, Cuerbakesino [1784] level 65-65, Corbot C-800 [3696] level 80-80

### Guide composition

[la-corbeau-cave](https://methodwakfu.com/pvm/la-corbeau-cave/); extraction=complete; version=1.70; client version match=unverified.

- Room 1 (complete): 3 × Corbac [ref 1152, monster], 2 × Corbic [ref 1153, monster], 2 × Corbac chef [ref 1155, monster]
- Room 2 (complete): 2 × Corbic [ref 1153, monster], 4 × Corbac chef [ref 1155, monster]
- Room 3 (complete): 2 × Corbac [ref 1152, monster], 2 × Corbic [ref 1153, monster], 3 × Corbac chef [ref 1155, monster], 1 × Korbot K-800 [ref 3696, boss]

### Native entrance and interiors

Entry map 949, object 25129, destination 2180, template 100. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'ZoneTrigger': 1, 'Door': 3, 'GenericActivableInteractiveElement': 1}.

- Door: 4461 at map 153 (5.0,7.0,0.0); 4463 at map 153 (12.0,17.0,-24.0); 4462 at map 153 (1.0,20.0,-8.0)
- ZoneTrigger: 4464 at map 153 (9.0,-1.0,-22.0)

### Local implementation

la-corbeau-cave v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 3 × Cuerbok [1152], 2 × Cuerbik [1153], 2 × Jefe cuerbok [1155], 1 × Cuerbakesino [1784]
- Configured room 2: 2 × Cuerbik [1153], 4 × Jefe cuerbok [1155], 1 × Cuerbakesino [1784], 1 × Corbot C-800 [3696]
- Configured room 3: 2 × Jefe cuerbok [1155], 2 × Cuerbakesino [1784], 3 × Corbot C-800 [3696], 1 × Korbot K-800 [3696]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Cresta Helada (native:128)

French alias: La Crête Givrée. Type: DUNGEON_2_ROOMS. Native level: 186. Maps: [1133].

Species pool: Esquistérico [4257] level 194-198, Amaníaco [4258] level 188-192, Sulfurado [4259] level 190-194, Cendragón [4260] level 203-208, Aguabrial [5165] level 200-200

### Guide composition

[la-crete-givree](https://methodwakfu.com/pvm/la-crete-givree/); extraction=complete; version=1.66; client version match=unverified.

- Room 1 (complete): 2 × Ammaniaque [ref 4258, monster], 2 × Schistérique [ref 4257, monster], 2 × Sulfurie [ref 4259, monster]
- Room 2 (complete): 3 × Ammaniaque [ref 4258, monster], 2 × Schistérique [ref 4257, monster], 2 × Sulfurie [ref 4259, monster]
- Room 3 (complete): 3 × Ammaniaque [ref 4258, monster], 2 × Schistérique [ref 4257, monster], 2 × Sulfurie [ref 4259, monster]
- Room 4 (complete): 1 × Cendragon [ref 4260, boss], 3 × Ammaniaque [ref 4258, monster], 2 × Schistérique [ref 4257, monster], 2 × Sulfurie [ref 4259, monster]

### Native entrance and interiors

Entry map 1124, object 28229, destination 2666, template 131. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 4, 'GenericActivableInteractiveElement': 5, 'Stele': 1}.

- Door: 28214 at map 1133 (20.0,-34.0,9.0); 28216 at map 1133 (19.0,-34.0,9.0); 28215 at map 1133 (20.0,-42.0,9.0); 28218 at map 1133 (66.0,-65.0,27.0)
- Stele: 34875 at map 1133 (57.0,-62.0,48.0)

### Local implementation

la-crete-givree v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Ammaniaque [4258], 2 × Schistérique [4257], 2 × Sulfurie [4259]
- Configured room 2: 3 × Ammaniaque [4258], 2 × Schistérique [4257], 2 × Sulfurie [4259]
- Configured room 3: 3 × Ammaniaque [4258], 2 × Schistérique [4257], 2 × Sulfurie [4259]
- Configured room 4: 1 × Cendragon [4260], 3 × Ammaniaque [4258], 2 × Schistérique [4257], 2 × Sulfurie [4259]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Montaña Conohos (native:136)

French alias: La Montagne Adezieu. Type: DUNGEON_4_ROOMS. Native level: 36. Maps: [1224].

Species pool: Crujidor ancestral [4510] level 44-48, Crujidor [4511] level 40-44, Crujibola [4512] level 38-42, Crujidor Real [4519] level 53-58, Crujidor ancestral de la mina [4878] level 44-48, Crujidor de la mina [4879] level 40-44, Crujibola de la mina [4880] level 38-42

### Guide composition

[la-montagne-adezieu](https://methodwakfu.com/pvm/la-montagne-adezieu/); extraction=complete; version=1.66; client version match=unverified.

- Room 1 (complete): 2 × Craqueleur [ref 4511, monster], 1 × Craqueleur Ancestral [ref 4510, monster], 3 × Craqueboule [ref 4512, monster]
- Room 2 (complete): 2 × Craqueleur [ref 4511, monster], 2 × Craqueleur Ancestral [ref 4510, monster], 3 × Craqueboule [ref 4512, monster]
- Room 3 (complete): 3 × Craqueleur [ref 4511, monster], 2 × Craqueleur Ancestral [ref 4510, monster], 3 × Craqueboule [ref 4512, monster]
- Room 4 (complete): 2 × Craqueleur de la mine [ref 4879, monster], 3 × Craqueboule de la mine [ref 4880, monster], 1 × Craqueleur de la mine Ancestral [ref 4878, monster]
- Room 5 (complete): 3 × Craqueleur de la mine [ref 4879, monster], 3 × Craqueleur de la mine Ancestral [ref 4878, monster], 1 × Craqueboule de la mine [ref 4880, monster]
- Room 6 (complete): 2 × Craqueboule [ref 4512, monster], 2 × Craqueleur [ref 4511, monster], 2 × Craqueleur Ancestral [ref 4510, monster], 1 × Craqueleur Royal [ref 4519, boss]

### Native entrance and interiors

Entry map 1134, object 17363, destination 972, template 139. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 5, 'Door': 6, 'GenericActivableInteractiveElement': 1, 'BackgroundDisplay': 1}.

- Internal transport object 35990 on map 1224: map 1224 (6,-14,-20), criterion=empty, item=0
- Internal transport object 35991 on map 1224: map 1224 (-4,-12,0), criterion=empty, item=0
- Door: 31409 at map 1224 (-8.0,-36.0,0.0); 31408 at map 1224 (-8.0,-21.0,0.0); 31410 at map 1224 (-5.0,-51.0,0.0); 31412 at map 1224 (9.0,-21.0,-19.0); 31411 at map 1224 (6.0,-51.0,-20.0); 35992 at map 1224 (9.0,-38.0,-20.0)

### Local implementation

la-montagne-adezieu v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=5.

- Configured room 1: 2 × Craqueleur [4511], 1 × Crujidor [4511], 3 × Crujibola [4512], 1 × Crujidor Real [4519], 1 × Crujidor ancestral de la mina [4878]
- Configured room 2: 2 × Craqueleur [4511], 2 × Crujibola [4512], 3 × Crujidor Real [4519], 1 × Crujidor ancestral de la mina [4878]
- Configured room 3: 3 × Craqueleur [4511], 2 × Crujidor Real [4519], 3 × Crujidor ancestral de la mina [4878]
- Configured room 4: 2 × Crujidor Real [4519], 3 × Crujidor ancestral de la mina [4878], 1 × Crujidor de la mina [4879], 1 × Crujibola de la mina [4880], 1 × Crujidor ancestral [4510]
- Configured room 5: 3 × Crujidor ancestral de la mina [4878], 3 × Crujidor de la mina [4879], 1 × Crujibola de la mina [4880], 1 × Crujidor ancestral [4510]
- Configured room 6: 2 × Crujidor de la mina [4879], 2 × Craqueleur [4511], 2 × Crujidor ancestral [4510], 1 × Craqueleur Royal [4519], 1 × Crujibola [4512]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Patapinxería (native:153)

French alias: La Patapoutrerie. Type: DUNGEON_2_ROOMS. Native level: 156. Maps: [963].

Species pool: Patapikot [4920] level 158-162, Patator [4921] level 160-164, Patapatas [4922] level 164-168, Mamapinxo [4923] level 173-178

### Guide composition

[donjons-la-patapoutrerie](https://methodwakfu.com/pvm/donjons/la-patapoutrerie/); extraction=complete; version=1.72; client version match=unverified.

- Room 1 (complete): 2 × Patapikot [ref 4920, monster], 2 × Patator [ref 4921, monster], 2 × Patapattes [ref 4922, monster]
- Room 2 (complete): 7 × Patapoutre [ref None, monster]
- Room 3 (complete): 8 × Patapoutre [ref None, monster]
- Room 4 (complete): 1 × Mamapoutre [ref 4923, boss], 2 × Patapikot [ref 4920, monster], 2 × Patator [ref 4921, monster], 2 × Patapattes [ref 4922, monster]

### Native entrance and interiors

Entry map 1210, object 25350, destination 2218, template 156. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 2}.

- Door: 25266 at map 963 (21.0,-24.0,-10.0); 25267 at map 963 (22.0,-24.0,-10.0); 25268 at map 963 (29.0,-19.0,-10.0)

### Local implementation

donjons-la-patapoutrerie v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Patapikot [4920], 2 × Patator [4921], 2 × Patapatas [4922], 1 × Mamapinxo [4923], 1 × Patapikot [4920]
- Configured room 2: 7 × Patator [4921], 1 × Patapatas [4922]
- Configured room 3: 8 × Patapatas [4922]
- Configured room 4: 1 × Mamapoutre [4923], 2 × Patapikot [4920], 2 × Patator [4921], 2 × Patapatas [4922], 1 × Mamapinxo [4923]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## La Pischina (native:143)

French alias: La Pichine. Type: DUNGEON_4_ROOMS. Native level: 111. Maps: [912].

Species pool: Pez zespadín [4723] level 115-119, Pez muertambre [4724] level 119-123, Chusmerluza [4725] level 115-119, Pez alfombra [4726] level 113-117, Zespadín Negro [4727] level 128-133, Leviatún [4889] level 125-125

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1208, object 14589, destination 2079, template 146. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 4, 'PositionTrigger': 4, 'Door': 5, 'LootChest': 1}.

- Door: 31487 at map 912 (54.0,-3.0,0.0); 24202 at map 912 (60.0,0.0,-4.0); 24203 at map 912 (61.0,0.0,-4.0); 31445 at map 912 (61.0,10.0,-4.0); 31444 at map 912 (60.0,10.0,-4.0)
- LootChest: 26428 at map 912 (60.0,17.0,0.0)
- PositionTrigger: 31448 at map 912 (33.0,6.0,1.0); 31447 at map 912 (24.0,15.0,1.0); 31449 at map 912 (52.0,-4.0,1.0); 31450 at map 912 (53.0,-4.0,1.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Dique Eskuálido (native:41)

French alias: La Skouale Sèche. Type: DUNGEON_3_ROOMS. Native level: 51. Maps: [467].

Species pool: Eskualindroso [4241] level 53-57, Eskualo martillo [4242] level 55-59, Eskualo lancero [4243] level 59-63, Eskualo Real [4244] level 68-73

### Guide composition

[donjons-la-skouale-seche](https://methodwakfu.com/pvm/donjons/la-skouale-seche/); extraction=unknown; version=1.87; client version match=unverified.


### Native entrance and interiors

Entry map 1118, object 27741, destination 970, template 39. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'AudioMarker': 9, 'GenericActivableInteractiveElement': 1}.

- Door: 16990 at map 467 (-5.0,-26.0,-9.0); 16991 at map 467 (-1.0,-35.0,-9.0); 16992 at map 467 (-10.0,-51.0,-17.0)

### Local implementation

donjons-la-skouale-seche v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Eskualindroso [4241], 1 × Eskualo martillo [4242], 1 × Eskualo lancero [4243], 1 × Eskualo Real [4244], 1 × Eskualindroso [4241], 1 × Eskualo martillo [4242], 1 × Eskualo lancero [4243], 1 × Eskualo Real [4244]
- Configured room 2: 1 × Eskualo martillo [4242], 1 × Eskualo lancero [4243], 1 × Eskualo Real [4244], 1 × Eskualindroso [4241], 1 × Eskualo martillo [4242], 1 × Eskualo lancero [4243], 1 × Eskualo Real [4244], 1 × Eskualindroso [4241]
- Configured room 3: 1 × Eskualo lancero [4243], 1 × Eskualo Real [4244], 1 × Eskualindroso [4241], 1 × Eskualo martillo [4242], 1 × Eskualo lancero [4243], 1 × Eskualo Real [4244], 1 × Eskualindroso [4241], 1 × Eskualo martillo [4242]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Torre Helada (native:10)

French alias: La Tour Gelée. Type: DUNGEON_3_ROOMS. Native level: 111. Maps: [516].

Species pool: Mekabra [2350] level 110-110, Mekarbok [2351] level 114-114, Mekanistro [2352] level 117-117, Mekazerker [2353] level 120-120, Sylargh [2354] level 130-130

### Guide composition

[la-tour-gelee](https://methodwakfu.com/pvm/donjons/la-tour-gelee/); extraction=complete; version=None; client version match=unverified.

- Room 1 (complete): 2 × Mékanistro [ref 2352, monster], 2 × Mékarbac [ref 2351, monster], 2 × Mékabra [ref 2350, monster], 1 × Mékazerker [ref 2353, monster]
- Room 2 (complete): 2 × Mékanistro [ref 2352, monster], 2 × Mékarbac [ref 2351, monster], 2 × Mékabra [ref 2350, monster], 2 × Mékazerker [ref 2353, monster]
- Room 3 (complete): 1 × Sylargh [ref 2354, boss], 2 × Mékanistro [ref 2352, monster], 2 × Mékarbac [ref 2351, monster], 1 × Mékabra [ref 2350, monster], 2 × Mékazerker [ref 2353, monster]

### Native entrance and interiors

Entry map 508, object 18036, destination 1083, template 13. Criterion:

```text
(empty on this entry)
```

Object counts: {'AudioMarker': 19, 'Teleporter': 8, 'GenericActivableInteractiveElement': 3, 'LootChest': 1}.

- Internal transport object 18027 on map 516: map 516 (0,-83,1), criterion=empty, item=0
- Internal transport object 18028 on map 516: map 516 (7,-269,0), criterion=empty, item=0
- Internal transport object 18030 on map 516: map 516 (2,-353,0), criterion=empty, item=0
- Internal transport object 18029 on map 516: map 516 (7,-178,0), criterion=empty, item=0
- Internal transport object 18031 on map 516: map 516 (0,-263,1), criterion=empty, item=0
- Internal transport object 18026 on map 516: map 516 (1,-173,0), criterion=empty, item=0
- LootChest: 18146 at map 516 (7.0,-356.0,0.0)

### Local implementation

la-tour-gelee v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 2 × Mékanistro [2352], 2 × Mékarbac [2351], 2 × Mékabra [2350], 1 × Mékazerker [2353]
- Configured room 2: 2 × Mékanistro [2352], 2 × Mékarbac [2351], 2 × Mékabra [2350], 2 × Mékazerker [2353]
- Configured room 3: 1 × Mekanistro [2352], 2 × Mékanistro [2352], 2 × Mékarbac [2351], 1 × Mékabra [2350], 2 × Mékazerker [2353]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## La Torre Mineral (native:133)

French alias: La Tour Minérale. Type: DUNGEON_3_PLAYERS. Native level: 36. Maps: [1159].

Species pool: Jadarmado [4648] level 37-45, Esmeraldín [4649] level 37-45, Agatank [4650] level 37-45, Agonía la Desenterrada [4651] level 53-58

### Guide composition

[donjons-tour-minerale-36](https://methodwakfu.com/pvm/donjons/tour-minerale-36/); extraction=partial; version=1.67; client version match=unverified.

- Room 1 (partial): None × Agonie la Déterrée [ref 4651, boss], 1 × Emeraldin [ref 4649, monster], 1 × Jadarme [ref 4648, monster], 1 × Agathank [ref 4650, monster]

### Native entrance and interiors

Entry map 1202, object 29076, destination 3117, template 136. Criterion:

```text
GetRealLevel() >= 36
```

Object counts: {'Teleporter': 1, 'PositionTrigger': 1, 'Door': 2, 'GenericActivableInteractiveElement': 5}.

- Door: 33367 at map 1159 (12.0,-1.0,0.0); 33368 at map 1159 (12.0,1.0,0.0)
- PositionTrigger: 29209 at map 1159 (17.0,-2.0,0.0)

### Local implementation

donjons-tour-minerale-36 v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Jadarmado [4648], 1 × Esmeraldín [4649], 1 × Agatank [4650], 1 × Agonía la Desenterrada [4651], 1 × Jadarmado [4648], 1 × Esmeraldín [4649], 1 × Agatank [4650], 1 × Agonía la Desenterrada [4651]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## La Torre Mineral (native:134)

French alias: La Tour Minérale. Type: DUNGEON_3_PLAYERS. Native level: 186. Maps: [1204].

Species pool: Jadarmado [4661] level 187-195, Esmeraldín [4662] level 187-195, Agatank [4663] level 187-195, Agonía Corazón Cristalino [4664] level 203-208

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1202, object 29076, destination 3124, template 137. Criterion:

```text
GetRealLevel() >= 186
```

Object counts: {'Teleporter': 1, 'StoppingPositionTrigger': 1, 'Door': 2, 'GenericActivableInteractiveElement': 5}.

- Door: 33369 at map 1204 (12.0,-1.0,0.0); 33370 at map 1204 (12.0,1.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Torre Mineral (native:164)

French alias: La Tour Minérale. Type: DUNGEON_3_PLAYERS. Native level: 201. Maps: [1294].

Species pool: Jadarmado [5226] level 202-210, Esmeraldín [5227] level 202-210, Agatank [5228] level 202-210, Agonía, Nigromante Lívida [5229] level 218-223

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1202, object 29076, destination 4411, template 167. Criterion:

```text
GetRealLevel() >= 201
```

Object counts: {'Teleporter': 1, 'StoppingPositionZoneTrigger': 1, 'Door': 2, 'GenericActivableInteractiveElement': 5}.

- Door: 33374 at map 1294 (12.0,-1.0,0.0); 33373 at map 1294 (12.0,1.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Laboratorio de Womewo (native:74)

French alias: Laboratoire de Womewo. Type: DUNGEON_3_ROOMS. Native level: 141. Maps: [1396].

Species pool: Wabbit huesudo [2604] level 145-149, Gwan Wabbit GM [2605] level 158-163, Pekewabbit huesudo [2606] level 143-147, Awelito zombbit vendado [2607] level 149-153, Zombbit wodo [2608] level 147-151

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1390, object 34727, destination 4620, template 185. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 3, 'Teleporter': 2, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Door: 34728 at map 1396 (-24.0,-8.0,0.0); 34729 at map 1396 (-46.0,2.0,16.0); 34730 at map 1396 (-49.0,10.0,10.0)
- Stele: 34859 at map 1396 (-47.0,16.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Larventura (native:65)

French alias: Larventura. Type: DUNGEON_4_ROOMS. Native level: 12. Maps: [902].

Species pool: Larva azul [123] level 8-18, Larva naranja [124] level 8-18, Larva verde [125] level 8-18, Larva violeta [785] level 8-18, Shin Larva [2157] level 23-28

### Guide composition

[larventura](https://methodwakfu.com/pvm/larventura/); extraction=unknown; version=1.87; client version match=unverified.


### Native entrance and interiors

Entry map 546, object 24026, destination 2053, template 66. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 4, 'Teleporter': 2, 'GenericActivableInteractiveElement': 1}.

- Door: 23896 at map 902 (-21.0,0.0,0.0); 23898 at map 902 (-38.0,-13.0,0.0); 23899 at map 902 (-37.0,-13.0,0.0); 23897 at map 902 (-46.0,-24.0,0.0)

### Local implementation

larventura v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 1 × Larva azul [123], 1 × Larva naranja [124], 1 × Larva verde [125], 1 × Larva violeta [785], 1 × Shin Larva [2157], 1 × Larva azul [123], 1 × Larva naranja [124], 1 × Larva verde [125]
- Configured room 2: 1 × Larva naranja [124], 1 × Larva verde [125], 1 × Larva violeta [785], 1 × Shin Larva [2157], 1 × Larva azul [123], 1 × Larva naranja [124], 1 × Larva verde [125], 1 × Larva violeta [785]
- Configured room 3: 1 × Larva verde [125], 1 × Larva violeta [785], 1 × Shin Larva [2157], 1 × Larva azul [123], 1 × Larva naranja [124], 1 × Larva verde [125], 1 × Larva violeta [785], 1 × Shin Larva [2157]
- Configured room 4: 1 × Larva violeta [785], 1 × Shin Larva [2157], 1 × Larva azul [123], 1 × Larva naranja [124], 1 × Larva verde [125], 1 × Larva violeta [785], 1 × Shin Larva [2157], 1 × Larva azul [123]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Panteón Viviente (native:89)

French alias: Le Caveau Relevé. Type: DUNGEON_3_ROOMS. Native level: 21. Maps: [901].

Species pool: Rata esqueleto [3212] level 19-23, Jalató esqueleto [3214] level 22-26, Guardia esqueleto [3215] level 26-30, Morfor [3216] level 38-43

### Guide composition

[le-caveau-releve](https://methodwakfu.com/pvm/le-caveau-releve/); extraction=unknown; version=1.87; client version match=unverified.


### Native entrance and interiors

Entry map 527, object 24025, destination 2006, template 90. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'LootChest': 1}.

- Door: 23889 at map 901 (-27.0,-8.0,0.0); 23890 at map 901 (-24.0,-17.0,0.0); 23891 at map 901 (-31.0,-30.0,0.0)
- LootChest: 26497 at map 901 (-24.0,-34.0,0.0)

### Local implementation

le-caveau-releve v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Rata esqueleto [3212], 1 × Jalató esqueleto [3214], 1 × Guardia esqueleto [3215], 1 × Morfor [3216], 1 × Rata esqueleto [3212], 1 × Jalató esqueleto [3214], 1 × Guardia esqueleto [3215], 1 × Morfor [3216]
- Configured room 2: 1 × Jalató esqueleto [3214], 1 × Guardia esqueleto [3215], 1 × Morfor [3216], 1 × Rata esqueleto [3212], 1 × Jalató esqueleto [3214], 1 × Guardia esqueleto [3215], 1 × Morfor [3216], 1 × Rata esqueleto [3212]
- Configured room 3: 1 × Guardia esqueleto [3215], 1 × Morfor [3216], 1 × Rata esqueleto [3212], 1 × Jalató esqueleto [3214], 1 × Guardia esqueleto [3215], 1 × Morfor [3216], 1 × Rata esqueleto [3212], 1 × Jalató esqueleto [3214]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Glaciar Cornudo (native:62)

French alias: Le Glaglacier Cornu. Type: DUNGEON_2_ROOMS. Native level: 96. Maps: [517].

Species pool: Glalito [2359] level 98-102, Glalí [2360] level 100-104, Glalí enmasquelado [2361] level 104-108, Glalí cornelado [2362] level 100-104, Lady Glalí [2363] level 113-118

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 504, object 18035, destination 1086, template 63. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 3, 'GenericActivableInteractiveElement': 2, 'Teleporter': 2}.

- Door: 18042 at map 517 (-13.0,-2.0,0.0); 18041 at map 517 (-27.0,-4.0,0.0); 18040 at map 517 (-26.0,-4.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## El Hammalmejil (native:68)

French alias: Le Hammamamoule. Type: DUNGEON_3_ROOMS. Native level: 81. Maps: [548].

Species pool: Alfombrini [2460] level 85-89, Tiburón maraquillo [2461] level 89-93, Gusano cherniego inmaduro [2462] level 83-87, Gusano cherniego voraz [2463] level 85-89, Bilbylmeja Nacarada [2464] level 98-103

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 458, object 19547, destination 1225, template 69. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 4, 'AudioMarker': 7, 'Teleporter': 1}.

- Door: 19111 at map 548 (-5.0,-21.0,-12.0); 19112 at map 548 (5.0,-4.0,0.0); 19109 at map 548 (16.0,-24.0,0.0); 19110 at map 548 (0.0,-29.0,-4.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Astrolillo (native:149)

French alias: Le Lampionaute. Type: DUNGEON_4_ROOMS. Native level: 156. Maps: [456].

Species pool: Asesino encapuchado [4767] level 157-165, Mago encapuchado [4768] level 157-165, Protector encapuchado [4769] level 157-165, Javeho [4924] level 173-178

### Guide composition

[lampionaute](https://methodwakfu.com/pvm/lampionaute/); extraction=partial; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Protecteur Encapuchonné [ref 4769, monster], 2 × Mage Encapuchonné [ref 4768, monster], 2 × Assassin Encapuchonné [ref 4767, monster]
- Room 2 (unknown): Unknown composition
- Room 3 (unknown): Unknown composition
- Room 4 (complete): 3 × Mage Encapuchonné [ref 4768, monster], 2 × Protecteur Encapuchonné [ref 4769, monster], 2 × Assassin Encapuchonné [ref 4767, monster]
- Room 5 (unknown): Unknown composition
- Room 6 (complete): 5 × Punching-Boule [ref None, monster]
- Room 7 (complete): 3 × Mage Encapuchonné [ref 4768, monster], 3 × Protecteur Encapuchonné [ref 4769, monster], 2 × Assassin Encapuchonné [ref 4767, monster]
- Room 8 (complete): 1 × Javého [ref 4924, boss]

### Native entrance and interiors

Entry map 235, object 17373, destination 1000, template 152. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 20, 'GenericActivableInteractiveElement': 14, 'AudioMarker': 2, 'BackgroundDisplay': 2, 'Stool': 11}.

- Internal transport object 17303 on map 456: map 456 (-5,-83,0), criterion=empty, item=0
- Internal transport object 17308 on map 456: map 456 (-5,-155,0), criterion=empty, item=0
- Internal transport object 17312 on map 456: map 456 (-59,-83,0), criterion=empty, item=0
- Internal transport object 17311 on map 456: map 456 (-59,-11,0), criterion=empty, item=0
- Internal transport object 17304 on map 456: map 456 (-5,-11,0), criterion=empty, item=0
- Internal transport object 17306 on map 456: map 456 (-5,-11,0), criterion=empty, item=0
- Internal transport object 17314 on map 456: map 456 (-49,-155,0), criterion=empty, item=0
- Internal transport object 17316 on map 456: map 456 (-49,-155,0), criterion=empty, item=0
- Internal transport object 17318 on map 456: map 456 (-49,-83,0), criterion=empty, item=0
- Internal transport object 17317 on map 456: map 456 (-49,-11,0), criterion=empty, item=0
- Internal transport object 17313 on map 456: map 456 (-6,-226,0), criterion=empty, item=0
- Internal transport object 17346 on map 456: map 456 (-60,-151,0), criterion=empty, item=0
- Internal transport object 17315 on map 456: map 456 (-6,-226,0), criterion=empty, item=0
- Internal transport object 17319 on map 456: map 456 (-61,-224,7), criterion=empty, item=0
- Internal transport object 17309 on map 456: map 456 (5,-83,0), criterion=empty, item=0
- Internal transport object 17310 on map 456: map 456 (5,-155,0), criterion=empty, item=0
- Internal transport object 17305 on map 456: map 456 (5,-227,0), criterion=empty, item=0
- Internal transport object 17307 on map 456: map 456 (5,-227,0), criterion=empty, item=0

### Local implementation

lampionaute v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=7.

- Configured room 1: 2 × Protecteur Encapuchonné [4769], 2 × Mago encapuchado [4768], 2 × Protector encapuchado [4769], 1 × Javeho [4924], 1 × Asesino encapuchado [4767]
- Configured room 2: 1 × Mago encapuchado [4768], 1 × Protector encapuchado [4769], 1 × Javeho [4924], 1 × Asesino encapuchado [4767], 1 × Mago encapuchado [4768], 1 × Protector encapuchado [4769], 1 × Javeho [4924], 1 × Asesino encapuchado [4767]
- Configured room 3: 1 × Protector encapuchado [4769], 1 × Javeho [4924], 1 × Asesino encapuchado [4767], 1 × Mago encapuchado [4768], 1 × Protector encapuchado [4769], 1 × Javeho [4924], 1 × Asesino encapuchado [4767], 1 × Mago encapuchado [4768]
- Configured room 4: 3 × Javeho [4924], 2 × Protecteur Encapuchonné [4769], 2 × Mago encapuchado [4768], 1 × Protector encapuchado [4769]
- Configured room 5: 1 × Asesino encapuchado [4767], 1 × Mago encapuchado [4768], 1 × Protector encapuchado [4769], 1 × Javeho [4924], 1 × Asesino encapuchado [4767], 1 × Mago encapuchado [4768], 1 × Protector encapuchado [4769], 1 × Javeho [4924]
- Configured room 6: 5 × Mago encapuchado [4768], 1 × Protector encapuchado [4769], 1 × Javeho [4924], 1 × Asesino encapuchado [4767]
- Configured room 7: 3 × Protector encapuchado [4769], 3 × Protecteur Encapuchonné [4769], 2 × Asesino encapuchado [4767]
- Configured room 8: 1 × Javého [4924]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Miasmausoleo (native:101)

French alias: Le Misolée. Type: DUNGEON_3_ROOMS. Native level: 81. Maps: [965].

Species pool: Aplastelero [3732] level 89-93, Kadavérica [3733] level 83-87, Gárgolo [3734] level 85-89, Viktoria Franka Enstein [3735] level 98-103

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 327, object 25352, destination 2219, template 104. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 1, 'Door': 5}.

- Door: 25302 at map 965 (26.0,-14.0,0.0); 25356 at map 965 (27.0,-14.0,0.0); 25303 at map 965 (20.0,-28.0,31.0); 25301 at map 965 (26.0,5.0,0.0); 25355 at map 965 (25.0,5.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Pasto Real (native:137)

French alias: Le Papaturage Royal. Type: DUNGEON_3_ROOMS. Native level: 36. Maps: [493].

Species pool: Muuumusca [4755] level 38-42, Muuugritón [4756] level 40-44, Muuugresa [4757] level 40-48, Muuugresa Real [4758] level 53-58

### Guide composition

[le-papaturage-royal](https://methodwakfu.com/pvm/le-papaturage-royal/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 3 × Moogrr [ref 4757, monster], 2 × Moogrron [ref 4756, monster], 1 × Moomouche [ref 4755, monster]
- Room 2 (complete): 3 × Moogrr [ref 4757, monster], 2 × Moogrron [ref 4756, monster], 2 × Moomouche [ref 4755, monster]
- Room 3 (complete): 1 × Moogrr Royale [ref 4758, boss], 2 × Moogrr [ref 4757, monster], 2 × Moogrron [ref 4756, monster], 2 × Moomouche [ref 4755, monster]

### Native entrance and interiors

Entry map 1134, object 17997, destination 1024, template 140. Criterion:

```text
not IsNeoServer()
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 1}.

- Door: 17721 at map 493 (-25.0,5.0,0.0); 17722 at map 493 (-31.0,0.0,0.0); 17723 at map 493 (-48.0,0.0,0.0)

### Local implementation

le-papaturage-royal v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 3 × Muuumusca [4755], 2 × Muuugritón [4756], 1 × Muuugresa [4757], 1 × Muuugresa Real [4758], 1 × Muuumusca [4755]
- Configured room 2: 3 × Muuugritón [4756], 2 × Muuugresa [4757], 2 × Muuugresa Real [4758], 1 × Muuumusca [4755]
- Configured room 3: 1 × Moogrr Royale [4758], 2 × Muuugresa Real [4758], 2 × Muuumusca [4755], 2 × Muuugritón [4756], 1 × Muuugresa [4757]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Cono de Crújian Jerry (native:63)

French alias: Le Pot d'Hagën-Glass. Type: DUNGEON_3_ROOMS. Native level: 111. Maps: [510].

Species pool: Crugmita [2339] level 113-117, Cruken polar [2340] level 115-119, Cructita [2341] level 115-119, Cruji d'Or [2342] level 119-123, Crújian Jerry [2343] level 128-133

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 504, object 18053, destination 1100, template 64. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 4, 'Door': 3, 'AudioMarker': 2, 'GenericActivableInteractiveElement': 2}.

- Internal transport object 20084 on map 510: map 510 (100,5,0), criterion=GetItemQuantity(17578) > 0, item=0
- Internal transport object 20082 on map 510: map 510 (17,-18,-17), criterion=empty, item=0
- Door: 18020 at map 510 (-6.0,-39.0,0.0); 18021 at map 510 (8.0,-34.0,0.0); 18022 at map 510 (26.0,-25.0,-11.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Tofullero (native:27)

French alias: Le Tofulailler. Type: DUNGEON_3_ROOMS. Native level: 12. Maps: [1087].

Species pool: Tofu [4] level 8-12, Tofona [5] level 10-14, Bebé tofu [6] level 4-8, Gorditofu [704] level 14-18, Tofu Real [1259] level 23-28

### Guide composition

[le-tofulailler](https://methodwakfu.com/pvm/le-tofulailler/); extraction=unknown; version=None; client version match=unverified.


### Native entrance and interiors

Entry map 527, object 26962, destination 2518, template 29. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 1}.

- Door: 26873 at map 1087 (13.0,-38.0,-8.0); 26874 at map 1087 (23.0,-35.0,-8.0); 26875 at map 1087 (39.0,-26.0,-12.0)

### Local implementation

le-tofulailler v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Tofu [4], 1 × Tofona [5], 1 × Bebé tofu [6], 1 × Gorditofu [704], 1 × Tofu Real [1259], 1 × Tofu [4], 1 × Tofona [5], 1 × Bebé tofu [6]
- Configured room 2: 1 × Tofona [5], 1 × Bebé tofu [6], 1 × Gorditofu [704], 1 × Tofu Real [1259], 1 × Tofu [4], 1 × Tofona [5], 1 × Bebé tofu [6], 1 × Gorditofu [704]
- Configured room 3: 1 × Bebé tofu [6], 1 × Gorditofu [704], 1 × Tofu Real [1259], 1 × Tofu [4], 1 × Tofona [5], 1 × Bebé tofu [6], 1 × Gorditofu [704], 1 × Tofu Real [1259]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Vid Vil (native:115)

French alias: Le Vignoble Ignoble. Type: DUNGEON_4_ROOMS. Native level: 141. Maps: [1079].

Species pool: Suma sacerdotisa Sydonia [4060] level 141-141, Copampino [4061] level 142-142, Doña Borgoña [4062] level 138-138, Don Peleón [4063] level 136-136, Hozpriora [4064] level 134-134

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 323, object 26766, destination 2485, template 118. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 8, 'ZoneTrigger': 2}.

- Internal transport object 26745 on map 1079: map 1079 (93,-62,0), criterion=empty, item=0
- Internal transport object 26750 on map 1079: map 1079 (93,-76,0), criterion=empty, item=0
- Internal transport object 26746 on map 1079: map 1079 (-6,-5,0), criterion=empty, item=0
- Internal transport object 26747 on map 1079: map 1079 (165,-134,0), criterion=empty, item=0
- Internal transport object 26751 on map 1079: map 1079 (265,-250,0), criterion=empty, item=0
- Internal transport object 26748 on map 1079: map 1079 (93,-76,0), criterion=empty, item=0
- ZoneTrigger: 26913 at map 1079 (265.0,-250.0,0.0); 26812 at map 1079 (165.0,-135.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Campos Hupremos (native:25)

French alias: Les Champs Pourchan. Type: DUNGEON_3_ROOMS. Native level: 36. Maps: [910].

Species pool: Diente de león diabólico [94] level 44-48, Rosa demoníaca [95] level 40-44, Mala semilla de girasol [135] level 38-42, Girasol explosivo [1274] level 44-48, Glotón espinoso [1275] level 40-44, Diente de Lennon, el Universal [1636] level 45-45, Planta Carnívora [1726] level 53-58, Rosa tenebrosa [4544] level 40-44

### Guide composition

[les-champs-pourchan](https://methodwakfu.com/pvm/les-champs-pourchan/); extraction=partial; version=1.67; client version match=unverified.

- Room 1 (unknown): 7 × Random monster species [ref None, monster]
- Room 2 (unknown): 7 × Random monster species [ref None, monster]
- Room 3 (partial): 1 × Plante Carnivore [ref 1726, boss], 7 × Random monster species [ref None, monster]
- Room 4 (complete): 1 × Pissdane l’insipide [ref 1636, monster], 1 × Tournesol éclatant [ref None, monster], 1 × Pissenlit diabolique [ref 94, monster], 1 × Rose démoniaque [ref 95, monster], 1 × Glouton épineux [ref None, monster], 1 × Pissenlion [ref 135, monster]

### Native entrance and interiors

Entry map 1134, object 14571, destination 2069, template 27. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 1, 'Door': 5, 'Board': 1, 'BackgroundDisplay': 1, 'LootChest': 1}.

- Door: 24134 at map 910 (15.0,44.0,0.0); 24136 at map 910 (5.0,52.0,0.0); 24135 at map 910 (15.0,45.0,0.0); 24132 at map 910 (22.0,37.0,0.0); 26490 at map 910 (28.0,41.0,0.0)
- LootChest: 26489 at map 910 (32.0,41.0,0.0)
- Board: 24131 at map 910 (15.0,36.0,0.0)

### Local implementation

les-champs-pourchan v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 7 × Diente de león diabólico [94], 1 × Rosa demoníaca [95]
- Configured room 2: 7 × Rosa demoníaca [95], 1 × Mala semilla de girasol [135]
- Configured room 3: 1 × Plante Carnivore [1726], 7 × Girasol explosivo [1274]
- Configured room 4: 1 × Girasol explosivo [1274], 1 × Glotón espinoso [1275], 1 × Diente de Lennon, el Universal [1636], 1 × Planta Carnívora [1726], 1 × Rosa tenebrosa [4544], 1 × Pissenlion [135], 1 × Rosa demoníaca [95], 1 × Mala semilla de girasol [135]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Ratacumbas (native:12)

French alias: Les Ratacombes. Type: DUNGEON_2_ROOMS. Native level: 66. Maps: [477].

Species pool: Ratíquita [1787] level 70-70, Ratuesa [1789] level 72-72, Ratocina [1790] level 74-74, Ratafiés [2313] level 84-84

### Guide composition

[donjons-les-ratacombes](https://methodwakfu.com/pvm/donjons/les-ratacombes/); extraction=complete; version=1.70; client version match=unverified.

- Room 1 (complete): 3 × Ratchitik Imbibé [ref None, monster], 3 × Rat’ Os Imbibé [ref None, monster]
- Room 2 (complete): 1 × Ratachouille [ref 2313, boss], 3 × Ratchitik Imbibé [ref None, monster], 2 × Rat’ Os Imbibé [ref None, monster], 1 × Ratgnagna [ref 1790, monster]

### Native entrance and interiors

Entry map 323, object 19010, destination 1217, template 15. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 4, 'GenericActivableInteractiveElement': 1, 'Door': 2}.

- Internal transport object 26463 on map 477: map 477 (-60,-18,0), criterion=empty, item=0
- Internal transport object 26464 on map 477: map 477 (-2,-91,0), criterion=empty, item=0
- Door: 18823 at map 477 (-63.0,2.0,-16.0); 18824 at map 477 (-62.0,2.0,-16.0)

### Local implementation

donjons-les-ratacombes v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 3 × Ratíquita [1787], 3 × Ratuesa [1789], 1 × Ratocina [1790], 1 × Ratafiés [2313]
- Configured room 2: 1 × Ratachouille [2313], 3 × Ratocina [1790], 2 × Ratafiés [2313], 1 × Ratíquita [1787], 1 × Ratuesa [1789]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Caseta del Yech'Ti'Wawa (native:8)

French alias: Niche du Yech'Ti'Wawa. Type: DUNGEON_2_ROOMS. Native level: 96. Maps: [518].

Species pool: Cuermut [2364] level 98-102, Cuerbela [2365] level 100-104, Mamiluba [2366] level 100-104, Mimut rabioso [2367] level 104-108, Yech'Ti'Wawa [2368] level 113-118

### Guide composition

[niche-yech-ti-wawa](https://methodwakfu.com/pvm/niche-yech-ti-wawa/); extraction=complete; version=1.59; client version match=unverified.

- Room 1 (complete): 2 × Mulmounes [ref None, monster], 2 × Cormounes [ref None, monster], 2 × Corbamouths [ref None, monster], 2 × Mulmouths Enragés [ref None, monster]
- Room 2 (complete): 1 × YeCh’Ti’Wawa [ref 2368, boss], 2 × Mulmounes [ref None, monster], 2 × Cormounes [ref None, monster], 2 × Corbamouths [ref None, monster], 2 × Mulmouths Enragés [ref None, monster]

### Native entrance and interiors

Entry map 507, object 18059, destination 1101, template 11. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 2}.

- Door: 18056 at map 518 (-38.0,16.0,0.0); 18057 at map 518 (-38.0,15.0,0.0); 18058 at map 518 (-39.0,20.0,0.0)

### Local implementation

niche-yech-ti-wawa v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 2 × Cuermut [2364], 2 × Cuerbela [2365], 2 × Mamiluba [2366], 2 × Mimut rabioso [2367]
- Configured room 2: 1 × Cuerbela [2365], 2 × Mamiluba [2366], 2 × Mimut rabioso [2367], 2 × Yech'Ti'Wawa [2368], 2 × Cuermut [2364]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Necromundo (native:196)

French alias: Nécromonde. Type: DUNGEON_3_PLAYERS. Native level: 216. Maps: [1403].

Species pool: Toross Mordal [5589] level 233-238

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1365, object 34843, destination 4654, template 188. Criterion:

```text
(empty on this entry)
```

Object counts: {'GenericActivableInteractiveElement': 5, 'Stele': 1, 'Door': 5, 'Teleporter': 1}.

- Door: 34835 at map 1403 (14.0,-1.0,0.0); 34838 at map 1403 (14.0,2.0,0.0); 34840 at map 1403 (14.0,3.0,0.0); 34836 at map 1403 (14.0,0.0,0.0); 34837 at map 1403 (14.0,1.0,0.0)
- Stele: 34852 at map 1403 (-6.0,-8.0,4.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Necrópelis de Morbax (native:150)

French alias: Nécropoil de Morbax. Type: DUNGEON_4_ROOMS. Native level: 81. Maps: [296].

Species pool: Chafo, el del Ocho [1750] level 95-95, Chaferloko, Rey Chafer [4739] level 98-103, Chafer arquero [4740] level 85-89, Chafer de élite [4741] level 93-98, Chafer lancero [4742] level 83-87, Chafer arquero de la mina [4881] level 85-89, Chafer de élite de la mina [4882] level 89-93, Chafer lancero de la mina [4883] level 83-87

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1137, object 14584, destination 742, template 153. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 7, 'AudioMarker': 5, 'GenericActivableInteractiveElement': 3, 'LootChest': 2, 'Door': 3, 'PositionTrigger': 1, 'Collector': 1}.

- Internal transport object 13331 on map 296: map 296 (71,13,0), criterion=empty, item=0
- Internal transport object 31460 on map 296: map 296 (80,-1,0), criterion=empty, item=0
- Internal transport object 13339 on map 296: map 296 (-11,13,-18), criterion=empty, item=0
- Internal transport object 31461 on map 296: map 296 (-39,-80,21), criterion=empty, item=0
- Door: 13324 at map 296 (-35.0,24.0,-16.0); 13323 at map 296 (-42.0,7.0,0.0); 31462 at map 296 (4.0,-80.0,1.0)
- LootChest: 13818 at map 296 (-36.0,-87.0,20.0); 26493 at map 296 (64.0,9.0,0.0)
- Collector: 13330 at map 296 (77.0,-12.0,0.0)
- PositionTrigger: 32173 at map 296 (68.0,-3.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neoala de la Embajadora (native:214)

French alias: Néo-Aile de l'Ambassadrice. Type: DUNGEON_2_ROOMS. Native level: 111. Maps: [1456].

Species pool: Bárbaro norteño [2344] level 115-119, Guarda norteño [2345] level 115-119, Arquero norteño [2346] level 113-117, Rastreador norteño [2347] level 125-129, Neokya, Mizz Frizz [5799] level 128-133

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 521, object 18068, destination 4754, template 206. Criterion:

```text
IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 6
```

Object counts: {'Door': 1, 'Teleporter': 2, 'GenericActivableInteractiveElement': 1}.

- Door: 35303 at map 1456 (12.0,13.0,-12.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neoantro del Cuervo Negro (native:213)

French alias: Néo-Antre du Corbeau Noir. Type: ULTIMATE_BOSS. Native level: 96. Maps: [1447].

Species pool: Neocuervo Negro [5797] level 110-110

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 962, object 25245, destination 4744, template 205. Criterion:

```text
not GetBooleanSystemConfiguration("beta.mode") and IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 5
```

Object counts: {'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neocastillo de Wagnar (native:212)

French alias: Néo-Château de Wagnar. Type: DUNGEON_3_ROOMS. Native level: 81. Maps: [1452].

Species pool: Murciego rechoncho [1825] level 85-89, Ghul [1827] level 85-89, Ghulotony [1828] level 89-93, Neovampyro [5796] level 95-95

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1232, object 30694, destination 4746, template 204. Criterion:

```text
IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 4
```

Object counts: {'Teleporter': 6, 'ZoneTrigger': 2}.

- Internal transport object 35335 on map 1452: map 1452 (92,-66,37), criterion=IsNeoServer(), item=0
- Internal transport object 35338 on map 1452: map 1452 (99,-73,37), criterion=IsNeoServer(), item=0
- Internal transport object 35336 on map 1452: map 1452 (5,-6,16), criterion=IsNeoServer(), item=0
- Internal transport object 35337 on map 1452: map 1452 (11,-108,0), criterion=IsNeoServer(), item=0
- ZoneTrigger: 35341 at map 1452 (11.0,-114.0,0.0); 35340 at map 1452 (5.0,11.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neocastillo del Wey Wabbit (native:216)

French alias: Néo-Château du Wa Wabbit. Type: DUNGEON_3_PLAYERS. Native level: 141. Maps: [1453].

Species pool: Tiwadow wabbit [2577] level 149-153, Caballewo wabbit [2578] level 147-151, Guawdia wabbit [2579] level 143-147, Wobot [2580] level 147-151, Jefe wobot [2581] level 147-151, Neowey Wabbit [5803] level 158-163

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1393, object 34667, destination 4751, template 208. Criterion:

```text
(IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 8)
and not (IsAchievementRunning(5182)
and IsAchievementObjectiveComplete(10854)
and not IsAchievementObjectiveComplete(10855))
and not (IsAchievementRunning(5187)
and IsAchievementObjectiveComplete(10774)
and not IsAchievementObjectiveComplete(10775))
```

Object counts: {'GenericActivableInteractiveElement': 6, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neociudad Prohibida (native:218)

French alias: Néo-Cité Interdite. Type: DUNGEON_3_PLAYERS. Native level: 171. Maps: [1457].

Species pool: Pandikaze [5041] level 175-179, Pandido [5042] level 179-183, Pandócil [5043] level 173-177, Neopandora [5805] level 188-193

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1252, object 31868, destination 4755, template 210. Criterion:

```text
IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 10
```

Object counts: {'GenericActivableInteractiveElement': 6, 'Teleporter': 1, 'Door': 3}.

- Door: 35296 at map 1457 (12.0,20.0,0.0); 35295 at map 1457 (11.0,20.0,0.0); 35294 at map 1457 (10.0,20.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neohacienda de la Balinería (native:211)

French alias: Néo-Domaine du Petit Groin. Type: DUNGEON_3_ROOMS. Native level: 66. Maps: [1458].

Species pool: Jabatillo [4760] level 66-68, Jabalina [4761] level 70-74, Balí agresivo [4762] level 74-78, Balí [4766] level 68-72, Neobalí Real [5795] level 83-88

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1136, object 14578, destination 4756, template 203. Criterion:

```text
IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 3
```

Object counts: {'Teleporter': 4, 'Collector': 1, 'Door': 2, 'LootChest': 1, 'BackgroundDisplay': 1, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 35311 on map 1458: map 1458 (65,-149,0), criterion=IsNeoServer(), item=0
- Internal transport object 35364 on map 1458: map 1458 (52,-43,-24), criterion=IsNeoServer(), item=0
- Door: 35309 at map 1458 (57.0,-34.0,-24.0); 35310 at map 1458 (73.0,-47.0,-12.0)
- LootChest: 35365 at map 1458 (63.0,-152.0,0.0)
- Collector: 35347 at map 1458 (48.0,-42.0,-24.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neomazmorra Abráknida (native:215)

French alias: Néo-Donjon Abraknyde. Type: DUNGEON_3_ROOMS. Native level: 126. Maps: [1454].

Species pool: Abráknido Ancestral [4886] level 134-138, Tronkónido oscuro [4887] level 130-134, Abráknido oscuro [4888] level 128-132, Neorroble Blando [5800] level 143-148

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1136, object 16936, destination 4752, template 207. Criterion:

```text
IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 7
```

Object counts: {'Door': 17, 'Teleporter': 2, 'GenericActivableInteractiveElement': 1, 'Stele': 1}.

- Door: 35355 at map 1454 (4.0,-31.0,-28.0); 35359 at map 1454 (3.0,-34.0,-28.0); 35360 at map 1454 (4.0,-34.0,-28.0); 35361 at map 1454 (4.0,-36.0,-28.0); 35349 at map 1454 (5.0,-31.0,-28.0); 35350 at map 1454 (6.0,-36.0,-28.0); 35352 at map 1454 (4.0,-28.0,-28.0); 35353 at map 1454 (4.0,-31.0,-29.0); 35354 at map 1454 (5.0,-32.0,-28.0); 35357 at map 1454 (3.0,-33.0,-28.0); 35356 at map 1454 (3.0,-32.0,-28.0); 35348 at map 1454 (5.0,-30.0,-28.0); 35351 at map 1454 (5.0,-36.0,-28.0); 35358 at map 1454 (4.0,-33.0,-28.0); 35362 at map 1454 (4.0,-39.0,-28.0); 35318 at map 1454 (34.0,-31.0,-14.0); 35317 at map 1454 (42.0,-14.0,-14.0)
- Stele: 35319 at map 1454 (23.0,-33.0,-28.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neomazmorra Martilloseco (native:210)

French alias: Néo-Donjon Marteaux-Aigris. Type: DUNGEON_3_ROOMS. Native level: 51. Maps: [1455].

Species pool: Marthos [5385] level 55-59, Parraguás [5386] level 53-57, Escudacha [5387] level 59-63, Cire Momore [5417] level 68-73, Neogoel el Gólem [5794] level 68-73

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1364, object 33645, destination 4753, template 202. Criterion:

```text
IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 2
```

Object counts: {'Door': 2, 'Teleporter': 2, 'GenericActivableInteractiveElement': 1}.

- Door: 35298 at map 1455 (20.0,-9.0,0.0); 35299 at map 1455 (32.0,-35.0,-24.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neopasto Real (native:209)

French alias: Néo-Papaturage Royal. Type: DUNGEON_3_ROOMS. Native level: 36. Maps: [1450].

Species pool: Muuumusca [4755] level 38-42, Muuugritón [4756] level 40-44, Muuugresa [4757] level 40-48, Neomuuugresa Real [5793] level 53-58

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1134, object 17997, destination 4740, template 201. Criterion:

```text
IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 1
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 1, 'Door': 2}.

- Door: 35272 at map 1450 (24.0,0.0,0.0); 35271 at map 1450 (41.0,0.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neopío Lajop (native:208)

French alias: Néo-Piou Lahoupe. Type: DUNGEON_3_ROOMS. Native level: 21. Maps: [1460].

Species pool: Pío rojo [87] level 22-30, Pío azul [88] level 22-30, Pío verde [90] level 22-30, Pío violeta [271] level 22-30, Piolina [272] level 26-34, Neopío Real [5792] level 38-43

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 527, object 24024, destination 4764, template 200. Criterion:

```text
IsNeoServer()
```

Object counts: {'Teleporter': 2, 'Door': 2, 'GenericActivableInteractiveElement': 1, 'LootChest': 1}.

- Door: 35285 at map 1460 (34.0,-2.0,0.0); 35286 at map 1460 (34.0,11.0,0.0)
- LootChest: 35288 at map 1460 (26.0,21.0,-1.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neopico del Monte Zinit (native:219)

French alias: Néo-Pointe du Mont Zinit. Type: ULTIMATE_BOSS. Native level: 186. Maps: [1446].

Species pool: Neoogrest [5806] level 230-230

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1124, object 28582, destination 4743, template 211. Criterion:

```text
not GetBooleanSystemConfiguration("beta.mode") and IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 11
```

Object counts: {'BackgroundDisplay': 1, 'Teleporter': 1, 'GenericActivableInteractiveElement': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neopastos de los Jalatós (native:207)

French alias: Néo-Pâturages des Bouftous. Type: DUNGEON_3_ROOMS. Native level: 12. Maps: [1459].

Species pool: Jalató [1] level 8-12, Jalatín negro [2] level 4-8, Jefe de guerra jalató [3] level 14-18, Jalatín blanco [39] level 4-8, Jalalínea [41] level 10-14, Neojalató Real [5791] level 23-28

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 527, object 26842, destination 4759, template 199. Criterion:

```text
IsNeoServer()
```

Object counts: {'Teleporter': 6, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 35279 on map 1459: map 1459 (170,8,0), criterion=IsNeoServer(), item=0
- Internal transport object 35281 on map 1459: map 1459 (169,-113,0), criterion=IsNeoServer(), item=0
- Internal transport object 35282 on map 1459: map 1459 (168,-7,0), criterion=IsNeoServer(), item=0
- Internal transport object 35280 on map 1459: map 1459 (36,-8,0), criterion=IsNeoServer(), item=0

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Neotymabar (native:217)

French alias: Néo-Roub'Bar. Type: DUNGEON_2_ROOMS. Native level: 156. Maps: [1451].

Species pool: Tym Adorrojo [2013] level 160-162, Tymadortista [2014] level 164-168, Tymador desbordado [2015] level 158-162, Rompetibias [2016] level 173-178, Remington Smis [2018] level 173-178, Neoremington Smis [5804] level 173-178

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1208, object 31685, destination 4745, template 209. Criterion:

```text
IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 9
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 2, 'Door': 1}.

- Door: 35276 at map 1451 (34.0,5.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Palacio de Rushu (native:181)

French alias: Palais de Rushu. Type: ULTIMATE_BOSS. Native level: 216. Maps: [1332].

Species pool: Rushu [5306] level 230-230

### Guide composition

[palais-de-rushu](https://methodwakfu.com/pvm/boss-ultimes/palais-de-rushu/); extraction=unknown; version=None; client version match=unverified.


### Native entrance and interiors

Entry map 1342, object 33257, destination 4489, template 176. Criterion:

```text
not GetBooleanSystemConfiguration("beta.mode")
```

Object counts: {'GenericActivableInteractiveElement': 3, 'PositionTrigger': 1, 'Teleporter': 1}.

- PositionTrigger: 33183 at map 1332 (-32.0,4.0,-4.0)

### Local implementation

palais-de-rushu v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Rushu [5306], 1 × Rushu [5306], 1 × Rushu [5306], 1 × Rushu [5306], 1 × Rushu [5306], 1 × Rushu [5306], 1 × Rushu [5306], 1 × Rushu [5306]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Palacio de Tsu (native:147)

French alias: Palais du Tsu. Type: DUNGEON_3_ROOMS. Native level: 66. Maps: [165].

Species pool: Gran boo [4915] level 70-74, Moskito [4916] level 68-72, Sanguijuela Tsu Tsu [4917] level 74-78, Zar Tsu Tsu [4918] level 83-88

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1209, object 14574, destination 739, template 150. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 1, 'LootChest': 1}.

- Door: 5993 at map 165 (-32.0,31.0,-8.0); 5994 at map 165 (-38.0,28.0,-8.0); 5995 at map 165 (-52.0,21.0,0.0)
- LootChest: 13816 at map 165 (-59.0,28.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Palacio Zollo (native:73)

French alias: Palais Lenald. Type: DUNGEON_4_ROOMS. Native level: 126. Maps: [1397].

Species pool: Zollo Juniol [2550] level 132-136, Zollo [2551] level 130-134, Zollo viejo [2552] level 134-138, Zollo goldo [2553] level 128-132, Lin Shi, Empeladol Zollo [2556] level 143-148

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1384, object 34748, destination 4634, template 74. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 8, 'Stele': 1, 'GenericActivableInteractiveElement': 1, 'Door': 4}.

- Internal transport object 34746 on map 1397: map 1397 (-18,0,4), criterion=empty, item=0
- Internal transport object 34740 on map 1397: map 1397 (-71,-40,0), criterion=empty, item=0
- Internal transport object 34741 on map 1397: map 1397 (-73,36,0), criterion=empty, item=0
- Internal transport object 34742 on map 1397: map 1397 (-23,-8,0), criterion=empty, item=0
- Internal transport object 34743 on map 1397: map 1397 (-23,8,0), criterion=empty, item=0
- Internal transport object 34745 on map 1397: map 1397 (-200,-11,0), criterion=empty, item=0
- Internal transport object 34744 on map 1397: map 1397 (-200,-11,0), criterion=empty, item=0
- Door: 34751 at map 1397 (-93.0,-39.0,0.0); 34749 at map 1397 (-95.0,37.0,0.0); 34752 at map 1397 (-129.0,-39.0,16.0); 34750 at map 1397 (-131.0,37.0,16.0)
- Stele: 34857 at map 1397 (-223.0,-14.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Pío Lajop (native:26)

French alias: Piou Lahoupe. Type: DUNGEON_3_ROOMS. Native level: 21. Maps: [311].

Species pool: Pío rojo [87] level 22-30, Pío azul [88] level 22-30, Pío verde [90] level 22-30, Pío violeta [271] level 22-30, Piolina [272] level 26-34, Pío Real [1187] level 38-43

### Guide composition

[piou-lahoupe](https://methodwakfu.com/pvm/piou-lahoupe/); extraction=unknown; version=1.87; client version match=unverified.

- Room 1 (unknown): Unknown composition
- Room 2 (unknown): Unknown composition
- Room 3 (unknown): Unknown composition

### Native entrance and interiors

Entry map 527, object 24024, destination 2017, template 28. Criterion:

```text
not IsNeoServer()
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 1, 'LootChest': 1, 'Door': 2}.

- Door: 13823 at map 311 (24.0,13.0,0.0); 13824 at map 311 (24.0,0.0,0.0)
- LootChest: 26903 at map 311 (16.0,23.0,-1.0)

### Local implementation

piou-lahoupe v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Pío rojo [87], 1 × Pío azul [88], 1 × Pío verde [90], 1 × Pío violeta [271], 1 × Piolina [272], 1 × Pío Real [1187], 1 × Pío rojo [87], 1 × Pío azul [88]
- Configured room 2: 1 × Pío azul [88], 1 × Pío verde [90], 1 × Pío violeta [271], 1 × Piolina [272], 1 × Pío Real [1187], 1 × Pío rojo [87], 1 × Pío azul [88], 1 × Pío verde [90]
- Configured room 3: 1 × Pío verde [90], 1 × Pío violeta [271], 1 × Piolina [272], 1 × Pío Real [1187], 1 × Pío rojo [87], 1 × Pío azul [88], 1 × Pío verde [90], 1 × Pío violeta [271]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Meseta de los Altos Vuelos (native:100)

French alias: Plateau des Haut-Vents. Type: ULTIMATE_BOSS. Native level: 156. Maps: [959].

Species pool: Garras de Acero [3582] level 170-170

### Guide composition

[boss-ultimes-plateau-des-hauts-vents](https://methodwakfu.com/pvm/boss-ultimes/plateau-des-hauts-vents/); extraction=partial; version=1.64; client version match=unverified.

- Room 1 (partial): None × Serre d’Acier [ref None, boss]

### Native entrance and interiors

Entry map 962, object 25246, destination 2205, template 103. Criterion:

```text
not GetBooleanSystemConfiguration("beta.mode")
```

Object counts: {'Teleporter': 1, 'ZoneTrigger': 1}.

- ZoneTrigger: 25237 at map 959 (0.0,0.0,0.0)

### Local implementation

boss-ultimes-plateau-des-hauts-vents v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Garras de Acero [3582], 1 × Garras de Acero [3582], 1 × Garras de Acero [3582], 1 × Garras de Acero [3582], 1 × Garras de Acero [3582], 1 × Garras de Acero [3582], 1 × Garras de Acero [3582], 1 × Garras de Acero [3582]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Pico del Monte Zinit (native:131)

French alias: Pointe du Mont Zinit. Type: ULTIMATE_BOSS. Native level: 186. Maps: [1156].

Species pool: Ogrest [4378] level 230-230

### Guide composition

[boss-ultimes-pointe-du-mont-zinit](https://methodwakfu.com/pvm/boss-ultimes/pointe-du-mont-zinit/); extraction=complete; version=1.92; client version match=unverified.

- Room 1 (complete): 1 × Ogrest [ref 4378, boss]

### Native entrance and interiors

Entry map 1124, object 28582, destination 2904, template 134. Criterion:

```text
not GetBooleanSystemConfiguration("beta.mode") and not IsNeoServer()
```

Object counts: {'BackgroundDisplay': 1, 'StoppingPositionTrigger': 1, 'GenericActivableInteractiveElement': 1, 'Teleporter': 2}.


### Local implementation

boss-ultimes-pointe-du-mont-zinit v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Ogrest [4378], 1 × Ogrest [4378], 1 × Ogrest [4378], 1 × Ogrest [4378], 1 × Ogrest [4378], 1 × Ogrest [4378], 1 × Ogrest [4378], 1 × Ogrest [4378]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Pastos de los Jalatós (native:90)

French alias: Pâturages des Bouftous. Type: DUNGEON_3_ROOMS. Native level: 12. Maps: [1086].

Species pool: Jalató [1] level 8-12, Jalatín negro [2] level 4-8, Jefe de guerra jalató [3] level 14-18, Jalatín blanco [39] level 4-8, Jalalínea [41] level 10-14, Jalató Real [44] level 23-28

### Guide composition

[donjons-paturages-des-bouftous](https://methodwakfu.com/pvm/donjons/paturages-des-bouftous/); extraction=complete; version=1.87; client version match=unverified.

- Room 1 (complete): 1 × Boufton Blanc [ref 39, monster], 1 × Boufton Noir [ref 2, monster], 1 × Bouftou [ref 1, monster]
- Room 2 (complete): 2 × Chef de Guerre Bouftou [ref 3, monster], 1 × Boufette [ref 41, monster], 1 × Boufton Blanc [ref 39, monster], 1 × Bouftou [ref 1, monster]
- Room 3 (complete): 1 × Bouftou Royal [ref 44, boss], 2 × Chef de Guerre Bouftou [ref 3, monster], 1 × Bouftou [ref 1, monster], 2 × Boufette [ref 41, monster]

### Native entrance and interiors

Entry map 527, object 26842, destination 2504, template 91. Criterion:

```text
not IsNeoServer()
```

Object counts: {'Teleporter': 6, 'GenericActivableInteractiveElement': 1}.

- Internal transport object 26845 on map 1086: map 1086 (152,-10,0), criterion=not IsNeoServer(), item=0
- Internal transport object 26849 on map 1086: map 1086 (0,-26,0), criterion=not IsNeoServer(), item=0
- Internal transport object 26850 on map 1086: map 1086 (151,-149,0), criterion=not IsNeoServer(), item=0
- Internal transport object 26853 on map 1086: map 1086 (150,-25,0), criterion=not IsNeoServer(), item=0

### Local implementation

donjons-paturages-des-bouftous v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Boufton Blanc [39], 1 × Boufton Noir [2], 1 × Bouftou [1]
- Configured room 2: 2 × Chef de Guerre Bouftou [3], 1 × Boufette [41], 1 × Boufton Blanc [39], 1 × Bouftou [1]
- Configured room 3: 1 × Bouftou Royal [44], 2 × Chef de Guerre Bouftou [3], 1 × Bouftou [1], 2 × Boufette [41]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Guarida de Kali (native:121)

French alias: Repaire de Kali. Type: DUNGEON_3_PLAYERS. Native level: 156. Maps: [1129].

Species pool: Berserkermana [4214] level 160-166, Tankorazón [4215] level 160-166, Sangrocente [4216] level 160-166, Kali [4217] level 173-178

### Guide composition

[repaire-de-kali](https://methodwakfu.com/pvm/repaire-de-kali/); extraction=partial; version=1.71; client version match=unverified.

- Room 1 (partial): 1 × Soeur Zerker [ref 4214, monster], 1 × Ensaigneur [ref 4216, monster], 1 × Tankoeur [ref 4215, monster], None × Kali [ref 4217, boss]

### Native entrance and interiors

Entry map 1122, object 27955, destination 2627, template 124. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 6, 'Door': 3}.

- Door: 27526 at map 1129 (-33.0,-60.0,-4.0); 27525 at map 1129 (-33.0,-62.0,-4.0); 27524 at map 1129 (-33.0,-61.0,-4.0)

### Local implementation

repaire-de-kali v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=0.

- Configured room 1: 1 × Soeur Zerker [4214], 1 × Ensaigneur [4216], 1 × Tankoeur [4215], 1 × Kali [4217], 1 × Berserkermana [4214], 1 × Tankorazón [4215], 1 × Sangrocente [4216], 1 × Kali [4217]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Guarida de los Magik Riktus (native:138)

French alias: Repaire des Magik Riktus. Type: DUNGEON_3_ROOMS. Native level: 96. Maps: [1249].

Species pool: Maltrahzero [1166] level 97-105, Malapiel [1167] level 97-105, Malajeta [1168] level 97-105, Malcac [1169] level 97-105, Sombrero Mágiko [4520] level 113-118

### Guide composition

[repaire-des-magik-riktus](https://methodwakfu.com/pvm/repaire-des-magik-riktus/); extraction=partial; version=1.67; client version match=unverified.

- Room 1 (partial): 1 × Malocac [ref 1169, monster], 1 × Malopo [ref 1167, monster], 1 × Malobouc [ref 1168, monster], 1 × Malus [ref None, monster], 2 × Riktus différent aléatoire (type non précisé) [ref None, monster]
- Room 2 (complete): 2 × Malocac [ref 1169, monster], 2 × Malopo [ref 1167, monster], 2 × Malobouc [ref 1168, monster], 2 × Malus [ref None, monster]
- Room 3 (complete): 1 × Chapo Magik [ref 4520, boss]

### Native entrance and interiors

Entry map 1134, object 31453, destination 3946, template 141. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 6, 'Door': 3, 'GenericActivableInteractiveElement': 2}.

- Internal transport object 31399 on map 1249: map 1249 (76,-62,0), criterion=empty, item=0
- Internal transport object 31401 on map 1249: map 1249 (163,-137,-1), criterion=empty, item=0
- Internal transport object 31400 on map 1249: map 1249 (-6,-7,0), criterion=empty, item=0
- Internal transport object 31402 on map 1249: map 1249 (72,-58,2), criterion=empty, item=0
- Door: 31404 at map 1249 (70.0,-47.0,0.0); 31789 at map 1249 (73.0,-58.0,0.0); 31788 at map 1249 (72.0,-58.0,0.0)

### Local implementation

repaire-des-magik-riktus v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Maltrahzero [1166], 1 × Malapiel [1167], 1 × Malajeta [1168], 1 × Malcac [1169], 2 × Sombrero Mágiko [4520], 1 × Maltrahzero [1166], 1 × Malapiel [1167]
- Configured room 2: 2 × Malapiel [1167], 2 × Malajeta [1168], 2 × Malcac [1169], 2 × Sombrero Mágiko [4520]
- Configured room 3: 1 × Chapo Magik [4520]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Guarida de los Supervillanos (native:79)

French alias: Repaire des Super-Vilains. Type: DUNGEON_3_PLAYERS. Native level: 96. Maps: [704].

Species pool: Merkator [2708] level 113-118, Kralaman [2709] level 113-118, Megatún [2710] level 113-118, Puerkevil [2714] level 113-118

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 709, object 20372, destination 1402, template 80. Criterion:

```text
(empty on this entry)
```

Object counts: {'GenericActivableInteractiveElement': 5, 'Door': 3, 'Teleporter': 1}.

- Door: 33319 at map 704 (1.0,-1.0,0.0); 33321 at map 704 (1.0,1.0,0.0); 33320 at map 704 (1.0,0.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Tymabar (native:144)

French alias: Roub'Bar. Type: DUNGEON_2_ROOMS. Native level: 156. Maps: [1250].

Species pool: Tym Adorrojo [2013] level 160-162, Tymadortista [2014] level 164-168, Tymador desbordado [2015] level 158-162, Rompetibias [2016] level 173-178, Remington Smis [2018] level 173-178

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1208, object 31685, destination 4021, template 147. Criterion:

```text
not IsNeoServer()
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 3}.

- Door: 31477 at map 1250 (-52.0,-19.0,0.0); 31478 at map 1250 (-53.0,-19.0,0.0); 31476 at map 1250 (-68.0,-14.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Colmena Madre Arenóptera (native:192)

French alias: Ruche-mère Sabléoptère. Type: DUNGEON_2_ROOMS. Native level: 141. Maps: [1395].

Species pool: Mantisesina [5475] level 145-149, Escarabasto [5476] level 149-153, Chaqueador [5477] level 143-147, Bombyxolita Endopterígota [5478] level 158-163

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1384, object 34670, destination 4580, template 184. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 1, 'Teleporter': 2, 'Stele': 1, 'GenericActivableInteractiveElement': 1}.

- Door: 34673 at map 1395 (1.0,-35.0,0.0)
- Stele: 34858 at map 1395 (23.0,-42.0,-12.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Rushu (native:222)

French alias: Rushu. Type: DUNGEON_ARCADE. Native level: 51. Maps: [1391].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 346, object 35959, destination 4790, template 214. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Santuario de Mihmol (native:85)

French alias: Sanctuaire de Mihmol. Type: DUNGEON_3_PLAYERS. Native level: 126. Maps: [816].

Species pool: Victus [3043] level 130-134, Mihmol, el Empalador [3048] level 143-148, Hexaku [3050] level 134-138, Tsubo [3051] level 128-132

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 793, object 27325, destination 1609, template 86. Criterion:

```text
(empty on this entry)
```

Object counts: {'GenericActivableInteractiveElement': 7, 'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Santuario de los Dragohuevos (native:129)

French alias: Sanctuaire des Dragoeufs. Type: DUNGEON_3_ROOMS. Native level: 186. Maps: [1132].

Species pool: Dragoloso [4208] level 188-192, Dragohuevo cocido [4209] level 194-198, Dragohuevo guerrero [4210] level 190-194, Huevo antiguo [4400] level 203-208, Aguabrial [5165] level 200-200

### Guide composition

[sanctuaire-des-dragoeufs](https://methodwakfu.com/pvm/sanctuaire-des-dragoeufs/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Dragoeuf Guerrier [ref 4210, monster], 2 × Dragoeu’r [ref 4208, monster], 2 × Dragoeuf à la coque [ref 4209, monster]
- Room 2 (complete): 2 × Dragoeuf Guerrier [ref 4210, monster], 3 × Dragoeu’r [ref 4208, monster], 2 × Dragoeuf à la coque [ref 4209, monster]
- Room 3 (complete): 2 × Dragoeuf Guerrier [ref 4210, monster], 3 × Dragoeu’r [ref 4208, monster], 3 × Dragoeuf à la coque [ref 4209, monster]
- Room 4 (complete): 1 × Oeuf Antique [ref 4400, unknown], 3 × Dragoeuf Guerrier [ref 4210, monster], 2 × Dragoeu’r [ref 4208, monster], 2 × Dragoeuf à la coque [ref 4209, monster]

### Native entrance and interiors

Entry map 1124, object 28245, destination 2727, template 132. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 6, 'Stele': 1}.

- Door: 28234 at map 1132 (-11.0,-72.0,9.0); 28232 at map 1132 (12.0,-41.0,9.0); 28233 at map 1132 (18.0,-52.0,9.0)
- Stele: 34874 at map 1132 (-39.0,-68.0,31.0)

### Local implementation

sanctuaire-des-dragoeufs v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Dragoeuf Guerrier [4210], 2 × Dragohuevo cocido [4209], 2 × Dragoeuf à la coque [4209], 1 × Huevo antiguo [4400], 1 × Aguabrial [5165]
- Configured room 2: 2 × Dragoeuf Guerrier [4210], 3 × Dragohuevo guerrero [4210], 2 × Dragoeuf à la coque [4209], 1 × Aguabrial [5165]
- Configured room 3: 2 × Dragoeuf Guerrier [4210], 3 × Huevo antiguo [4400], 3 × Dragoeuf à la coque [4209]
- Configured room 4: 1 × Oeuf Antique [4400], 3 × Dragoeuf Guerrier [4210], 2 × Dragoloso [4208], 2 × Dragoeuf à la coque [4209]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Escarantera Abandonada (native:151)

French alias: Scarrière Abandonnée. Type: DUNGEON_3_ROOMS. Native level: 81. Maps: [909].

Species pool: Escaraboss [4909] level 86-90, Escaramosca [4910] level 81-81, Escaramelo [4911] level 91-95, Escarabela [4912] level 81-85, Escaradoro [4913] level 98-103

### Guide composition

[scarriere-abandonnee](https://methodwakfu.com/pvm/scarriere-abandonnee/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 3 × Scaramel [ref 4911, monster], 2 × Scaraboss [ref 4909, monster], 2 × Scarabruni [ref 4912, monster]
- Room 2 (complete): 2 × Scaramel [ref 4911, monster], 3 × Scaraboss [ref 4909, monster], 3 × Scarabruni [ref 4912, monster]
- Room 3 (complete): 1 × Scarador [ref 4913, boss], 2 × Scaramel [ref 4911, monster], 3 × Scaraboss [ref 4909, monster], 2 × Scarabruni [ref 4912, monster]

### Native entrance and interiors

Entry map 1137, object 14583, destination 2072, template 154. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 3, 'Door': 3, 'Board': 1, 'GenericActivableInteractiveElement': 1, 'LootChest': 2}.

- Internal transport object 24166 on map 909: map 909 (42,-34,0), criterion=empty, item=0
- Door: 24170 at map 909 (20.0,-18.0,0.0); 24171 at map 909 (32.0,-21.0,0.0); 24172 at map 909 (36.0,-48.0,0.0)
- LootChest: 24165 at map 909 (40.0,-35.0,1.0); 26429 at map 909 (63.0,-40.0,0.0)
- Board: 24169 at map 909 (31.0,-33.0,0.0)

### Local implementation

scarriere-abandonnee v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 3 × Escaraboss [4909], 2 × Escaramosca [4910], 2 × Escaramelo [4911], 1 × Escarabela [4912]
- Configured room 2: 2 × Escaramosca [4910], 3 × Escaramelo [4911], 3 × Escarabela [4912]
- Configured room 3: 1 × Scarador [4913], 2 × Escarabela [4912], 3 × Escaradoro [4913], 2 × Escaraboss [4909]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Sliptorium (native:48)

French alias: Sliptorium. Type: DUNGEON_2_ROOMS. Native level: 81. Maps: [325].

Species pool: Juanpi Ylsen [1777] level 85-89, Grimm Berruguen [1778] level 83-87, Gran Bayotoro [1779] level 89-93, Monja [1786] level 98-103

### Guide composition

[sliptorium](https://methodwakfu.com/pvm/donjons/sliptorium/); extraction=complete; version=1.72; client version match=unverified.

- Room 1 (complete): 2 × Grimm Beurguen [ref 1778, monster], 2 × Gros Nambourg [ref 1779, monster], 3 × Raymond Garden [ref 1777, monster]
- Room 2 (complete): 1 × Nonne [ref 1786, boss]

### Native entrance and interiors

Entry map 323, object 14294, destination 703, template 46. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 2, 'Teleporter': 6, 'GenericActivableInteractiveElement': 52, 'ZoneTrigger': 4}.

- Internal transport object 14010 on map 325: map 325 (208,106,0), criterion=empty, item=0
- Internal transport object 14011 on map 325: map 325 (0,-45,0), criterion=empty, item=0
- Internal transport object 27552 on map 325: map 325 (144,-54,0), criterion=empty, item=0
- Internal transport object 16126 on map 325: map 325 (203,93,0), criterion=empty, item=0
- Door: 14009 at map 325 (-4.0,-36.0,0.0); 14008 at map 325 (-4.0,-35.0,0.0)
- ZoneTrigger: 16129 at map 325 (143.0,-58.0,0.0); 16132 at map 325 (146.0,-61.0,0.0); 16130 at map 325 (144.0,-61.0,0.0); 16131 at map 325 (145.0,-59.0,0.0)

### Local implementation

sliptorium v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=1.

- Configured room 1: 2 × Grimm Beurguen [1778], 2 × Gros Nambourg [1779], 3 × Gran Bayotoro [1779], 1 × Monja [1786]
- Configured room 2: 1 × Nonne [1786]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Fuente del Mal (native:154)

French alias: Source du Mal. Type: DUNGEON_3_ROOMS. Native level: 141. Maps: [1254].

Species pool: Bulbiflor [5035] level 145-149, Bulbomatorral [5036] level 143-147, Bulbambú [5037] level 149-153, Bulbruto [5040] level 158-163

### Guide composition

[source-du-mal](https://methodwakfu.com/pvm/source-du-mal/); extraction=complete; version=None; client version match=unverified.

- Room 1 (complete): 2 × Bulbambou [ref 5037, monster], 2 × Bulbiflore [ref 5035, monster], 2 × Bulbuisson [ref 5036, monster]
- Room 2 (complete): 2 × Bulbambou [ref 5037, monster], 3 × Bulbiflore [ref 5035, monster], 2 × Bulbuisson [ref 5036, monster]
- Room 3 (complete): 2 × Bulbambou [ref 5037, monster], 3 × Bulbiflore [ref 5035, monster], 3 × Bulbuisson [ref 5036, monster]
- Room 4 (complete): 1 × Bulbrute [ref 5040, boss], 2 × Bulbambou [ref 5037, monster], 3 × Bulbiflore [ref 5035, monster], 2 × Bulbuisson [ref 5036, monster]

### Native entrance and interiors

Entry map 1252, object 31856, destination 4031, template 157. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 4, 'Stele': 1}.

- Door: 31815 at map 1254 (-18.0,23.0,-16.0); 31814 at map 1254 (-21.0,13.0,-16.0); 31816 at map 1254 (20.0,17.0,-32.0)
- Stele: 34865 at map 1254 (39.0,12.0,-46.0)

### Local implementation

source-du-mal v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Bulbambou [5037], 2 × Bulbomatorral [5036], 2 × Bulbuisson [5036], 1 × Bulbruto [5040], 1 × Bulbiflor [5035]
- Configured room 2: 2 × Bulbambou [5037], 3 × Bulbambú [5037], 2 × Bulbuisson [5036], 1 × Bulbiflor [5035]
- Configured room 3: 2 × Bulbambou [5037], 3 × Bulbruto [5040], 3 × Bulbuisson [5036]
- Configured room 4: 1 × Bulbrute [5040], 2 × Bulbambou [5037], 3 × Bulbomatorral [5036], 2 × Bulbuisson [5036]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Guarida de los Tejaroxores (native:126)

French alias: Tanière des Blérox. Type: DUNGEON_2_ROOMS. Native level: 186. Maps: [1130].

Species pool: Rastrejón [4203] level 187-195, Tejardor [4204] level 187-195, Tejoso [4205] level 187-195, Tejónidas el Furioso [4318] level 203-208, Aguabrial [5165] level 200-200

### Guide composition

[taniere-des-blerox](https://methodwakfu.com/pvm/taniere-des-blerox/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Fouirox [ref 4203, monster], 2 × Blérage [ref 4204, monster], 1 × Blérours [ref 4205, monster]
- Room 2 (complete): 2 × Fouirox [ref 4203, monster], 2 × Blérage [ref 4204, monster], 2 × Blérours [ref 4205, monster]
- Room 3 (complete): 3 × Blérage [ref 4204, monster], 2 × Fouirox [ref 4203, monster], 2 × Blérours [ref 4205, monster]
- Room 4 (complete): 1 × Blerwitch le Furax [ref None, boss], 1 × Fouirox [ref 4203, monster], 1 × Blérage [ref 4204, monster], 1 × Blérours [ref 4205, monster]

### Native entrance and interiors

Entry map 1122, object 27980, destination 2629, template 129. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 3, 'GenericActivableInteractiveElement': 5, 'Teleporter': 2, 'Stele': 1}.

- Door: 27992 at map 1130 (-15.0,-41.0,19.0); 27990 at map 1130 (-22.0,-42.0,19.0); 27991 at map 1130 (-22.0,-41.0,19.0)
- Stele: 34876 at map 1130 (-11.0,-56.0,3.0)

### Local implementation

taniere-des-blerox v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Fouirox [4203], 2 × Blérage [4204], 1 × Blérours [4205]
- Configured room 2: 2 × Fouirox [4203], 2 × Blérage [4204], 2 × Blérours [4205]
- Configured room 3: 3 × Blérage [4204], 2 × Fouirox [4203], 2 × Blérours [4205]
- Configured room 4: 1 × Tejónidas el Furioso [4318], 1 × Fouirox [4203], 1 × Blérage [4204], 1 × Blérours [4205], 1 × Tejoso [4205], 1 × Tejónidas el Furioso [4318], 1 × Aguabrial [5165], 1 × Rastrejón [4203]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Templo del Gran Orrok (native:99)

French alias: Temple du Grand Orrok. Type: DUNGEON_2_ROOMS. Native level: 66. Maps: [955].

Species pool: Gramañón [3568] level 70-74, Gracky [3571] level 74-78, Grala [3573] level 68-72, Gran Orrok [3587] level 85-85

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 943, object 25236, destination 2204, template 102. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'GenericActivableInteractiveElement': 1, 'Door': 3}.

- Door: 25191 at map 955 (4.0,-9.0,0.0); 25192 at map 955 (5.0,-9.0,0.0); 25180 at map 955 (1.0,0.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Thalos-Kyarrelmne (native:225)

French alias: Thalos-Kyarrelmne. Type: DUNGEON_ARCADE. Native level: 51. Maps: [1445].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Object counts: {'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence; Native entrance route not resolved in exported bulk routes.

## Teatro Intemporal (native:202)

French alias: Théâtre intemporel. Type: DUNGEON_3_PLAYERS. Native level: 231. Maps: [1429].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1430, object 35049, destination 4714, template 194. Criterion:

```text
not (IsAchievementRunning(5553)
and IsAchievementObjectiveComplete(11474)
and not IsAchievementObjectiveComplete(11475))
```

Object counts: {'Stele': 1, 'Teleporter': 1}.

- Stele: 35081 at map 1429 (-20.0,-6.0,0.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Tumba de Pandala (native:157)

French alias: Tombeau de Pandala. Type: DUNGEON_2_ROOMS. Native level: 186. Maps: [1255].

Species pool: Fantasma de pandido [5053] level 194-198, Fantasma de pandulo [5054] level 190-194, Fantasma de tanuki chan [5055] level 188-192, Fantasma de yokai [5056] level 188-192, Fantasma de Tanukui San [5059] level 203-208

### Guide composition

[donjons-tombeau-de-pandala](https://methodwakfu.com/pvm/donjons/tombeau-de-pandala/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 1 × Fantôme Tanuki-Chan [ref 5055, monster], 2 × Fantôme Pandit [ref 5053, monster], 1 × Fantôme Pandule [ref 5054, monster], 2 × Fantôme Yokaï [ref 5056, monster]
- Room 2 (complete): 1 × Fantôme Tanuki-Chan [ref 5055, monster], 2 × Fantôme Pandit [ref 5053, monster], 2 × Fantôme Pandule [ref 5054, monster], 2 × Fantôme Yokaï [ref 5056, monster]
- Room 3 (complete): 2 × Fantôme Tanuki-Chan [ref 5055, monster], 2 × Fantôme Pandit [ref 5053, monster], 2 × Fantôme Pandule [ref 5054, monster], 2 × Fantôme Yokaï [ref 5056, monster]
- Room 4 (complete): 1 × Fantôme Tanukouï-San [ref 5059, boss], 1 × Fantôme Tanuki-Chan [ref 5055, monster], 2 × Fantôme Pandit [ref 5053, monster], 2 × Fantôme Pandule [ref 5054, monster], 2 × Fantôme Yokaï [ref 5056, monster]

### Native entrance and interiors

Entry map 1252, object 31935, destination 4037, template 160. Criterion:

```text
(empty on this entry)
```

Object counts: {'Door': 3, 'Teleporter': 2, 'GenericActivableInteractiveElement': 4, 'Stele': 1}.

- Door: 31871 at map 1255 (31.0,-14.0,-36.0); 31870 at map 1255 (37.0,-19.0,-36.0); 31869 at map 1255 (38.0,-19.0,-36.0)
- Stele: 34878 at map 1255 (29.0,2.0,-36.0)

### Local implementation

donjons-tombeau-de-pandala v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 1 × Fantôme Tanuki-Chan [5055], 2 × Fantôme Pandit [5053], 1 × Fantasma de tanuki chan [5055], 2 × Fantasma de yokai [5056], 1 × Fantasma de Tanukui San [5059], 1 × Fantasma de pandido [5053]
- Configured room 2: 1 × Fantôme Tanuki-Chan [5055], 2 × Fantôme Pandit [5053], 2 × Fantasma de yokai [5056], 2 × Fantasma de Tanukui San [5059], 1 × Fantasma de pandido [5053]
- Configured room 3: 2 × Fantôme Tanuki-Chan [5055], 2 × Fantôme Pandit [5053], 2 × Fantasma de Tanukui San [5059], 2 × Fantasma de pandido [5053]
- Configured room 4: 1 × Fantôme Tanukouï-San [5059], 1 × Fantôme Tanuki-Chan [5055], 2 × Fantôme Pandit [5053], 2 × Fantasma de pandulo [5054], 2 × Fantasma de tanuki chan [5055]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Tumba de Tal Kasha (native:194)

French alias: Tombeau de Tal Kasha. Type: ULTIMATE_BOSS. Native level: 141. Maps: [1400].

Species pool: Tal Kasha [5500] level 155-155

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1393, object 34826, destination 4650, template 187. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Toross (native:223)

French alias: Toross. Type: DUNGEON_ARCADE. Native level: 51. Maps: [1405].

Species pool: Unknown native pool

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 346, object 35960, destination 4791, template 215. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 1}.


### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Torre de las Miss Adefesio (native:189)

French alias: Tour des Miss Moches. Type: DUNGEON_3_PLAYERS. Native level: 51. Maps: [154].

Species pool: Leila [5445] level 68-71, Enca [5446] level 68-71, Arpel [5447] level 68-71, Ydalipe [5448] level 68-71, Leila [5481] level 65-65

### Guide composition

[donjons-tour-des-miss-moches](https://methodwakfu.com/pvm/donjons/tour-des-miss-moches/); extraction=unknown; version=1.87; client version match=unverified.


### Native entrance and interiors

Entry map 1389, object 34565, destination 4570, template 182. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 4, 'GenericActivableInteractiveElement': 4}.


### Local implementation

donjons-tour-des-miss-moches v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=2.

- Configured room 1: 1 × Leila [5445], 1 × Enca [5446], 1 × Arpel [5447], 1 × Ydalipe [5448], 1 × Leila [5481], 1 × Leila [5445], 1 × Enca [5446], 1 × Arpel [5447]
- Configured room 2: 1 × Enca [5446], 1 × Arpel [5447], 1 × Ydalipe [5448], 1 × Leila [5481], 1 × Leila [5445], 1 × Enca [5446], 1 × Arpel [5447], 1 × Ydalipe [5448]
- Configured room 3: 1 × Arpel [5447], 1 × Ydalipe [5448], 1 × Leila [5481], 1 × Leila [5445], 1 × Enca [5446], 1 × Arpel [5447], 1 × Ydalipe [5448], 1 × Leila [5481]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Pestrucería Abandonada (native:146)

French alias: Truchière Abandonnée. Type: DUNGEON_3_ROOMS. Native level: 66. Maps: [495].

Species pool: Pestruz [4867] level 68-72, Pestruzillo [4868] level 70-74, Pestruzkito [4869] level 74-78, Ausgría, Thor Pestruz [4871] level 83-88

### Guide composition

No reviewed guide; room composition unknown.

### Native entrance and interiors

Entry map 1136, object 17998, destination 1031, template 149. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 3, 'GenericActivableInteractiveElement': 1}.

- Door: 17752 at map 495 (-45.0,-13.0,0.0); 17754 at map 495 (-46.0,-27.0,0.0); 17756 at map 495 (-59.0,-56.0,12.0)

### Local implementation

No configuration in the reviewed installed-generation bundle.

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance; Reviewed per-room monster composition and guide evidence.

## Fábrica Buhatrás (native:159)

French alias: Usine Hibourg. Type: DUNGEON_3_ROOMS. Native level: 186. Maps: [1271].

Species pool: Minibuhatrás [5134] level 190-194, Mago buhatrás [5135] level 194-198, Gentilbúho [5136] level 190-194, Bubobubo Buhatrás [5137] level 203-208, Conde Kontatrás [5155] level 200-200

### Guide composition

[usine-hibourg](https://methodwakfu.com/pvm/usine-hibourg/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Minibourg [ref 5134, monster], 2 × Gentibourg [ref 5136, monster], 2 × Mage Hibourg [ref 5135, monster]
- Room 2 (complete): 3 × Minibourg [ref 5134, monster], 2 × Gentibourg [ref 5136, monster], 2 × Mage Hibourg [ref 5135, monster]
- Room 3 (complete): 3 × Minibourg [ref 5134, monster], 3 × Gentibourg [ref 5136, monster], 2 × Mage Hibourg [ref 5135, monster]
- Room 4 (complete): 1 × Granduk Hibourg [ref 5137, boss], 2 × Minibourg [ref 5134, monster], 3 × Gentibourg [ref 5136, monster], 2 × Mage Hibourg [ref 5135, monster]

### Native entrance and interiors

Entry map 1264, object 32272, destination 4199, template 162. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 6, 'ZoneTrigger': 1, 'GenericActivableInteractiveElement': 2}.

- Internal transport object 32299 on map 1271: map 1271 (139,-140,1), criterion=empty, item=0
- Internal transport object 32296 on map 1271: map 1271 (155,-140,1), criterion=empty, item=0
- Internal transport object 32298 on map 1271: map 1271 (255,-266,0), criterion=empty, item=0
- Internal transport object 32297 on map 1271: map 1271 (67,-65,1), criterion=empty, item=0
- ZoneTrigger: 32422 at map 1271 (259.0,-268.0,0.0)

### Local implementation

usine-hibourg v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Minibourg [5134], 2 × Gentibourg [5136], 2 × Mage Hibourg [5135]
- Configured room 2: 3 × Minibourg [5134], 2 × Gentibourg [5136], 2 × Mage Hibourg [5135]
- Configured room 3: 3 × Minibourg [5134], 3 × Gentibourg [5136], 2 × Mage Hibourg [5135]
- Configured room 4: 1 × Granduk Hibourg [5137], 2 × Minibourg [5134], 3 × Gentibourg [5136], 2 × Mage Hibourg [5135]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

## Volcán Or'Hodruin (native:127)

French alias: Volcan Or'Hodruin. Type: DUNGEON_2_ROOMS. Native level: 186. Maps: [1131].

Species pool: Bolrag de Dor'Mor [4324] level 187-195, Gulnaz de Dor'Mor [4325] level 187-195, War'Hg magmático [4326] level 187-195, Saur'Hon, el Señor de la Llama [4327] level 203-208, Aguabrial [5165] level 200-200

### Guide composition

[volcan-orhodruin](https://methodwakfu.com/pvm/volcan-orhodruin/); extraction=complete; version=1.67; client version match=unverified.

- Room 1 (complete): 2 × Bolrag du Dor’Mor [ref 4324, monster], 2 × War’Hg Magmatique [ref 4326, monster], 1 × Gulnaz du Dor’Mor [ref 4325, monster]
- Room 2 (complete): 2 × Bolrag du Dor’Mor [ref 4324, monster], 2 × War’Hg Magmatique [ref 4326, monster], 2 × Gulnaz du Dor’Mor [ref 4325, monster]
- Room 3 (complete): 3 × Bolrag du Dor’Mor [ref 4324, monster], 2 × War’Hg Magmatique [ref 4326, monster], 2 × Gulnaz du Dor’Mor [ref 4325, monster]
- Room 4 (complete): 1 × Sor’Hon, Seigneur de la Flamme [ref 4327, boss], 2 × Bolrag du Dor’Mor [ref 4324, monster], 2 × War’Hg Magmatique [ref 4326, monster], 3 × Gulnaz du Dor’Mor [ref 4325, monster]

### Native entrance and interiors

Entry map 1123, object 28036, destination 2631, template 130. Criterion:

```text
(empty on this entry)
```

Object counts: {'Teleporter': 2, 'Door': 4, 'GenericActivableInteractiveElement': 6, 'Stele': 1}.

- Door: 28051 at map 1131 (-15.0,-24.0,20.0); 28050 at map 1131 (-15.0,-23.0,20.0); 28052 at map 1131 (-18.0,-35.0,20.0); 28053 at map 1131 (-43.0,-35.0,40.0)
- Stele: 34873 at map 1131 (-30.0,-43.0,43.0)

### Local implementation

volcan-orhodruin v2: policy=generated_native_species_policy; official=False; official order verified=False; automatic transition edges=3.

- Configured room 1: 2 × Bolrag de Dor'Mor [4324], 2 × Gulnaz de Dor'Mor [4325], 1 × War'Hg magmático [4326], 1 × Saur'Hon, el Señor de la Llama [4327], 1 × Aguabrial [5165], 1 × Bolrag de Dor'Mor [4324]
- Configured room 2: 2 × Gulnaz de Dor'Mor [4325], 2 × War'Hg magmático [4326], 2 × Saur'Hon, el Señor de la Llama [4327], 1 × Aguabrial [5165], 1 × Bolrag de Dor'Mor [4324]
- Configured room 3: 3 × War'Hg magmático [4326], 2 × Saur'Hon, el Señor de la Llama [4327], 2 × Aguabrial [5165], 1 × Bolrag de Dor'Mor [4324]
- Configured room 4: 1 × Saur'Hon, el Señor de la Llama [4327], 2 × Aguabrial [5165], 2 × Bolrag de Dor'Mor [4324], 3 × Gulnaz de Dor'Mor [4325]

Unresolved: Official internal gate/teleport sequence and runtime collision validation; Exhaustive noncombat interactions, secrets, resources and quest NPCs; Live full-run acceptance except separately recorded Jalato acceptance.

