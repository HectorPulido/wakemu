# Area PV identity allocation

## Representative witnesses

Frozen bounded screening reports monster5005 (Rocío la Matinal), spell1910 at53, with three `Native area/fighter identity collision` failures. Monster2259 (Embogal), spell1847, has three `Duplicate runtime actor identities` failures. Other target attempts encounter native casting eligibility limits; these are separate failures. The stored witness does not include the conflicting numeric UID, so it does not by itself prove that both actual executions collided with player7.

The validator creates player7 and negative monster IDs, and initializes the running-effect UID sequence at1 (`validate_monster_spell_activation.py`). The shared allocator previously excluded owned effects and active/retired areas but did not exclude fighter identities. A normal area could therefore receive PV identity7 after enough allocations. Registered-area resolution rejects that collision; combined fighter/area target enumeration independently rejects duplicate IDs. A new test reproduces this exact player7 collision path through actual area creation and resolver selection.

## Native namespace evidence and bounded correction

Installed `eYQ.C` obtains its area identity `rGF` through `PN.bae()->PW.baj()`. This is separate from the running effect UID. `Qq.Sn()` and `Qq.QF()` return the instance field `aHm`, the registered area PV identity. Source extracts: `.runtime/local/native-area-eYQ-lifecycle.txt` and `.runtime/local/native-area-Qq-current.txt`.

Ordinary running effects may legitimately share a numeric identity with a fighter: the unchanged actor snapshot test explicitly expects effectUID1 with actorID1. Therefore the generic effect allocator remains unchanged.

`Fight.allocate_area_uid` uses the checkpointed sequence but skips fighter identities (including dead fighters) and active/retired area PV identities. It delegates remaining owned-effect validation to the existing allocator; a genuine owned-effect collision still rejects without consuming the original counter. Exhaustion while skipping also leaves the counter unchanged.

`NativeEffectAreaHandler` accepts a separate optional area UID callback; normal runtime supplies this allocator. Ordinary runner UIDs keep the original provider. Native eYJ private faN preparation also uses the area callback for its area identity, while retaining the original callback for its running effect. Existing standalone callers retain their explicit allocator behavior.

Border/bootstrap generation is unchanged. Battleground faP and environmental glyphs receive explicit constructor identities and already reject fighter collisions; their fixed geometry and creation policy are outside this correction.

## Verification and limits

Five NEW tests cover player7, negative monster identity, dead fighter and active/retired areas, ordinary effect identity overlap, owned-effect rejection, exhaustion, deepcopy rollback, JSON-restored counter and actual creation/resolver uniqueness. Together with three untouched original effect UID tests and six original fakefighter tests,14/14 pass locally. Independent bounded gate pending.

No database, live catalog, service or deployment was changed. The two representative references still require native replay: fixing this demonstrated general allocation gap does not prove their full spell chain is qualified.

Independent Luna gate passed all22 scoped methods (NEW5, originalUID3, fakefighter6, target-aura2, private-aura6). Receipt `.runtime/monster-blocker-recovery-20261011/offline-spell-supplement-area-uid-tests.json`. A final bounded audit adds owned private faN `area_uid` values to the reserved-PV set: these live under running-effect records rather than global Qq maps. The NEW skip test now reserves privatePV10 under distinct runner30, in addition to player7/active8/retired9, and allocates11. Only those five affected NEW tests were rerun locally;5/5 pass. Independent incremental confirmation requested. Other scoped results remain applicable.

The final private-area delta passed independent Luna5/5 with stable `combat_state.py` and NEW test hashes. Receipt `.runtime/monster-blocker-recovery-20261011/offline-area-uid-private-skip-final-tests.json`. All bounded allocation gates are now clean; representative monster replay remains pending.
