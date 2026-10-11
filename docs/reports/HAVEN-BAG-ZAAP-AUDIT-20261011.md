# Haven Bag Zaap inventory —2026-10-11

Status: native and current-server inventory complete; a dedicated Haven Bag Zaap source is not accredited. No server/client changes or service operations were performed. Catalog reads used the running World's version-pinned PostgreSQL native catalog.

| Path | Installed native contract | Current server behavior |
| --- | --- | --- |
| Ordinary Zaap | Native destination kind1; account-known plus default-known destinations, native destination criteria and access checks. `csO` sends13686 with two big-endian int64 values: source and destination. | `native_transports.resolve` accepts verified public source objects only, instance0, same map and distance/height bounds. Destination must be known and have exactly one verified arrival altitude. Local `WAKFU_ALL_ZAAPS=1` projects all routable destinations and waives server criteria. No transport currency deduction is implemented in this handler. |
| Haven Bag exit | Map9 `DimensionalBagExitTrigger`13901 at(-4,2,0); leave request12247 is a separate lifecycle. | Restores `HavenBagSession.outside`, clears bag/UI/world state and rejoins the exterior. This is a return point, not a destination selector. |
| Native out-only Zaap | Type70 `ZaapOutOnly`, action76 `ZAAP_OUT_ONLY`, provider `bRq`; native localization explicitly says `haven.world.zaap.name`. This is the Haven World provider and must not be silently identified as a Haven Bag object. | Public-source routing rejects private instances. No dedicated Haven Bag Zaap handler exists. |
| Haven Bag furniture | Published catalog contains1,440 templates:1,292 Decoration,48 PortableCraftTable,48 MerchantDisplayer,26 FxDecoration,25 DimensionalBagBackgroundDisplay and1 DimensionalBagShelf. No Zaap type is present. | Current furniture deployment does not create a Zaap destination/source. |

The current transport catalog has166 entries and165 mapped objects, including45 Zaap destinations. All45 have one verified arrival height. The complete reference/map/XYZ/default-discovery/criterion inventory is in [the destination table](HAVEN-BAG-ZAAP-DESTINATIONS-20261011.md). This is an ordinary Zaap inventory, not a fabricated Haven Bag destination list. Neither transport reference957 nor a Zaap/ZaapOutOnly object on map9 exists in this published catalog.

The native out-only menu remains useful evidence for a future server projection: `bCu.dSG` synthesizes `flG(0,957)` to attach action76. `dfN.c` invokes `bRk.p(source,true)` for out-only mode; that provider unions account-known Zaaps with default-known IDs, excludes the source, filtered maps and failing destination criteria, and constructs temporary `fzQ` links. It reuses13686 on travel. Ordinary mode uses published native links instead. Destination restrictions include native map access and grouped-hero checks. No numeric Kama cost was accredited for an out-only Haven Bag route; the inspected out-only base provider returns no cost label, and this must not be converted into a claim about every production transport's pricing.

A future implementation should first identify or explicitly choose the server-owned source projection and its location. It should then route only a live bag session with matching account/actor/instance, use the same authoritative destination-known policy as ordinary travel, preserve the persisted exterior return point until an atomic successful travel, and perform the established bag leave notifications before the destination world bootstrap. It must not globally weaken `_source`'s private-instance guard. Tests should cover owner and guest bags, arbitrary/foreign source IDs, distance, unknown destination, destination criteria, reconnect, bag exit versus travel, failed transition rollback and guest inventory preservation. Graphical confirmation of the actual native source/menu remains necessary before implementing that route.

Private evidence: `.runtime/haven-zaap-20261011/live-catalog.json`, `zaap-menu-routing.javap.txt`, `outonly-action.javap.txt`, `menu-controller.javap.txt`, `outonly-cost-wire.javap.txt`, `outonly-base-cost.javap.txt` and `destination-criteria.javap.txt`. Native classes were inspected read-only from the installed `client/lib/wakfu-client.jar`; no client file was changed.

## Additional source verification

A fresh PostgreSQL READ ONLY query found no persisted character at map9. This does not establish whether a bag is open: HavenBagSession explicitly keeps interior location in memory while PostgreSQL retains the exterior return point. Live client or server session inspection is required. The active native map9 catalog contains ordinary bag consoles, exit, lock, account chest, ranch entrance, stools, GenericActivableInteractiveElement32433 (parameter1431), and remote Teleporter32439–32443 (parameter4005). None is typed Zaap or ZaapOutOnly. Those remote Teleporters are not accredited Zaap destination selectors and must not be reclassified merely because they teleport. The original out-only localized label resolves exactly to `zaap del merkamundo`, distinguishing that provider from a Merkasaco. The45 ordinary destination labels now resolve through native localization family36 in the linked inventory.

The remaining concrete evidence is the actual interactive object identity/type emitted when clicking the visible Merkasaco object, its native action and source ID in13686, and its dynamic creation/placement authority. A currently open native bag scene or a captured original interaction can supply that evidence; persisted character SQL positions cannot establish the live bag scene. No arbitrary957 source, private-instance bypass or guessed bag travel handler was introduced.

Native follow-up resolves lobby object32433: the original GenericActivableInteractiveElement factory is bBJ, producing bBH. Its getName reads localization family106 using flb.d(); reference1431 resolves to `Orquestrión`. It is the music console, not a destination selector. Bytecode evidence: `.runtime/haven-zaap-20261011/generic-activable.javap.txt`, getName.

## Live graphical correction

The native bag scene DOES display a large blue portal above the northwest stairs. Absence from the Zaap registry does not mean the portal graphic is absent. The screenshot supplied by Hector (`Screenshot 2026-10-11 at 1.40.58 PM.png`) confirms that graphic. Its function must be attributed through the original scene object and native consumer before calling it a Zaap. Live scene inspection resolved all7 rendered interactives: exit13901, merchant1563, crafting1565, management1544, account chest13261, deployed herbalist workbench1099511634125 and plush tofu1099511634126. No other rendered interactive exists in that inspected scene;957 is absent. RanchEntrance36028 at(-9,5,4) exists in raw map data but is not rendered as an interactive. Its projected base is near the visible portal; this is a candidate association, not a proven ownership link. A right-click on the visible portal produced no native context menu.

| Rendered identity | Native class / label | Native function |
| --- | --- | --- |
|13901|bAP / unnamed|Bag exit WALKON5|
|1563|bBb / Consola de historial de ventas|ACTIVATE0; currently unusable|
|1565|bAL / Consola de gestión de la artesanía|ACTIVATE0|
|1544|bAE / Consola de gestión del merkasako.|ACTIVATE0, ACTIVATE2/31|
|13261|bzb / Cofre de cuenta|START_BROWSING12, STOP_BROWSING13|
|1099511634125|bDc / Gran taller de herbolario|MOVE27, REPACK23, ROTATE29, ACTIVATE0|
|1099511634126|bAs / Tofu de peluche|MOVE27, REPACK23, ROTATE29|

The two dynamic identities belong to the account-shared bag owner character1, not the currently selected character10. Querying only the selected character's empty furniture would miss them. Native registry inspection confirmed both rendered identities and names. The actual blue portal graphic is retained in `.runtime/haven-zaap-20261011/live-visible-blue-portal.png`; all80 native map9 static IDs were queried in bounded40-ID batches, retained in `live-bag-registry-all-map9.json` alongside it. No Zaap travel13686 was emitted during the inspected interaction. Enter/leave used the original verified HUD `dimensionalBagButton` (`cVt.ad`, `wakfu.controlCenter:openCloseDimensionalBag`) and restored the prior exterior(-9,-4,-1), preserving the `/d` draft; Hector subsequently re-entered and moved near the portal.

A current server publication difference needs native qualification: `sync_static_world` skips normal static snapshots for map9 and republishes only the account chest for the owner. This can explain missing native interaction state independently of the static portal artwork. It is not evidence that the portal is a Zaap, and does not authorize replacing the native RanchEntrance contract with Zaap travel.
