# Tofullero: native controller and opening evidence

This investigation reuses the [automatic-flow extraction](AUTOMATIC-FLOW-REVIEW.md) and [native geometry work](GEOMETRY-TOPOLOGY.md). The focused [Tofu native-flow proof](TOFU-NATIVE-FLOW.md) verifies directed paths with each gate state and keeps exploration exports separate from combat. No running service, database state or encounter was changed. The implementation proposal below keeps native movement evidence separate from unknown official monster composition and server-only controller rules.

## New native scenario binding

The installed client does not select a scenario Lua file from the map ID. Its actual native chain is:

```text
server message 13411 -> cAS.dp(body)
  byte reward flag
  int event/action ID (atv)
  int scenario ID (atu)
  signed byte argument count
  count * signed long arguments
-> cio -> ahp.a(scenario_id, event_id, arguments, reward)
-> ahp.sw(scenario_id) -> scenario/<scenario_id>.lua
-> event_<scenario_id>_<event_id> or reward_<scenario_id>_<event_id>
```

`ahp` replaces hyphens with underscores in function names, which explains negative challenge IDs. This is a server-supplied controller dispatch, not a recoverable map-to-script relationship from a coincidentally matching filename. The relevant native classes can be inspected with `javap -classpath client/lib/wakfu-client.jar -c -private cAS cio ahp` and `javap -v ahp` for exact function-name templates.

A reusable exporter, `server/tools/audit_dungeon_controller_capture.py`, decodes 13411 and verifies the target Lua function exists. It writes private arguments only under the explicitly selected private output path. It rejects truncation, negative argument counts and trailing bytes instead of manufacturing controller evidence.

The existing official Jalató capture's completed snapshot contains **nine dispatches**, with all target functions resolving against installed Lua. Their scenario IDs are 2715, 2184, 2174, 2501 and 2413. Scenario 2501 / event 21866 is difficulty-change UI notification, not a Tofu gate controller. This available capture does not establish Tofullero's scenario or unlock event.

## Tofu-specific evidence

- Definition 27, map 1087, native three-room type.
- Doors 26874 and 26875 are visible closed-baseline physical separators; hidden door 26873 is not a blocking separator. Their native parameters are empty.
- None of these door IDs occur literally in installed Lua. No `Tofulailler` or `Tofu Royal` controller name was found in the archive. This does not prove a server-side controller does not exist; it proves these client files do not supply its identity.
- `scenario/-1087.lua` is an unrelated resource challenge and must not be bound to map 1087.
- Native player class hierarchy `biB -> bjo -> big -> eGj` has no overrides of `bcK`, `bcL` or `bvz` before eGj. The normal player therefore inherits the native movement limits used by the geometry investigation. Using exploration profile `(6,0,4)` rather than the combat-export profile resolves the native entry-to-first-region connection. Combat geometry must remain unchanged.
- With entry connected and physical separators applied, room ordering can be rooted in the native entry and traversed through the separator chain, rather than sorting object IDs or component sizes. This establishes a physical progression candidate, not the official encounter composition or server victory callback.

## Encounter evidence still missing

The archived Tofullero guide states three rooms and identifies the boss, but `composition-catalog.json` has no extracted per-room records for it. The native references describe the species pool, not room counts. The current generated local roster includes boss reference 1259 in early rooms, so it cannot be used as official room evidence.

The guide has three visual room-plan references whose archived downloads are absent:

- [Room 1](https://methodwakfu.com/wp-content/uploads/2019/01/Tofulailler_Salle1_SansVT.jpg)
- [Room 2](https://methodwakfu.com/wp-content/uploads/2019/01/Tofulailler_Salle2_SansVT.jpg)
- [Room 3](https://methodwakfu.com/wp-content/uploads/2019/01/Tofulailler_Salle3_SansVT.jpg)

These are research leads and may be older layouts. Their image contents were not available in this investigation; no counts or positions have been inferred from filenames. Version matching and actual roster review remain necessary before representing them as authoritative.

## Proposed source change after evidence review

1. Use a separate native **exploration** movement graph for entry and physical room traversal; preserve combat/spell movement rules.
2. Derive ordered regions from the native entry and the exact physical separator chain. Keep door IDs as object identity, never as order.
3. Replace automatic room teleporting with native Door state publication for the two physical separators. Tie each state change to the existing durable, instance-owned room completion receipt. Preserve idempotency, defeat/withdrawal rejection, party isolation and reconnect restoration.
4. Label this as a deliberate local victory-based progression policy until the official Tofu controller dispatch/unlock evidence is available. A correctly reconstructed corridor does not certify the official event controller.
5. Supply reviewed room rosters separately; do not pad every room from the dungeon species pool. Preserve the accepted Jalató transport route as a regression control.

This is reusable: normal exploration geometry, entry-rooted gate chains, authoritative completion receipts and native state packets are system components. Only independently sourced room composition and special native controllers belong to individual dungeons.

## Prepared source correction: roster policy

`dungeon_local_roster_policy.draft` now accepts explicit trusted `boss_references`. Generated early encounters exclude those references, and an incomplete final encounter receives at most one generated final boss. Reviewed complete room quantities retain priority. Ultimate-boss drafts no longer pad encounters to eight units; a single-species native ultimate-boss definition yields one boss. An unresolved intermediate encounter such as Magmog's Boufrog cannot be replaced by the final boss.

[Tofu DEV roster draft](tofu-local-roster-draft.json) explicitly uses boss reference 1259 and the non-boss native pool 4, 5, 6 and 704. It has three encounters with eight actors each; only the final encounter contains a single Tofu Royal. These are **deliberate DEV quantities**, not recovered official per-room counts. The geometry builder consumes the same general draft function and independently reviewed physical flow.

Magmog's intermediate identity remains ambiguous: the installed French catalog contains Boufrog references 2009 and 4457 at level 115. Neither should be chosen by sorting ID or replaced by Magmog 42. The draft generator rejects that unresolved encounter until an explicit reviewed identity is supplied.

Validation: 12 roster-policy unit tests pass; 25 directed tests pass together with materialization, controller-capture and Lua extraction checks, including ultimate singleton generation, no early generated boss, preservation of known quantities and rejection of an unresolved preboss. Source and draft artifacts only; no policy was installed in the live database and no service was restarted.
