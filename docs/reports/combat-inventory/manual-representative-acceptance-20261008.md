# Representative manual spell acceptance

Status: `wakemu-world:complete-20261008-r31` is deployed and healthy. Hector confirmed Desbalizaje works. Compact encounter formation and mirrored border effects are deployed; manual border acceptance remains pending. The validated movement-idle fallback requires reloading the combined client agent. Additional interior scene glyphs remain in progress.

Preparation and result tracker: [manual-representative-readiness-20261008.csv](manual-representative-readiness-20261008.csv). All nine cards are currently pending manual execution. Update their preparation status, tested build and first failing step as evidence arrives; pending does not mean the mechanism is known to fail.

This is the current manual plan. Hector does **not** need to test every spell against every enemy. Automated checks retain responsibility for the complete class/dependency inventory; these cards sample the shared engine and visible client behavior. Passing the sample does not turn unverified mechanics into completed work.

## Live regression acceptance

Observed on r05: Hector confirmed Contact Beacon and Seeking Arrow. Server fight51 recorded victory and exploration return. Remaining checks include passive-dependent visibility, fresh-fight surrender, and absence of snapshot/checkpoint diagnostics after the next deployment.

After buildcombat-20261008-r05 is confirmed active, reconnect and use the canonical current-room group, or run `!exitdungeon` before spawning a test encounter. With Npers at the existing modulated level50, start a new fight, press Ready, cast a clear ranged arrow, and place Baliza de Contacto on a highlighted empty cell. The beacon must appear for its Cra owner before its states/stat updates. Trigger it with an owned arrow; secondary damage must appear. End the turn and attack on the next owned turn without roster errors. Kill the remaining enemies: results and exploration return must occur without a stuck turn. In a separate fresh fight, summon a beacon and surrender: registered summons must not prevent the owning player from leaving. Stop at the first failure and report the visible message. Full passive-dependent enemy visibility is a separate check.

## Session size and order

Start with M1, M3, M4 and M5: range/resources, beacon reactions, captured summons and carrying. These directly address reported failures. Then use M2, M6, M7 and M8 to cover conditional walls, health/state consumption, areas and ordinary healing. Stop a card at its first failure and continue an independent card; do not repeat the same failure across many spells or enemies.

Use one ordinary enemy profile throughout. Three members of the same profile are enough for area selection. A second client is only needed for the ally-healing variant; the other cards are designed around one tester. No monster AI or monster spell validation is required.

## Preparation owned by the implementer

Before Hector starts, supply a ready-to-run card sheet containing the deployed build, prepared character names/levels/decks, target level/HP, exact costs and range from installed casting data, state/area names and trigger conditions, and the expected result of each selected sequence. Prepare one owned captured creature for M4. Supply a verified physical-wall arena and the exact legal sequence reaching Precision30 for M2. Bind M7 to one verified glyph-producing spell and its actual footprint/duration. These prerequisites are **not** investigative tasks for Hector.

Do not ask Hector to guess item IDs, populate a captured roster, find a suitable wall, discover a state-building sequence, or reset a level200 character. There is no verified chat command here to grant arbitrary spells, change class, force states, heal/reset resources, or give critical chance. A missing preparation item leaves that card pending.

The existing roster tool prepares `Prueba Ocra`, `Prueba Osamodas`, `Prueba Pandawa`, `Prueba Sacro`, `Prueba Feca` and `Prueba Aniripsa`, among other classes. Confirm their actual existence and builds first; this document does not claim they have been created for this account. Use level200 for the common session unless the supplied card explicitly says otherwise. Fresh roster decks contain only the first12 active spells: the implementer must supply the legal decks listed below before testing.

## Verified setup commands

These commands are entered outside combat and the haven bag, using the test account with its existing command permissions. `!mob` requires the deployed combat-test option. Read-only container commands do not restart services.

```text
!ayuda
!pos
!tp 1134 -8 -7 -1
!mob 5525 1 1
```

Expected: help/position responses, map1134 instance0, and a new reachable enemy group. Enter the fight through that group's ordinary interaction, place and press Ready. If that enemy would die before the sequence ends, the implementer must supply a tested higher spawn level or a new encounter; do not increase difficulty blindly.

For three area targets, change only the final command:

```text
!mob 5525 1 3
```

Use a fresh fight when a card says clean state. Record the character, spell name, tooltip cost/range, turn, resources and relevant state levels before casting. A screenshot before and after, plus one sentence describing a mismatch, is sufficient for Hector's initial report. The implementer collects server logs and classifies the mechanism.

## M1 — Cra basic damage, range and resource rejection

Deck: Flecha Ardiente4769 and Flecha Buscadora4813. Use the ordinary target, no special range state for the baseline.

1. Select Flecha Ardiente. Compare tooltip minimum/maximum with highlighted cells. Cast on a legal target at the displayed range boundary, following the supplied placement card.
2. Check that the server accepts the highlighted legal target; AP/MP/WP decrease by the displayed costs exactly once. The floating damage and HP decrease must agree.
3. Try one target outside maximum range and, where minimum exceeds0, inside minimum. Expect refusal with unchanged resources and HP. If the client refuses to send the cast, record that fact rather than claiming server-side rejection was tested.
4. Spend enough resources using legal casts to make the same spell unaffordable. Try it again: no damage, state change or extra resource loss. End the turn and verify the resource HUD refreshes correctly.

Covers: ordinary damage, range publication, costs, rejection and turn refresh. Do not compare a critical hit with a normal-hit expected value.

## M2 — Cra conditional line of sight and range restoration

Use a prepared **level20** Cra, no passive or equipment modifiers, deck Flecha de Retroceso4810 / Flecha Buscadora4813 / Flecha Azotadora4816 / Flecha Fulminante4820. Production Ready grants Tiro Preciso7752. Spell7792 (Baliza de Contacto) is a different object from state7792 (Precision).

The [actual normal transaction result](native-cra-conditional-wall-transactions-20261008.json) now verifies the full offline sequence with no injected state, life or resources. On map1134, put the caster at `(-7,-7,-1)` and native Pestruzillo5574 level133,4500HP at `(-7,0,-1)`. Their actual native heights are6 and4. Both native fcr casting rays are blocked by the Vz column at `(-7,-5)`; the source/target distance is7. The preparation cell `(-13,-7,-1)` is empty, clear and distance6. All endpoints are in one458-cell native bounded arena. This supersedes the earlier low-obstacle fixture: its raised-target ray was clear, so accepting its LOS=True control was correct.

**Operator preparation:** supply a real encounter whose permitted placement exposes these exact endpoints before giving the card to Hector. Native `!mob` does not guarantee an exact-coordinate spawn. The verified commands are `!tp 1134 -7 -7 -1` and `!mob 5574 133 1`, but the latter only creates a nearby group; it must not be presented as placing the enemy at `(-7,0,-1)`. The offline mechanics are ready; that live encounter placement and graphical acceptance remain pending. Do not ask Hector to discover coordinates or restart containers.

1. After Ready and the actual owner turn begins, record6PA and the ordinary target display. Cast **Flecha Fulminante at the empty preparation cell `(-13,-7,-1)`**. Expect3PA spent,3PA remaining, targetHP4500 unchanged, and Precision state7792 at level30. Do not end the turn.
2. Use **Tiro Preciso on self**. Expect0PA and1PW spent, state7757 present, and Precision30 still present. Cast **Flecha Buscadora at the enemy `(-7,0,-1)`**. Expect acceptance through the genuine wall,2PA spent and1PA remaining. In the verified normal-hit fixture, enemyHP4500 becomes4496. Record critical hits separately rather than requiring this normal amount from them. Precision is consumed by Buscadora.
3. Start an independently prepared equivalent fight/turn and repeat Fulminante at the empty clear cell to build Precision30. Toggle **Tiro Preciso on and then off before casting Buscadora**. Expect0PA and1PW per toggle,3PA still available and state7757 absent. Try the same enemy behind the wall. Expect native LOS rejection `twG`, no resource cost, and enemyHP4500 unchanged. This control is deliberately independent of step2; do not use its already spent PA or Precision.
4. If an out-of-range comparison is required, prepare another fresh threshold before testing it. A spent Precision state cannot prove range enforcement while the exemption is active. Rejoin is optional until its exact supported client flow is supplied.

The offline on/off controls selected original conditional rule0 (LOS=False) and rule2 (LOS=True) respectively. These are actual normal requests with costs, grants, owned spellbook, native terrain and committed state lifecycle. No level200 equivalence or next-turn Precision persistence is claimed. Graphical highlights, tooltip/server agreement and real encounter placement must still be checked on the running client build.

## M3 — Cra beacons: three elements and cleanup

Granted spells: Baliza de Alineamiento7793, Baliza de Contacto7792, Baliza de Destrucción4807 and Desbalizaje6349. Representative arrows: Flecha de Retroceso4810 (air), Flecha Azotadora4816 (earth), Flecha Fulminante4820 (fire).

Actual normal lifecycle/reuse run03 verifies all three below at Cra level20, noncritical branch, against Pestruzillo5574 level133/4500HP. On the prepared map1134 placement, Cra is(-8,-7,-1), the beacon cell is(-12,-7,-1), and the enemy is(-13,-7,-1). Every initial beacon costs2AP; Desbalizaje costs1AP. After normal turn boundaries, the same arrow on the removed beacon cell produces zero additional enemy HP loss, and re-invocation on that cell succeeds. The recorded re-invocation plan costs0 under the resulting actual state/cost context; do not generalize that contextual value to every fresh beacon cast.

| Beacon/action | Native profile/state | Arrow cost | Measured secondary enemy HP loss |
| --- | --- | --- | --- |
| Alineamiento7793 | 3798 / 7781 | Retroceso4810: 3AP+1WP | 4 |
| Contacto7792 | 3799 / 7780 | Azotadora4816: 3AP | 3 |
| Destrucción4807 | 3800 / 7779 | Fulminante4820: 3AP | 2 |

Evidence: `cra-beacon-reuse-diagnostic-03.json`, SHA256`752593b2328a2fce99d1096f9b8a6cad0f16ee596eae7efaad6beb8c2e4abe5b`, sources stable, three verified sequences. This normal-hit reuse trace is separate from the earlier nine-pair elemental matrix and three critical cases. The observed secondary amounts apply to its captured actor/stat snapshots, not arbitrary level20 equipment. Visual/client acceptance remains pending.

1. Start a fresh fight. Confirm the beacon/desbalizaje actions are granted normally; they must not require inserting extra spells into the active deck.
2. Place one beacon on an eligible empty cell. Verify its footprint, ownership and states against the card. Try an occupied/illegal destination: no phantom beacon or extra cost.
3. Use the supplied representative arrow/target arrangement to trigger that beacon near the ordinary enemy. Check the **secondary reaction**, affected cells and state changes, not merely the arrow's primary damage. Repeat the card's short air/earth/fire arrangement for the other beacon branches.
4. Remove a beacon with Desbalizaje or its documented normal lifecycle, then use the same arrow again. Expect no reaction from the removed beacon; its old location must be usable. Start a fresh fight and confirm no old beacon remains.

Covers: automatic access, summoned-object states, owner-triggered reactions, elemental branch selection, geometry and cleanup. The implementer must supply the verified beacon/arrow reaction table and exact secondary expectations after the production trace. No restriction to a matching incoming element is assumed: native arrows contain branches for all three owned beacon types. The automated nine-pair matrix verifies that relationship; Hector only repeats the three representative arrangements. The three arrows alone do not prove three reactions.

## M4 — Osamodas captured creature: one complete lifecycle

For current live acceptance, use [the prepared complete Osamodas card](manual-osamodas-system-20261008.md) and account-owned `Prueba Osamodas` (id13, level200, initially empty Symbiot). The historical profile5347 fixture below is additional automated evidence, not a prepared live prerequisite.

Additional engine evidence: `capture-empty-symbiot-06.json` used a fresh empty Symbiot, actual mark7348 costing1AP, and attack7312 costing4AP/1WP. The original profile4 target at level8 lost46HP to reach0; slot0 became available with profile4. No slots or death were injected. The checkpoint serialized successfully, but this report does not prove database persistence, a later summoned creature, or client visuals. A concurrent change to `characters/aptitudes.py` made the aggregate source-stability gate false; combat delivery source was unchanged during this case.

Action: granted Invocación7348. Use the prepared owned profile5347 descriptor in slot3. The source-backed level153 fixture's summoned action book is7356/7357/7358, each at level153; this is the book to verify for that exact build, not an assertion about other captured profiles or levels.

1. Start a fresh level153 Osamodas fight with profile5347 selected in slot3. Confirm Invocación7348 is in the owner's book at level153 and slot3 is available. Use a prepared placement with the owner at `(-23,-143,70)` and the adjacent cell `(-23,-142,70)` empty.
2. Cast7348 on `(-23,-142,70)`. The verified plan costs1AP,0MP,0WP (sample owner AP6→5, MP3→3). Expect one visible controlled profile5347 creature and its three-action book7356/7357/7358 at level153. The captured descriptor remains selected in slot3, which becomes unavailable while the creature is in play.
3. On the same owned turn, cast7348 again on the occupied creature cell `(-23,-142,70)` when the prepared source condition is met. The native range for this level153 sample is1–4; the audit did not persist the second cast's resource plan, so read and record its installed tooltip cost instead of assuming the first cast's cost. The observed transaction selected the actual creature295 and completed child326443, family859, through the HasStateFromUser(7134, target) branch. The target was at1HP before this cast sequence and ended at HP0 / KO_TIME0.
4. After the outer effect chain settles, verify the exact retirement: actor295 remains in the fight/global fighter identity as OUT_OF_PLAY; QI slot2 is removed and its QK byte becomes-1; captured slot3 becomes available again. The slot remains selected and its profile5347 descriptor is preserved. The old occupied cell must no longer have that actor's QI obstacle; do not expect a duplicate creature or a stale QI row.

Evidence: `.runtime/combat-review-20261008/summon-recall-retired-slot-13.recall.json`, SHA256 `50b7571bf93c96d1925c5e5a98dda13d03b2fa19f9b0e958321d6b8332d64b74`; full report `.runtime/combat-review-20261008/summon-recall-retired-slot-13.json`, SHA256 `d75c8c90992b20eaa0ef6f9b69b4c01844d48f230a5eaf15674abf6e755b6372`. The source fight was unchanged, family859 completed, exactly QI slot2 was removed, and only captured-slot3 availability changed. This is server-side transaction evidence; actual client appearance, visible slot refresh, and animation remain pending.

Covers: roster selection, family324, scaling, initial states, ownership, creature book, timeline, occupancy, recall and settled QI/roster retirement for this sampled owned captured creature. One creature is the default sample; another is added only if its descriptor represents a genuinely different unverified mechanism.

## M5 — Pandawa carry, throw and occupancy

Granted actions: Karcham6847 and Chamrak6848. The legal deck and any setup required by their tooltips are prepared in advance.

1. Start a fresh fight and confirm both actions are granted. Stand adjacent to the supplied eligible target; use Karcham.
2. Check the carrying relation and visuals. Move one legal cell: the carried actor must follow without leaving a blocking ghost on its old location. Costs must match the tooltip.
3. Use Chamrak on the supplied legal empty destination. Expect the target exactly once at that destination; it becomes targetable there and the carry relation is cleared.
4. Try an occupied/illegal throw and Chamrak without a carried target. Expect rejection without partial movement or resource loss. Repeat carry→throw once, then finish the fight and verify cleanup.

Covers: grants, reciprocal carrying, movement callbacks, source/controller identity, packet presentation, QI occupancy and rejection atomicity.

## M6 — Sacro health-dependent states, healing and consumption

Spells: Sangre a Sangre5028, granted Corazón Sanguíneo6065 and Corte8586 when the native level requirement is met. Use the supplied clean build and state-value sheet; offline level20 values must not be copied onto a different manual build.

1. Start a fresh fight. Note current/maxHP, armor and granted actions.
2. Cast Sangre a Sangre using the supplied target. Check target damage, self-damage and the stored state separately. The self-HP loss must match the prepared percentage/rounding expectation for this actual maximumHP.
3. Use Corazón Sanguíneo. Check the separate healing and armor results, and verify the stored/consumed states are removed or changed exactly as the card specifies.
4. Attempt the affected action in its negative state condition, then advance its documented expiry. An existing granted button may become unusable rather than disappear: match the actual native access rule. No repeated consumption or old armor/state may leak into the next fight.

Covers: HP percentages, stat maxima, group child levels, armor, healing, state consumption and state-conditioned access.


### Optional M6 continuation — Venganza and the temporary attack book

This checks state-dependent book replacement, a different mechanism from Osa dragon form. Use a fresh supplied level200 Sacrier with5028 available, native innate3702 and no selected passive, against the surviving native enemy spawned with `!mob 5574 133 1`. Do not run the healing/consumption sequence above in this fresh encounter. The implementer must identify the three temporary action names/icons on the supplied build before asking Hector to test.

1. Complete Ready. Confirm **Venganza8587** is granted but cannot be used before its native state prerequisite; note the original action bar.
2. Cast **Sangre a Sangre5028** on the same eligible enemy, up to twice on each actual Sacrier turn, and stop once the native9322 prerequisite makes Venganza usable. End/acknowledge intervening turns normally. The clean offline fixture costs3AP per cast and loses142HP per cast (maximum2850); six casts plus the following ordinary boundary produce native9322. Actual enemy damage may satisfy the prerequisite sooner; record the state and stop at that legal point. Expect actual state/resource changes, not a forced grant. These numeric values apply only to the supplied fixture.
3. When Venganza is legally usable, cast it on yourself. Expect2AP+1WP consumed and the native temporary5900 book containing8588,8589 and8590. Check the client action buttons and tooltips update.
4. Use one temporary attack on the supplied eligible enemy. Prefer8590 to exercise the newly verified inverse cone; if the implementer selects8588, that is the exact restoration branch already recorded. All three native actions independently commit with0AP/0MP/0WP in the offline source fixture. Check the original book returns after the selected action and the consumed temporary button cannot be cast again through a stale shortcut.
5. End the fight and enter another. Confirm the original actions and conditional Venganza availability are reconstructed without stale temporary attacks.

Automatic evidence: `class-morph933-lifecycle-05.json`, SHA256 `867b9b8f9cd5ed058f2fb18f9a45a8db3eda99bb6339c685e01c1f172c4e346b`: parent plus all three independent children commit, restoration through8588, foreign/expired UID rejection and source/checkpoint validity pass. The manual continuation samples one child; it does not require three repeated encounters. Client appearance, shortcuts and reconnect remain pending acceptance.

## M7 — One Feca area: creation, movement, turn and expiry

Representative: **Fecalistófedes6967**, native Feca breed1, cast on an empty legal cell, creates **GLYPH1474** through original effects298539→298540→298542. Use a deck containing6967 and excluding passives6988,6994 and6999 for this card. Original creation criteria require a free target cell, at least2WP, and no area1477 within distance2. Actual Ready/cast run03 verified level200 resources6AP/3MP/6WP →1AP/3MP/4WP: total5AP and2WP, with MP unchanged. The ordinary cast plan charges5AP/0WP; the original glyph branch separately consumes2WP. Do not assume sufficient resources from the displayed maximum.

The installed footprint has exactly five cells: center plus the four cardinal neighbors. Without6999, the creation runner has duration1; native metadata selects the target clock and the current server timing provider falls back to the caster when that recipient is a cell. Actual Ready/cast run03 verified paired1474/1477 creation, the five-cell footprint, ownership, movement non-activation and45damage to native Pestruzillo5574 level133 (4500HP) at its turn start. Run03 completes normal expiration and post-expiry cell reuse with stable source/tool hashes, plain checkpoint serialization and unchanged input source. Earlier failed expiry runs are superseded for this exact case. No live client acceptance is claimed.

Use the source-validated common enemy for this card:

```text
!mob 5574 133 1
```

Verified fixture: Feca at `(-23,-143,70)`, enemy at `(-22,-143,70)`, empty glyph center `(-22,-142,70)`. Cross cells are `(-23,-142)`, `(-22,-143)`, `(-22,-142)`, `(-22,-141)` and `(-21,-142)`, on height70. The actual timer is caster7, round2, start: both areas disappear when the next Feca turn starts. These coordinates identify the offline arena fixture; use an equivalent legal placement only if the manual arena differs.

1. With the level200 Feca and native level133 enemy positioned as above, cast6967 on `(-22,-142,70)`. Check the five-cell cross, Feca ownership, exact resource loss, and measured expiration boundary. An occupied-cell cast must follow its actual alternative branch; it is not automatically an illegal cast or a glyph.
2. Move the Feca to `(-23,-142,70)` inside the cross, then to `(-23,-141,70)` outside using normal movement. **Creation and movement do not activate this glyph:** its original entry mask is10000, with empty exit/removal masks. No movement damage is expected for this representative.
3. End the Feca turn with the enemy still at `(-22,-143,70)`. At the enemy turn start, its HP must change from4500 to4455. The current server policy maps glyph turn-start activation to event10000; that mapping is explicitly a server policy, not a recovered original server producer. Root298554 excludes caster state6925 at level5 and target fight property75; the damage child also applies the original6988/radius guard. Compare only the target accepted by those original selectors/criteria.
4. End the enemy turn. At the next Feca turn start, both1474/1477 areas must disappear and enemy HP remain4455. Move into the former cross at `(-22,-141,70)`; no activation is expected. Check that the area disappears and no later turn-start activation or blocking survives in its old five-cell footprint. Do not add an overlapping-glyph branch to this card.

Covers: original empty-cell creation branch, native cross geometry, ownership, movement non-activation, explicit turn-start policy, selectors, resource threshold and normal removal. Measured cost and first enemy activation are5AP+2WP and45damage for the exact level200/level133 fixture above. Evidence: `.runtime/combat-review-20261008/feca-glyph-manual-03.json`, SHA256 `68623dd650aba04bcb232f8f76efb54ba4576efe5e1b781b58e39eddfe3eb0b3`. This verifies one complete server sequence, not all Feca glyph variants or graphical client behavior.

## M8 — Ordinary healing and overheal cap

Spell: Aniripsa Palabra Sanadora779, with a legal target from its actual tooltip. Prefer the prepared injured ally; use self only if the installed rule permits self. A helper client is optional for the other cards, required for this ally variant.

1. Start the supplied encounter and obtain a known HP deficit by normal combat. Record target current/maxHP and healer resources.
2. Cast Palabra Sanadora on the legal injured target. Compare floating healing, HP increase, maximum cap and resource loss with the card.
3. Cast with a deficit smaller than the prepared heal. The target must stop at its actual maxHP; the displayed result and server HP must agree.
4. Try a disallowed target or insufficient resources. Expect no unintended damage/healing or partial cost. End a turn and check the HP HUD remains synchronized.

Covers: fixed healing, selectors, overheal clipping and rejection, complementing Sacro's percentage/state healing.

### Symbiot selection and persistence acceptance after deployment

Use the prepared Osamodas and captured creature from M4. Select its occupied slot in the normal Symbiot UI, then summon it through Invocación. Finish the fight normally and start another: the creature must remain captured, the selected slot must be preserved, and availability must recover. Disconnect and reconnect outside combat, reopen Symbiot, and repeat the summon. Record any missing creature, changed selection or stale unavailable slot as a single lifecycle failure. This checks the newly connected selection13571, settlement persistence and departure reset together. Native roster hydration is connected to character entity serialization; its visible client result still requires this acceptance sequence.

## M9 — Osamodas dragon transformation and return

Status: the owned state/cost/cooldown roundtrip is automatically verified; appearance, attack changes, summon interaction and complete fight cleanup still need acceptance. Reuse the M4 character and owned creature.

Forma Dracónica7349 is granted by innate7129 through native326448; its grant excludes an active family933 effect and instance862. The actual Ready/owned-grant audit committed7349 on the owner's cell for AP2/MP0/WP0, installed state7123, advanced ordinary end-turn/ACK cycles through the native cooldown, and committed7349 again for AP0/MP0/WP0 to remove7123. State7134 level5 remained after the return. The passive Simbiosis7337 is not the active transformation command. No933 or859 effect executed in either7349 parent trace: class11 profile5900's temporary book and captured-creature recall are separate mechanisms and are not this test's evidence.

1. Record the normal appearance, visible book, resources and M4 summon. Select Forma Dracónica7349 and target your own cell. Expect AP loss2, no MP/WP loss and state7123 installed. Record the client appearance and book; those are not yet automatically certified.
2. End turns normally, including the owned creature's turn, until the native two-turn cooldown permits7349 again. A rejected early recast must not spend resources or partly change form.
3. Cast7349 again on your own cell. Expect AP0/MP0/WP0, removal of7123 and preservation of the existing summon/control state7134. Check that appearance and visible actions return cleanly; do not assume this invokes933 or859.
4. The separate transformed attack and precise summon interaction require their own supplied native expectations. Do not treat the verified state roundtrip as an attack/book test.
5. Finish or leave through the normal owned teardown, then enter a fresh fight. The source-proven availability reset restores owned creature slots without changing their profile, name or selected slot; the live cleanup acceptance remains pending.

Evidence: `.runtime/combat-review-20261008/osa-dragon-manual-02.json`, SHA256 `cbb2f1533ca5b84682fe4826dfcca9761d1f46ba700aebbb526e58f1821a9b85`; source/tool stable. Client appearance, temporary-book behavior and complete summon fight cycle are not certified by this artifact.

## Conditional additions, not a default exhaustive session

Add **one** additional card only if automated inventory leaves a mechanism uncovered: Sram trap5182/5183 entry→trigger→removal; Tymador bomb→Detonación6495 chain; Selotrop gate placement→cast/travel→removal; a transformation granting temporary actions; or a nonzero-floor encounter. The implementer supplies the exact sequence and expected values first. Do not ask Hector to explore every combination.

For the native nonzero-floor variant, the verified anchor is:

```text
!tp 1134 61 -128 50
!mob 5525 1 1
```

Repeat M1 movement/basic cast there only when selected-floor behavior needs manual confirmation.

## M10 — Sram trap creation, activation and exhausted removal

Status: actual owner-entry lifecycle passed in immutable run02 and independent NPC activation/displacement passed in immutable enemy01; live client acceptance remains pending. Representative **Trampa de Repulsión5182**, Sram breed4, is a temporary action granted by the original Ready/state path. Use its actual raw UID5182, not a fabricated ordinary packed spell UID. Alternative **Trampa de Atracción5183** exercises the same constructor with a pull child.

5182 creates native TRAP778 through family308. Its native cross has radius1, one activation, owner activation enabled, and actual captured damage/healing characteristic authority restricted to ten PCs. Root409840→409841 is a push child (family300, parameters2/0/1/0), guarded by absence of target fight property11. No HP damage is promised for this representative. Native trap child coordinates are its center, not a replacement target location. The original `Qq.baD` predicate is zero activations and no execution in progress; its completed-activation cleanup caller is the explicit Wakemu policy `wakemu.successful-activation.Qq.baD-v1`.

Offline preparation command, for the implementer:

```sh
PYTHONPATH=server python3 server/tools/audit_sram_trap_manual.py --output .runtime/combat-review-20261008/sram-trap-manual-01.json
```

Measured run02: Sram level200 on map1134, owner origin(-23,-143,70), legal trap center(-24,-142,70), entry(-23,-142,70). The native cross contains center and the four cardinal neighbors. Cost is2AP+1WP, with MP unchanged by the cast; actual AP6→4 and MP3→3 were recorded. The one-step owner movement costs1MP. Family300 child409841 completed, but the owner stayed at the entry cell: this owner case does **not** establish a two-cell enemy push; the independent enemy01 result below does. The charge1 areaUID226 disappeared from active Qs and its surviving manager remained in retired226. Evidence: private `sram-trap-manual-02.json`, SHA256`d598aedef0c557b917f6ed24b5502b7065445a24423c8eb4f89997f4481493ef`, source stable. Coordinates apply only to that prepared arena; supply an equivalent placement if the live encounter starts elsewhere.

Independent enemy01: the native NPC starts(-22,-143,70), becomes the actual current fighter through ordinary end/ACK, and follows the legal path(-22,-142,70)→(-23,-142,70). Activation moves it to(-23,-140,70), a two-cell +Y push from the triggering cell. The original child uses the current Wakemu area callback source owner7 at(-23,-143,70); that measured direction follows this owner/source position, not a claim that the unrecovered original server used the trap center as caster. The area is removed, with no surviving retired manager in this NPC variant. HP before/after was not captured, so this report makes no HP-damage claim. Evidence: private `sram-trap-enemy-01.json`, SHA256`749f8c2b9152711d983116fa7f628a6063edcdf710413da5daa41d2a6290f31a`, source stable. This validates the supplied geometry and original push-child branch, not all possible trap placements.

1. Start the supplied level200 Sram encounter against `!mob 5574 133 1`. Confirm the granted Trampa de Repulsión button is present after ordinary Ready.
2. Cast on the supplied empty legal center. Check the five-cell cross, Sram ownership and2AP+1WP cost. MP must not change during the cast.
3. For the verified owner variant, move one step to the supplied entry cell. Check1MP cost and that the owner remains on that entry cell. For the independent enemy variant, let the prepared NPC enter using the supplied two-step route on its actual turn. Expect the measured two-cell push to(-23,-140,70); an equivalent live placement must preserve the owner/source and triggering-cell direction.
4. Check that the single-charge trap disappears after successful activation. Its old footprint must not activate a second time. Surviving owned child effects may retain their original manager identity without retaining a spatial trap.

The harness checks unpublished spell previews and failed movement callbacks preserve their source fight. A passing constructor/unit suite alone does not certify this card or the client display.

## Report format and acceptance limits

Use one row per card: `ID | character/level | build | pass/fail/blocked | first failing step | expected | observed | screenshot/log reference`.

If time is limited, report only the first failing step with spell/state names and before/after resources. Do not repeat it with ten enemies. The implementer expands the failure into automated regressions and tells Hector when a materially changed build is ready for a focused retest.

Manual pass certifies the visible sampled sequence on that build. Complete18-class coverage, exact conditional variants, all captured descriptors, critical branches and uncommon interactions stay in automated verification/inventory; this document neither requires813 manual spell rows nor certifies those untested mechanics.


## M11 — Sram Double: appearance, control and next-turn persistence

Status: production cast, atomic commit, next owned turn, legal class damage death/removal and JSON checkpoints passed; live client appearance remains pending. Use a level100 Sram with the legitimate **Double4603** action available through the normal spellbook/Ready path. Do not inject a grant or use a fabricated spell UID. The recorded arena owner is(-23,-143,70); the adjacent empty target is(-23,-142,70), with native range1, line of sight and free-cell checks.

1. Enter the prepared encounter and complete Ready. Confirm Double is available and the Sram has at least2AP and1WP.
2. Cast Double on the adjacent empty legal cell. Expect2AP+1WP consumption (recorded AP6→4, WP1→0), one controlled double with the Sram's appearance, and no inventory or player-stat clone.
3. End and acknowledge the Sram turn, play/end the double's controlled turn, then let the enemy complete its turn. Confirm the Sram starts the next owned turn and the double remains a valid registered actor, with no frozen timeline or checkpoint failure.
4. On the next owner turn, try Double on the existing double cell. The captured negative case rejects atomically with native `twI`, preserving the entire source checkpoint. This demonstrates rejection, not which specific free-cell/range/availability predicate rejected it; that distinction still requires full native decision diagnostics.
5. Use the legitimate deck action **Ataque Mortal4581** on the double during successive actual Sram turns, ending/acknowledging intervening turns normally. In the recorded L100 fixture three successful casts reduce double HP421→258→95→0. On the lethal cast the double must leave the timeline and its QI slot must become-1; later casts/movement must continue without a frozen fight. These damage values apply only to the recorded character, not arbitrary equipment.

Offline evidence: `sram-4603-commit-cycle-04.json`, SHA256`ea1b0cec7a08e1f401f0bbfdeaec0cc1fb80b78f4e6aac34e6f1045586d867be`, stable source, seven visual regressions passed. Actual actor229/controller7 retained model40 and105 appearance bytes; its307 creation notification13497 was218 bytes. State9179 on the owner has duration2/end clock; double states3667 and1304 are indefinite. The measured next cycle preserves all three: **state9179 expiration is not evidence that the double itself disappears**. Independent `sram-double-lifecycle-01.json` SHA256`6c6d36fbd8dcc7f8024884a9e46517d9d13b329766b2a32d26cfe6f05a2b3bfd` proves final retirement through three real4581 casts, with no HP injection, final HP0/QI-1/out-of-order and valid checkpoint. The source is preserved; owner9179 expiration remains a separate mechanism.

## M12 — Steamer Microbots: rail movement and explicit removal

This is an optional short card for the distinct rail mechanism. Offline normal casts and owned movement passed; client rail drawing/HUD and the prepared live placement remain pending. Use a prepared level200 Steamer with the legal Maquinaria6919 deck and the **Microbot7008** action granted by actual Ready. Do not inject that action or its UID. The implementer must prepare map1134 with the caster at `(-8,-7,-1)` and a surviving enemy away from the three rail cells.

1. Cast Microbot at the empty cell `(-7,-7,-1)`. Expect one bot and1AP+1WP consumed. End the turn normally and wait for the next Steamer turn.
2. Cast Microbot at `(-5,-7,-1)`. Expect another1AP+1WP consumed and a rail joining the bots through `(-6,-7,-1)`. End the turn normally.
3. On the next owned turn, move one cell from `(-8,-7,-1)` onto the first bot: expect1MP consumed. Then request the **two-cell path in one movement** through `(-6,-7,-1)` to `(-5,-7,-1)`: expect1MP consumed, not2. Check the client MP display and final position.
4. On a later owned turn, cast Microbot on the existing first bot at `(-7,-7,-1)`. Expect the first bot and connecting rail to disappear; the second bot remains. The measured removal cast costs1AP+1WP.
5. Cast Microbot again on that now-empty first cell. Expect a new bot and restored rail if the legal source checks accept the request. Actual run02 verifies this separate reconstruction with a fresh UID and a reconnected rail. Client reconstruction/rendering remains a pending acceptance step.

Evidence: [native movement contract and actual transaction limits](native-microbot-owned-movement-20261008.md). Do not wait for an assumed bot timer: eight recorded production turn cycles retained the bots. This card does not certify four-/six-cell live movement, rail-only/always-one-MP transformations or client reconnect rendering.
