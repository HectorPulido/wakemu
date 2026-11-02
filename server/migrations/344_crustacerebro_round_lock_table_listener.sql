-- Explicit Wakemu producer for the original recurring Illusory Shore body.
-- 303952 installs6849; native1004 root316099 removes that lock with316100.
-- Its lifetime is unlimited. The separate one-shot304322 remains unchanged,
-- and the original False conditions on304265/305210 remain authoritative.
INSERT INTO native_npc_constructor_table_listeners
    (monster_reference,state_id,root_id,source_sha256,metadata_sha256,authority,source_uri)
VALUES
    (5182,6504,303952,
     '00f39207bf00bd0419e47eae16fb8478c110fe4f31b8be0b76f0f6ac25b9cd0a',
     '0a3378dbd13292521c4e1466b4c06911350dee574f8705b7d6ad95a03b2a87fe',
     'wakemu-reviewed-native-round-lock6849-reset1004-recurring-constructor',
     'native0793:state/6504/effect/303952;state/6849/effect/316099/316100');
