# Scope static interactive hydration to the native loaded neighborhood

## Evidence

The live server and client logs establish two distinct publication problems. Client timestamps below are America/Bogota; server timestamps are UTC.

* At 12:09:36.462, client interactive31687 reports duplicate registration. Server `scene_objects_synchronized` at17:09:36.462846 includes31687. Movement hydration reconstructs already attached objects through13984 and then updates their retained states through12344. This directly explains that warning, but does not prove a minimap or CPU regression.
* At12:09:23.158, native QY cannot find definition34643. The server sent a forced full-map static snapshot at17:09:23.125838 for interaction12870. The actor's immediately preceding accepted position was(-18,-134), native partition(-1,-8), while object34643 is at(17,-50), partition(0,-3), well outside the loaded3×3 neighborhood. Another failure at12:09:12.710 follows the full-map14689 snapshot at17:09:12.146808.
* The17:08:30–17:09:50 interval contains79 movement scene publications,65 accepted walks, two full static publications and one14689 request. The repeated approximately one-second duplicates primarily follow the existing finite scene retry schedule, extended by new movement requests.

## Server correction

`world_static.snapshots(map_id, position=character)` now selects only the existing native18-cell partition neighborhood through `world_scene_sync.dynamic_snapshots`. It preserves every selected object's native dynamic state, current registered dungeon entrance overrides and altitude-independent region ownership. Calling without `position` retains the complete catalog API for offline inspection.

The dispatcher must supply the current character position from `sync_static_world`. Existing delayed scene hydration remains responsible for future partitions. No scheduled retry, private dungeon door override or Haven Bag chest publication is removed. No client modification is required.

This change removes attempts to construct far-away objects whose definitions cannot be registered in the currently loaded neighborhood. It does not claim that all missing definitions are solved: nearby lazy-load timing remains subject to existing retries.

## Why permanent creation dedup remains unsafe

Native13984 reconstructs and attaches an interactive;12344 mutates an existing one and ignores missing objects. Successful TCP delivery does not establish attachment, and14689 is a value-cache refresh rather than a scene-ready acknowledgement. Existing reviews `INTERACTIVE-DUPLICATE-PUBLICATION-20261010.md` and `COMBAT117-RETURN-INTERACTIVES-20261009.md` document why first-send-only suppression can break late-loading doors/transports. This correction deliberately retains those creation retries. Repeated duplicate warnings can therefore remain while movement continues.

## Validation

Five focused `test_world_static_scope` cases cover the actual far-definition example, nearby LootChest preservation, every catalog object's reachable partition, native states and entrance overrides, repeated retries, altitude independence and empty scopes. Companion suites are `test_world_static`, `test_world_scene_sync` and static dispatcher tests. Syntax compilation passes; automated execution is delegated to Luna. No deployment or client acceptance is claimed here.
