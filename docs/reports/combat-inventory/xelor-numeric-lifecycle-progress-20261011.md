# Xelor numerical and lifecycle qualification — 2026-10-11

## Current evidence boundary

The initial offline10/10 accepted casts at levels20/200 are only context discovery. Their old shared test fixture supplied WP6 rather than the native Xelor WP12, and its compact arena clipped clock hours. This is not a demonstrated Xelor resource or clock engine defect. No class-readiness percentage is inferred.

New `server/tests/test_xelor_runtime_pipeline.py` uses the native breed-resource fixture from `audit_active_spells.fixture`: AP6/MP3/WP12, complete native snapshots/QI, actual exported map1134 topology with bounded radius12 and lawful NPC3646level12. Initialization and actual turn-start occur before gameplay. Common casting uses granted UIDs and native LOS; the source fight must remain unchanged after every successful preview.

Five frozen regression methods cover:

1. Low/high Ready: WP12/maxWP12, AP6/MP3, all three native grants5345/3909/7794, innate states6755/4464 and first table/round1.
2. Actual3909 resource exchange with native per-turn limits: first cast AP+1/WP−1 and6752level1; another cast in the same turn must reject atomically. After actual end/ACK/start, the two-end-tick state retains level1 and the next lawful cast selects AP+2/WP−2 with6752level2. Current PG3909 conditional criteria select cost from6752;99153family844 reads that state with factor1/constant1 and dispatches312932family31 at the resulting level. The initial proposed four casts in one turn was an incorrect test expectation because it omitted `native-spell-limits`; production correctly rejected it. Current PG3909 baseline and every conditional limit publish `[0,1,0,0]` (one cast per turn).
3. Actual775 and2839 exact receipts: respectively AP−1/WP−1 and WP−4 from the native WP12 baseline.
4. Actual5345 lawful full-dial placement: AP−2, unchangedWP12,6759level12, twelve owner7 HOUR areas1546–1557, one registered3791 summon with an explicitly empty native ability book.
5. Dial state serializes as a JSON checkpoint, isolates a private deep copy and survives actual owner-end/ACK/start with refreshed AP, registered roster and current-hour state. This is server-side structural lifecycle evidence, not a client reconnect claim.

The first focused run exposed a fixture prerequisite: the native NPC3646 wins initiative, so common casting correctly rejected requests before owner7's turn. The fixture now advances actual NPC end/ACK/start until owner7. The corrected run passes Ready, exact775/2839 receipts, full12-hour dial and checkpoint/owner-cycle methods. Log: `.runtime/xelor-readonly-20261011/focused-runtime-tests-corrected.log`, active677. The revised3909 usage-plus-next-turn method passed against active677 in `.runtime/xelor-readonly-20261011/remainder-rediagnostics.log`. All five pipeline methods now have passing terminal evidence across those two logs. Source SHA6fc593fd95a9fd4fc3fb86135e3d69c246f8c37712e3c809120bcc301e444aea.

## Parallel work and remaining acceptance

The separate owner is qualifying the21-active/20-passive matrix, including native7189 dial geometry and7190 mechanism replacement. Exact roots False are not sufficient to call a passive disabled: several consumers live in other owned spells or conditional casting tables.

The native existing-dial recast route5345 contains313166family28 guarded by IsOwnSummon3791, followed by307313167 and6761 application. An actual same-cell recast can qualify death/unregistration/rebirth without synthetic HP injection; that targeted regression is planned after the current frozen run. HoraActual6759 has native death listener313313 and intrinsic/contextual resource listeners, so full dial retirement should include area and state cleanup rather than only the summon disappearing.

No production code change is currently justified by these probes. Complete client reconnect, multi-client timeline display, death animations and dungeon progression remain system/manual acceptance. They are not implied by successful source inspection or a JSON snapshot.

## Actual paid-WP current-hour reaction

Ordinary775 after5345 passes exact AP/WP debit and HoraActual6759 wrapping12→1. Current compiled314228 contains413004 and413005, but its inherited eYg group uses limit1/count-success mode: successful413004 stops the group. Thus ordinary paid casts do not require9245 or412999. The frozen server test expecting those references has an incorrect expectation and is not passing evidence.

The actual suspension fallback is now qualified in `.runtime/xelor-readonly-20261011/clock-suspension-current.log` against published677. First actual751 on the owned dial installs348441 and9245level2. Actual775 makes413004 reject its suspension-marker guard and413005 add one paid WP:9245level3,6759 remains12, AP4→3 and WP12→11. After a lawful owner-turn boundary, a second actual751 releases the stored amount:6759 wraps12+3→3 and9245 disappears. The native release producer is413421 (critical alternative413424), whose intrinsic event mask contains2202. The subscribed412992 branch consumes that event and invokes412999 to clear9245. This is a real cast-driven release, not a fabricated event.

The successful probe performs the boundary and recast consecutively. A staged permanent candidate adds phase-tagged observations and an intermediate assertion to prove explicitly that the boundary retains the counter and only the second751 releases it. It also retains an ordinary-payment control. Candidate: `.runtime/xelor-readonly-20261011/permanent-candidates/test_xelor_clock_resource_runtime.py`, SHA4a48030d9234d75468f0d2c872c8047fbfa1814b4a70d8c20f2971e2a6db80ef. It has not been promoted into frozen server/tests. The candidate passed both methods against actual677 in `.runtime/xelor-readonly-20261011/permanent-clock-candidate-current.log`: the explicit intermediate assertion retains9245level3 through the boundary, and the phase-tagged release observation attributes412999/413421 only to the second751.

## Deja Vu odd/even numerical controls

`test_xelor_deja_vu_runtime.py` compares actual754 HP loss across passive7185 present/absent and native current hour12/1. Hour1 is obtained through actual775 WP payment; no state, HP, resource or critical branch is injected. Native312878 requires odd6759, and312879 applies -25 to the triggering final accumulator. The even-hour control must remain unchanged; the odd-hour pair must show the native reduction. This new regression is queued, not yet passed.

## Granted7794 follow-up after the source freeze

The Ready test proves7794 ownership only. Its active numerical semantics remain unqualified. Current native6759 rollover branch349616→349618 applies6779 through349445 and, for an owned dial3791 target,7887 through353231→353232. Both native counters have maximum4 and indefinite duration. Actual7794 reads6779 through844 roots349446/349447, applies scaled6744 through348377/348378, clears6779 through349754/349755 and conditionally clears7887 on an owned3791 through353233/353234. This creates a legal future test sequence: actual5345, actual paid-WP rollover, then granted7794 using its actual native target/cost eligibility. Compare no-charge versus charged outcomes and preserve a foreign-owner control. Do not inject counters to manufacture the branch. State6744 has a one-caster-end duration, so inspect the application before real end expiration rather than expecting persistence after a full turn helper.

## Deja Vu fixture attribution

Actual diagnostic (`deja-vu-eligibility-current.log`) shows5345's native swap moves the owner to(-6,-7), adjacent to the enemy(-5,-7).754 requires native range2–4, so the rejected baseline is a fixture geometry error. Staged `.runtime/deja-vu-legal-probe.py` moves over native edges to(-7,-7), skipping an already-reached goal and respecting actual MP across lawful turns. It uses legallevel60 (7185 unlock50), four controls and a nonlethal HP guard to avoid clipping a level200 hit to the weak enemy's remaining HP. The legal placement probe reached all four cases: baseline/even22, baseline/odd22, passive/even22, passive/odd17. Its original truncating expectation16 was incorrect: native UP.bt/GT.l in `server/wakfu_server/items/equipment_damage.py:158` uses stochastic floor/ceiling rounding. The revised probe requires16–17 plus an exact observer of additional_final=-25 only in the passive/odd case, and0 in all other cases. This stronger source-qualified probe passed against actual677 in `deja-vu-legal-final.log` (SHAfc756619c0bd3fb99b67b387e581baf514ad225cbe91aba0a3f4e72241637236). Full permanent module SHAaf63b68a61d20a8dbac8395431a62d0433ebad4fa0a54c00d80f785e21afb287 passed as a full unittest module in `permanent-dejavu-charge-current.log` alongside the granted-charge module (2/2, actual677). No engine change is justified by either fixture or rounding mistake.

## Granted7794 actual numerical result

The actual probe `granted-7794-current.log` qualifies baseline versus one naturally built charge: baseline6744level6 and charged6744level12, with6779 and owned-mechanism7887 cleared after actual7794. Charge construction uses four actual2839 casts separated by lawful owner turns; the first rollover clears7788, and later rollover builds6779. No HP/resource/state injection is used. The permanent candidate SHA2466c46732f8513895d978abcc2f18391f2c315ba43d593f90d497d176d876bd additionally requires7887 present at the charge level before consumption. That stronger module passed in `permanent-dejavu-charge-current.log` (2/2 together with DejaVu, actual677), including actual7887 before-presence and after-cleanup. Foreign ownership remains separate acceptance.
