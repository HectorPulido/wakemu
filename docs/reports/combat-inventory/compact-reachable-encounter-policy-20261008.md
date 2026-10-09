# Compact reachable encounter policy

The old production default was radius89 around the player. That is the native
wire rectangle limit, not evidence of an original encounter formation rule.
Monsters' world positions were mandatory seeds, allowing a dispersed group to
stretch the scenario and leaving disconnected platforms unusable. Installed
resources reviewed here provide native selected surfaces and directed movement
edges; no original server compact formation algorithm was recovered.

`compact_encounter` now implements the requested budget of at most4900 rectangle positions, including blocked holes,
independent of aspect ratio (including10×490),
player position anchored, all monsters assigned unique valid positions in the
same mutually reachable native component. Forward and reverse traversal excludes
one-way drop destinations. Ambiguous reachable heights are removed and both
traversals repeated, so removing a bridge cannot silently strand a participant.
Original positions inside the component remain preferred. Other monsters are
formed near six native path steps, with their original position as a deterministic
tie breaker. Insufficient capacity fails without inventing terrain.

`local_arena` applies this budget to NPC encounters and does not use the old
radius environment setting for them. Friendly duels retain the configured
radius and preserve both players' positions. Durable
placement persists ordered source-to-combat coordinates and generates zones
from the combat coordinates. Bootstrap validates the original owned monster
reference first, then installs relocated Actor positions and matching wire
coordinates. This does not mutate the owned world monster reference or HP.
Native surface indices and source provenance are still rebuilt by the verified
surface selector; no all-zero terrain attestation is introduced.

Ten pure topology tests passed, including disconnected stacked platforms,
all dispersed monsters, one-way drops, unique destinations and capacity failure.
Further bootstrap/placement integration verification is delegated separately.
No services were restarted.

## Budget and wire bounds

Native fct serializes width and height as int32, and the complete rectangle mask
count as a signed short. The encounter policy caps both selected cells and rectangle positions at4900,
including blocked holes. The separate native format limit is32767 positions;
neither dimension has a70-cell maximum. The
selector expands in deterministic native BFS order and checks rectangle capacity
before adding a cell. It recomputes forward/reverse reachability after budget
truncation. A directed loop whose return route falls beyond the selected budget
is excluded rather than represented as falsely reachable. No invented edge or
surface fills the omitted area.

The10×490 and70×70 full grids retain all4900 native cells. An80×80 grid is
truncated to a connected native subset whose bounding rectangle is at most4900 positions, and its displaced monster is relocated
onto that selected component. The perimeter/provider interface remains
`native_border_cells` / `wakemu.compact-cardinal-perimeter-v1`.

A sparse150×150 L-shaped corridor is clipped before its rectangle exceeds4900,
even though its playable cells alone would fit. Its distant monster is relocated
within the bounded connected subset.
