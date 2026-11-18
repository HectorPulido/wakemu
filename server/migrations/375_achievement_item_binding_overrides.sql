-- Native aJP item rewards optionally carry a foS binding override in ckl[2].
-- Retain that per-unit identity instead of silently replacing the item template.
ALTER TABLE inventory_item_bindings ADD COLUMN binding_type smallint
    CHECK (binding_type BETWEEN 0 AND 8);
