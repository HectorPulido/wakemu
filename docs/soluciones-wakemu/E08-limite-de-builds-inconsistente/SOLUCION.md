# Solución propuesta — E08

Alinear cupos anunciados y validación con un catálogo autoritativo y tipos nativos.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Acotar capacidades nativas

Comprobado: configuración 2510 `non.permanent.build.limit`=24; el contador excluye builds permanentes. Se identificaron 16 tramos permanentes y el modelo nativo acepta índice 3. El desbloqueo es 51. 13776/13811 usan byte con signo; validar el rango de cada carrier y contar builds no permanentes por separado.

## 2. Definir cupo por personaje

Resolver allowed_indices/count por política, nivel y características soportadas. Misma función alimenta bootstrap, create/save/activate/delete y presupuesto. Builds existentes fuera del cupo requieren migración explícita, no borrar silenciosamente.

## 3. Actualizar validaciones y schema propuestos

Quitar máximo 2 disperso solo donde el contrato nativo admita nuevos índices; validar cardinalidad, identidad, tamaño y ownership. Si se conserva cupo 3, emitir configuración visible compatible para que UI no ofrezca 24. Documentar cualquier limite técnico que impida esa coherencia.

## 4. Preservar referencias y selección

Crear índice nuevo produce cuatro hojas completas, active válido y deck/gear registrables. No sobrescribir 0 ni 1 por usar contador equivocado. Borrar libera cupo según política y los índices persistidos permanecen estables.

## 5. Probar bordes y recuperación

Primer índice, último válido y primero inválido por cada nivel; request duplicado, índices negativos/byte con signo y recarga con hojas antiguas. Reconnect y journal deben conservar la misma capacidad/lista que mostraron al crear.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

El cupo que la interfaz ofrece corresponde al que el servidor valida; cada índice conserva su identidad.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.

## Revisión posterior a tus respuestas

[Desbloqueo 51, cupo no permanente 24 y respuesta 13811 verificados](REVISION-RESPUESTAS.md). Esta revisión sustituye las dudas anteriores sobre esos contratos. Las referencias a casts son históricas o trabajo de otra sesión; no se continúan aquí.
