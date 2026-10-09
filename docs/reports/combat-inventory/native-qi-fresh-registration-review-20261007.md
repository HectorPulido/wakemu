# Native fresh actor QI registration

The concrete client fight producer is `buH.x(eGj)`, overriding the generic `fcb.x(eGj)`. Its bytecode checks `bcN != -1` and that the actor anchor is inside QI, then invokes `QI.i(QK)` at offset 31. This uses the actor's supplied obstacle byte. The generic base implementation invokes `QI.f(QK)` at offset 5, allocating the first free byte; it does not establish the concrete client's fresh registration contract. `big.doV` also registers an existing supplied byte through `QI.i` when its slot is empty.

Evidence: `.runtime/combat-review-20261007/fcb-current.javap`, method `x(eGj)`; `/tmp/wakemu-buH-qi-register.txt`, method `x(eGj)`, lines 417–434; `/tmp/wakemu-big-qi-register.txt`, method `doV`. These are offline disassemblies, not observations of a running client. Fresh registration requires the actual serialized arena, supplied actor bytes, and attested physical radii. An out-of-bounds actor is skipped by `buH.x`; generic `QI.i` behavior alone must not be used to claim client registration there.

Movement on `eGj.a(int,int,short)` updates the registered QI position before the actor position assignment, subject to actual carry and registration guards. Carry transitions explicitly toggle indexing. HP zero alone does not prove removal or indexing changes. Join and summon insertion need explicit producer events; reconstructing registration from the current roster loses this contract and QL touched-cell history.

## Atomic fresh producer regression

`test_combat_qi_snapshot_atomicity.py` injects two prepared `ActorSnapshot` records, with the second radius outside the signed-byte domain. It verifies rejection before **any** `ActorSnapshot.install` call, unchanged actor fields and obstacle bytes, unchanged fresh-order boundary, absent installed QI slots, and an unallocated effect UID seed. This exercises the public initialization boundary without loading native catalogs.

Validation: `PYTHONPATH=server /tmp/wakemu-combat-review-venv/bin/python -m unittest discover -s server/tests -p test_combat_qi_snapshot_atomicity.py` — 1 passed. The producer now preflights all prepared radii through `prepare_fresh_actor_slots` before installing actor snapshots, then commits the prepared registry.
