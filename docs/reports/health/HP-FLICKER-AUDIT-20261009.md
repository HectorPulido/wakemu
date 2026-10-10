# Overhead HP flicker audit

Status: reviewed against deployed r57; manual acceptance pending.

The previous format-11 world entity refresh retained the captured player's public characteristics, including HP 3084. r57 replaces this section with owned public characteristics. This is a concrete stale-data source and a plausible explanation for the reported transient HP bar changes; the report does not establish that every flicker has this cause.

Reviewed paths:

- `wire.owned_public_characteristics`: effective owned HP and maximum feed the existing native actor characteristic codec. Explicit native defaults clear omitted stale rows.
- `equipment_stats.effective_character`: preserves supplied injured HP, clamped to the effective maximum; it does not heal an existing HP field to full.
- `wire.adapt(12436)`: publishes owned character HP rather than the capture.
- `combat_lifecycle.outside_progression`: uses the same owned effective character and native actor codec.
- `health_store.tick` and the session regeneration publisher: use persisted owned HP.
- Format-28 map transitions and native bootstraps contain identity and position, with no captured HP section.

Read-only verification executed inside the deployed r57 world container: the native owned serializer, with an injured effective character of HP 300 / maximum 1050 and mocked equipment/resource evaluators, emitted HP row `(1, 300, 0, 1050, 0)`. This isolates the serializer and confirms that it does not replace current HP with captured 3084, native default 50, or full 1050. It is not an end-to-end client test. No runtime source edits were made during this audit.

Manual acceptance: fully relaunch both clients, place them in the same exterior, injure A in combat, then let B watch A's overhead bar while A equips/removes the mount, feeds it, and enters/exits the Haven Bag. Compare both clients' displayed HP. Actual equipment HP changes and regeneration are expected; momentary unrelated large spikes or resets are not. If it persists, record the exact time and action so the publication sequence can be correlated with diagnostics.
