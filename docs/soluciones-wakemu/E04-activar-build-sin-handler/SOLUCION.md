# Solución propuesta — E04

Implementar activación nativa de build como transición propia, con rechazo seguro.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Fijar la solicitud observada

La petición 13776 contiene identidad i 64 e índice de un byte. Conservar una fixture sintética de 9 bytes y contrastarla con el rechazo gráfico registrado. No reutilizar guardar 12772 ni la notificación de borrado 12837.

## 2. Usar la respuesta nativa verificada

La respuesta de activación comprobada es 13811 (`ctV`): i64 de personaje y byte con signo de índice, total 9 bytes. Su consumidor `ciu` llama `eQX.R` y selecciona vía `eQW.QT`. El probe acepta índice 3 y rechaza un cuerpo truncado de 8 bytes. Falta ensayar por separado el rechazo y el desbloqueo de la selección optimista; no añadir un campo status que este mensaje no tiene.

## 3. Autorizar antes de cambiar

Comprobar personaje propio, generación de sesión, índice disponible, hojas completas, fase y revisión. El rechazo conserva selección y salud; el contrato nativo debe restaurar controles y check.

## 4. Confirmar selección y efectos juntos

Persistir índice y revisión según E05 y recalcular estadísticas desde la misma hoja. Aplicar una política explícita para combate y modulación. No alterar un snapshot de combate de manera incidental.

## 5. Probar respuesta y recuperación

Tras commit durable enviar la respuesta verificada. Repetir la petición y cortar antes del ACK: no duplicar bonus ni curar salud y reconstruir la selección desde almacenamiento al reconectar.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

El check optimista del cliente se confirma por servidor o se revierte con un mensaje probado.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.

## Revisión posterior a tus respuestas

[Desbloqueo 51, cupo no permanente 24 y respuesta 13811 verificados](REVISION-RESPUESTAS.md). Esta revisión sustituye las dudas anteriores sobre esos contratos. Las referencias a casts son históricas o trabajo de otra sesión; no se continúan aquí.
