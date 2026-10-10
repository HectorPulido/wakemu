# Native gem recovery investigation

## Confirmed cause

`own_bag` serialized the internal `room.enabled` value into `uB.adK`.
That native field is the permanent-primary flag, not floor availability.
`fvw.a(yx)` loads it into `fvw.tky`; `fvw.w(true, false)` immediately
returns `fvx.tkI` when it is true, before requesting any server transfer.
Insertion marks every occupied room enabled, so reopening the bag made
all installed primary gems non-removable in the native client.

Only room 0 now serializes this flag as true. Existing database layouts
need no migration: optional occupied rooms remain enabled internally but
no longer become fixed native primaries after reopening.

The rearrangement validator also confused occupancy with immovability:
it rejected an enabled primary moved into an empty room. It now protects
the fixed entrance explicitly and recomputes occupancy after a move.
Only deployed furniture blocks room removal; a recovered furniture item
retaining its old room metadata does not occupy that room.

## Native geometry and constraints

`fvu.gX(byte)` maps room index to origin `(index / 3 * 6, index % 3 * 6)`.
The server's `(x // 6) * 3 + y // 6` mapping already matches the client.
Recovery is selected in the gem controller and does not require walking
to a disconnected room. The fixed-primary flag explains why such a room
could not be recovered through that controller.

`fvw.w` also rejects a primary with a secondary or with a nonempty native
furniture list (`fvm.gpk()`). These native constraints are preserved.
The final bool still selects primary when true; no selector reversal is
part of this fix.

Native bytecode evidence from `client/lib/wakfu-client.jar`:

- [fvw gem state and removal](evidence/native-fvw-gem-recovery.javap.txt)
- [fvu room coordinate mapping](evidence/native-fvu-room-grid.javap.txt)

## Acceptance

After deploying the complete checkout, leave and reopen the haven bag to
refresh its native configuration. Install a garden/decorative gem in an
optional room, including a disconnected corner. Exit, reopen and recover
the gem through its controller into an empty inventory slot. Its UID must
return once, the optional floor must disappear, and the entrance primary
must remain protected. Repeat after reconnecting. A primary with a
secondary must first require recovering the secondary, and a furnished
room must first require recovering its deployed furniture.

Focused Python regressions are in `test_haven_bag.HavenBagTests` for the
wire flags across all nine occupied rooms and moving an enabled optional
primary while refusing either direction of an entrance-primary swap.
Source changes alone do not establish a deployed or visual pass.
