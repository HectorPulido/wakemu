# Native QL byte iterator topology

QL.c creates a default `TByteHashSet` for each touched cell. QL removal keeps
the cell's empty set. Actual iteration scans occupied hash slots descending;
rebuilding from final occupants loses collisions, removals and rehash history.

The independently exported installed byte-set contract captures constructor
capacity, load factor, compaction factor/countdown and PrimeFinder capacities.
`TByteHash` invokes `HashFunctions.hash(int)`, the identity hash, then masks
the signed result with0x7fffffff. This differs from the native long-map hash.
Probing, descending rehash insertion and automatic compaction are verified
against actual byte-set execution rather than assumed from the long producer.

`ExportNativeTroveByteSet.java` exported **12000 deterministic lifecycle
steps** covering all256 signed byte values, insertion, duplicate insertion,
removal, reinsertion, growth, free-space rebuilds and auto-compaction. Python
matched every return value, iterator order and complete persisted
keys/states/size/free/compaction countdown: **zero mismatches**. The initial
oracle stored mutable array references; it was corrected to clone each native
snapshot before the successful differential run.

`NativeQIRegistry` now persists per-cell byte topology and exposes
`ordered_U(x,y)`. Fresh construction consumes the original owned registration
order. Register, movement, removal and indexing toggles update actual history;
empty cells retain topology. Fight checkpoints store the plain dictionary
`native_qi_byte_topology`. QI actor movement, area creation/removal and class
summon registration preserve that checkpoint. Unknown legacy history rejects
ordered queries and is never reconstructed from a final set.

Two integration test methods cover unknown-history rejection and lifecycle
checkpoint preservation; validation is delegated to the test agent.
Casting and displacement consumers can use actual multi-occupant order. This
does not establish unrelated unordered collections or unsupported lifecycle
producers. No services, database or runtime clients were touched.
