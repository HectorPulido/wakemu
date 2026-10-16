-- Scale future objective prizes once; historical versions and entitlements stay frozen.
CREATE OR REPLACE FUNCTION pg_temp.objectives_reward_x10(value jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result jsonb; entry record;
BEGIN
 IF jsonb_typeof(value)='array' THEN
  SELECT COALESCE(jsonb_agg(pg_temp.objectives_reward_x10(item) ORDER BY ord),'[]'::jsonb) INTO result FROM jsonb_array_elements(value) WITH ORDINALITY AS items(item,ord);
  RETURN result;
 ELSIF jsonb_typeof(value)<>'object' THEN RETURN value;
 END IF;
 result:='{}'::jsonb;
 FOR entry IN SELECT * FROM jsonb_each(value) LOOP
  result:=result||jsonb_build_object(entry.key,pg_temp.objectives_reward_x10(entry.value));
 END LOOP;
 IF value->>'kind'='kamas' THEN result:=jsonb_set(result,'{amount}',to_jsonb((value->>'amount')::bigint*10));
 ELSIF value->>'kind'='random_item' THEN result:=jsonb_set(result,'{quantity}',to_jsonb((value->>'quantity')::bigint*10));
 ELSIF value->>'aeV'='5' THEN result:=jsonb_set(result,'{ckl,1}',to_jsonb((value->'ckl'->>1)::bigint*10));
 ELSIF value->>'aeV'='6' THEN result:=jsonb_set(result,'{ckl,0}',to_jsonb((value->'ckl'->>0)::bigint*10));
 END IF;
 RETURN result;
END;
$$;
DO $$
DECLARE applied integer;
BEGIN
 INSERT INTO settings(name,value) VALUES('objectives_economy_multiplier','10') ON CONFLICT(name) DO NOTHING;
 GET DIAGNOSTICS applied=ROW_COUNT;
 IF applied=1 THEN
  CREATE TEMP TABLE objective_economy_previous ON COMMIT DROP AS SELECT key,revision,policy FROM objectives_reward_policies;
  INSERT INTO objectives_reward_policy_audit(policy_key,revision,operator,policy) SELECT key,revision,'migration186: reward multiplier x10',policy FROM objectives_reward_policies;
  UPDATE objectives_reward_policies SET policy=pg_temp.objectives_reward_x10(policy),revision=revision+1,updated_at=CURRENT_TIMESTAMP;
  INSERT INTO objectives_definition_audit(definition_key,revision,operator,definition)
   SELECT key,revision,'migration186: fixed reward multiplier x10',definition FROM objectives_definitions
   WHERE definition->'rewards'<>pg_temp.objectives_reward_x10(definition->'rewards');
  UPDATE objectives_definitions SET definition=jsonb_set(definition,'{rewards}',pg_temp.objectives_reward_x10(definition->'rewards')),revision=revision+1,updated_at=CURRENT_TIMESTAMP
   WHERE definition->'rewards'<>pg_temp.objectives_reward_x10(definition->'rewards');
  -- Upgrade only active unreserved snapshots matching the exact prior policy.
  -- Previously settled snapshots, reservations, item draws and delivered prizes are untouched.
  UPDATE objectives_public_hunts h SET reward_snapshot=jsonb_build_object('key',p.key,'revision',p.revision,'policy',p.policy)
   FROM objectives_reward_policies p JOIN objective_economy_previous old USING(key)
   WHERE h.status IN('pending','alive','in_fight') AND h.reward_snapshot->>'key'=old.key
    AND (h.reward_snapshot->>'revision')::integer=old.revision AND h.reward_snapshot->'policy'=old.policy;
  UPDATE objectives_pvp_events e SET reward_snapshot=jsonb_set(jsonb_set(e.reward_snapshot,'{participation}',jsonb_build_object('key',participation.key,'revision',participation.revision,'policy',participation.policy)),'{winner}',jsonb_build_object('key',winner.key,'revision',winner.revision,'policy',winner.policy))
   FROM objectives_reward_policies participation JOIN objective_economy_previous old_participation USING(key), objectives_reward_policies winner JOIN objective_economy_previous old_winner USING(key)
   WHERE e.status IN('open','in_fight') AND NOT e.rewards_reserved
    AND e.reward_snapshot->'participation'->>'key'=old_participation.key AND e.reward_snapshot->'participation'->'policy'=old_participation.policy
    AND (e.reward_snapshot->'participation'->>'revision')::integer=old_participation.revision
    AND e.reward_snapshot->'winner'->>'key'=old_winner.key AND e.reward_snapshot->'winner'->'policy'=old_winner.policy
    AND (e.reward_snapshot->'winner'->>'revision')::integer=old_winner.revision;
 END IF;
END;
$$;
INSERT INTO settings(name,value) VALUES('objectives_assignment_counts','{"daily":2,"weekly":6,"mission":2}') ON CONFLICT(name) DO UPDATE SET value=settings.value||'{"daily":2,"weekly":6}'::jsonb;
INSERT INTO settings(name,value) VALUES('objectives_travel_cost_kamas','500000') ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value;
SELECT pg_notify('wakemu_objectives_updates','all');
