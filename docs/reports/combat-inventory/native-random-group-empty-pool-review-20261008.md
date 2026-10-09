# Native random-group empty eligibility pool

The normal-cast baseline exposes class 6, level 200, spell 2079, group 359505 → lottery 359670. This is an invalid native lottery context, not evidence that an empty pool should execute successfully.

Original bytecode `.runtime/local/native341-eXR.txt` establishes that `eXR.C` stores the evaluated parameter-zero draw count unchanged. `eXR.fPC` filters child definitions with `t(eVn)`, totals their probabilities, then calls `GS.ne(total)` once for each requested draw. There is no empty-pool or nonpositive-total success branch. `.runtime/local/native24-GS.txt` establishes that `GS.ne(int)` directly invokes `java.util.Random.nextInt(int)`, which rejects a nonpositive bound. The runtime positive-total guard therefore remains intact.

Group 359670 requests one draw. Its thirteen children 359671/359674/359677/359680/359683/359686/359689/359692/359695/359698/359701/359704/359707 each have probability 100 and require an actual target state 7961 through 7973 respectively. They additionally exclude a specific existing effect and apply actual deck/table-turn conditions. Rejecting every child produces total zero. The baseline records no unsupported predicate exception before this guard; it does not establish that the native state-producing prerequisite chain has been exercised.

The next validation must run source-owned state producers and then the actual spell, preserving deck membership, effect membership and table-turn parity. Injecting states or converting this exception into a no-op would conceal the prerequisite gap. The automatic precondition planner owns that follow-up.

Regression: `test_empty_criteria_pool_is_not_a_successful_native_no_op` verifies rejection for a positive requested draw and zero draws for nonpositive requested counts. Verification: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_random_group` — 6 tests passed. No services, databases, client or AI were accessed.
