-- Native close/discard (12561) has no request token or body. The service
-- stores a synthetic receipt identity for each locked temporary-item snapshot.
ALTER TABLE temporary_inventory_transfer_receipts
    DROP CONSTRAINT temporary_inventory_transfer_receipts_operation_check;
ALTER TABLE temporary_inventory_transfer_receipts
    ADD CONSTRAINT temporary_inventory_transfer_receipts_operation_check
    CHECK (operation IN (1,2,3));
