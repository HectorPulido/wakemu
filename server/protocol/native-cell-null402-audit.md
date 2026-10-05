# Native402: cell-only null effect

Installed eVi.rvE registers402 with eXG and label «Effet Vide sur cellule».
eXG extends eXE, overrides bbz=false, bbA=false, bbB=true; its constructor
calls bbx. eXE.C reads only parameter0 at level0 when present, converts it
to signed byte execution status; parameterless preserves fresh status-1.
eXE.c is empty and bcd=true. eZR.a marks executed after c independently of
status. Application success must not be inferred from status or changed stats.

Qe.a(PK,PL,PN,PV,x,y,z,PS) initializes bfs=null. The bbB&&!bbA branch makes
one application on the supplied cell before any actor-target iteration.
No actor-area selector is used for that cell branch. If Ty or bbX retains it,
Qe adds the effect to caster bfr.bax(), not a cell actor invented by the server.
This differs from actor-target null400; routing402 through actor selection
would multiply applications or drop empty-cell casts.

combat_cell_null.NativeCellNullHandler uses explicit StatExecutionContext
for eligibility/retention/clocks. Ordinary authority selects the cell branch
for402 and keeps target_id=None. Flags outside audited1/17 reject. A retained
row has manager/owner=caster, payload_target_id=None, original cell and payload,
state owner UID/timer when supplied. NativeStatHandler.remove delegates eXG;
central retained view, state replacement and timer removal share that row.

Wire: iN1UID,2baseUID(fresh self),3definition,4value0,5position{x1,y2,z3},
6caster; field7target is absent. iN11 is complete explicit native TimeDatas,
with status2 and executed5. A status-only TimeDatas is invalid native protobuf
because required clock fields are missing. cvY13497 application uses the
ordinary18-byte fight/action/sequence/class/payload-length header. cvZ13560
removal appends actual caster managerID and UID. The codec validates payload
UID, absent target, position presence, zero value and exact caster owner;
incorrect outer owner is rejected.

Offline ProbeNativeCellNull calls native eXE.C/c and serializes eXG with a
cell-only target, then checks Python payload with native eXG decoding. It does
not fake a combat client context: the expected missing-caster-context log in
this isolated decoder does not affect protobuf identity/status validation.
Native target-selection and manager ownership are accredited by complete Qe
bytecode, not that decoder's absent-world context. Run Java22 javap -c -p
on eVi/eXG/eXE/Qe/eZR to reproduce; javac with client/lib/* and .runtime/java
then ProbeNativeCellNull /tmp/native402.bin /tmp/python402.bin.

Five dedicated tests cover identity/retention/removal, wrong owner rejection,
actor-target/clone rejection before allocation, eligibility and private-preview
rollback. Sixteen combined cell/removal/stat tests pass. Subscribed402 clone
registration and automatic fresh402 event production are explicit pending
paths; the handler rejects subscriptions rather than pretending their support.
No spell/breed ID branches exist in execution.


Real common-entry re-audit (sources_stable=True) saved in
`docs/reports/combat-inventory/native-cell-null402-real-casts.json`:6463 at
levels1/200 now executes and changes actor state with original rollback
preserved;6469 at levels5/200 passes402 and stops at the explicit unaudited
anv/cone-2 geometry. No breed/spell-specific execution branch was introduced.
The separate cell resolver test forbids actor-candidate callbacks and verifies
exactly one application/UID even when an actor was supplied as parent target.
