# Samaracito teleport lifecycle audit

The frozen failure for monster5007 (Samaracito exiliado), spell5947 at level68, reports the generic ordinary displacement guard. The receipt predates the detailed actor diagnostic, so its exact failing HP/radius/carry operand cannot be reconstructed from that error alone. This audit does not claim monster qualification.

The actual spell graph starts with damage188912 (family5, amount66) and188493 (family5, amount53), followed by state applications and groups282930/282931. Those groups reach282928/282932, containing target teleports282929/282933 (family340). Both teleport definitions have no parameters, no trigger masks and native flag17. There is no swap422 in this spell closure. The monster's native profile has radius `cqR=0`; the original failing recipient is not identified by the old receipt.

## General ordering correction

Installed native declarations show eZB extends eZR and eZC/eZD extend eZB, with no override of `i` or `bcd`. `eZR.i` first checks its actual recipient `bfs.baG` and native `bcd` policy. The inspected `Qe.k` path calls `i` at offset71 and returns on rejection, before clone `n` at offset424; `eZR.n` calls `C`. Bytecode is retained in `Qe-teleport-life.javap` and `eZR-private-area-audit.javap` under the private recovery directory.

The Python dispatcher already provides an eligibility hook before `prepare_effect`, and retained handler wrappers preserve that hook. Previously teleport preparation could reach `_calculate_teleport` and `_ordinary` before this corpse decision. The new `NativeDisplacementHandler.native_eligibility` uses the existing authoritative `runner_target_life_eligible` only for teleport families302/340. It evaluates the runner recipient, which may differ from the moved actor for302. It preserves native flags, PL and target-mask policy evaluation and fails closed when those operands are unknown. No radius/carry guard was relaxed.

New tests use a real Fight and owned lethal damage before the exact5947 teleport operands. They verify corpse rejection before preparation, living recipients reaching the existing preparation path, and unknown corpse policy failing before preparation. The old swap branch remains unchanged. A fresh monster replay is still required to determine whether this correct ordering resolves the frozen5007 failure.
