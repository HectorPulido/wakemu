# Enutrof implementation refresh — 2026-10-10

Native breed **3**. Estimated implementation **75% (±15 percentage points)**, using the weighted rubric below. This measures available implementation and integration, not the fraction of spells tested or manual certification. No class-wide acceptance has been demonstrated. The initial inventory refresh was read-only. Subsequent authorized runtime qualification and the shared321 correction are recorded below; no services were restarted and no catalog was activated by this class owner.

## Current authority and denominator

Read-only PostgreSQL transaction checked active release `548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd`. The previous [review](../remaining-classes-20261010/3-review.md) and [typed inventory](../remaining-classes-20261010/3-inventory.json) supply the historical dependency edges. Current presence was checked by typed record collection, not by matching unrelated numeric IDs. The historical graph was not regenerated, so newly introduced dependencies outside it are not claimed exhaustive.

The owned roster is 21 active spells, 17 passives and four granted actions. With seven companion abilities this reaches49 spell definitions. Owned/extras direct closure has762 effects and39 states; adding innate3652/4464/5197 yields980 effects and46 states, five profiles and eight areas. The larger denominator includes shared cosmetic innate4464. Current release contains980/980 effects,49/49 spells,5/5 profiles,8/8 areas and45/46 states.

State8873 remains absent, but its current apply effects394229/394230 both require `IsInFight() and False`. This is confirmed dormant data absence, not evidence that an enabled Enutrof action fails. The old blocked-state label must not be used to reject the entire class.

## Complete owned roster

Every row has published spell data and shared execution routes. **U** means the complete class-specific action/passive sequence is unverified, not absent. The JSON records each row's transitive families, states, profiles and areas. Root lists originate in the historical typed projection; current presence was refreshed.

| ID | Native label | Kind | Roots | Status |
|---:|---|---|---|---|
| 2008 | Pala del Juicio | active | 384964, 384968 | U |
| 2010 | Pala Asesina | active | 384980, 384981 | U |
| 2011 | Jarabe de Pala | active | 241993, 241995, 385333, 385334 | U |
| 2012 | Pala Drona | active | 384982, 384990, 385960, 385961 | U |
| 2013 | Pala Sísmica | active | 36828, 255073, 386033, 386037 | U |
| 2014 | Cortes | active | 254912, 385319 | U |
| 2015 | Timo | active | 36836, 159555, 384864, 384867, 385970, 385973 | U |
| 2016 | Impuesto | active | 243408, 243449, 254920, 254923 | U |
| 2017 | Depuración | active | 254928, 385326, 385327, 385329 | U |
| 2018 | Fusión | active | 384923, 384926, 386107, 386113 | U |
| 2019 | Meteoro | active | 384870, 384888 | U |
| 2021 | Brasas | active | 384930, 384931 | U |
| 2022 | Río de Lava | active | 384915, 384917 | U |
| 2026 | Riqueza Sísmica | active | 243307, 243316, 384850 | U |
| 2032 | Purga | active | 384951, 384954 | U |
| 2037 | Explosión de Grisú | active | 384911, 384912, 384913, 384914 | U |
| 2064 | Fuerza de la Edad | active | 254979, 384840 | U |
| 6324 | Aceleración | active | 384824, 384839 | U |
| 6337 | Torpeza | active | 243063, 243065, 300062, 385341 | U |
| 8240 | Avaricia | active | 385357 | U |
| 8242 | Corrupción | active | 385377 | U |
| 2009 | Geología Avanzada | passive | 385818 | U |
| 2028 | Arte de los Caminantes | passive | 386210 | U |
| 2039 | Bendición Anutrof | passive | 386011 | U |
| 5059 | Colocaciones Bursátiles | passive | 386179 | U |
| 5071 | Codicia | passive | 386178 | U |
| 5075 | Perfórtanker | passive | 386207 | U |
| 5076 | Cotización en Bolsa | passive | 385994 | U |
| 6326 | Intereses Acreedores | passive | 386078 | U |
| 8272 | Intercambio Asíncrono | passive | 385985 | U |
| 8273 | Estribo | passive | 385992 | U |
| 8274 | Provectrato | passive | 385794 | U |
| 8275 | La Binocular | passive | 386077 | U |
| 8276 | Seguro a Todo Riesgo | passive | 386082 | U |
| 8277 | Protección Mineral | passive | 386097 | U |
| 8278 | Optimización Focal | passive | 386104 | U |
| 8279 | Tuneladora | passive | 386132 | U |
| 8280 | Herencia | passive | 386211 | U |
| 2027 | Llamada del Compañero | granted | native grant; see JSON | U |
| 2038 | Perfórserker | granted | native grant; see JSON | U |
| 2063 | Excavación | granted | native grant; see JSON | U |
| 6405 | Deuda | granted | native grant; see JSON | U |

## Grants, states and resources

Current innate3652→384427→384677 grants2063/6405/2027/2038 via384678/384680/384681/384973, bar2 slots0–3 respectively. All four use the real exclusion `not HasEffectWithActionId("caster",933) and GetInstanceId() <> 862`. The alternative5197→241782→242154 grant2038 also requires2027 in the deck. These are actual649 definitions, not injected base-deck spells. Acquisition, repeated activation, expiration and reconnect should be exercised together before accepting the class.

Treasure3652/8552, investment8553–8554, deposits5203–5205/8559–8567, debt5395 and Perfórserker702 all have current definitions. Generic state application/removal and current-stat consumers exist. That establishes machinery, not exact class-specific accumulation, ceilings, reset or prospecting-to-loot behavior.

Perfórserker702 contains37098, family808/eWq. `combat_ap_as_mp.py:21` validates actual actors/PA and installs an AP observer; factory wiring is `combat_effect_runtime.py:543`. `combat_ap_property_cost.py:1` explicitly forbids positive AP costs under AP_AS_MP; it does not blindly remap spell AP costs to MP. No family933 occurs in this historical Enutrof effect closure. Its presence in grant exclusions is not evidence of a missing933 form book. Native form entry, altered legal costs, movement gain and exit still need an owned-action test.

## Companion constructor and books

All five profiles1380–1384 have current abilities2058,2077,3541,3542,8257,8258,8259; raw UID equals reference, maximum245, override−1. Their initial-state exports have property15 and an explicitly empty initial-state triple list. Empty is native constructor data, not a missing book/state. Characteristics and property records are present. Generic summon creation, original owner/controller, native targeting, book serialization, retirement and reconnect implementations exist. No dedicated Enutrof complete2027→companion turn→ability→removal proof was found. A generic summon test mentioning1380 is not that proof.

## Areas and deposits

Current202/203/204/205 are ENUTROF_DEPOSIT/type12/faU, point geometry, with root388707/388706/388705/388703. Their actual `raw_bdh[0]` is1 for all four; different visual IDs do not justify inventing four different grade operands. Current207/209/781/1925 are glyph definitions rooted158232/384653/157651/386264. All eight are present. Empty entry masks on781/1925 are data, not automatically a failure.

`combat_effect_area.py:214` recognizes deposits and lines390–392 persist native grade provenance; `combat_area_contracts.py:10` maps the subtype tofaU. `combat_effect_area_events.py:314` implements current-turn10000, line327 frozen movement entry10001/stay10008/exit10002, line351 removal10011. Its line378 Qq running-source path forwards actual source mask6 events;10006 is supported at lines14/276. No separately named external10006 publisher was found. Consequently **full deposit10006 delivery is unverified**, while creation, movement and grade support are implemented; it would be false to describe all deposits as unsupported.

`test_combat_deposit_area_lifecycle.py` contains four constructor/ownership/grade/null-manager checks using real exported prototypes. `test_combat_effect_area_events.py`, `test_combat_area_predicates.py`, generic summon/AP-as-MP/resource tests cover shared pieces. They do not demonstrate owned Enutrof mining, upgrade, consumption, yield and complete reset.

## Reusable changes since the earlier review

Current shared code includes native retained replay/Qj reentrancy protection and separate activation ancestry; family1001 clone UID forwarding; safe self-removal during current-stat callbacks; corpse eligibility no-op handling; death1013 channel6 delivery; pre-end death synchronization;321 decurse lifecycle events; live summon PB properties; actual summon flags in stat snapshots; multiplayer registration, timeline and reconnect ownership fixes. These remove concrete shared failure modes relevant to this closure. Their successful Cra/Iop/Pandawa/Ecaflip or captured-summon cases are supporting shared evidence, **not an Enutrof functional pass**. Workspace support does not certify that a particular live container contains every change.

## Missing versus unverified

* Confirmed data absence: dormant8873 only, with literalFalse producer guards.
* No missing handler family was identified in the existing72-family class route inventory:60 registered and12 factory-authority-gated. The old route matrix is historical, not a fresh runtime factory execution count. Current explicit808/813 wiring and area/retention producers were inspected.
* Highest-risk unverified integration: deposit10006 and upgrade/consumption order; prospecting/treasure actual settlement; companion profile/book/control lifecycle; Perfórserker AP/MP entry and restoration; state/area cleanup and private client action-bar restoration.
* No new enabled gameplay defect was proven by this read-only audit. Unknown branches remain unknown.

## Estimate and next acceptance

| Domain | Maximum | Estimated implemented points |
|---|---:|---:|
| Published/shared foundations |25|24|
| Core mechanics |30|25|
| Passive/secondary interactions |30|18|
| Lifecycle/client integration |15|8|
| Total |100|75|

The estimate discounts missing end-to-end class proof and uncertain producer coverage; it is not obtained by counting untested spells as broken or by counting handlers as finished mechanics.

Next technical battery should initialize an actual Enutrof deck and all real innates; acquire the four native grants; exercise each active with positive/negative native conditions; compare each passive enabled/disabled at relevant levels; create/mine/upgrade/consume all four deposits and verify entry/exit/removal; obtain each companion profile and use its seven-book actions; enter/exit Perfórserker through actual2038; verify AP/MP/WP, treasure caps/reset, rejection rollback, real death and next-turn cleanup; checkpoint/reconnect without duplicate effects; finally check prospecting against authoritative reward calculation. Manual acceptance should follow that complete sequence with exact build/commands once those preconditions are verified, rather than inventing a runnable class battery from catalog labels.

## Authorized qualification follow-up — 2026-10-11

The original **U** table is the historical evidence state at inventory time, not a current claim that these primitives remain untested. Current qualification is maintained in [the semantic evidence JSON](../enutrof-passive-qualification-20261010.json), [the manual battery](../enutrof-manual-acceptance-20261010.md), and `server/tests/test_enutrof_runtime.py`. Active release remains548e1468…; tests use actual owned initialization, grants, turn-start, legal casts and unchanged-source transaction snapshots.

Verified cases include all14 ordinary elemental attacks with rejected-self rollback; all17 passive configurations initializing with the four actual grants; automatic Drheller ownership and all seven book records; duplicate2027 rejection; real Drheller turn3541 creating203 after legal8240 removal of the controller's existing203; mining baseline/2009,2028 cost substitution and8278 minimum range;2026 conversion to207 versus5076's209;8240 native ore buff/consumption;6405 level1 versus6326 level2 with atomic repeated-mark rejection;2039 first-turn treasure;2037 native two-cell cross damage; and actual Perf entry/exit with delayed maximum-MP restoration and8272/8274/8275 conditional casting tables. Independent passive qualification covers5059,5071,5075 and8276; remaining cases are explicitly tracked rather than inferred from initialization.

A genuine shared omission blocked8273: applying state842 constructs subscribed child242089, family321/eZi, but `combat_subscription_runners.SUBSCRIPTION_FAMILIES` did not include321. The correction adds321 to the central deferred-runner registry. Existing generic registration, replay, removal and `NativeStateDecurseHandler.prepare_activation` now handle it; no spell or breed exception was added. Original eZi inherits the base eZR serializer and has no additional wire codec, so its fresh deferred payload has value0/unexecuted status and the original PL, without fabricated subclass fields. The permanent codec/registry regression, complete decurse tests and actual2039/8273 branch passed8/8 in `enutrof-decurse-fix-focused.log`.

Important native prerequisites: Ready already constructs the Drheller, and first actual1001 creates deposits.3541's385405 rebinds the source to the controller;385439 requires that controller to have no203, so the positive fixture consumes the existing203 through8240 first. The resulting203 belongs to the controller while marker781 belongs to the companion. Perf exit242970 is a target-clock-one-turn MP-loss effect; immediate maximumMP0 is native and must expire through the real next turn. Treasure8552 does not imply a prospection buff: settlement already consumes authoritative stat33, and the actual mining test proves no invented PP increase.

This is automated implementation evidence, not a completed client acceptance or deployment receipt. Companion death/reinvocation and Tuneladora now pass actual-action regressions: a native7962 attack kills the owned companion, followed by a legal2027 creating a different owned UID;8279 reduces the companion maximumMP by3 and its real ore action teleports it to the selected deposit cell. Remaining8277/8280 interactions and the final combined regression remain pending before provisional readiness.

### Fresh own-area selector correction — verification pending

The8277 protection branch applied its native buff but failed to consume the owned deposit: effect386100 (family843) received actor7 at the deposit cell instead of the registered owned Qq. Its fcE mask contains bit43 (own Qq) and bit51. The existing native selector already checks actual Qq identity and owner equality, but the server fresh-child relationship routing omitted bit43 and preserved the transmitted actor. The narrow correction includes bit43 in that routing; explicit already-selected/replayed PVs retain their existing path. A generic regression covers selection of an owned area, exclusion of a foreign area at the same cell, and preservation of an explicit replay recipient. The focused generic owned-Qq resolver and actual8277 deposit removal now pass in `enutrof-qq-rootfocused.log`; the final protection-state timing assertion remains under source qualification, so a complete8277 PASS is not yet claimed. This is not a deployment receipt. The group live-coordinate implementation was already present and was not changed for this fix.

### Final technical gate

The frozen Enutrof runtime, companion lifecycle and deferred-subscription aggregate passed21/21 on active548e1468… (`enutrof-final-coherent.log`). Independent8277 callback validation passes: actual386098 grants100 resistance, the matching858x protection is level1 during application and0 after native end expiration, and the owned deposit is consumed; passive-off/no-deposit controls remain negative. Both8280 contextual companion-death and owner-to-companion treasure receipt cases pass. These results support provisional technical readiness, with the complete manual battery still pending. Independent5075 evidence remains limited to its observed end-boundary branch; the separately unrecovered74mh caller is not silently certified.


### Current release and multiplayer follow-up — 2026-10-11

The current authority is677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d;
the548e inventory and older gates above are historical. Current selected
aggregate27/27 passes (`enutrof-coherent-active677-final.log`). An additional
actual multiplayer8277 test passes1/1: real owner7 deposits are consumed with
386098/+100 resistance, while another actual player8's deposit survives with
no386098. See [current contextual evidence](../enutrof-passive-branches-20261011.md).
This closes that ownership branch, not every enabled native path.

The full18-class diagnostic subsequently exposed2010 push-then-damage recipient
loss: fresh QK selection used the old point after384976 moved its selected
recipient, so241977 selected nobody. A generic staged point-leaf recipient
correction outside the frozen server passes11 focused methods, preserving
actor-group fresh selection, Xelor7189 and Eliotrope7206. Until that candidate
is applied and the coordinated gate passes, the old all14-elemental claim is
not a current unmodified-server pass. No class-specific exception was added.


Current additional receipts: actual multiplayer8277 ownership control1/1,
all six previously book-only controlled companion actions plus6337 numeric
control2/2, and fourteen normal/critical pairs plus bounded checkpoint/new-fight
serialization2/2 are green on actual677. The last2/2 uses the staged generic
resolver candidate and clear-LOS fixture, so the integrated current-server
gate remains required. Full evidence and numeric pairs are in the current
contextual report. Profiles1381–1384 have identical current books/initial-state
data to1380; lawful cosmetic acquisition is a manual appearance prerequisite,
not a proven gameplay-route failure. The5075/event74 producer remains unknown,
and actual client reconnect is not certified by JSON serialization.
