# Family 934: actor reset callback chain

## Representative scope

Dragopavo salvaje (3173, level 30) is a useful ordinary-looking representative. The same missing family affects DJ Bilbyboy (2502), Blii (2534), Nox (5718), and the generic admin monster (2381); the admin definition has other missing families. Names do not establish encounter readiness.

## Native behavior and reusable dependency

The installed runner is `eXl extends eZR`, with no parameters and actor targeting. Its calculation phase is empty. Application returns for a null target, invokes inherited `d(Qe, boolean)`, then calls `eGj.dnu()` when the target is an `eGj`.

`dnu()` obtains the target's `fcb` context and returns if absent. Otherwise its exact call order is `aN(actor)`, `B(actor)`, `be(actor)`, `aO(actor)`, `aX(actor)`, `actor.fqz()`, `bd(actor)`, `aQ(actor)`, `bf(actor)`. The `aX` call restores the original controller/team and overlaps the authority being recovered for family 207. It is only one step of this larger reset operation.

Installed bytecode is retained as `next-family-runners/eXl.txt` and `eGj-properties.txt`. Recover each callback and the inherited application phase before implementing the handler. A controller-only reset or a generic kill/despawn alias would omit native behavior. This audit makes no handler, activation, or full-monster qualification claim.
