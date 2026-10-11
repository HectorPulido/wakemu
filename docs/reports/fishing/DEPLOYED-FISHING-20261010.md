# Fixed fishing spots, 2026-10-10

## Behavior

The reviewed local distribution contains 3,377 fixed fishing spots across 40 maps and 51 supported resource references. The 52nd reference, 306, exposes opaque encounter actions without a fixed primary product and remains excluded. Nineteen species require explicitly recorded local fishing ground fallbacks; these are local placements, not claims about official spawn locations. Ambiguous heights and unreachable surfaces remain excluded.

Fishing uses native profession-75 approach positions within three horizontal tiles, including supported height differences. Harvest uses native duration and fixed primary item, the existing transactional inventory/XP path, and durable occupation/receipt checks. The current local reward policy grants one item and 50 base profession XP, with existing territory modifiers. Candidate lists are not treated as verified random loot tables.

Successful harvest schedules restoration after 300 seconds. Native deletion actions recreate the same public resource identity; native empty-stage actions restore the existing resource. The shared fixed-resource restoration helper guards identity, stage, and cell conflicts. Exhausted cells remain reserved. Fishing does not participate in flora reproduction or flora population affinity.

Navigation is pinned independently to immutable SQL release `20f2731c921701c025af2d8416696e5b01c7346fc9393408b47533c092cab5fa`: 41 documents totaling 514,480 bytes. The global gameplay catalog remains unchanged. AI is not part of the deployment.

## Complete manual acceptance

1. Reconnect after the deployment and use this chat command:

   ```text
   !teleport 527 -9 20 -3
   ```

2. The level-0 fishing resource is at `(-8,20,-4)`, next to the arrival location. Its resource reference is 369, stage 2, action 1670; the durable UID is `3112655964259278748`.
3. Select the available fishing action. The character should fish for six seconds and receive one native item with reference 8105 and 50 base fishing XP. Territory modifiers may increase XP.
4. The harvested spot becomes unavailable. An immediate retry must not grant a second reward.
5. Wait five minutes. The same spot should become harvestable again without reconnecting; fish once more to verify another item/XP reward.
6. Change maps and return with the same teleport command. The current available/exhausted state should match the elapsed timer.
7. Existing mining remains available. A level-0 vein can be checked with `!teleport 527 -110 0 0`, targeting `(-111,0,3)`.

This location covers deletion-style fishing. The automated lifecycle suite additionally covers native empty-stage restoration, concurrent refill, guarded conflicts and reward replay.

## Validation and deployment

The migration and all 3,377 spots are installed. Complete world and ecology images were rebuilt from the current shared checkout; 759 image files match their host sources, including combat and spells. The gameplay catalog remains `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`. The AI container ID, image and start timestamp remain unchanged. World and ecology are healthy. A live external-worker probe restored and published both a deleted resource and an empty stage-1 resource in 0.769 seconds after their deadlines were made due. Both regained the original UID and active stage. Final SQL readback confirms all 3,377 fishing spots and 2,881 mining veins active. Graphical acceptance remains pending.

Automated validation: **144 tests passed**: 81 integration tests, 31 fishing/mining lifecycle tests, five navigation tests and 27 additional mining-navigation/flora/ecology/concurrency regressions. The two fishing harvest tests passed again after stronger XP, reward replay and early-refill assertions. Both publication forms are checked: stage revival uses opcode 12782 and insertion uses opcode 13135. This is a focused validation set; no complete repository suite result is claimed.

Integration regression command:

```sh
PYTHONPATH=server:server/tests:server/tools .runtime/local/verification-venv/bin/python -m unittest test_ecology_plants test_resource_collect test_planting test_planting_runtime test_ecology_population test_mineral_ecology test_catalog_gc_bootstrap
```

Run PostgreSQL tests with `WAKFU_POSTGRES_TEST_URL` pointing to an isolated test database, and runtime catalog reads configured separately. Initial result: 81 tests passed in 86.103 seconds.
