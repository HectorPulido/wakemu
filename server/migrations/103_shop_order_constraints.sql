-- Durable receipts must retain valid native item identities and quantities.
ALTER TABLE shop_orders
    ADD CONSTRAINT shop_order_item_uid_positive CHECK(item_uid > 0),
    ADD CONSTRAINT shop_order_item_ref_positive CHECK(item_ref > 0),
    ADD CONSTRAINT shop_order_quantity_native CHECK(quantity BETWEEN 1 AND 32767);
