-- Preserve visible affinity while replacing native score domain units.
UPDATE characters SET ecology_value=sign(ecology_value)::integer *
 LEAST(9900,round(10000*(1-power(2::numeric,-abs(ecology_value)::numeric/500)))::integer);
ALTER TABLE characters DROP CONSTRAINT characters_ecology_value_check;
ALTER TABLE characters ADD CONSTRAINT characters_ecology_value_check
 CHECK(ecology_value BETWEEN -9900 AND 9900);
ALTER TABLE personal_ecology_receipts DROP CONSTRAINT personal_ecology_receipts_requested_delta_check;
ALTER TABLE personal_ecology_receipts ADD CONSTRAINT personal_ecology_receipts_requested_delta_check
 CHECK(requested_delta BETWEEN -19800 AND 19800);
UPDATE personal_ecology_receipts SET
 requested_delta=
  sign(after_value)::integer * LEAST(9900,round(10000*(1-power(2::numeric,-abs(after_value)::numeric/500)))::integer)
  -sign(before_value)::integer * LEAST(9900,round(10000*(1-power(2::numeric,-abs(before_value)::numeric/500)))::integer),
 before_value=sign(before_value)::integer *
  LEAST(9900,round(10000*(1-power(2::numeric,-abs(before_value)::numeric/500)))::integer),
 after_value=sign(after_value)::integer *
  LEAST(9900,round(10000*(1-power(2::numeric,-abs(after_value)::numeric/500)))::integer),
 evidence=evidence || jsonb_build_object('value_unit','basis_points',
  'source_value_unit','native_score','original_native_delta',requested_delta);
UPDATE settings SET value=jsonb_set(value,'{version}','2') || '{"unit":"basis_points"}'::jsonb
 WHERE name='personal_ecology_policy';
-- Empty local habitats need a non-zero target to make replenishment useful.
-- Native per-family limits remain authoritative; this is only the fallback.
UPDATE settings SET value=jsonb_set(value,'{plant,minimum}','10')
 WHERE name='personal_ecology_policy' AND value #>> '{plant,minimum}'='0';
