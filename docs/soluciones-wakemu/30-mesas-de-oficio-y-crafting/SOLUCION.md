# Solución propuesta — 30

Cargar mesas visibles y ejecutar recetas con consumo, producto y XP consistentes.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Diagnosticar presencia antes de interacción

Elegir mapa/mesa/ID/type; comprobar catálogo, loader de entorno y si la entidad existe nativamente.13984 actualiza bEG existente, no crea la ausente. Revisar orden de carga map→objects→snapshot, altura y estado; no añadir snapshots infinitamente para hacer aparecer objeto que no existe.

## 2. Verificar recursos disponibles

Servidor solo puede usar entidades/assets de la instalación propia del usuario. Si faltan en esa distribución, documentar bloqueo de datos y compatibilidad, no empaquetar/client ni editar assets. Para mesas portátiles revisar template/mobiliario y instancia merkasaco 26.

## 3. Decodificar mesa/receta

La UI nativa abre localmente mediante `cWp.eVB()` → `dag.a()`: no inventar una respuesta de apertura. Atender 12231 (`com`: mesa i64, receta i32, cantidad i32); separar 13515 (`coo`, i64 adicional todavía por resolver) y la improvisación. Cotejar resultados, receta/cantidad y cancelación según [la revisión ejecutada](REVISION-RESPUESTAS.md). Validar oficio aprendido/nivel, mesa correcta, distancia, propiedad/ACL y mapa. Una fila recipe catalogada no valida crafting ni receta disponible.

## 4. Confirmar producción atómica

Reservar ingredientes por UID/quantities y espacio de productos. Multiplicar cantidades con límites, consumir, crear unidad/stack con propiedades 22 y otorgar XP8 junto con recibo. Inventario lleno, material insuficiente o solicitud vieja rechazan antes de consumir; no usar destroy como reciclaje.

## 5. Sincronizar productos y progreso

Deltas de ingredientes, inserción/stack de productos y XP en orden probado. La misma petición no se repite por animación/client retry. Publicar estado de mesa para dos clientes sin inventarios privados y liberar ocupación tras cancelación/corte.

## 6. Aceptar mapa y mesa portátil

Dos clientes ven entidad y completan recetas independientes o reserva según regla. Probar merkasaco y mazmorra si hay mesas allí, reconnect y restore. Documentar coverage por tipo de mesa/receta, no afirmar todos oficios por una receta.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Ver mesa no acredita crafting; cada receta conserva materiales y concede resultado/XP una vez.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
