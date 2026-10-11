# Builds priority: physical same-UID mount publication

## Current source and publication

The running World container is `wakfu-local-world-1`, image
`wakemu-world:systems-20261011`, image ID
`sha256:74d90f6cef80728886aa00733d2a5a889d749cded44d5bd13523b1cf51bda7c6`.
Read-only hashes of its `/app/wakfu_server/items/mount_feeding.py` and
`mount_feeding_wire.py` match current source exactly. Feeding publication is
already present there. The separately verified world-characteristic zero-reset
correction in `combat_lifecycle.py` differs and remains staged; it was not
retested during this audit.

Actual current feeding sequence is: commit owned inventory state; food12470;
pet12470; same-UID pet12471; rich equipment13078; then owned and nearby15548
actor/PET refresh, world progression and mount snapshot. No server-side item
identity is intentionally changed. The original two-UID Store/PostgreSQL
regression already proved durable feeding and inactive-build deletion protection;
it was not repeated.

## Newly executed original physical consumer

The bounded original-JAR oracle now executes genuine native physical handlers,
superseding the earlier decoder-only physical acceptance limit:

1. Actual server `inventory_move.synchronization` emits13713/BAGS for owned
   container1/reference2175/capacity30, initially empty.
2. Original `cwY` decodes it and `biB.as(cwY.eJQ())` creates the original `bFS`
   container. Native `fkK.d` and `fkK.ay` register the actor and active owner index.
3. Original `chK.b(cxa)` handles12471 A0/B0 insertions with distinct UIDs and slots.
4. Original `chK.b(cwZ)` removesA, then original12471 inserts its updated same UID
   with XP100. Assertions observe A100/B0 in the real physical inventory.
5. Original complete `chZ` handles the rich13078 refresh.
6. Original12470 removesB only; native physical A remains XP100.

Owner final replay exits0. A genuine `bLK` opened before those updates retains
its original XP0 pet object through physical and rich publication. That does
**not** establish a live GUI defect: the server subsequently publishes15548/PET,
and full selected-panel/UI notifications were not executed in this offline
replay. No speculative server correction is introduced.

Private setup explicitly supplies the native current-actor `aTx.hsi` and actor
identity fields without running the unavailable complete graphical bootstrap.
The default offline account context is0, with native owner/active indexes
registered consistently to that context; this is not an account-authentication
acceptance test. Packet actor/container identities remain the actual fixture1.
The definition fixture remains the earlier minimal identity definition with
stack limit1, not a qualification of full native item eligibility/effects.
Actual `fwt` pet model76 properties are unchanged. No native handler,
reconciliation or panel class is replaced.

## Callback trace and remaining acceptance

Native13078 `chZ` calls `bIM`/`fph`, then `dbU.oV(owner)`. The latter only copies
inventory into its temporary registry when the build editor is active; it is
not a general pet-panel reconstruction operation. Original actor PET listener
`bjL.zm` calls `bjo.b(rw)`/`bjo.a(rw)`; the mount branch reattaches the equipped
rich pet observer after constructing its actor representation. That is distinct
from an already opened `bLK` feeding panel.

The remaining complete graphical acceptance is therefore: keep a feeding panel
open for equippedA, feedA, check its level/XP and statistics immediately, switch
between same-referenceA/B and builds, reject deletion of an inactive-build item,
remove that reference and deleteB only, reconnect and verifyA/food state. Use
the single Systems acceptance journey rather than individual repeated probes.
Root separately qualifies dungeon modulation49/49; this worker did not repeat
or edit those modules. No additional proven server defect was found here.

## Evidence and exact bounded command

Private evidence: `.runtime/local/builds-priority-20261011/` and actual server
fixture provenance in `.runtime/local/builds-priority-physical-mount-20261011/`.
The original insertion/removal/registry fixture SHA is
`5bdbbdfdadce222a4cfbd899a3b5782e36b5af5a5e84000eb922419532335dda`;
the actual newly generated13713 BAGS body is31bytes, SHA
`c4d1f02a9f2461620ac651723796d0b85ac373a536a54a7e2983301929b1ebdd`.
Final owner log is `physical-replay.log`; intermediate bootstrap attempts are
not acceptance receipts. Luna independent review is pending at report creation.

```sh
javac -J-Xmx128m -proc:none -cp 'client/lib/*' -d .runtime/local/builds-priority-20261011 .runtime/local/builds-priority-20261011/VerifyPhysicalMountReplay.java
java -Xmx128m -Djava.awt.headless=true -Djava.library.path=client/natives -cp 'client/lib/*:.runtime/local/builds-priority-20261011' VerifyPhysicalMountReplay .runtime/local/builds-priority-physical-mount-20261011/server-fixtures.json .runtime/local/builds-priority-physical-mount-20261011/empty-bags13713.bin
```

No client interaction, client mutation, service restart/build, live attach,
database mutation or runtime source edit occurred in this audit.

Independent verification: Luna reviewed the actual server fixture provenance and
the native handler/reflection boundary, then ran the final original-JAR replay
once with a 128 MiB heap. It completed with exit 0 in 0.938 seconds. The native
physical container held A at 100 XP and B at 0 XP after replacement; removing B
preserved A. Fixture metadata explicitly reported account 0, actor 1, capacity
30 and accepted slots 0/1. The serializer hashes remained unchanged. This does
not establish full PET/UI notification or graphical panel refresh. The private
receipt is `builds-priority-20261011/independent-physical-receipt.json`.
