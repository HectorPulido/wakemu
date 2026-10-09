# Native actor physics sources

Native `eGj.bvz()` returns the literal short4. `big`, `bjo` and `bje`
inherit this method; jump is not inferred from creature level or an `eGH`
profile. `eGj.efR()` returns its mutable `pGF` coordinate; `baM()` returns a
copy of that same coordinate. The base coordinate setter `eGj.a(int,int,short)`
mutates `pGF` and publishes the associated QI relocation.

`ProbeNativeActorPhysics.java` verified inherited method declarations,
physical versus copied coordinates, and mutation using the actual native
base setter. It invokes the base method explicitly to avoid the `big` UI
animation override in this offline probe. A first direct `bjo.a(...)` attempt
entered OpenGL initialization and failed with `UnsatisfiedLinkError`; no
running client or service was involved. The corrected probe exited0 with PASS.

Fresh `ActorSnapshot` now captures `native_physical_position` and
`native_jump_height`; installation rejects missing or changed physics before
mutating the actor. Player, NPC and class summon snapshots using the shared
`_finish` producer receive these exact fields. The authoritative
`move_registered_actor` producer updates the physical coordinate with actual
movement. Moving an actor whose physics authority is absent leaves it absent.
Casting consumers must reject absent facts when native Sn needs them.

Three focused unit tests cover installation, actual relocation, unknown
authority preservation and malformed snapshots. Validation is delegated to
the test agent. This does not establish carry, rendered animation coordinates,
monster AI or future external physics producers.
