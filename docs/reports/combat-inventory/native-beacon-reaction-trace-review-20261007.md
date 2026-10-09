# Beacon reaction trace qualification

The immutable `class-summon-reactions-sixtrace-02.json` audit creates all six sampled summon profiles through production Ready and the summon dispatcher. The three beacon profiles (3798, 3799, 3800) contain their native initial states, but none records a retained `execute_activation` during the three sampled class spell dispatches. This metric alone does not establish a missing listener or successful beacon damage.

The retained state 1304 runner 177977 subscribes to event 1 on channel 1: healing, not the incoming damage events in these probes. Cra state 3419 includes actual owner subscriptions for 1028, 1025, 1024, 202/2276 and 2287/2288. The sampled dispatches publish ordinary damage events 0/2/5/8/2216, or null-effect events 0/185/187. Owner listener 416581 subscribes to event 2 on channel 3, but the local channel-3 manager is the beacon, not its owner; its subscription is not global. Family 649 retained entries are spell grants, not absent event listeners.

The complete spell traces also contain direct beacon branches. Spell 4810 runs the matching profile branch 352371, 352372 or 352373 successfully. The original catalog identifies each as a family-400 null effect, without children, parameters or published-event masks, with native selector `fcE(mask=1)`, execution mode 2 and effect flag 17. Their shapes are cross radius 4, cross radius 1 and circle radius 2. These successful null runners are not proof of reactive HP loss. Corresponding branches in the other sampled spells fail their actual target criteria.

Next validation must distinguish retained subscription activation, direct null/visual execution, and actual reactive damage with its original producer. Select source-qualified spell roots and preserve their geometry, ownership and spell-container facts. Do not manufacture 1024/1025/1028 from generic incoming damage or infer a missing retained listener from the zero activation count.

This review changes no service, runtime event rules or AI code. It records the exact scope of the existing offline evidence and the remaining beacon gameplay gap.

## Follow-up source inventory, October 8

The server already has a shared 1028 producer in `combat_start_events.deliver_fight_start`: it delivers external channels 6/60/61 at the first-turn boundary, after participant initialization. `prepare_server_initialization(fight_start=True)` invokes this producer directly. The sixtrace-02 production Ready closure passes that flag, so its opening event was already delivered; no additional turn cycle is required for 1028. Bare readiness without this initialization flag is different. Its source header explicitly identifies the boundary as server inference; it must not be reported as an original client callsite.

Native state definitions qualify the listener roles:

| Listener | External mask | Original eligibility and children |
| --- | --- | --- |
| 347168 | 1028 | Unconditional group; grants five family-649 spells and applies state 3420 through 394949. |
| 351403 | 1024 | Active spell 7807; children 351404 and 351784. |
| 352326 | 1024 | Caster state 3431, excluding active 7807 with deck spell 6945; children 395230 and 395231. |
| 350554 | 1025 | Children select actual active Cra spells; 352071 selects 4816/4809/4820, and 352075 selects 4811/4817/4810/4821/4818. Their children apply caster states 7758, 7760 and 7793, with original state-dependent criteria. |

These 1025 children are caster state updates, not proof of beacon reactive damage. An omitted cast-boundary event could affect these mechanics, but its precise before/after semantics remain unproved.

An offline constant/callsite scan of `wakfu-client.jar` found no combat method containing literal 1028, and no qualifying combat producer containing literal 1024 or 1025. Native `eFK.pyl` lists all three as external event IDs; `eFl` classifies 1028 with 1003/1001/1005/1002 by BitSet intersection. Neither class emits an event. Other matching constants occur in unrelated join-error, UI, protobuf and graphics namespaces. This does not exclude dynamically supplied event IDs or server-only producers.

`FindNativeBeaconEventSources.java` provides a single native definition load to inventory actual published `eVn.aZO` bits for all three IDs. Compilation passed with a 128 MB javac heap. The serialized 256 MB JVM run completed with exit 0: all 178,337 installed definitions were checked, and **1024, 1025 and 1028 each have zero published aZO producers**. Results are saved in `native-beacon-event-sources-20261008.json`. No lifecycle rule is relaxed or added from the incomplete external callsite evidence.

The casting source audit independently confirms that Python `activeSpellScope` supplies criterion context, not evidence of a native pre/post-spell emitter. The audited native `eVt` construction paths cover client preview, effect child groups and network restoration; they do not establish a normal-server external 1024/1025 producer. These remain explicit producer gaps until a source-qualified lifecycle contract is available.

## Null parameter qualification and legal gameplay audit

The native `eXE.C` contract evaluates parameter zero at **level zero** and stores a signed-byte graphical execution status. Its applied value is zero. Thus the initial-state null rows with parameters `[1, 0.05]` produce status 1; those parameters are not level-scaled damage. The separate damage rows 357566/357565/357567 retain literal `False` criteria and parameters `[1, 0.04]`. Their displayed formula must not be confused with null status or activated by bypassing that criterion.

A bounded streaming extraction of the original mechanic graph identified thirty own-beacon null branches across ten Cra arrows. Their original criteria require `IsOwnSummon` for profiles 3798/3799/3800 and exclude deck spell 6957. Original geometry is respectively `cross-h4b4-g4d4`, `cross-h1b1-g1d1`, and `circle-2`; the previous contact-beacon circle description was incorrect. Arrow 4810 contains branches for all three profiles, so three matching-element examples alone do not establish the complete reaction matrix.

`server/tools/audit_cra_beacon_manual_sequence.py` prepares legal normal casts from production Ready: the granted beacon spell, an arrow aimed at the created beacon, and cleanup spell 6349. It records native initial states, enemy HP before/after, actual events, and source hashes. Its optional nine-case matrix covers each beacon against each sampled element. The legal trace is pending automated execution; no reactive damage implementation or gameplay success is claimed here. A recovered reaction implemented through an explicit Wakemu policy must distinguish original data from the unavailable original server producer.

## Actual legal reaction ancestry recovered

The first legal normal transaction audit (`cra-beacon-manual-01.json`) records EARTH damage references 350703/351918 and FIRE references 351933/351952 against the nearby enemy. This evidence is stronger than the old direct-null trace, but HP loss alone does not distinguish ordinary arrow damage. The next audit adds a legal post-cleanup arrow at the original cell as a negative control and qualifies arrow range before choosing beacon placement. The original AIR fixture selected distance five although arrow 4810 has an unmodifiable maximum range four; that rejection is a fixture error.

A bounded original-graph ancestry extraction identifies actual native beacon-dependent damage routes: state 7802 roots 350694/351908 select target state 7780, and state 7804 roots 351929/351948 select target state 7779. Their class-999 children use ring-one/contact or circle-two/destruction geometry, set a level override from authoritative actor level, and execute damage children with parameters `[0, 1]`. These are distinct from the initial states' literal-False display damage rows. EARTH application 350939 creates state 7802 only when the target has state 7778 from the current owner and deck spell 6957 is absent. The full original nodes and ancestry edges are preserved in `native-cra-beacon-reaction-contract-20261008.json`.

Both normal and critical reaction roots appeared in the first audit. The roots have original variants zero/one; the current source-backed state iterator uses `ALL` for states not in the exported selective-child list (which is currently empty). This observation requires a native state-variant contract check before claiming the damage amount correct. No gate has been relaxed and no additional beacon policy has been installed.

A bounded constant-pool scan of every original `wakfu-client.jar` class found no reference to `fyW.ox(Z)V`. Original `fyW` initializes its `tyH` flag to false, `guW()` reads that flag, and `ox(boolean)` is its setter. Original `eZk.c` only filters child variant `dd(1)` against carrier `rHA` when `guW()` is true. Therefore the installed-client data supports the observed all-variant state iteration, not an inferred selective normal/critical server rule. A changed server rule would need a declared Wakemu policy, rather than a claim that this unavailable caller was recovered.

## Explicit Wakemu paired-state critical policy

Wakemu now recognizes a narrow structural alternative: exactly two nonempty family-330 root groups with native variants zero/one and identical criteria, mode parameters, selectors, masks, timing, geometry and probability. These pairs select the **current causing execution** normal or critical branch. Unpaired or structurally mixed states retain native `ALL`; native `guW=true` retains its original carrier-19 selection. This policy supplies the unavailable server-side selective-state choice and does not claim recovery of `fyW.ox` callers.

The triggering runner's actual definition variant supplies an event's critical fact; immediate casts supply the already authoritative transaction branch. The old beacon creation's carrier critical flag is not the reaction's critical source. Unit regressions exercise normal creation followed by a critical impact and the reverse, missing causing authority, and unpaired/mixed preservation. The production legal harness offers `--critical` for a normal-created beacon followed by an actual critical arrow; its post-cleanup control remains mandatory.

For the recovered contact/destruction state-level-three group contracts, the native child damage bases before mastery/resistance are:

| Authoritative caster level | Normal class-999 override | Critical class-999 override |
| --- | --- | --- |
| 1 | 3 | 3 |
| 20 | 5 | 6 |
| 200 | 27 | 33 |

The override uses native float32 operations and truncation through the existing `level_group_override`; damage children `[0,1]` consume that override. These numbers are not final HP loss. Actual elemental mastery, critical mastery, resistances, facing, flags and resource absorption continue through `NativeDamageHandler`. No extra scalar is applied by the variant policy.

## Nine-pair matrix qualification

The frozen `cra-beacon-manual-02.json` matrix commits all nine legal creation, arrow, Desbalizaje and same-cell control sequences. Eight arrow cases record enemy HP loss (AIR −4, EARTH −3, FIRE −2 for the level-20/profile-5574 fixture), while all nine post-cleanup controls record zero loss. Contact + AIR places the beacon at (−12,−7,−1) to respect AIR maximum range four, with the enemy at (−14,−7,−1). Original contact reaction 351978 has ring-one geometry, so that enemy at distance two is correctly unaffected. This is an outside-footprint negative case, not a failed native damage producer. The revised general arrangement moves the enemy to (−13,−7,−1), allowing a legal adjacent recipient for all nine pairs.

Every same-cell recreation attempt rejects `twV`, including after the next owner turn. Desbalizaje leaves the beacon as an OFF_PLAY corpse with its indexed QK and states; original `eGj.bcP()` is always true. The current source-backed QI producer intentionally preserves OFF_PLAY occupancy until a verified OUT_OF_PLAY transition. Therefore reaction success and zero post-cleanup damage are separate from physical removal: cleanup does not yet certify reuse. General KO_TIME-zero retirement is being addressed through its own lifecycle contract, without clearing a corpse's slot or states solely from HP zero. The harness records reaction, cleanup and cell reuse separately and requires all applicable checks for its overall result.

### Reuse diagnostic and shared free-cell producer (2026-10-08)

The three-case `cra-beacon-reuse-diagnostic-01.json` records the actual
`eZl.new_eHD.pRO_false` beacon origin, completed KO14-zero retirement, an
OUT_OF_PLAY global status and removed QI occupancy. Retained actor identities
still have their state ledgers; this alone does not establish a state-count bug.
The state-range producer uses the actual `baF` membership and excludes those
retired actors when the native default `in_play=True` applies.

The shared cell condition producer incorrectly treated every Actor whose
coordinate equals the target as an occupant. Original `eOV.a` offsets 105–178
instead visits `Qs.bdm` Qq objects, compares their coordinates, and applies
`Qq.bcP` (or any Qq for the strict option); offsets 181–205 then reject a
non-null `QI.V`. Actor identity persistence after QI removal is therefore not
occupancy. The adapter now obtains Qq facts from the registered area provider,
and the ordinary casting obstacle callback queries the current QI registry
rather than the static-only obstacle table. No HP filter or beacon-specific
condition override is involved. The focused adapter regression checks retained
actor identity, blocking/nonblocking Qq, strict mode and QI occupancy. Runtime
reuse certification remains pending the fresh diagnostic rerun.
