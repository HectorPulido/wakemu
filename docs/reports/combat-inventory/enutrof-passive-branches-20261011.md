# Enutrof contextual passive qualification — 2026-10-11

This review owns six passives:5059,5071,5075,8276,8277,8280. Source is published
PostgreSQL revision548e1468d1c17a9542b34419c8a4f6c539696135fb4ffd4c03e8dae29c9f4edd.
Current result: all six assigned passives have passing actual positive and
negative branch tests. The general OWN_Qq selector fix resolved8277. Separate
5075 special74 caller and a multiplayer foreign-deposit manual probe remain
explicitly unqualified; this is not complete manual acceptance.

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
