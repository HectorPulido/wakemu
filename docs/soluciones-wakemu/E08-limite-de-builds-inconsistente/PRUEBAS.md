# Pruebas y aceptación — E08

## Revalidación PostgreSQL — 2026-10-05

El lote aislado `test_aptitudes test_live_console test_build_capacity test_builds test_build_journal test_equipment_stats test_equipment_full_set test_equipment_full_set_ready test_equipment_combat_integration test_ring_build_integration` pasó: **54 tests OK** en contenedores efímeros `world`, con PostgreSQL y migraciones 001–008.

| Invariante | Evidencia PostgreSQL |
| --- | --- |
| Índice e identidad separados del cupo | `test_sparse_index_and_native_byte_boundaries` acepta índices dispersos3,24,127 y rechaza −1,128, booleanos y floats. |
| Cupo por cantidad, no por índice máximo | `test_capacity_is_count_not_max_index`: 24 hojas no permanentes permiten índice24; una hoja adicional en índice127 excede cupo. Clasificación permanente falsa no evade la validación. |
| Setting durable | `test_database_capacity_controls_validation_and_reopen`: setting1 se lee tras reabrir, valida una hoja y rechaza la siguiente; setting inválido25 falla al cargar. |
| Límite en el camino de escritura | `test_database_capacity_rejects_save_without_partial_insert`: con cupo1 `Store.save_build` guarda una hoja, rechaza la segunda y tras reabrir solo permanece la primera. |
| Carrier nativo del setting | `test_native_capacity_carrier_is_exact_for_one_and_default_twenty_four` comprueba el opcode22318 y los cuerpos hexadecimales exactos para1 y24; `test_native_capacity_carrier_rejects_invalid_types_and_bounds` rechaza None, booleanos, valores fuera1–24, float y string. El decoder nativo del carrier aplica delta24→1 y conserva `calendar.delta7`. |
| Índice alto persistido | `test_high_index_save_reopen_and_effective_stats`: índice127 se guarda, reabre y evalúa;128 falla. |
| Catálogo compartido | `test_metadata_equipment_and_aptitudes_share_catalog` alinea índices de metadata, registro de equipo y aptitudes para0 y127. |

## Gap de anuncio

El código actual envía el carrier22318 antes del paquete23082 del bootstrap y con las respuestas de guardado exitoso o rechazado. La prueba/lectura del decoder nativo confirma actualización del estado de configuración y preservación de otra clave; aún falta observar visualmente el contador en la UI durante una sesión y verificar la secuencia completa de creación/selección/borrado.
