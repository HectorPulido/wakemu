-- Actor IDs enter LuaState.pushNumber(double) during death presentation.
-- Keep durable group/receipt IDs unchanged; reserve a separate exact actor range.
CREATE SEQUENCE IF NOT EXISTS lua_exact_npc_actor_ids AS bigint
 MINVALUE 1125899906842624 MAXVALUE 2251799813685119
 START WITH 1125899906842624 INCREMENT BY 128 NO CYCLE;
