> Interpretation correction: palette drops do not automatically open a text
> editor. Absence of that editor does not establish drag failure. Hector now
> confirms both `?` and downward-arrow placement persists on the big map. Neither
> appears on the minimap immediately; both appear after character selection and
> re-entry. Neither palette icon creates a compass. The historical screenshots
> below remain evidence; the old editor-based failure inference is superseded.

# Live personal-note and compass probe — 2026-10-11

## Result

The client remained on `wayo` at `(-241,-83,0)` throughout the recorded probe. The native `M` key opened the world map, and **Marcadores** opened its three-icon palette. Two normal canvas drag actions from the third palette icon toward distant map cells completed without opening the note editor or producing a verifiable new personal-note record. The screenshots show the map and palette still open. Therefore no note text was entered, no new note or minimap visibility is claimed, and compass creation was not attempted.

The readable actor roster had only `wayo` as a positive player actor; the remaining loaded entities were monsters/NPCs. There was no second owned, visible chat actor available for the native **Mostrar** action. No private chat message was sent, no actor was fabricated, and the existing `/l` chat draft was left untouched.

## Evidence

- `.runtime/local/compass-live-luna-20261011/map-after-drag.png` — full-map frame after the second palette drag; map and Marcadores palette remain visible, no note editor.
- The inspector reported `wayo` at `(-241,-83,0)` before and after the probe.
- The local actor snapshot showed only actor ID `10` (`wayo`) as a player actor; other entries were monsters/NPCs.
- `M` was sent as an ordinary key event with `submit=false`; the click and drag actions used the existing local inspector endpoints.

## Limits

This run does not establish successful note creation, local persistence, minimap rendering, or a live compass target. The recorded run did not independently establish a new marker identity. Editor absence is not a valid failure criterion; use big-map marker presence and coordinates instead. Native bytecode evidence continues to distinguish palette-note creation from **Mostrar** compass creation as documented in `NATIVE-PERSONAL-DESTINATION-20261011.md`.

## Later direct user evidence

Hector confirms both `?` and the downward-arrow marker are accepted on the big
map without requesting text. Neither appears on the minimap immediately. After
leaving through character selection and returning, the icons remain on the big
map and also appear on the minimap; the arrow still does not create a compass.
This verifies persistence and reload rendering for his own probe and supersedes
the historical editor-based uncertainty. It does not retroactively certify the
coordinates or identity of the separate automated probe above.
