# Bulk native Lua coordinate and visual joins

## Scope and output

This read-only follow-up joins the previously extracted **1,143 literal actor
coordinate expressions in 196 Lua entries** against the installed conversational
catalog's explicit `visual_id` field. It does not assign a breed by slicing a
graphics number or by matching a character name. The machine-readable complete
ledger is `.runtime/local/npc-lua-bulk-source-20261011/ledger.json`.

- 1,134 expressions have a literal graphics value, either directly in the call
  or through a variable with one distinct literal assignment value in its entry.
- 533 expressions match at least one conversational catalog visual.
- 145 expressions match exactly one catalog breed, covering 52 distinct breeds.
- The complete visual candidate union contains 184 breeds. Shared visuals retain
  every candidate; a unique visual is evidence of compatibility rather than a
  direct original server actor-reference field.
- Four expressions additionally match exact native objective XYZ and a compatible
  breed candidate, on maps 1388, 527, 895 and 1295.

The input inventory includes lexical expressions and comments, as documented in
its original report. These counts must not be represented as executed or
permanent NPC spawns. Variable resolution is lexical and explicitly recorded;
it does not claim evaluation of arbitrary Lua expressions.

## Exact objective-coordinate joins and additional event leads

| Source | Original XYZ | Native visual breed candidates | Map evidence |
| --- | --- | --- | --- |
| `scenario/2543.lua:611` | (0,-19,3) | Airyna5460 | Objective10614, map1388 |
| `scenario/2340.lua:517` | (11,155,0) | Gúltar4688/5319 | Objectives11519/11675, map527 |
| `scenario/2120.lua:802` | (0,-2,0) | Abuelita Ditocas3257 | Objectives11508/9449, map895 |
| `scenario/2454.lua:361` | (-231,-45,-80) | 3405/5156/5204/5211 | Objectives9967/9972/9974/9976/10085, map1295 |

All four matching objective markers were already classified `exact_walkable` in
the geometry ledger. Their original Lua XYZ corroborates the coordinate, but
shared graphics and story visibility still require independent qualification.

The same native event source regions also contain three additional literal
coordinate leads:

- `event_2340_19819`: Kamuuumila4793 at (11,157,0) and Tristepin4687 at
  (7,157,0), alongside the Gúltar objective anchor above.
- `event_2454_21275`: El último viajero5252/5273 at (-223,-34,-80), alongside
  the Pandora objective anchor above.

The ledger retains these seven total rows in `same_event_source_proposals`.
For the three additional leads, map527/map1295 is a **same-event inference**,
not a direct map field. They are actionable targets for an independent captured
actor/map match; they are not unconditional runtime spawn instructions.

## Explicit map-source check

A scan of all Lua entries containing actor creation found literal comparisons
against `Context.getPlayerInstanceId()` in 14 relevant entries. Inspection shows
camera or sea-effect helper checks, rather than branches controlling actor
creation. Accordingly, the ledger records these as source context only and does
not propagate their map IDs into every actor in the file. Scenario filename and
event numbers are not interpreted as map IDs.

No runtime source, SQL, client asset, service or image changed. No new dialogue
root or quest state was assigned. Coordinate/visual evidence is kept independent
from the placement importer's action availability.
