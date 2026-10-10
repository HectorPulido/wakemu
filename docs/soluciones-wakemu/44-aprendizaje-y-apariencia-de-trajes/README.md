# 44. Costume learning and appearance

**Status: deployed separately in world r63; manual acceptance pending.** Read-only verification matched the running implementation to current source. This agent did not restart services.

Hector reported that guard costume 9727 and ninja costume 12202 could not be
learned. Both use native cosmetic action `bIt`; the shared item-use handler
incorrectly routed them to furniture learning. The actor appearance also sent
zero as its active costume reference.

The implementation routes learning by native action metadata, consumes one
owned item atomically, saves account ownership and prevents duplicate
consumption. Native category 3 selections now publish the selected costume to
the wearer and nearby players and survive reconnects. Existing finisher
selections remain supported. Migration 092 includes the installed client's
1,234 cosmetic learning actions, including 562 costumes.

The focused automated gate passed 27 tests: six unit tests, five isolated
PostgreSQL tests and sixteen existing regressions. The installed-client costume
component decoder also passed. No restart or runtime database change was
performed by this agent. Arbitrary preset creation, copying and deletion and
selection of other cosmetic categories remain outside this implementation.

Native evidence and complete manual acceptance steps:
[COSTUME-LEARNING-20261009.md](../../reports/cosmetics/COSTUME-LEARNING-20261009.md).
