The installed client `aMb.csd` array contains native abilities (`aMk.d` spell reference, `aMk.tL` level parameter). `bbo` passes these into `blj.du`; `bPD.a` uses actor level when the parameter is -1. Wonejo reference 5525 therefore owns spell 7962. Reference 2 owns 5769.

The separate `aMb.csr` array contains loot definitions. The `fqH` source labels this as `LootDefinitionBuilder`, with item reference, quantity bounds and drop rate. Earlier catalog versions incorrectly called these `spell_forms`. Numeric overlap with spell IDs did not establish ability ownership; that interpretation has been removed. Reference 2's loot item 2026 is not its combat ability.

The catalog exports client references, not official server populations or spawn positions. Raw remaining loot fields are retained without unsupported semantic labels. Native ability ownership alone does not establish valid target selection, effect branching or complete monster AI.
