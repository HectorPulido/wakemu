# Monster combat extraction

Offline installed-client evidence. No runtime catalogs were published.

## Complete inventory

- monsters: 2874
- owned_spell_ids: 3091
- zero_level_ability_records: 7
- ability_records_above_sampled_effect_levels: 1121
- monsters_with_abilities: 1934
- monsters_with_initial_states: 1679
- monsters_with_dependency_gaps: 13
- monsters_missing_casting: 0
- monsters_missing_root_metadata: 0

## Initial low-level review cohort

| Monster | Ref | Levels | Owned spells | Initial states | Dependency gaps |
|---|---:|---|---|---|---|
| Jalató | 1 | 8–12 | 5767 (Mordedura de Jalató) | [] | [] |
| Jalatín negro | 2 | 4–8 | 5769 (Baba Negra) | [] | [] |
| Jefe de guerra jalató | 3 | 14–18 | 5773 (Cuchillada), 5777 (Carga Cornuda), 5776 (Llamada de la Manada) | [] | [] |
| Tofu | 4 | 8–12 | 549 (Piquito de Tofu), 7359 (Piquito de Tofu), 7360 (Picotazo), 7361 (Tofullería) | [] | [] |
| Bebé tofu | 6 | 4–8 | 5790 (Desplume) | [] | [] |
| Jalatín blanco | 39 | 4–8 | 5768 (Baba Blanca) | [] | [] |
| Gorditofu | 704 | 14–18 | 1434 (Picotazo), 1435 (Voltereta) | [{'state_id': 4412, 'level_parameter': 1, 'native_flag': 0}] | [] |
| Miaumiau negro | 1482 | 1–245 | 5231 (Husmiau) | [] | [] |
| Jalató amoroso | 1724 | 8–12 | 548 (Mordedura de Jalató) | [] | [] |
| Jefe miaumiau | 1851 | 7–7 |  | [] | [] |
| Jalató del amor | 1861 | 10–10 | 5767 (Mordedura de Jalató) | [] | [] |
| Jalató | 1918 | 10–10 |  | [] | [] |
| Jalató de Haluín | 2048 | 8–12 | 5767 (Mordedura de Jalató) | [] | [] |
| Jalatín de Haluín | 2090 | 1–1 | 800 (Baba Negra) | [{'state_id': 1543, 'level_parameter': 1, 'native_flag': 1}] | [] |
| Jalató de Haluín | 2092 | 10–10 | 3090 (Mordisqueo), 3047 (Mandíbula Viviente), 3046 (Bota Veloz), 3048 (Estabilidad Defensiva) | [] | [] |
| Jalató de Haluín | 2104 | 10–10 | 3060 (Mordedura de Jalató) | [{'state_id': 1543, 'level_parameter': 1, 'native_flag': 1}] | [] |
| Miaumiau de las nieves | 2373 | 1–1 | 1774 (Zarpacín) | [] | [] |
| Miaumiau angora | 2598 | 6–8 | 3804 (Agilidad Felina), 1774 (Zarpacín) | [] | [] |
| Miaumiau | 2616 | 4–6 | 1774 (Zarpacín), 3803 (Delicadeza) | [] | [] |
| Miaumiau blanco | 2617 | 4–6 | 2794 (Miaumiaullido), 3831 (Lametazo) | [] | [] |
| Espíritu de jalatín blanco | 2778 | 5–5 | 4019 (Mordedura del Espíritu Jalató) | [] | [] |
| Jalató espectral | 2808 | 1–1 |  | [] | [] |
| Jalató de primavera | 2869 | 8–12 | 5773 (Cuchillada), 5776 (Llamada de la Manada), 5777 (Carga Cornuda) | [] | [] |
| Miaumiau negro | 3668 | 0–1 | 4861 (Maramiaumiau) | [] | [] |
| Jalató de carrera | 3976 | 1–1 | 5675 (Desplazamiento) | [] | [] |
| Jalató de carrera | 3980 | 1–1 | 5675 (Desplazamiento) | [] | [] |
| Jalató de carrera | 3981 | 1–1 | 5675 (Desplazamiento) | [] | [] |
| Jalató de carrera | 3982 | 1–1 | 5675 (Desplazamiento) | [] | [] |
| Jalató de carrera | 3983 | 1–1 | 5675 (Desplazamiento) | [] | [] |
| Jalató de carrera | 3984 | 1–1 | 5675 (Desplazamiento) | [] | [] |
| Tofu corrupto joven | 4010 | 1–1 | 5708 (Pico Stasiado) | [] | [] |
| Jalató blindado | 4011 | 1–1 | 5709 (Mordedura Stasiada) | [] | [] |
| Jalató stasiado | 4014 | 3–3 | 5731 (Mordedura Stasiada) | [{'state_id': 4322, 'level_parameter': 1, 'native_flag': 1}] | [] |
| Tofu corrupto | 4015 | 2–2 | 5732 (Pico Stasiado) | [{'state_id': 4322, 'level_parameter': 1, 'native_flag': 1}] | [] |
| Embrialma de jalató | 4023 | 1–1 |  | [] | [] |
| Embrialma de tofu | 4024 | 1–1 |  | [] | [] |
| Miaumiau de oro | 4102 | 1–1 |  | [] | [] |
| Jalató de San Patírico | 4212 | 8–12 | 548 (Mordedura de Jalató) | [] | [] |
| Jalató rosa | 4452 | 8–12 |  | [] | [] |
| Jalató | 5462 | 1–1 |  | [] | [] |
| Jalató celestial | 5526 | 8–8 | 7981 (Tempestad Celestial) | [] | [] |
| Súper miaumiau negro | 5535 | 1–245 | 7986 (Súper Husmiau) | [] | [] |

## Owned ability samples at the minimum actor level

Costs are native AP/MP/WP. A zero cost is retained. Parameters below are native family arguments, not inferred damage.

### Jalató (1)

- **Mordedura de Jalató (5767), level 8**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182616, 183253], conditional tables=0.
  - Root 182616: family 3, parameters [10], children [], flags [22], criteria ``.
  - Root 183253: family 3, parameters [12], children [], flags [22], criteria ``.

### Jalatín negro (2)

- **Baba Negra (5769), level 4**: range [2, 4], costs [3, 0, 0], LOS=False, linear=False, roots=[182656, 183259, 183260, 182655], conditional tables=0.
  - Root 182656: family 4, parameters [3], children [], flags [22], criteria ``.
  - Root 183259: family 4, parameters [3], children [], flags [22], criteria ``.
  - Root 183260: family 48, parameters [2], children [], flags [17], criteria ``.
  - Root 182655: family 48, parameters [2], children [], flags [17], criteria ``.

### Jefe de guerra jalató (3)

- **Cuchillada (5773), level 14**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182626, 183265, 183266, 182686], conditional tables=0.
  - Root 182626: family 2, parameters [10], children [], flags [22], criteria ``.
  - Root 183265: family 2, parameters [12], children [], flags [22], criteria ``.
  - Root 183266: family 304, parameters [4406, 20, -1], children [], flags [17], criteria ``.
  - Root 182686: family 304, parameters [4406, 15, -1], children [], flags [], criteria ``.
- **Carga Cornuda (5777), level 14**: range [3, 4], costs [2, 0, 0], LOS=True, linear=True, roots=[182639, 183277, 182640, 183278, 182641, 183279], conditional tables=0.
  - Root 182639: family 305, parameters [], children [], flags [17], criteria `not HasFightProperty("caster", 11)`.
  - Root 183277: family 305, parameters [], children [], flags [17], criteria `not HasFightProperty("caster", 11)`.
  - Root 182640: family 3, parameters [7], children [], flags [22], criteria `GetDistanceBetweenCasterAndTarget() == 1`.
  - Root 183278: family 3, parameters [8], children [], flags [22], criteria `GetDistanceBetweenCasterAndTarget() == 1`.
  - Root 182641: family 304, parameters [131, 1, -1], children [], flags [17], criteria `GetDistanceBetweenCasterAndTarget() == 1 and not IsSummonedFromSymbiot("caster") and False`.
  - Root 183279: family 304, parameters [131, 1, -1], children [], flags [17], criteria `GetDistanceBetweenCasterAndTarget() == 1 and not IsSummonedFromSymbiot("caster") and False`.
- **Llamada de la Manada (5776), level 14**: range [0, 0], costs [1, 0, 0], LOS=True, linear=False, roots=[182668, 183271, 183299, 183300], conditional tables=0.
  - Root 182668: family 304, parameters [4420, 1, -1], children [], flags [17], criteria ``.
  - Root 183271: family 304, parameters [4420, 1, -1], children [], flags [17], criteria ``.
  - Root 183299: family 304, parameters [4421, 10, -1], children [], flags [17], criteria ``.
  - Root 183300: family 304, parameters [4421, 15, -1], children [], flags [17], criteria ``.

### Tofu (4)

- **Piquito de Tofu (549), level 8**: range [1, 2], costs [3, 0, 0], LOS=True, linear=False, roots=[183319, 4130, 183320, 183289], conditional tables=0.
  - Root 183319: family 5, parameters [12], children [], flags [22], criteria ``.
  - Root 4130: family 5, parameters [10], children [], flags [22], criteria ``.
  - Root 183320: family 304, parameters [4417, 15, -1], children [], flags [17], criteria ``.
  - Root 183289: family 304, parameters [4417, 10, -1], children [], flags [17], criteria ``.
- **Piquito de Tofu (7359), level 8**: range [1, 3], costs [0, 0, 1], LOS=True, linear=False, roots=[327526, 327626], conditional tables=0.
  - Root 327526: family 330, parameters [0, 1, 1], children [327527, 327528], flags [], criteria ``.
  - Root 327626: family 330, parameters [0, 1, 1], children [327627, 327628], flags [], criteria ``.
- **Picotazo (7360), level 8**: range [1, 1], costs [0, 0, 1], LOS=True, linear=False, roots=[327531, 327631], conditional tables=0.
  - Root 327531: family 330, parameters [0, 1, 1], children [327532, 327533, 327534], flags [], criteria ``.
  - Root 327631: family 330, parameters [0, 1, 1], children [327632, 327633, 327634], flags [], criteria ``.
- **Tofullería (7361), level 8**: range [0, 0], costs [0, 0, 1], LOS=True, linear=False, roots=[327663], conditional tables=0.
  - Root 327663: family 330, parameters [], children [327535, 327543, 327544], flags [], criteria ``.

### Bebé tofu (6)

- **Desplume (5790), level 4**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182839, 183317, 183318, 183302], conditional tables=0.
  - Root 182839: family 4, parameters [3], children [], flags [22], criteria ``.
  - Root 183317: family 4, parameters [3], children [], flags [22], criteria ``.
  - Root 183318: family 304, parameters [4417, 15, -1], children [], flags [17], criteria ``.
  - Root 183302: family 304, parameters [4417, 10, -1], children [], flags [17], criteria ``.

### Jalatín blanco (39)

- **Baba Blanca (5768), level 4**: range [2, 4], costs [3, 0, 0], LOS=False, linear=False, roots=[182657, 183261, 182618, 183262], conditional tables=0.
  - Root 182657: family 4, parameters [3], children [], flags [22], criteria ``.
  - Root 183261: family 4, parameters [3], children [], flags [22], criteria ``.
  - Root 182618: family 55, parameters [2], children [], flags [17], criteria ``.
  - Root 183262: family 55, parameters [2], children [], flags [17], criteria ``.

### Gorditofu (704)

- **Picotazo (1434), level 14**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[13808, 183321], conditional tables=0.
  - Root 13808: family 3, parameters [9], children [], flags [22], criteria ``.
  - Root 183321: family 3, parameters [12], children [], flags [22], criteria ``.
- **Voltereta (1435), level 14**: range [3, 5], costs [3, 0, 0], LOS=True, linear=True, roots=[183322, 13810, 183301, 183323], conditional tables=0.
  - Root 183322: family 4, parameters [12], children [], flags [22], criteria ``.
  - Root 13810: family 4, parameters [9], children [], flags [22], criteria ``.
  - Root 183301: family 304, parameters [1779, 1, -1], children [], flags [17], criteria ``.
  - Root 183323: family 304, parameters [1779, 1, -1], children [], flags [17], criteria ``.

### Miaumiau negro (1482)

- **Husmiau (5231), level 1**: range [1, 3], costs [3, 0, 0], LOS=True, linear=False, roots=[161815, 361104], conditional tables=0.
  - Root 161815: family 304, parameters [7957, 120, -1], children [], flags [], criteria `False`.
  - Root 361104: family 330, parameters [], children [361105, 361106], flags [], criteria ``.

### Jalató amoroso (1724)

- **Mordedura de Jalató (548), level 8**: range [1, 1], costs [4, 0, 0], LOS=True, linear=False, roots=[4129, 4128], conditional tables=0.
  - Root 4129: family 3, parameters [13], children [], flags [22], criteria ``.
  - Root 4128: family 3, parameters [8], children [], flags [22], criteria ``.

### Jefe miaumiau (1851)


### Jalató del amor (1861)

- **Mordedura de Jalató (5767), level 10**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182616, 183253], conditional tables=0.
  - Root 182616: family 3, parameters [10], children [], flags [22], criteria ``.
  - Root 183253: family 3, parameters [12], children [], flags [22], criteria ``.

### Jalató (1918)


### Jalató de Haluín (2048)

- **Mordedura de Jalató (5767), level 8**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182616, 183253], conditional tables=0.
  - Root 182616: family 3, parameters [10], children [], flags [22], criteria ``.
  - Root 183253: family 3, parameters [12], children [], flags [22], criteria ``.

### Jalatín de Haluín (2090)

- **Baba Negra (800), level 1**: range [1, 4], costs [4, 0, 0], LOS=False, linear=False, roots=[49231], conditional tables=0.
  - Root 49231: family 48, parameters [2], children [], flags [17], criteria ``.

### Jalató de Haluín (2092)

- **Mordisqueo (3090), level 10**: range [1, 1], costs [2, 0, 0], LOS=True, linear=False, roots=[72608], conditional tables=0.
  - Root 72608: family 1, parameters [1], children [], flags [17], criteria ``.
- **Mandíbula Viviente (3047), level 10**: range [0, 0], costs [0, 0, 1], LOS=True, linear=False, roots=[71702], conditional tables=0.
  - Root 71702: family 31, parameters [3, 1, 0], children [], flags [17], criteria ``.
- **Bota Veloz (3046), level 10**: range [0, 0], costs [0, 0, 1], LOS=False, linear=False, roots=[71701], conditional tables=0.
  - Root 71701: family 41, parameters [3, 1, 0], children [], flags [17], criteria ``.
- **Estabilidad Defensiva (3048), level 10**: range [0, 0], costs [0, 0, 1], LOS=True, linear=False, roots=[71703], conditional tables=0.
  - Root 71703: family 304, parameters [1537, 1, -1], children [], flags [17], criteria ``.

### Jalató de Haluín (2104)

- **Mordedura de Jalató (3060), level 10**: range [1, 1], costs [4, 0, 0], LOS=True, linear=False, roots=[71872], conditional tables=0.
  - Root 71872: family 1, parameters [1], children [], flags [17], criteria ``.

### Miaumiau de las nieves (2373)

- **Zarpacín (1774), level 1**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182773, 182774], conditional tables=0.
  - Root 182773: family 3, parameters [8], children [], flags [22], criteria ``.
  - Root 182774: family 3, parameters [10], children [], flags [22], criteria ``.

### Miaumiau angora (2598)

- **Agilidad Felina (3804), level 6**: range [0, 4], costs [2, 0, 0], LOS=True, linear=False, roots=[96481, 182767], conditional tables=0.
  - Root 96481: family 304, parameters [4409, 20, -1], children [], flags [17], criteria ``.
  - Root 182767: family 304, parameters [4409, 30, -1], children [], flags [17], criteria ``.
- **Zarpacín (1774), level 6**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182773, 182774], conditional tables=0.
  - Root 182773: family 3, parameters [8], children [], flags [22], criteria ``.
  - Root 182774: family 3, parameters [10], children [], flags [22], criteria ``.

### Miaumiau (2616)

- **Zarpacín (1774), level 4**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182773, 182774], conditional tables=0.
  - Root 182773: family 3, parameters [8], children [], flags [22], criteria ``.
  - Root 182774: family 3, parameters [10], children [], flags [22], criteria ``.
- **Delicadeza (3803), level 4**: range [1, 1], costs [2, 0, 0], LOS=True, linear=False, roots=[96479, 182769], conditional tables=0.
  - Root 96479: family 304, parameters [4410, 40, -1], children [], flags [17], criteria ``.
  - Root 182769: family 304, parameters [4410, 50, -1], children [], flags [17], criteria ``.

### Miaumiau blanco (2617)

- **Miaumiaullido (2794), level 4**: range [0, 0], costs [3, 0, 0], LOS=True, linear=False, roots=[64489, 64488], conditional tables=0.
  - Root 64489: family 258, parameters [12], children [], flags [4], criteria ``.
  - Root 64488: family 258, parameters [10], children [], flags [4], criteria ``.
- **Lametazo (3831), level 4**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182778, 182777], conditional tables=0.
  - Root 182778: family 4, parameters [10], children [], flags [22], criteria ``.
  - Root 182777: family 4, parameters [8], children [], flags [22], criteria ``.

### Espíritu de jalatín blanco (2778)

- **Mordedura del Espíritu Jalató (4019), level 5**: range [1, 1], costs [4, 0, 0], LOS=True, linear=False, roots=[105144, 332059], conditional tables=1.
  - Root 105144: family 321, parameters [2324], children [], flags [17], criteria ``.
  - Root 332059: family 321, parameters [7299], children [], flags [17], criteria ``.

### Jalató espectral (2808)


### Jalató de primavera (2869)

- **Cuchillada (5773), level 8**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[182626, 183265, 183266, 182686], conditional tables=0.
  - Root 182626: family 2, parameters [10], children [], flags [22], criteria ``.
  - Root 183265: family 2, parameters [12], children [], flags [22], criteria ``.
  - Root 183266: family 304, parameters [4406, 20, -1], children [], flags [17], criteria ``.
  - Root 182686: family 304, parameters [4406, 15, -1], children [], flags [], criteria ``.
- **Llamada de la Manada (5776), level 8**: range [0, 0], costs [1, 0, 0], LOS=True, linear=False, roots=[182668, 183271, 183299, 183300], conditional tables=0.
  - Root 182668: family 304, parameters [4420, 1, -1], children [], flags [17], criteria ``.
  - Root 183271: family 304, parameters [4420, 1, -1], children [], flags [17], criteria ``.
  - Root 183299: family 304, parameters [4421, 10, -1], children [], flags [17], criteria ``.
  - Root 183300: family 304, parameters [4421, 15, -1], children [], flags [17], criteria ``.
- **Carga Cornuda (5777), level 8**: range [3, 4], costs [2, 0, 0], LOS=True, linear=True, roots=[182639, 183277, 182640, 183278, 182641, 183279], conditional tables=0.
  - Root 182639: family 305, parameters [], children [], flags [17], criteria `not HasFightProperty("caster", 11)`.
  - Root 183277: family 305, parameters [], children [], flags [17], criteria `not HasFightProperty("caster", 11)`.
  - Root 182640: family 3, parameters [7], children [], flags [22], criteria `GetDistanceBetweenCasterAndTarget() == 1`.
  - Root 183278: family 3, parameters [8], children [], flags [22], criteria `GetDistanceBetweenCasterAndTarget() == 1`.
  - Root 182641: family 304, parameters [131, 1, -1], children [], flags [17], criteria `GetDistanceBetweenCasterAndTarget() == 1 and not IsSummonedFromSymbiot("caster") and False`.
  - Root 183279: family 304, parameters [131, 1, -1], children [], flags [17], criteria `GetDistanceBetweenCasterAndTarget() == 1 and not IsSummonedFromSymbiot("caster") and False`.

### Miaumiau negro (3668)

- Spell 4861, level 0: no positive-level sample.

### Jalató de carrera (3976)

- **Desplazamiento (5675), level 1**: range [0, 0], costs [0, 0, 0], LOS=False, linear=True, roots=[177016, 177055, 177061], conditional tables=15.
  - Root 177016: family 302, parameters [0, 0, 1, 0], children [], flags [17], criteria ``.
  - Root 177055: family 321, parameters [4193], children [], flags [17], criteria ``.
  - Root 177061: family 447, parameters [1], children [], flags [17], criteria ``.

### Jalató de carrera (3980)

- **Desplazamiento (5675), level 1**: range [0, 0], costs [0, 0, 0], LOS=False, linear=True, roots=[177016, 177055, 177061], conditional tables=15.
  - Root 177016: family 302, parameters [0, 0, 1, 0], children [], flags [17], criteria ``.
  - Root 177055: family 321, parameters [4193], children [], flags [17], criteria ``.
  - Root 177061: family 447, parameters [1], children [], flags [17], criteria ``.

### Jalató de carrera (3981)

- **Desplazamiento (5675), level 1**: range [0, 0], costs [0, 0, 0], LOS=False, linear=True, roots=[177016, 177055, 177061], conditional tables=15.
  - Root 177016: family 302, parameters [0, 0, 1, 0], children [], flags [17], criteria ``.
  - Root 177055: family 321, parameters [4193], children [], flags [17], criteria ``.
  - Root 177061: family 447, parameters [1], children [], flags [17], criteria ``.

### Jalató de carrera (3982)

- **Desplazamiento (5675), level 1**: range [0, 0], costs [0, 0, 0], LOS=False, linear=True, roots=[177016, 177055, 177061], conditional tables=15.
  - Root 177016: family 302, parameters [0, 0, 1, 0], children [], flags [17], criteria ``.
  - Root 177055: family 321, parameters [4193], children [], flags [17], criteria ``.
  - Root 177061: family 447, parameters [1], children [], flags [17], criteria ``.

### Jalató de carrera (3983)

- **Desplazamiento (5675), level 1**: range [0, 0], costs [0, 0, 0], LOS=False, linear=True, roots=[177016, 177055, 177061], conditional tables=15.
  - Root 177016: family 302, parameters [0, 0, 1, 0], children [], flags [17], criteria ``.
  - Root 177055: family 321, parameters [4193], children [], flags [17], criteria ``.
  - Root 177061: family 447, parameters [1], children [], flags [17], criteria ``.

### Jalató de carrera (3984)

- **Desplazamiento (5675), level 1**: range [0, 0], costs [0, 0, 0], LOS=False, linear=True, roots=[177016, 177055, 177061], conditional tables=15.
  - Root 177016: family 302, parameters [0, 0, 1, 0], children [], flags [17], criteria ``.
  - Root 177055: family 321, parameters [4193], children [], flags [17], criteria ``.
  - Root 177061: family 447, parameters [1], children [], flags [17], criteria ``.

### Tofu corrupto joven (4010)

- **Pico Stasiado (5708), level 1**: range [2, 2], costs [3, 0, 0], LOS=True, linear=False, roots=[180568], conditional tables=0.
  - Root 180568: family 5, parameters [3], children [], flags [], criteria ``.

### Jalató blindado (4011)

- **Mordedura Stasiada (5709), level 1**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[180581, 181027, 181028], conditional tables=0.
  - Root 180581: family 3, parameters [4, 0], children [], flags [17], criteria `not (IsSidestabbed("target") or IsBackstabbed("target"))`.
  - Root 181027: family 3, parameters [8, 0], children [], flags [17], criteria `IsSidestabbed("target")`.
  - Root 181028: family 3, parameters [12, 0], children [], flags [17], criteria `IsBackstabbed("target")`.

### Jalató stasiado (4014)

- **Mordedura Stasiada (5731), level 3**: range [1, 1], costs [3, 0, 0], LOS=True, linear=False, roots=[181228, 181227], conditional tables=0.
  - Root 181228: family 3, parameters [8], children [], flags [22], criteria ``.
  - Root 181227: family 3, parameters [7], children [], flags [22], criteria ``.

### Tofu corrupto (4015)

- **Pico Stasiado (5732), level 2**: range [2, 2], costs [3, 0, 0], LOS=True, linear=False, roots=[181230, 181231], conditional tables=0.
  - Root 181230: family 5, parameters [2], children [], flags [22], criteria ``.
  - Root 181231: family 5, parameters [3], children [], flags [22], criteria ``.

### Embrialma de jalató (4023)


### Embrialma de tofu (4024)


### Miaumiau de oro (4102)


### Jalató de San Patírico (4212)

- **Mordedura de Jalató (548), level 8**: range [1, 1], costs [4, 0, 0], LOS=True, linear=False, roots=[4129, 4128], conditional tables=0.
  - Root 4129: family 3, parameters [13], children [], flags [22], criteria ``.
  - Root 4128: family 3, parameters [8], children [], flags [22], criteria ``.

### Jalató rosa (4452)


### Jalató (5462)


### Jalató celestial (5526)

- **Tempestad Celestial (7981), level 8**: range [2, 5], costs [3, 0, 0], LOS=True, linear=False, roots=[367632, 367630], conditional tables=0.
  - Root 367632: family 1, parameters [5], children [], flags [], criteria ``.
  - Root 367630: family 1, parameters [4], children [], flags [], criteria ``.

### Súper miaumiau negro (5535)

- **Súper Husmiau (7986), level 1**: range [1, 3], costs [3, 0, 0], LOS=True, linear=False, roots=[367879, 367880], conditional tables=0.
  - Root 367879: family 304, parameters [7957, 200, -1], children [], flags [], criteria `False`.
  - Root 367880: family 330, parameters [], children [367881, 367882], flags [], criteria ``.

## Limits

- Extracted data does not certify executable casts or complete monster mechanics.
- Full effect parameter samples cover levels 1..200; separate native level-zero casting/effect evidence and raw curves are retained. Levels >200 require additional parameter sampling.
- State 304/321 and spell-grant 649 parameter links are conservative candidates across all sampled levels, not unconditional execution.
- Other dynamic references, summon/area creation, scripts and server-only mechanics require semantic reconstruction; raw definitions are retained.
- Native combat AI scripts and official decision policies are not reconstructed by this bundle.
- Runtime authority remains the pinned PostgreSQL release; these files are offline import/review artifacts only.
