# Final manual review attestation: furniture and miscellaneous

Final `prices.csv` SHA-256: `d8acd33cfd41501b0e7caf02930f9c5c9d0a6cf1b3ac67a2381b44ece35dfba7`.

Reviewed all 46 final changes against `.runtime/local/item-pricing-20261011/prices-before-review.csv` and the generated `price-review-changes.csv`, within the original 2987-reference scope. Nine are the approved denomination floors; the other 37 propagate ingredient valuations into furniture, stations, one Haven Gem and miscellaneous crafting. All changes increase prices; none introduces a sale below modeled ingredient cost without a publication hold.

All 1450 original hold decisions remain applied. There are 20 scope entries with modeled ingredient cost above sale price; every one is held. All 12 category-cap entries are held, or retain a price at least as high as ingredient cost. No further hold or price change is required.

## Specific final deltas

- Gran taller de pescador (17422): 300,000 → 370,000; approved recipe-cost propagation. The earlier review maximum of 300,000 is superseded by this final value.
- Mesa de la nave Zinit (22135): 220,000 → 270,000; approve propagated ingredient costs.
- Merkambiente almas (27932): 99,000 → 130,000; approve propagated ingredient costs.
- Bloque de cristal azul (28041): 51,000 → 76,000; approve propagated ingredient costs while preserving uncertainty flags.
- Archisfera infernal (32973): 980,000 → 990,000; approve propagation; remains below 1,000,000 group cap and above modeled ingredient costs.
- Currency-denominated items remain held despite conservative name-based floors. No payout behavior is inferred from names.

## Complete changed-reference trace

| Reference | Item | Before | Final | Publication hold |
|---:|---|---:|---:|---|
| 9842 | Gran taller de armero | 220000 | 230000 | no |
| 9844 | Gran taller de panadero | 220000 | 230000 | no |
| 9845 | Gran taller de cocinero | 270000 | 300000 | no |
| 9846 | Gran taller de ebanista | 220000 | 230000 | no |
| 9850 | Gran taller de marroquinero | 220000 | 230000 | no |
| 14951 | 6000 kamas | 2200 | 6000 | yes |
| 15305 | 6000 kamas | 2100 | 6000 | yes |
| 17222 | 9000 kamas (merkamundo) | 2200 | 9000 | yes |
| 17223 | 9800 kamas (merkamundo) | 2200 | 9800 | yes |
| 17234 | Alfombra zolla | 84000 | 85000 | no |
| 17419 | Gran taller de herbolario | 210000 | 220000 | no |
| 17420 | Gran taller de campesino | 210000 | 220000 | no |
| 17422 | Gran taller de pescador | 300000 | 370000 | no |
| 17457 | Cama Wey Wabbit | 93000 | 95000 | no |
| 17466 | Gwan tótem wabbit | 93000 | 94000 | no |
| 18213 | Alfombra de esporas | 84000 | 85000 | no |
| 18310 | 4000 kamas | 2200 | 4000 | yes |
| 18313 | 5000 kamas | 2200 | 5000 | yes |
| 18578 | Cráneo de cristal | 97000 | 110000 | no |
| 18579 | Planta de Anutropía | 97000 | 99000 | no |
| 19205 | Reloj de arena decorativo | 110000 | 120000 | no |
| 20033 | 5000 kamas | 2100 | 5000 | yes |
| 20491 | 10600 kamas (merkamundo) | 2200 | 10600 | yes |
| 20492 | 11400 kamas (merkamundo) | 2200 | 11400 | yes |
| 22135 | Mesa de la nave Zinit | 220000 | 270000 | no |
| 27575 | Merkagema de Bonta | 67000 | 70000 | no |
| 27932 | Merkambiente almas | 99000 | 130000 | no |
| 27935 | Merkambiente llama | 8000 | 8800 | no |
| 27938 | Merkambiente géiser | 7300 | 8200 | no |
| 27948 | Merkambiente llama azul | 200000 | 210000 | no |
| 28038 | Muro de piedra | 66000 | 67000 | no |
| 28039 | Bloque de piedra | 66000 | 68000 | no |
| 28040 | Bloque de cristal verde | 70000 | 85000 | no |
| 28041 | Bloque de cristal azul | 51000 | 76000 | no |
| 28125 | Muro de piedra - ángulo superior | 52000 | 54000 | no |
| 28126 | Muro de piedra - ángulo lateral | 52000 | 54000 | no |
| 28127 | Muro de piedra - ángulo inferior | 52000 | 54000 | no |
| 28128 | Muro de piedra - cruz | 52000 | 54000 | no |
| 28395 | Pared de hielo | 75000 | 81000 | no |
| 28397 | Pared de hielo - ángulo lateral | 98000 | 110000 | no |
| 28398 | Pared de hielo - ángulo superior | 99000 | 110000 | no |
| 30776 | Llave de intervención de Cire Momore | 340000 | 360000 | no |
| 32972 | Archisfera divina | 690000 | 710000 | no |
| 32973 | Archisfera infernal | 980000 | 990000 | no |
| 32986 | Archisfera mística | 470000 | 480000 | no |
| 32987 | Archisfera eterna | 640000 | 660000 | no |

Verdict: approve final estimates with existing publication holds. This attests pricing-data review; it does not attest client playtesting or publication. No prices, database entries or services were edited during this final review.
