# Mining vein installation — 2026-10-10

Installed 2,881 fixed mineral slots on 46 maps, covering all 51 supported mineral
references. All slots were initialized as available. This is the reviewed local
distribution, not a claim about official spawn locations.

Gameplay catalog remains `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`.
Mining geometry is pinned separately through `WAKFU_MINING_CATALOG_REVISION` to
complete SQL release `14b63a5b28014e455fd9910c99fe037e6d957ac9b40508335bfe130c2ee54518`.
The navigation reader checks release completeness, document SHA256, native
provenance and harvesting approaches. It does not change the active gameplay
catalog. The AI Compose section was restored exactly to its pre-task content and
the previously running AI image was restored after an unnecessary rebuild/stop.

World and ecology are built from the complete shared checkout. Image/source
verification covers 754 Python, migration and entrypoint files. The pre-install
backup of gameplay data is private under `.runtime/local/mining-deployment/`;
immutable native catalog documents and records are retained in PostgreSQL.
Initial mineral appearance events were acknowledged while world was stopped:
login/map snapshots publish the initialized resources without a startup queue.
Normal exhaustion and respawn still use durable publication events.

Validation: 70 focused tests passed with a dedicated PostgreSQL test database;
5 startup heap tests passed. The monolithic server suite was interrupted during
cyclic GC with observed failure markers and no final totals. It is not a passing
full-suite result. All nine navigation tests passed, including the independent revision and checksum
regressions. Logs are alongside installation evidence in the private deployment directory.

## Manual acceptance

1. Reconnect to the game and enter `!teleport 527 -110 0 0` in chat.
2. The adjacent vein is at `(-111, 0, 3)`, resource37/stage1, miner level0.
   Collect it with a free inventory slot. Expect a six-second action, item1846
   and 50 base profession XP. Territory bonuses may affect XP.
3. Expect the vein to disappear, remain absent after reconnecting, and return
   to the same position after 300 seconds plus the scheduler tick. Collect again.
4. With another player watching, repeat: both should see exhaustion/return;
   simultaneous harvesting must not duplicate the reward.
5. Try with a full inventory, then free a slot and retry. Failed delivery should
   leave the vein intact and grant no item or XP. Ordinary plant harvesting and
   combat/spells should retain their existing behavior.

World and ecology report healthy after restart. A deliberately due exhausted
vein outside the manual acceptance location was restored and its appearance
publication acknowledged automatically in 1.009 seconds. All 2,881 slots are
available afterward. The global gameplay catalog remains unchanged. This runtime
worker check complements the 300-second policy and lifecycle tests; graphical
acceptance remains for Hector.
