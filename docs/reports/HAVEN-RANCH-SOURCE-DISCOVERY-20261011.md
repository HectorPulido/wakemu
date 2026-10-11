# Haven Ranch original terrain sources — 2026-10-11

Status: bounded read-only source investigation complete. No runtime, client, database, GUI, build or service change. Qualified ordinary portal implementation remains staged; this is not a deployment or graphical acceptance receipt.

## Result

The five withheld portal alternatives are **original developer/admin-gated placeholders in this installed client release**, rather than five missing server-generated landscapes. Every one has all of the following independently checked boundaries:

- Both native visibility and access require `GetBooleanSystemConfiguration("trunk") or HasAdminDataAccessRight()`.
- The original `aML.cuf()` dynamic slot/view collection is empty.
- The original `worlds.lib` loader resolves no world declaration for its map identity.
- The installed distribution manifest contains no topology, graphics, environment, lighting or paper archive for that identity.

There is consequently no original base terrain or declared dynamic slot/view producer to reconstruct. Sending an invented owned slot or height would not recover original content. No client modification, fabricated terrain, guessed destination or permissive criterion is introduced.

## Complete destination inventory

| Raw biome | Original world | Entry XY | Native sort order | Original visibility and access | Dynamic slots | Entrance template1 |
| --- | --- | --- | --- | --- | --- | --- |
|1|1440|(28,6)|6|`GetItemQuantity(32864) >= 1 or HasAdminDataAccessRight()`|4; visual templates1547/1548|QT35; qualified ordinary route|
|2|1466|(-8,-10)|1|`GetBooleanSystemConfiguration("trunk") or HasAdminDataAccessRight()`|0|QT0; withheld placeholder|
|3|1467|(-8,-10)|2|Same developer/admin criterion|0|QT31; withheld placeholder|
|4|1468|(-8,-10)|3|Same developer/admin criterion|0|QT32; withheld placeholder|
|5|1469|(-8,-10)|4|Same developer/admin criterion|0|QT33; withheld placeholder|
|6|1470|(-8,-10)|5|Same developer/admin criterion|0|QT34; withheld placeholder|
|7|1034|(1,1)|1|Same developer/admin criterion|0|Not referenced; no portal QT action|

**Seven definitions are not seven entrance destinations.** Original `aNb` template1 references exactly `[1,2,3,5,6,4]`. `flH` sorts these definitions and assigns the six QT actions. Biome7 exists in the raw catalog but is not included in the entrance; the server must not add it to the menu or accept it as a declared route. Its destination1034 is an existing world whose Spanish map label is “ruinas de la antigua bonta”. The ordinary biome1 action uses `desc.mru.openRanch.1=entrar en el merkalugar`, and map1440 is “merkalugar”. Other five world labels are absent from the installed Spanish text source.

`aML.cnW`/`fBm.dcu` is the native sorting field. The MRU label producer `cXl.eVa` first uses `desc.mru.openRanch.<biomeID>`, then the world localization key; it does not treat this sorting field as a label or map identity.

The ordinary route has its original item/admin menu visibility gate. The original client menu predicates remain intact. The prepared server now checks fresh owned item/trusted-administrator entitlement on entry and switching and truthfully projects ACCESS_ADMIN_DATA115 for actual administrators; it does not grant ordinary accounts that privilege. An administrator can legitimately see placeholder choices even without usable terrain; those requests continue to be rejected without changing the scene. [Entitlement implementation and qualification](HAVEN-RANCH-ENTITLEMENT-AUDIT-20261011.md).

## Primary source chain

The bounded Java export uses the original installed `apw` bdata loader and original `aML`, `aMM`, `aMN`, `aNb` and `aNc` getters. It recovers all7 definitions, every declared slot/view and the complete entrance list. The exact data is preserved in [HAVEN-RANCH-NATIVE-SOURCE-INVENTORY-20261011.json](HAVEN-RANCH-NATIVE-SOURCE-INVENTORY-20261011.json), including source SHA256 fingerprints.

`bbE.a(aML)` copies the native access/visibility criteria and dynamic slots into `fBm`. `ceK.nc` chooses the biome and installs `ceM`/`ceQ`. `ceM.a(fBm,fBE)` iterates **only** declared `fBm.gxg()` slots. For each slot, a view is instantiated only if the selected `fBq` state exists in the slot's original `fBk.gwX()` map; `ceU` then reads the original `fBl.gxb()` visual template. An empty slot catalog therefore provides no original dynamic terrain, even if an arbitrary owned-state record were sent. Biome1's four slots reference installed Haven building images1547/1548; no corresponding declarations exist for biomes2–6.

A separate original `cdH` loader reads `client/contents/maps/data.jar!/worlds.lib` and resolves the requested identities:

| World | Original declaration |
| --- | --- |
|1034|Present; native ID1034, one region and one submap|
|1440|Present; native ID1440|
|1466–1470|All absent|

## Installed version and provider boundary

`client/config.properties` explicitly binds topology, graphics, environment and lighting to local `contents/maps/<category>/%d.jar`; world declarations are local `contents/maps/data.jar!/worlds.lib`, and Haven building/patch sources are local `contents/hm/hm.jar`. `Zz.fz(world)` substitutes the world identity into the configured topology path. No remote fallback is present in this qualified source path. This statement concerns these original runtime providers; it does not claim that an external updater could never install a different client release.

The installed `manifest.json` contains4,870 file entries. It declares all five map archive categories for1440 and none for1466–1470. The installed `maps/data.jar` SHA1 matches the distribution manifest entry, distinguishing the missing declarations from accidental truncation of that archive. The central graphics atlas contains unrelated numeric sprite identities resembling1466–1470; these are images, not map definitions or terrain providers, and do not establish a recoverable map.

The six earlier empty-provider floor checks remain useful but were not repeated. This follow-up adds stronger independent definition, world-declaration and distribution evidence. It resolves the missing-provider investigation without enabling prototype content. A different accredited original asset release or deliberately new terrain content would be needed for those five alternatives.

## Reproduction and bounded resource use

Private sources and receipts are under `.runtime/local/ranch-biome-source-20261011/`:

- `ExportRanchSources.java`: original7-biome/entrance/slot/view export.
- `InspectRanchWorlds.java`: original declaration lookup.
- `sources.json` and `worlds.log`: decoded values and lookup results.

Both original Java programs ran sequentially with `java -Xmx128m`; no full terrain export or bulk geometry load was performed. Independent lightweight assertions passed for the exact seven-definition/six-choice distinction and all five prototype criteria, zero slot catalogs and zero manifest map assets. Source evidence does not replace the80 existing portal/session tests or the pending coordinated deployment and complete graphical journey in [HAVEN-RANCH-PORTAL-20261011.md](HAVEN-RANCH-PORTAL-20261011.md).
