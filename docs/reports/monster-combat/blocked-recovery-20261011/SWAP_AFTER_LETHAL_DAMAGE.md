# Swap after lethal owned child

Offline representative: Mento (3392), level158, spell4638. The recorded failure has target HP0, baG=true, baK=false, ordinary radius0 and no carry relation. Native roots144112/146887 apply damage before conditional branches144121/146891; those branches contain swap children144115/146892 (family422, flag17, all seven target masks null).

The existing displacement corpse rejection covered only push/pull300/301. Native eXk inherits eZR.i: when bcd() is false and bfs.baG() is true, the runner is rejected before eXk.c. eXk does not override bcd. Its later c additionally checks source eHH baG/baK; those rules were not changed. Native eXK/eXJ fOt resolve bfs, while eXD.c separately checks fOt.baK before movement.

The narrow fix extends the existing proven runner_target_life_eligible precheck to422. This skips a rejected swap child instead of raising a displacement error for its parent spell. Unknown native definition masks/PL authority continue to raise; positive-HP movement and all geometry/carry guards remain unchanged.

Source verification: javap -classpath client/lib/wakfu-client.jar -c -p eZR/eXk/eXD/eXK/eXJ. eZR.i offsets0–27 and eXk.c offsets0–55 establish the distinct runner/caster guards. Existing native-runner-corpse-policy422 identifies eZR as policy owner.

Added tests: server/tests/test_combat_swap_after_lethal_damage.py, actual Fight damage/death registration followed by swap rejection with exact4638 eligibility operands; unknown-mask fail-closed regression. Original tests were not edited. Python compilation passed. Execution and representative replay remain pending because this worker environment rejects TCP to the read-only local PostgreSQL catalog (Operation not permitted). No services or catalog writes.
