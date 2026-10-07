-- Native item rarity identifies these later harvests as RARE versus normal UNUSUAL.
-- Optional transition probability remains local emulator policy, not official.
-- Excludes825 (same UNUSUAL product) and843 (mixed normal-stage rarity).
-- Cardo60/Fresno139 retain032 policy and any active controlled test override.
UPDATE resource_growth_transitions SET probability=0.01
 WHERE from_stage=3 AND to_stage=4 AND resource_reference IN (
 8,18,23,76,79,102,150,151,152,162,174,179,263,296,298,317,334,335,349,350,351,352,353,354,356,357,379,380,381,382,384,385,386,387,388,396,397,400,401,523,532,554,555,556,557,569,570,575,576,577,578,589,590,591,601,602,605,606,607,608,612,613,614,646,647,648,649,761,762,763,764,765,766,781,782,783,784,785,786,833,834,837,838,841,842,844
 );
