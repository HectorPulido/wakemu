# Native Haven Bag portal repair

Status: server implementation integrated; original80-case Ranch/Haven Bag/static/chest baseline passed, followed by26 affected Ranch entitlement regressions and5 separate trusted administrator-rights cases. Counts overlap and are not a combined total. Deployment and live client acceptance remain pending.

The visible blue portal belongs to installed map9 RanchEntrance36028, raw type85, template1, graphic binding120, at(-9,5,4). It is not an ordinary Zaap source. The original native choice35 is localized as “Entrar en el merkalugar” (`desc.mru.openRanch.1`); its destination1440 is localized as “Merkalugar” (`content.77.1440`). No client files are modified.

## Implemented authority and lifecycle

`haven_bag_native_scene` publishes the installed baseline for an authorized bag session. The original13984 decoder reconstructs the installed raw object as nativebDq; it does not retype it as a Zaap. The independent Java oracle verifies raw36028, coordinates and six original QT actions; final graphical insertion requires the live renderer.

`haven_ranch_authority` validates the live selected actor lease, owned map9 session, actual installed RanchEntrance, native choice and parameter, adjacent same-height position and native walkable terrain. Both portal12870 and biome12380 additionally check fresh owned item32864 possession or the trusted SQL administrator role under selected lease and durable combat exclusion. Stale cached item/administrator flags do not authorize entry. Return13982 remains allowed after entitlement loss. Native ACCESS_ADMIN_DATA115 is truthfully projected only for trusted administrators, independently of ADMIN_CHAT110. [Exact entitlement authority and qualification](HAVEN-RANCH-ENTITLEMENT-AUDIT-20261011.md). Source(-9,5,4) itself is nonwalkable; its adjacent(-8,5,4) is walkable and reachable from bag spawn(3,3,0) in18 native edges.

`RanchSession` retains two separate return locations: the immediate map9 bag location and the parent's persisted exterior. Movement and ordinary build/inventory refresh use the active private session. Ranch coordinates are never written as the exterior position. Bag furniture and chest authorization retain the original strict map9 ownership checks. Native hero requests are rejected through their existing error-response handlers while inside the ranch; exterior-position hero activation is suppressed there.

Entry sends13256 cleanup,13864(account owner,map identity,empty authoritative model with positive snapshot clock),13974 destination,12318 position. Native13982 false returns to the parent bag with13256 then13974; no empty13864 is sent because the native consumer would recreate a Ranch model. Parent bag layout and furniture are republished. Native12247 unwinds the child before leaving the parent bag. Disconnect/reconnect retains the saved exterior.

The initial owned model has no animals, paddocks, bridges or furniture. Planting, Flora harvesting and nested bag entry are rejected while inside. This does not claim a breeding or livestock system.

## Installed destination qualification

| QT wire action | Biome | Native map and XY | Result for an empty owned model |
|---|---|---|---|
|35|1|1440(28,6)|Original topology asset proves walkable Z4; enabled|
|0|2|1466(-8,-10)|Developer/admin-gated placeholder: no world declaration, map assets or dynamic slots|
|31|3|1467(-8,-10)|Same original placeholder boundary; rejected without changing scene|
|32|4|1468(-8,-10)|Same original placeholder boundary; rejected without changing scene|
|33|5|1469(-8,-10)|Same original placeholder boundary; rejected without changing scene|
|34|6|1470(-8,-10)|Same original placeholder boundary; rejected without changing scene|

Missing archives alone were not treated as proof of an unsupported route. OriginalceK.nc installs a dynamicceM/ceQ provider. A second oracle constructs the installed definition with emptyfBE, then queriesceM.af and its native actors at every entry tile. All six dynamic queries return only the nonwalkable sentinel(bLD=-1,Z=-32768). Map1440 additionally has the original base terrain providing Z4. The five other selector destinations are deliberately withheld original developer/admin placeholders. A follow-up recovered their exact original definitions: each has zero dynamic slots/views, both access and visibility require `GetBooleanSystemConfiguration("trunk") or HasAdminDataAccessRight()`, none has a `worlds.lib` world declaration, and none has any map archive in the installed version manifest. Supplying an initial owned structure cannot recover a floor when no original slot/view or base map is declared. Enabling these would require new terrain/world content or a different original client asset release; neither is invented or installed here.

Private reproducible evidence: `.runtime/local/ranch-hydration-area.log`, `ranch-installed-area.log`, `ranch-dynamic-floor-area.log`, `ProbeRanchDynamicFloor.java`, and `InspectRanchNativeHeights.java`. These generated artifacts and captures are not committed.

## Seven catalog biomes versus six portal choices

The raw original `aML` catalog contains seven biomes. Installed RanchEntrance template1 explicitly references only `[1,2,3,5,6,4]`; its native sorted QT mapping produces the six choices inventoried above. Biome7 points to existing map1034, entry(1,1), sort order1, zero dynamic slots, and the same developer/admin access and visibility criterion. Its map name is “ruinas de la antigua bonta”. It is not referenced by the entrance, has no portal QT action, and is not an additional enabled destination. `aML.cnW` is the native sort order, not a name or map identity.

Biome1/map1440 carries the original visibility/access criterion `GetItemQuantity(32864) >= 1 or HasAdminDataAccessRight()`; its localized native action is “entrar en el merkalugar”. The server now enforces the same item/trusted-administrator entitlement on both entry and biome switching. The native client still owns menu visibility; after deployment a fresh ordinary owner needs the real item, and a trusted administrator receives the original115 permission. An administrator may see prototype choices; the server continues rejecting them safely.

Primary original-data evidence and exact local provider/manifest boundary: [native source inventory](HAVEN-RANCH-NATIVE-SOURCE-INVENTORY-20261011.json), [source discovery report](HAVEN-RANCH-SOURCE-DISCOVERY-20261011.md). This resolves the source investigation for the five alternatives; deployment and graphical acceptance of the qualified normal route remain pending.

## Complete manual acceptance after deployment

Preparation: use an ordinary owned character outside combat, with one free inventory slot. If it does not already hold Bioma Esmeralda32864, use `/l !item 32864 1` through the authorized development console. Expect that real item in the ordinary inventory; keep it throughout the round trip. This satisfies the native possession gate and is not consumed. Alternatively use a freshly logged-in actual administrator after the trusted115 wire correction is deployed. Ordinary owner without the item has no legitimate entry option; a forced request must be rejected without a scene change.

1. Enter the Haven Bag using the native HUD button. Walk up the stairs to the portal, ending adjacent at(-8,5,4).
2. Open the portal's native context menu and select “Entrar en el merkalugar”. Expect map1440 at(28,6,4), native Ranch controls, an empty owned place and no exterior monsters or invented livestock.
3. Walk, open inventory, change an ordinary equipped item/build, close and reopen inventory. Expect the same Ranch scene and the updated owned item/build; no jump to the saved exterior and no healing.
4. Try changing the main hero. Expect the native rejection and a responsive UI with the current actor unchanged.
5. Use the native Ranch return control. Expect the exact prior bag location, portal and deployed furniture. Use the bag HUD exit. Expect the exact saved exterior and current owned build/health.
6. Repeat entry and reconnect while inside. Expect the persisted exterior and normal controls, without a stale Ranch context.
7. If another installed biome choice is visible, select it. Expect a clear rejection with the actor and scene unchanged; this is a documented unavailable empty-model route.

Automated regressions cover nested return, wounds and metadata preservation, closed/replayed session rejection, exact native context fields/order, owner/guest/account/map/instance/lease checks, source/action/body validation, walkable range, qualified destinations and actual dispatcher integration.
