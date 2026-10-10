# Fight 117: duplicate interactives after returning to exploration

## Evidence

Client log `.runtime/local/preferences/logs/wakfu.log.2` records fight 117 ending at 18:58:40.201 America/Bogota (23:58:40.201 UTC), followed by leaving/reloading map 1134 at 18:58:41.114. The user's reported 18:58:48 timestamp matches a second burst of duplicate attachments.

The 18:58:40–55 window contains 105 duplicate partition errors: one at 18:58:42, 52 at 18:58:45, and the same count at 18:58:48. It also contains 307 missing-definition errors and 307 failed-spawn errors at 18:58:42. Private extracted evidence is saved at `.runtime/local/diagnostics/combat117-return-client.log`.

Native bytecode distinguishes two operations:

- `cEX` handles 13984 by calling `bEG.b(identity, payload)` and `cdE.l(instance)`: reconstruct and attach an interactive.
- `cEY` handles 12344 by looking up `cdE.mL(identity)` and applying `bEG.as(payload)` followed by `aWA()`: update the retained instance. Missing instances are ignored.

The production `sync_scene_world` callback previously sent both operations on every finite retry, reconstructing objects that the previous delivery already attached. Repeated attempts therefore generate duplicate attachment errors even when the final state remains usable.

## Proposed correction withheld

An update-only 12344 retry was evaluated and reverted before deployment. Although it avoids duplicate attachments, 12344 ignores missing instances. Initial whole-map hydration already drops unknown definitions, so newly loaded partitions may require a first 13984 attachment before updates can work. Replacing every movement replay with updates risks leaving newly loaded doors or transports unavailable.

A sound correction must distinguish first attachment after partition loading from subsequent state refreshes and account for registry eviction when partitions unload. A prototype retained-registry test cannot prove the missing-instance case safe, and was removed together with the proposed production edit. Existing malformed snapshot decoding tests remain unchanged.

The 307 missing-definition failures and repeated duplicate errors remain unresolved. Initial bootstrap versus lazy partition registration needs additional protocol/lifecycle investigation; do not close the complete exit-synchronization issue on this diagnosis alone.

## Manual acceptance

1. On map 1134, enter and finish a normal fight, then return to exploration.
2. Wait at least ten seconds and walk across a native partition boundary.
3. Confirm nearby doors/transports remain visible and usable after returning and walking.
4. Inspect the client log: repeated identical duplicate-interactive bursts should stop. Record any missing definitions or unusable interactives, including position and timestamp, because initial hydration remains a separate investigation.

No production changes or service restart remain from this investigation. Deployment is owned by the root agent; this issue is excluded from the geometry performance release.
