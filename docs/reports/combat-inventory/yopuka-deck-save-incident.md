# Baraja de Prueba Yopuka: rechazo silencioso en combate

La captura del 4 de octubre de 2026 acredita cuatro solicitudes 12772 del personaje20. Las dos primeras, a23:02:28Z y23:03:15Z, terminaron en `combat_world_action_rejected`: el guard general de acciones de mundo descartó la solicitud antes de guardar y no entregó respuesta12284. La edición optimista permaneció en pantalla hasta volver a entrar.

Las solicitudes a23:04:53Z y23:10:38Z sí terminaron en `build_saved` y `journal_committed`. Redis conserva la última baraja `[4778,4783,4780]`. La discrepancia temporal con SQLite corresponde al checkpoint diferido del journal, no acredita pérdida.

La entrega real también es correcta:12666 a23:09:49Z contiene la baraja de cinco posiciones guardada a23:04:53Z;12666 a23:12:40Z contiene la última de tres. Los12284 de ambas solicitudes aceptadas contienen los mismos datos. El12666 a23:04:21Z contiene la baraja inicial, coherente con los dos rechazos anteriores.

## Corrección preparada

`builds.blocked_save_messages(character, body)` entrega únicamente12284 negativo con la hoja previa autoritativa. Valida identidad e índice; no modifica el almacenamiento ni envía un snapshot de recursos fuera de combate. La conexión al guard de main se coordina por separado. No permite modificar el combate activo ni afirma que la edición rechazada se guardó.

Validación: `PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_builds.py -q`:10 pruebas pasan. La regresión comprueba restitución de baraja, ausencia de paquetes de recursos, conservación del almacenamiento y rechazo de identidad ajena. Pendiente: integración y comprobación cliente de rechazo visible. Los datos privados de captura permanecen en `.runtime/`.
