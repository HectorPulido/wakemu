# Solución propuesta — 13

Enrutar cada mensaje solo a los destinatarios del canal correspondiente.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Inventariar peticiones por canal

Con tres cuentas capturar general/local, privado, grupo y otros canales solicitados; identificar canal, destinatario, mensaje y codec de respuesta. El handler 12366 actual publica texto por WORLD.broadcast; no agregar interpretaciones de campos sin decodificación completa.

## 2. Definir presencia y destinatarios

Registro cuenta/personaje/sesión/nombre normalizado y mapa/party. Privado resuelve personaje vigente y política offline/ignorado; local usa mapa/instancia/proximidad; grupo usa party, nunca COMBAT_GROUPS NPC. Canales nacionales dependen de 24 y no se habilitan con nación falsa.

## 3. Separar comandos de mensajes

Antes de difundir texto, decidir si es comando y autorizar mediante 32. Texto privado que comienza con ! no debe convertirse en comando de otra cuenta ni difundirse. Validar tamaños UTF-8, rate limit y destinatario sin almacenar secretos o payloads completos en logs.

## 4. Enviar con contrato por canal

Mantener autor, canal, destinatario y eco propio correctos. Errores de no conectado/ignorando/permisos usan respuestas verificadas. Serializar una vez y enviar fuera de locks globales; un destinatario lento no bloquea el canal completo.

## 5. Validar entrega y aislamiento

A envía a B mientras C está cercano: C nunca recibe el privado. Mover una sesión de mapa/party y revalidar al publicar para evitar destinatarios obsoletos. Definir ID/recibo si se permite reintento, sin duplicar eco ni mensajes a otros.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Un privado nunca usa broadcast; solo destinatarios autorizados reciben el contenido.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
