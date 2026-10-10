# Gem removal inventory refresh (2026-10-09)

Hector confirmed installation persists in r56live. Removing a gem clears the room,
but its inventory icon only reappears after leaving and entering again.

## Native evidence

Fresh `javap -classpath 'client/lib/*' -c -p` inspection confirms:

- `chk` consumes response 12451 through `bpq.a(byte,long,byte,boolean,true)`.
- `bpq.a(BJBZZ)` resolves the destination container with `fkH.at`, but the
  remote branch only calls `bpi.c(room,primary,true)` and `aPY()`.
- Inherited `fvs.c(BZZ)` delegates to `fvw.w(ZZ)`.
- `fvw.w(ZZ)` clears the selected gem field. Neither branch inserts an item
  into inventory. The destination position is only used by the request branch.

Local inspection output: `.runtime/local/gem-removal-{bpq,bpi,fvs,fvw}-20261009.txt`.
These generated files are private investigation artifacts, not deliverables.

## Source correction

After the atomic durable transfer, `haven_bag_transfer.remove` returns:

1. 12451: remove the native room gem reference.
2. 12471: insert the restored inventory item in the requested container/slot.

The inventory message uses the hydrated durable item, preserving UID, quantity,
element masks and shard state. No full inventory reset or map transition is
required. This correction does not modify combat, furniture or gem insertion.

Regression coverage verifies response order and hydrated item encoding for
primary and secondary removal. Deployment and GUI acceptance remain separate.

## Manual acceptance after deployment

1. Give a decorative gem with `!item 4263 2` and open the owner's haven bag.
2. Install a primary gem in an empty room, then a secondary gem of the same type.
3. Keep the inventory open and remove the secondary gem into a free slot.
4. Its icon must appear immediately, without closing the inventory or leaving.
5. Remove the primary gem. Its icon must also appear immediately and the room
   must disappear.
6. Reconnect: both returned gems must remain, with no duplicated quantities.
