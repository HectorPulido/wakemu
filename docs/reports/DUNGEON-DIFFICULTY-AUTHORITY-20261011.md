# Dungeon difficulty authority — implementation candidate

Status: the native scaling supplement passes all 250 profile/level combinations through the real generic runtime. Dispatcher integration, full manual acceptance remain required before closing issues 10/29. No deployment or service restart was performed by this worker.

## Installed native contracts

- Outgoing `cpJ` opcode 12296 serializes object int64, destination int32, competitive Boolean byte, Stasis int32 (17 bytes). `bEk` copies `flF.geE()` and `flF.GN()` into these fields.
- Outgoing `cou` opcode 12223 uses `ayq`: actor int64, Stasis int32, dungeon instance int64 (20 bytes). The private Java oracle executed both serializers for every level 1–10 and both Boolean modes: **40 cases passed**.
- Incoming `cuC` opcode 13339 reads instance int64, payload length int32, then ProtoDungeon bytes. Handler `ciZ` resolves that instance, parses through `eVa.eD`, replaces its `fBf` context and refreshes `bqc.dFs()`. This updates the existing instance without map bootstrap.
- `eUY` validates the installed native minimum through **10**. `eQS.dK` rounds the definition's recommended level upward to 20,35,50,65,80,95,110,125,140,155,170,185,200,215,230. Its above-230 fallback is configured and has not been invented here.
- Offline `aKU` export yields 151 definitions: 141 permit difficulty selection (`cnh`), 32 force competitive mode (`cni`). `bqf.gQ` uses native forced mode OR the selected Boolean. Migration 125 includes the 144 definitions whose native level falls in the verified band domain.
- Each definition's native `cnm` selects its exact localization profile. All 25 profile keys agree across installed FR/EN/ES/PT archives. Profiles declare HP, damage, normal reward and competitive reward percentages. `bqf` passes competitive mode as the fourth formatting argument. The extractor retains archive/member SHA-256 evidence; no client files were changed.

Private reproducible evidence is under `.runtime/dungeon-stasis-20261011/`: `wire.javap.txt`, `entry-serializer.javap.txt`, `difficulty-wire-validation.javap.txt`, `context-update-handler.javap.txt`, `context-update-wire.javap.txt`, `definition-wire-fields.javap.txt`, `native-definition-flags.json`, `native-tooltip-percentages.json`, `VerifyDungeonDifficultyWire.java`.

## Candidate server authority

Migration 125 separates mutable run selection from immutable encounter snapshots. An authenticated current party leader selects before admission; native bounds, minimum, availability and forced mode are enforced. Entry configuration participates in the run creation transaction. Unknown native definitions remain playable under their existing pinned policy without synthesized Stasis rewards.

The encounter snapshot pins selection revision, level, competitive cap, native profile, HP/damage percentages and reward rate. Shared XP and drops consume the same durable rate; ordinary receipt shapes and default multipliers stay unchanged. Competitive criterion entitlement includes actors exactly at the native cap, rather than requiring a numerical level reduction. Owned effective character sheets must apply the same cap before combat snapshots.

The scaling initializer now applies native HP and conditional damage branches to private fresh snapshots before publication. Dispatcher integration must preserve the same transaction and selection revision across actor creation and encounter admission. The selector permits downward Stasis changes between settled encounters; the PostgreSQL lifecycle regression passed. Prior encounter snapshots remain immutable.

## Issue 10 boundaries

The 686 direct rows with opaque complex criteria remain disabled by Hector's instruction. Their native exported Boolean supplies no expression to evaluate. Stasis/competitive authority does not resolve Stele or score contracts: 634 Stele-tagged rows span 35 species; 268 score-tagged rows span species 4378,5306,5608,5806 (thresholds 15,000 through 15,000,000). Their native providers and the meaning of `CAN_BE_LOOTED_IN_STELE` still need accreditation. Do not synthesize a score or interpret an enum label as its evaluation contract.

The prior rollMax audit found no installed lottery consumer; this implementation adds no guessed global cap. See [the criteria audit](DROP-CRITERIA-COVERAGE-20261011.md) and [the reward audit](rifts/DROPS-REWARD-AUDIT-20261011.md).

## Automatic verification and integration handoff

The first isolated gate passed77/78; the failure was a stale fake context fixture lacking the newly queried native definition. After preserving the canonical registry assertions and explicitly mocking the selected native overlay, that module passed4/4. The separate current rift regression gate passed55/55. The second dungeon gate passed81/81 after forced-default selection, request-instance validation and stale-roster admission checks were added. Host `python3` cannot run these suites because it lacks psycopg; compile validation and the offline Java serializer oracle succeeded.

`encounter_scaling(db, instance_id)` locks the durable run and returns its exact profile plus `selection_revision`; unknown definitions and native fixed-difficulty arenas return None. The caller must hold that transaction through actor preparation and admission, calling `bind_encounter(..., expected_selection_revision=profile['selection_revision'])`. A mismatch rolls back admission instead of granting a different tier to an older roster. `select(..., expected_instance_id=...)` validates the client instance inside the owned run transaction. The entry path and initial selection both honor forced competitive mode. `dungeon_context.update_packet(...)` returns the verified13339 message for the current instance.

Additional native reward provenance: `bam.dbL()` explicitly loads state7447 containing difficulty bonuses. Its normal root335583 and competitive root335577 resolve child effects through `fyE.aag`; the children provide level (`fKR`) and bonus (`So(0)`, integer cast plus100) to `eQN.b(mode,level,percentage)`. Actual native probability consumer `brq.Y(double)` reads `eQN.g(mode,level)/100`. This proves a reward-state link; it does not prove HP/damage state application or rounding. The existing local drop algorithm remains the documented reference policy, not a claim of full native Wakfu formula parity.

## Native combat scaling investigation

Read-only extraction located state7260's level1 HP child330869 (class16, parameters70,0,1,0,1,0), level3 child330882 (140%) and level4 child330890 (210%), matching declared type3 HP percentages. Damage is **not** a blanket mastery multiplier: class430 modifies triggering values through conditional groups. Enemy branches exclude triggering action1; allied branches exclude actions24/25. State7261 additionally distinguishes challengers. The existing generic combat runtime supports class430, so application should preserve these native trees.

The required general dungeon-kind→state binding is not yet established. A scan of all123 installed library JARs followed by exact disassembly of every constant/sipush candidate found zero actual bytecode references to states4542,6460,7260,7261,7262. `eQM` exposes kind ID/name only; exported `aKU` definitions contain no state reference. Raw effect tables contain self-reapplication links and a special breed5329→7261 link, which do not establish a general dungeon rule. Equal UI HP curves do not distinguish the states' other mechanics. Do not activate an arbitrarily chosen state or replace conditional damage with a blanket multiplier.

Private artifacts: `native-stasis-state-roots.json`, `native-stasis-state-first-children.json`, `native-stasis-state-grandchildren.json`, `state-binding-class-candidates.json`, `all-state-binding-candidates.javap.txt`, `native-reward-state-7447.json`. No scan process remains active.

## Explicit local combat policy candidate

Hector's requested implementation proceeds with a qualified local policy rather than asserting the missing whole-state binding. `wakemu-dungeon-native-curve-branches-v1` selects original native class16 HP effects and the two exact conditional330→430 damage branches by their frozen declared percentage. It excludes other ambiguous state mechanics. The supplement contains78 original references:22 HP effects,28 conditional roots and28 value-modifier children. Every reference has native level range0–32767 and zero parameter slopes; all250 declared profile/level combinations resolve within these guards.100% uses no effect.

Migration128 stores the additive native supplement in SQL. Its loader preserves existing ordinary effects and rejects reference conflicts. All78 references already have installed native retained metadata; no metadata invention is required. The generic16 constructor extension remains scoped to actual detached SELF authority, preserving the ordinary inactive and cross-actor guards. Initialization returns an atomic private preview and pins the immutable encounter profile, original effect references and receipt hash. No active-phase bypass is used.

The dedicated real-runtime test passed250/250 profile/level combinations through fresh actor snapshots and the existing NPC effect factory. The four catalog and seven scaling tests also passed, with no skips and stable source/migration hashes (`.runtime/local/verification-scaling-128-20261011/tests.log`). Planner/orchestration tests alone do not certify conditional combat behavior or deployment. The previous missing native whole-state binding remains an explicit parity limitation, rather than blocking this named local policy.

The selector now permits native downward Stasis changes between settled encounters while preserving competitive mode/cap and prior frozen profiles. Active encounters, upward changes and mode changes remain blocked. The PostgreSQL lifecycle regression passed in the 30/30 focused gate (`.runtime/local/verification-dungeon-difficulty-r2-20261011/tests.log`).


The final conditional-attack regression passed with stable source fingerprints:
the same native Wonejo attack deals5 at100% and10 at200% after the actual
constructor receipt is installed, through the generic combat runtime. The
companion drop regression verifies that Stasis10/competitive/710% reward rate
cannot authorize missing Stele/score conditions and consumes no RNG for them.
Both methods passed against isolated migrations1–128 (`.runtime/local/verification-targeted-20261011/tests.log`, `fingerprints.json`, `changed: []`).

## Integrated publication and health verification

The real fight-entry boundary passed15/15 tests: revision-fenced binding, scaling after fresh snapshots and before registration, and placement reconstruction. Strict scaling constructor receipts now publish retained effects even for monsters without ordinary initial states. The combined constructor/build/hydration/matrix gate passed15/15; three persistent dispatcher regressions verify fixture publication, unconditional fresh reload after recovery and native selection ACK after reconnect bootstrap. Canonical health entry/exit/recovery and main/hero rollback/death/regeneration passed95/95 on isolated migrations1–129 with unchanged fingerprints. Evidence: `.runtime/local/verification-scaling-dispatch-20261011/`, `.runtime/local/verification-fast-20261011/` and `.runtime/local/verification-dungeon-health-20261011/`. No deployment or graphical acceptance is implied.


The transactional dungeon reward path passed against current migrations1–132:
owned entry/selection, durable encounter binding, actual Fight damage/terminal
transition, authoritative settlement contexts, reward-policy resolution, XP/kama
award, native drop decisions and SQL attempt receipts. Replay recovers the same
decisions without RNG. The targeted method passed1/1 in7.328s; evidence is
`.runtime/local/verification-dungeon-drop-settlement-20261011/target-rerun2.log`.
This is an isolated PostgreSQL/server integration test, not a deployed TLS or
graphical-client acceptance claim.
