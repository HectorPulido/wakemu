# Cotejo nativo y alcance — 27

## 13948: estado meteorológico actual

La clase `ctm` consume un payload de37bytes en big endian: i64 opaco, byte firmado, seis float32 e i32 de clima. El enum `Vl` es `0 ABSENT`, `1 LIGHT`, `2 HEAVY`, `3 STORM`. `chl` instala el estado en el modelo del territorio. El servidor preserva el payload y publica el estado por mapa, instancia y región calculada desde las celdas nativas. No se acredita que el i64 seleccione región.

La política general desplegada usa `ABSENT` y valores neutrales locales configurables. La inicialización conserva filas previas. La flora consulta el enum persistido; no se le asignan efectos a temperaturas o lluvia sin evidencia.

## 13895: forecast estructurado

El envelope `cBl.dp` contiene un u16 de longitud y el cuerpo de `bRV.fe`. Cada fila diaria mide12bytes: season u8, dos muestras i8, wind u16, clima i32, ajuste i8 y modificador i16. Luego hay un count de ajustes estacionales y registros `{season u8, min i8, max i8}`; el parser consume posiciones de relleno de3bytes cuando faltan registros para sus ranuras auxiliares. Las temporadas son ordinals0–3: invierno, primavera, verano y otoño. Los estados de clima comparten `Vl` con13948.

El consumidor `bRY` usa las filas para la previsión diaria y gráfica. La prueba Java del JAR instalado decodifica el vector sintético del encoder local. No se encontró productor server-side ni fuente oficial de forecast, calendario de datos o unidades físicas. Los nombres de campos reflejan el layout, no unidades Celsius.

## Fuente local y garantías

`territory_weather_forecast.py` ofrece codec estricto, persistencia estructurada por `(map_id, instance_id, region_id)`, versiones monotónicas y outbox versionado. El publicador filtra por mapa, instancia, región y lease actual; `packet_for_territory` produce un paquete vacío explícito para un ámbito sin forecast. El outbox coalesce versiones superseded, conserva reintentos tras fallo y no afirma ACK del cliente.

La migración058, el tick y la ruta de bootstrap están conectados en fuente. El smoke TLS completo ya pasó en candidata aislada; no afirmar que el forecast ya esté desplegado ni que sus datos sean upstream.

## Fuentes del servidor

- `server/wakfu_server/maps/territory_weather.py`: parser13948, persistencia, cambio de clima, outbox y tick.
- `server/wakfu_server/maps/territory_weather_forecast.py`: codec y política local13895 por ámbito exacto.
- `server/wakfu_server/maps/territory_cells.py`: mapa/región nativos resueltos por celda.
- `server/migrations/020_territory_weather.sql`, `055_territory_weather_transitions.sql`, `056_territory_weather_local_policy.sql`, `058_territory_weather_forecast_policy.sql`: persistencia por fases.
- `.runtime/local/review-continuacion-20261004/ForecastNativeProbe.java`: vector local verificado con el parser instalado.
