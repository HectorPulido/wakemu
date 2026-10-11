# Installed Lua actor source ledger

This follow-up inspects the complete installed scripts archive rather than only
`interactiveDialogs/` or environment decorative actors. It recovers an additional
**1,143 literal actor coordinate expressions in 196 script entries**. These are
cinematic/source coordinate candidates, not accredited world NPC placements.

The archive contains 27,263 Lua files and 1,578 lexical `Actor.createActor` call
occurrences. Of the literal coordinate expressions, 1,128 occur in scenario
scripts, seven in generic interactive-element actions, five in event scripts and
three in root scripts. The inventory includes comments and local helper calls;
it deliberately avoids pretending that lexical counts are executed actor counts.

Reproduce with:

```sh
python3 sniffer/audit_native_lua_actor_sources.py .runtime/local/native-lua-actor-source-ledger.json
```

Each record preserves archive entry, entry SHA256, source line, complete call,
arguments, XYZ and nearest preceding function declaration. That declaration is
a source anchor, not an inferred execution scope. The manifest explicitly lists
missing world map, breed identity, visibility and initial dialogue contracts.

## Concrete additional source leads

`scenario/2121.lua` defines `NPC_otomai_gfx = 181404009` and creates this visual
actor at `(-10,-1,65)` and `(43,1,80)` in separate scripted events. The latter is
inside `event_2121_17201`; its immediately preceding comment references objective
6025. It also creates `NPC_melee` at `(54,1,-25)`. These identifiers are client
mobile/graphics identities, not native monster breed identifiers. Objective6025
is absent from the installed exported quest definitions, so that comment does
not establish an available native map join.

`scenario/1485.lua` names a local `amnesiqueId`, creates the cinematic actor at
`(-58,-216,7)`, equips explicit appearance parts, moves it to `(-58,-220,7)` and
uses localized bubble key `quest.crimson.lampionaute.00.07`. This recovers concrete
appearance, position, movement and dialogue bubble evidence for a story scene.
It does not identify a persistent conversational actor or its initial tree root.

`scenario/2543.lua` creates a named local `airyna` visual using graphics1111505460
at `(0,-19,3)`. Again, no direct map/breed/initial-root contract accompanies that
call.

## Native API inventory and qualification

The complete lexical API inventory records `Server.triggerEvent` 1,391 times,
`Context.getPlayerInstanceId`26 times and no literal `Dialog.*`, `Dialogue.*` or
`Map.*` calls. `Context.getPlayerInstanceId` identifies the current player's
instance; it must not be treated as a hardcoded script-world placement mapping.
Native scenario callbacks rely on original scenario event definitions for their
execution conditions, so their filename/event numbers cannot be silently used
as map IDs.

All these additional coordinates remain useful extraction evidence. **Zero new
complete world spawn + native breed + visibility + initial dialogue joins are
qualified by this archive branch.** No client assets, server sources, database,
services or images were modified. The only changes are this report, an offline
inventory tool and a private generated ledger.
