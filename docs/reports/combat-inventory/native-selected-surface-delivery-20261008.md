# Selected native surface delivery

Fresh encounter placement rebuilt the arena through `combat_placement_policy._arena`, dropping both selected Vy indices and catalog provenance. The general producer now reconstructs each selected altitude from the published native ordered surface catalog, requires a unique matching index, writes that index into the wire mask, and forwards provenance to bootstrap. First placement and retry share this implementation; no existing live masks are repaired.

Two isolated regressions passed locally and again in image r14. Parent verification additionally used real map527 terrain: player `(-213,-41,0)`, enemy `(-214,-45,0)`. Placement preserved all masks and provenance; actual `QI.i(-210,-41,0)` resolved `NativeSurface(z=0, bld=0)`. The parent deployed image `791dd1d03974dd0b7fd358691addeb4499e78981d5af171be3ce150d474c1fde` (r14). Client gameplay verification remains separate from this selected-surface delivery proof.

The database placement-policy test intentionally uses synthetic map1134 coordinates. Its fixture now explicitly supplies a native-shaped flat surface catalog and provenance through mocks, with index zero determined by its single surface per cell. Production validation remains strict. The fixture was syntax-checked only; no database tests, service operations, or restarts were performed by this agent.
