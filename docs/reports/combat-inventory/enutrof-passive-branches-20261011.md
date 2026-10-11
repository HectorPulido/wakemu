# Enutrof contextual passive qualification — 2026-10-11

This review owns six passives:5059,5071,5075,8276,8277,8280. Current authority is
PostgreSQL revision677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d;
the historical548e investigation below is retained as a chronology, not the
current release gate. The current coherent aggregate passes27 tests for its
selected paths. Each assigned passive has an exercised positive and negative
branch, but this does not qualify every branch:5075 special74 caller remains
unqualified. The actual multiplayer foreign-deposit control now passes as
recorded in the final follow-up below. The general
OWN_Qq selector fix resolved the exercised8277 context. This report is not
complete technical or manual acceptance.

Full effect trees come from the scoped read-only published-records export;
metadata-only records sharing an ID are not allowed to replace actual trees.
No production implementation, database, services or restart was changed here.

Tests use actual breed3 level200 Ready/first1001, legal deck passives, owned
casts and ordinary turn-end/ACK/start pipelines. No state, effect area, summon,
resource or external event is injected. Enemy HP20000 is the existing durable
target fixture prerequisite, not a passive output. The inherited cast helper
uses an explicitly clear-LOS oracle; blocked LOS is outside these cases.

|Passive|Actual native positive branch|Negative control|Acceptance assertion|
|---|---|---|---|
|5071 Codicia|2026 converts owned deposits to207;2063 extracts actual207 through384753/386088.|2063 on207 without5071 rejects atomically.|Owned converted area removed; ordinary reward increases maxMP by1.|
|5059 Colocaciones Bursátiles|Same actual207 extraction with5071+5059 selects386195/state8553 instead of386193/386194.|5071 alone grants immediateMP and does not create8553.|8553 level1,maxMP gain0; actual next1001 consumes deferred state. Further detailed heal receipt remains separately qualified.|
|5075 Perfórtanker|2038 creates real702; actual1002 creates8572 whose386209 selects resistance.|Baseline selects385058 damage instead.|8572 level1,correct native completed leaf,other leaf absent,characteristic snapshot changes. Paid74/8590 route is not proved by this case.|
|8276 Seguro a Todo Riesgo|Actual2039 first1001 grants8552;1002→385942→386083→386084armor and386085decurse.|2039 without8276 retains treasure and never executes386084.|Armor leaf completes and treasure disappears; actual characteristic delta required. Exact armor formula is not inferred from Ready.|
|8277 Protección Mineral|Actual ordinaryMP movement onto an owned202–205 deposit,then1002→386098resistance+matching8589/8586/8587/8588state+386100area removal.|Offdeposit with8277,and ondeposit without8277.|Correctstatelevel1,resistance leaf completes,characteristic delta,originaldeposit removed.|
|8280 Herencia|Actual innate companion owns3614;its1037→386216 checks controller deck;386217 kills only with enemywithin2.|No8280+near,and8280+far.|Correct actual enemy range,completed kill and HP0 only in positive case. Owner treasure-end AP/MP transfer386213/386214 is a separate branch not covered by companion death.|

`test_enutrof_passive_branches.EnutrofPassiveBranchTests` contains the first four
passives in three methods. The first execution was relayed as passed; the
runner's imported TestCase discovery also ran unrelated modules, so imports
were changed to module imports before further runs. Exact final command/count
is owned by Luna's validation report.

`test_enutrof_passive_contexts.EnutrofPassiveContextTests` contains8277/8280.
Execution is queued with Luna; these are pending until actual results arrive.
A failed geometrical prerequisite is distinguished from a rejected native
passive branch, and no fixture mutation is used to bypass it.

## Initial contextual results and unresolved finding

Luna's first contextual run observed the intended8277 resistance/state positive
branch, but its original deposit UID remained after the end boundary. The
expected386100843 removal therefore remains a concrete failed assertion, not
accepted behavior. The root's caster-position predicate succeeded. A targeted
rerun now records386100's exact diagnostic status and coordinates; retained
null-PV event anchoring in `combat_event_replay.py` is an investigation
candidate, not yet a proven native discrepancy or an authorized core change.

The8280 far-distance7 fixture was rejected by actual native terrain during
construction, before passive execution. It was corrected to the established
legal distance3; the test still independently asserts actual companion/enemy
range. Near/no-passive and near/passive cases reached their assertions in the
first run. Final8280 result awaits the corrected rerun.

`test_enutrof_inheritance_receipt.EnutrofInheritanceReceiptTests` additionally
qualifies8280's separate owner treasure-end branch: actual2039 creates8552
level1, then owner1002 must give the owned3614 companion exactly+1maxAP and
+1maxMP through386213/386214. Baseline2039 without8280 must preserve both
maxima. This is queued separately and is not implied by the1037 death case.

Subsequent source inspection supersedes the stale-cell hypothesis:
`combat_effect_dispatch.py` already anchors on-target330 children to the live
selected actor position, matching original eYg's bfs.bcz/bcA/bcB accessors.
Effect386100 uses fcE mask2260595906707457 (bits0,43,51): bit43 requires an
owned Qq area. However the server fresh-child relationship policy in
`combat_effect_resolver.py` recognizes low relationship bits but omits bit43;
a transmitted actor target therefore survives for this pointanD child and
cannot satisfy IsOwnSpecificArea. This is a concrete policy-gap candidate
reported to root for a general fix, with native bit43 semantics already
implemented in `combat_effect_targets.py`. No class-specific workaround or
shared-core edit was made by this review.

Luna's corrected contextual rerun confirms8280 near/far controls pass. The
8277 trace is now exact:386100/family843,level200,caster7,target7,
cell(-9,-7,-1),ancestors386097/386100,status`skipped_condition`,followed by
`no_effect`. Actual owned depositUID49/reference202 is at that same cell.
This rejects the stale-anchor explanation and confirms that the actor target
fails the owned-area criterion while the intended matching area exists. Root
has the general OWN_Qq/bit43 fresh-child selection fix request. Evidence log:
`.runtime/remaining-six-refresh-20261010/enutrof-8277-8280-final.log`.

The final inheritance log now reports `Ran 2 tests in 25.960s — OK`:
corrected near/far companion1037 cases and the separate exact+1maxAP/+1maxMP
owner treasure-end receipt both pass, including no8280 controls. Log:
`.runtime/remaining-six-refresh-20261010/enutrof-inheritance-final.log`.
The8277 area-removal mismatch remains unresolved at this report revision;
its resistance/state branch is observed, but full passive acceptance waits
for the general selector fix and rerun. All three new modules compile.

## Resolved8277 and exact callback timing

Root's general fresh-child OWN_Qq selector fix is now present in
`combat_effect_resolver.py` (SHA c718d44b…), with generic own/foreign-area
selection and replay regression. Actual8277 now removes the matching deposit.
The previous final-state-level1 assertion was incorrect: published8586–8589
have duration1,endtick,target clock. `prepare_server_turn_end` delivers1002
then1037; `RuntimeMessages._end_owned` subsequently expires the end-clock
states before adopting that preview. The test now observes actual dispatcher
callbacks:386098 produces an exact+100 resistance characteristic delta;
the matching386099/101/102/103 application has the correct858x statelevel1;
the deposit is consumed; final statelevel is0 after expiry. No-passive and
offdeposit negative cases remain. Luna reports targeted1/1PASS, testSHA
defccd8e…, log`.runtime/remaining-six-refresh-20261010/enutrof-8277-lifecycle-final.log`.

This class fixture has one Enutrof controller, so a second player's actual
foreign deposit is not constructed here. Generic selector own/foreign
negative coverage is separate evidence and is not mislabeled as a two-player
8277 acceptance run.

## Separate5075/event74 source boundary

Publishedstate8590 owns386125/family912 subscribingchannel3[74], whose
children choose3462 normally or8607 when5075 is equipped. This separate
branch is not implied by the passing Bestiality8572 test. Original eWf
constructor initializesrAA/rAB false; bbx offsets56–66 adds74 only whenrAA
is true;mh(boolean) writesrAA,mi(boolean) writesrAB. A constant-pool scan of
the original client jar for classes referencing eWf and methodmh found only
eWf itself, not an external producer. Current PaidAbilityPolicy explicitly
setsmi=true,mh=false: ordinary paid casts therefore correctly do not emit74
from that policy. The original server mh caller remains unrecovered. No
invented74 event, class exception or modified native switch was introduced.
This enabled consumer's special caller context remains unqualified.

## Manual additions for these six passives

Use separate legal decks, enough actual MP, and an allied player where needed.
With5071, convert a reachable owned deposit using2026 and extract207 using2063;
expect consumption and immediate+1MP. Without5071 that converted-deposit
extraction must reject without cost. Add5059: expect8553level1 and delayed
reward at the next own turn instead of immediateMP. Enter2038 with and
without5075, finish the turn and compare Bestiality's resistance versusdamage
branch. With2039+8276, observe real treasure then finish the turn: armor must
be awarded and treasure consumed;2039 alone must preserve treasure. With8277,
walk onto an owned202–205 deposit and finish: observe the protection
application and consumed deposit; the native one-end-tick state may already
be absent after the boundary completes. Repeat on a teammate's deposit as a
pending multiplayer negative acceptance case. With2039+8280, finish an own
turn with treasure: the actual companion gains+1AP/+1MP. End the companion's
turn near an enemy(within2): it dies via its1037 branch; repeat far away and
without8280 to check it survives. Check actual turn ownership, cleanup and
no ghostQI after companion death.

## Current authority and event74 caller audit — 2026-10-11

The historical548e introduction records the original investigation. Current
coherent validation is PostgreSQL revision
`677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`:
`.runtime/remaining-six-refresh-20261010/enutrof-coherent-active677-final.log`
reports27/27 passing, zero failures/errors/skips, and identical start/end
catalog revision. This aggregate includes generic subscription-runner tests;
it does not mean27 independently tested Enutrof spells or complete multiplayer
manual acceptance. A subsequent actual multiplayer foreign-deposit control
now passes; its separate receipt below supplements this earlier aggregate.

A fresh bytecode audit confirms `eWf.bbx` offsets56–66 publishes74 only when
`rAA` is true. `mh(boolean)` writes that field; constructor and pooled reset
`aWr` clear it. `mi(boolean)` controls a different field and the2188/2234/2263
resource-payment notifications. Thus paying AP/MP/WP does not intrinsically
prove that74 occurred. Current `PaidAbilityPolicy` explicitly choosesmi=true
andmh=false; enabling74 for all paid casts would introduce a new server policy,
not recover an observed native caller contract.

The new scan resolves exact JVM Methodref/InterfaceMethodref owner, name and
signature across all classes in `client/lib/*.jar`. Eight class files contain
an `eWf` UTF8 constant; **zero** contain a method reference to
`eWf.mh(Z)V` or `eWf.mi(Z)V`. This is stronger than the historical string
co-occurrence scan (which counted the setter declaration itself). Artifacts:
`.runtime/local/enutrof-eWf-exact-callers-20261011.json` and
`.runtime/local/enutrof-eWf-caller-audit-20261011.txt`.

This establishes the runner's switch contract and the absence of a direct
caller in the available client jars. It does not establish absence from the
unavailable original server, reflection, or separately supplied classes.
State8590/effect386125's5075-dependent74 consumer therefore remains an enabled
but producer-unqualified branch. No fabricated event, switch change, gameplay
code, catalog write, or service action was introduced by this audit. Recovering
an authentic external caller or explicitly defining a reviewed server caller
policy is required before claiming that branch as actual end-to-end coverage.

### Global catalog and inherited-caller reconciliation

A further read-only revision677 audit searched every indexed effect source,
including spell, granted-spell, state, captured closure and retained metadata.
It found84 distinct channel3/event74 subscribers; subscriptions are consumers,
not evidence that their event is produced. The state8590 application producers
are386129 and386131 (each also duplicated in retained metadata). These install
the consumer state; neither changes `eWf.rAA` or publishes74. The fresh
`native-current-stat-events.json` index contains no74/eWf producer descriptor.
Private evidence is `enutrof-global-event74-8590-20261011.json` and
`enutrof-current-stat-event74-20261011.json` under `.runtime/local/`.

To close an inherited-method-reference loophole in the original scan, the
class-file audit now parses57,242 class identities and superclass links from
all available `client/lib/*.jar`. It searches every Methodref/InterfaceMethodref
named `mh` or `mi` with signature`(Z)V`, then resolves whether its declaring
owner is eWf or any subclass. **No eWf subclasses and no direct or inherited
setter call references were found.** Evidence:
`.runtime/local/enutrof-eWf-inherited-callers-20261011.json`; its reproducible
read-only scanner is `.runtime/local/audit-ewf-inherited-callers.py`.

This wider inventory does not recover an authentic event74 caller. The exact
remaining boundary is an enabled5075-dependent consumer with a known native
runner switch, but an unavailable original server switch-setting caller.
Installing8590, paying ordinary costs, or finding other74 subscribers cannot
replace that missing caller evidence. No `mh=true` policy or synthetic74
notification was introduced. The27-test coherent aggregate remains valid for
its exercised paths and does not certify this separate producer context.


## Actual multiplayer deposit ownership — 2026-10-11

The runtime-only staged test
`.runtime/full-regression-20261011/probe_enu8277_multiplayer.py` passed1/1 on
actual published revision677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d.
Evidence: `.runtime/full-regression-20261011/enu8277-multiplayer-current.log`.
Three ordinary player records and all three decks are supplied before Ready;
players7 and8 are actual Enutrofs. Real player8 turns create its deposits;
player7 then reaches a selected deposit with ordinary movement and runs its
actual1002 boundary. No area ownership, state, resource or event is fabricated.

With8277, an owned player7 deposit triggers386098 and an observed+100
resistance delta, then consumes that deposit. On a distinct player8 deposit,
386098 never completes and the exact foreign deposit UID remains registered.
Both controls use the same full multiplayer turn authority. This closes the
previously unconstructed foreign-player branch; it does not qualify5075's
unknown event74 producer or client reconnect behavior. The permanent test is
staged outside the frozen server tree until the coordinated source freeze ends.


## Remaining enabled-route coverage audit

The27-test aggregate is a selected integration gate, not an exhaustive native
branch denominator. Source review of the current Enutrof test modules establishes
the following remaining limits; no missing implementation is inferred merely
from absent tests.

| Scope | Existing proof | Still unqualified |
|---|---|---|
|21 owned actives|14 ordinary elemental casts;2026 conversion;2037 cross;2064 companion support;6324 mobility;8240 ore consumption;8242 target state;6337 legal form cast/cost|6337 target resource effect is not asserted. Alternate conditions and critical outcomes across the elemental tree are not exhaustively paired.|
|Four Ready grants|2027/2038/2063/6405 acquisition; duplicate rejection; actual form, mining and debt; actual companion KO/reinvocation|Complete grant cleanup/reconnect/second-fight action-bar behavior is not class-qualified.|
|Seven companion book entries|All seven are serialized;3541 actually executes deposit creation/8279 teleport|2058,2077,3542,8257,8258,8259 have no actual ability-cast assertion in the Enutrof modules. Presence is not execution.|
|Five companion profiles1380–1384|Owned constructor/profile range and companion lifecycle are exercised|Each profile's own ability/initial-property/retirement combination is not individually demonstrated.|
|Critical selection|Native machinery exists|The Enutrof cast helper explicitly supplies critical=False; no class-specific normal/critical numeric matrix is demonstrated.|
|Deposits|Actual creation, movement, mining, conversion, grade provenance, ownership consumption and multiplayer8277 control|External10006 delivery remains source-unqualified; all four visual types and every upgrade/order combination are not exhaustively exercised.|
|5075|Actual1002 Bestiality branch|Separate8590/event74 consumer has no recovered legitimate current publisher. Ordinary paid AP/MP/WP must not be used as invented74 evidence.|
|2010|Source-isolated displacement-recipient defect and private generic candidate11/11|Current unmodified server fails the exposed push-then-damage case; candidate must be applied after freeze and gated before claiming closure.|

Evidence scope was checked directly against `server/tests/test_enutrof_runtime.py`,
`test_enutrof_companion_lifecycle.py`, `test_enutrof_passive_branches.py`,
`test_enutrof_passive_contexts.py`, and `test_enutrof_inheritance_receipt.py`.
Their snapshot imports support transaction rollback assertions; they are not
checkpoint restore/reconnect tests. This audit does not claim to have regenerated
the historical980-effect closure from all current root types. A fresh current
closure reconciliation remains necessary before describing every enabled native
conditional route as complete.


### Source-valid companion profile prerequisites

Current2027 roots255225/37144/156906 include a first-success family341 selector.
Its actual307 children37093/255226/255227/255228/255229 select profiles1380/1381/1382/1383/1384
by the caster's cosmetic states6242–6246. With no cosmetic state, the first
child selects1380. Changing character level or RNG seed is not a legitimate
way to select another profile. The exact native criteria exclude the other
four cosmetic states for each branch.

Published retained metadata contains304 producers295543/295549/295555/295561/295567
for those cosmetic states, but the current indexed effect-tree roots do not
contain those producers. Read-only item-action and equipment-effect records
also provide no matching producer. Consequently all-five profile acceptance
requires the actual lawful cosmetic acquisition/application route; injecting
the states would only test an artificial constructor prerequisite. The
default1380 lifecycle is exercised, while the other four lawful constructor
contexts remain explicit source-authority boundaries. Raw current metadata is
in `.runtime/full-regression-20261011/enu-remaining-ability-metadata.json` and
`enu-remaining-effect-closure.json`.


### Additional event74 producer check

A current read-only all-effect-record query finds zero authored emit masks
`target_masks[6]` containing74; see
`.runtime/full-regression-20261011/enu-global-authored-emit74.json`. This is
distinct from the enabled channel3 subscription consumers. The57,242-class
bytecode scan contains zero `mh/mi(Z)V` method references across any owner.
`eWf.rAA` is private; its setter is the only true-write path in the inspected
class, while constructor/reset clear it. These additional checks recover no
legitimate producer and do not authorize inventing one. Original server-only,
reflective or unavailable-source contracts remain outside the available proof.

All five current Drheller profiles have identical published seven-action book
payloads and identical initial-state/property payloads; this source equivalence
is recorded in `enu-profile-authority-compare.json`. It supports shared
implementation reuse, while actual cosmetic-state-dependent births remain a
separate acceptance boundary.


### Six controlled companion abilities and Torpeza — terminal qualification

The corrected actual-action probe passes2/2 at unchanged PostgreSQL677; log
`.runtime/full-regression-20261011/enu-remaining-actions-corrected.log`, probe
SHA8f9304eb… . Together with the prior3541 test, all seven default-profile
companion abilities now execute through owned native action dispatch.

- 2058: ordinary companion movement first establishes native linear range2..3;
the real enemy is pulled from[-5,-7] to[-6,-7], with positive bounded distance
reduction and AP payment. Empty eligible cells are not used as pull evidence.
- 2077: selected deposit disappears, its selected-cell marker781 belongs to the
actual companion, and the source-authored conversion children complete.
- 3542: actual protection child386173 raises companion armor0→205.
- 8257/8258/8259: after lawful8240 consumption of the existing requested deposit,
the actual companion creates204/205/202 respectively at its selected cast cell
with controller7 ownership, plus companion-owned781.
- 6337: both ordinary and actual Perfórserker forms reduce actual hostile MP3→2;
self-target rejection leaves the complete snapshot unchanged. No AP reduction
is invented.

The permanent equivalent is staged outside the frozen server tree as
`test_enutrof_remaining_actions_candidate.py`. These cases retain the existing
explicitly clear-LOS fixture and do not certify blocked native LOS. They qualify
the default1380 action book, not the unavailable lawful cosmetic prerequisites
for other profiles. The earlier coverage-audit rows describing these abilities
and6337 as unqualified are superseded by this terminal receipt.


### Paired critical attacks and bounded checkpoint/new-fight gate

The runtime-only candidate probe
`.runtime/full-regression-20261011/probe_enu_critical_checkpoint.py` passes2/2
at actual unchanged PostgreSQL677; evidence
`.runtime/full-regression-20261011/enu-critical-checkpoint-current.log`. It
injects only the staged generic QK point-leaf resolver candidate in-process;
therefore this is candidate evidence, not an unmodified-server or deployment
receipt. The existing clear-LOS fixture remains an explicit scope limit.

|Spell|Normal damage|Critical damage|AP|WP|
|---:|---:|---:|---:|---:|
|2008|59|73|2|0|
|2010|82|102|3|0|
|2011|110|137|3|1|
|2012|110|137|4|0|
|2013|152|189|5|1|
|2014|95|118|3|1|
|2015|50|62|2|0|
|2016|110|137|4|0|
|2017|192|239|5|2|
|2018|101|126|3|1|
|2019|76|94|2|1|
|2021|76|94|3|0|
|2022|152|189|5|1|
|2032|76|94|3|0|

All28 actual casts preserve the source fight snapshot, deal positive damage,
use identical AP/WP payment in each pair, and have a strictly greater critical
result. Values describe this deterministic level200 fixture, not universal
damage independent of equipment/target resistances.

The second case serializes the actual companion checkpoint through JSON and
preserves account owner3, controller7 and all seven native book entries. After
a real8240 consumes an owned deposit, an independently constructed fresh fight
has exactly one owned companion, its original book, four grants, original AP
and original deposits; the prior source snapshot remains unchanged. This
qualifies serialization and absence of shared/global fight-state leakage.
`fight_checkpoint_store` deliberately aborts interrupted fights and does not
restore client timelines; no resume API, actual client reconnect or complete
live battle-exit/reentry contract is claimed.

Profiles1381–1384 share identical published action books and initial-state
payloads with1380. Their lawful cosmetic marker prerequisites remain a manual
appearance prerequisite, not a proven missing gameplay handler. The remaining
5075/event74 legitimate producer boundary remains open. Provisional status
requires the coordinated integrated gate after applying the staged generic
fix; these focused passes are not a100% claim.
