# Desbalizaje6349 pre-target UI criterion — source investigation

The native6349 casting definition has cost1AP, range1–6, no LOS. Its criterion is `NbSummons("caster") > 0 and ((not IsSpellInDeck(6952) and (IsOwnSummon(3798) or IsOwnSummon(3799) or IsOwnSummon(3800))) or IsSpellInDeck(6952))`. The automatic grant347173 selects raw6349 UID, bar2/slot4, caster-level capped245. Native eWn.fMO inserts the raw object into the book/execution registry and shortcut; it does not grant a packed player UID.

Independent UI route: bPO's `usable` property obtains the actual current fighter and resolves its book object through `big.js(shortcutUID)`, then invokes `buH.a(caster,bookobject,null,true)` (bytecode2877–2983). fbX delegates to fcO; fcO supplies the spell's full gtP criterion to fcj. fcj's null-cell branch746–769 evaluates `amb.b(caster,null,spell,fight)` and returns twV when false. The eOG IsOwnSummon criterion defaults to target and returns−1 for a null resolved target (bytecode61–67); fyG is not ePy and supplies no fallback target. Thus this code path rejects6349 with6952 absent even when the global summon count is positive. AP alone cannot make this criterion true before target selection.

The `#expression#` grammar is not an evaluation bypass: eQd parses token380 and calls `alS.cK(false)`; this marks the expression's bDA presentation flag. eTI checks bDA when formatting descriptions. amb.b and the AND implementation alr still evaluate the expression. The canonical published6349 cast_criterion_raw currently contains no # markers in any case.

This explains a concrete pre-target rejection route, but does not certify the live client's selected predicate object or status return without inspection. A separate live GF/dTB count inspector is being prepared by the casting agent. Native NbSummons also requires roster dTE=true, dsA=false, dpr object identity equal to caster, and no ffe.sft exclusion; rendering a beacon alone does not prove those facts. Source dumps are `/tmp/wakemu-desbalizaje-{bPO,fbX,fcO,fcj,eOG,amb,alr,alS,eTI}.txt`. No production or client edits were made.

## Confirmed live summon-registration defect (fight73)

On 2026-10-08 at19:12:38 and19:13:50 UTC, the actual client reported native `NbSummons` count0 with two living Cra beacons: actor60/breed3798 and actor33/breed3800. Both controllers were actor6 with object identity equal to the selected Cra. Both had `dTE=false`, `dsA=false`, and property103 absent. Thus ownership is correct, but the native summon flag is wrong. The pre-target UI patch cannot repair this failed global criterion. Private evidence: `.runtime/combat-review-20261008/desbalizaje-live-native-count-fight73.json`. The producer/reset cause and correction remain under investigation.

This was a shared summon-registration regression, not a Cra-only spell exception. Osamodas acceptance must inspect actual native summon count and each summon flag/controller after creation, stat snapshots, turn transitions, and reconnect. Do not consider ownership alone sufficient and do not bypass `NbSummons` to hide a missing native flag.

## General serializer correction

`registered_summon_stats` serializes `pW.Uh=1` from validated `is_summon=True` authority. Native `eGn.zl` reads `eGj.dTE` into this field and `eGn.zm` applies it through `eGj.ly`; the prior false byte reset the constructor flag. Registered307/324/1002 postcommit and reconnect snapshots share this serializer. Ordinary PC/NPC flags remain false. The 12873 envelope roundtrip and serializer tests passed. The fix is included in `complete-20261008-r31`.

Manual acceptance procedure: reconnect to the deployed world, enter a fresh fight, place one beacon within six cells, retain at least1AP, and use Desbalizaje. The beacon must disappear, its published bonuses apply, and no summon-count rejection occur. Inspect the native count before/after (1→0) rather than accepting the button alone as proof. Repeat the shared count/snapshot/reconnect gate for Osamodas.

## Manual acceptance recorded

Hector confirmed Desbalizaje works after deployment of complete-20261008-r31 (2026-10-08). The pre-deployment failure and native count0 were captured in fight73. This confirms the tested Cra sequence; Osamodas manual acceptance, all other Cra mechanics, and unrelated classes are not implied.
