# Further physical expansion review

## Kaskarlusca: resolved by explicit transit-region policy

The original four geometric regions contain 285, 275, **1**, and 353 cells.
The third region is the stair cell `[-37,-11,4]`, between native gates 17284
and 17283. Exhaustive same-region anchor search confirms it cannot host six
players and an encounter; changing the anchor cannot solve this.

The offline preparation tool now supports contracting singleton intermediate
walking regions into the following encounter region. It preserves every native
cell and gate. In Kaskarlusca, gates 17284 and 17283 both open after the second
victory. The resulting three encounters use explicit local roster policy and
retain the reviewed final boss reference 4240. This does not claim official
encounter quantities or prove boss mechanics.

Three unit tests pass. Existing six-player formation validation and full
exploration-sequence validation pass. Additional checks cover every original
directed boundary before and after its victory frontier. The candidate still
requires isolated PostgreSQL lifecycle acceptance before runtime activation.

## Sliptorium: final exit contract requires backward transport support

The native teleport topology has three regions: entry at `[0,-1,-20]`, second
arrival `[208,106,0]`, and third arrival `[144,-54,0]`. No exterior exit belongs
directly to region three, so the current `bind_exits` requirement fails.

However, native source **16126** returns from region three to region two:
approach `[144,-53,0]`, destination **900** at `[203,93,0]`. Both source center
and arrival are literal native endpoints, and the destination has no criterion,
item cost, or forbidden destination flags. Region two contains exterior source
**14012** at `[210,91,2]`, destination **692** to map **323**, `[0,-131,0]`.
There is also exterior source 14007 in the entrance region.

This is a preparation/validation limitation, not evidence of absent native
exit data. The next implementation must prove the directed walking paths from
the final encounter to source 16126, from destination 900 to source 14012, and
bind exterior usability to completed-run state. It must retain the literal
backward transport; a fabricated direct final-room teleport is unnecessary.

The reviewed guide contains two encounters, with Nonne in its second encounter,
whereas native extraction has three walking regions. A local three-encounter
adaptation must remain explicitly documented; the third region must not be
presented as a verified official combat room.

No runtime writes, client changes, combat changes, or spell changes were made
by this investigation.
