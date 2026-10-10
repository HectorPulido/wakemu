# Duplicate interactive publication: safe boundary review

Client console 10:14–10:21 local repeatedly reports duplicate interactive IDs 26865, 26878, 31674, 27141 and 33010. The movement scene hydration path schedules finite one-second retries for the complete 3x3 neighborhood, including overlap. Each poll sends regional-loader 12318, full 13984 attachments, and retained-instance 12344 updates.

Native behavior documented in `official-tainela-dynamic-state-route-20261008.md`: cEX/13984 reconstructs an object and cdz refuses attachment when its ID already exists; cEY/12344 updates an existing object and ignores missing objects. The latter distinction makes naive creation dedup unsafe: successful TCP delivery does not establish that the client's lazy definition/partition was ready to accept the attachment.

A local first-attachment/per-partition dedup prototype was retracted completely before validation or deployment after reviewing the identical historical safety failure in `COMBAT117-RETURN-INTERACTIVES-20261009.md`. No implementation from this investigation remains. Same-chunk suppression of 12318 also lacks direct native proof that loader retries are unnecessary, so it was not introduced.

A safe general solution needs either native retained-instance presence feedback or a demonstrated loading-ready acknowledgement boundary, with first attachment retry until that boundary, retained updates thereafter, and reset on partition eviction/map transitions/reconnect. Suppressing warning logs alone would hide symptoms without reducing object construction. Duplicate publication remains open and excluded from r71. Existing late-loading door/transport behavior is preserved.
