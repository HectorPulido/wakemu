# Shared native owner selection routing

Ordinary fresh effect resolution previously used a hardcoded family list for
cell delivery and actor selection for other non-group families. Native339
eYQ was absent from that list: its actual bbA=false/bbB=true route silently
selected no actors on an empty cell and never reached area creation.

The shared resolution provider now consumes `native_owner_flags` for every
family. That helper uses the closed native owner catalog and the separately
verified dynamic group So(2) policy. The native Qe.a fresh route is:

- bbB=true and bbA=false: supply the cell once without actor selection.
- bbA=true: select actors, including both-flags-true runners.
- both false: no fresh delivery; existing bound-state eligibility remains
  separate and explicit PV replay routing is unchanged.

Cell eligibility uses those same flags. No cell route invents an actor
selector or tests walkability at this shared selection stage. Actual effect
criteria, native geometry and runner-specific guards remain independent.
Unknown owner proof rejects instead of assuming an actor route.

Four focused tests exercise the actual `NativeEffectResolver` pipeline for339
and seven other cell-only families, six both-flags families plus ordinary
damage, the neither-flag dynamic group case, and an unresolved native owner.
Actor candidate callbacks deliberately fail if a cell route calls them.
Actual339 factory creation integration is delegated to the collision test
agent with its verified Qq fixture; unit execution is delegated to validation.
This change is general owner routing, not per-spell compatibility logic.
No service or runtime process was restarted.
