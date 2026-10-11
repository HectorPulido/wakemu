# Wild gobball subscription dependency

The frozen extraction identifies monster2765 (Jalató salvaje, level50) with initial state triple `(2315, 1, 0)`, Absorción de Fluido Vital. This is the only monster containing that initial state and the following effect104345 in the extracted dependency inventory.

The state installs effects104348 (family400), 107183 (family120), 104344 (family330), and109633 (family330). The relevant routes are:

- Immediate group104344 selects relationship mask3 and contains effect104345, family304/eWu. That child subscribes through target mask index1 `[2]`, selector mask0, with parameters `[2315, 0, 1, 0, -1, 0]`.
- Group109633 itself subscribes through target mask index3 `[2148]`, selector mask1, and carrier application/removal flags. Its child109634 is family321/eZi with no subscription masks.

The first route explains an immediate-delivery failure before the shared family304 recovery: the group reaches a subscribed leaf, which must be installed as a fresh deferred listener rather than calculate and apply state2315 immediately. Existing native source evidence for Qe.d and fresh eWu serialization applies to this runner; no new family-specific behavior is required.

Current `combat_subscription_runners.py` includes both304 in deferred runners and330 in group subscription families. `combat_effect_runtime.py` upgrades subscriptions to registration using authoritative retained runtime metadata; `combat_state_handler.py` separately registers subscribed initial-state children. This audit makes no additional runtime change and does not claim the full monster replay passed. The existing strict `Subscribed effect requires native event delivery` check remains intact for unaudited paths.

The new regression `test_monster_wild_gobball_subscription.py` exercises the actual104345 parameters, native masks, level1 and state ownership. It requires registration without invoking condition evaluation, probability calculation or state application before its native event. Full monster qualification remains a separate offline replay requirement.

Static profile decoding is distinct from runner calculation: `EffectDispatcher.execute` computes `effect_profile` before the subscription branch, so `begin_group` receives parameters `[2315, 1, -1]` and probability100. The NEW regression initially expected empty profile values; that assertion was corrected after inspecting this ordering. The retained runtime constructs the fresh zero/unexecuted eWu wire payload separately through `deferred_payload`; decoding operands does not apply state2315 or invoke its probability acceptance callback.
