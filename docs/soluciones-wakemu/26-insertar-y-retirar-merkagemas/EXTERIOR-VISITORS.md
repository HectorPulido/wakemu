# Exterior Haven Bags and visitors

Source implementation publishes a native template 3700 dynamic interactive (`cwG`, 13664) at the owner's exterior return position while the owner is inside. Loaded players receive it immediately; arriving players receive the registry snapshot. Owner exit or disconnect removes it through `cwH` (13082). Entries are scoped by connection lease, map and instance.

The exterior payload is supported by the shipped client: `bAT`/`bAU` section 3 holds world ID, position and `ua` owner identity; `ama.L` is the packed position codec. `cWt` sends `crv` (13578) with `bpq.Xi()`, the owner's character ID. Foreign successful `cyT` (13307) embeds `tR`, rather than the two flags used for own entry. The Java oracle `server/tools/java/VerifyHavenBagExterior.java` checks the native codecs.

The interior instance uses the account's canonical bag owner. A visitor session overlays the owner's bag layout, restores the visitor's exterior point on exit, and marks `haven_bag_visitor`. Public room access and explicit character access are checked against the current durable owner configuration; locked bags reject foreign accounts. Guild membership access is not implemented. Same-account access remains owner access.

Furniture layout synchronization deliberately omits furniture objects; dynamic 13664 records then render the furniture once, preventing duplicate client room occupancy.

## Manual acceptance after the complete image is deployed

1. Use two accounts A and B on the same exterior map and instance, adjacent to one another. Keep A's bag unlocked with access allowed for everyone.
2. A enters its bag. B must see a bag at A's original exterior position with A's name, and A must see the current room floors and deployed furniture.
3. B walks away and returns, or reconnects while A remains inside. The same bag must appear at the same position, without duplicates.
4. B uses the native bag entry action. B must enter A's interior, see A's room layout and furniture, and see A. B must not be able to modify A's gems, room configuration or furniture.
5. B exits. B returns to its own previous exterior position. A's bag remains visible while A remains inside.
6. A locks the bag. B's next entry attempt must fail and leave B outside.
7. A exits. B sees the exterior bag disappear. Repeat with A disconnecting from the interior: it must disappear again. A reconnects at the persisted exterior point.

Deployed in complete shared r57, healthy after migration085. Visual acceptance remains pending.
