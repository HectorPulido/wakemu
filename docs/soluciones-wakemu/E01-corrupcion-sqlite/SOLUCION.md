# Solución propuesta — E01

Asegurar integridad y recuperar una copia consistente antes de confiar en progreso/ecosistema.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Identificar BD y versión afectadas

Correlacionar boot, path, hora, errores y writers; no usar basename world.sqlite 3 para confundir instancia principal/aislada. Leer integridad actual únicamente sobre copia consistente y preservar logs. El quick_check correcto de un personaje/prueba no descarta un archivo distinto históricamente dañado.

## 2. Preservar backup verificable

Planear backup online con SQLite backup API o procedimiento autorizado que incluya coherencia de WAL/SHM; copiar solo.db mientras escribe puede omitir commits. Guardar hashes/timestamps y configuración fuera deGit. No borrarWAL, VACUUM o recovery sobre original; preservar evidencia primero.

## 3. Diagnosticar sobre copia

Abrir URI mode=ro de la copia, ejecutar PRAGMAquick_check, integrity_check yforeign_key_check; registrar páginas/tablas afectadas. Comparar recursos, recibos, UIDunique, wallets y baselines del journal. Buscar falta de espacio, filesystem, truncado/copias y concurrencia, sin atribuir origen al bolso sin evidencia.

## 4. Elegir recovery explícito

Preferir respaldo sano y reconciliar journals/recibos posteriores; si se requiere recuperación de páginas usar herramienta SQLite sobre copia y validar lo salvado. No rellenar cantidades/XP de forma arbitraria; ledger debe detectar pérdida o duplicación. Documentar qué datos no pudieron recuperarse.

## 5. Ensayar reparación y cutover

Migrar copia a schema actual y correr recorridos de inventario/planta/premios. Preparar comparación fila/revisión/recibos, backup y plan de retorno. Sustituir BD o reiniciar servicio solo con autorización explícita fuera de este trabajo; no afirmar reparación desplegada por generar una copia.

## 6. Evitar repetición

Definir backups/checks, alarmas de corrupción/espacio, shutdown seguro y recuperación de Redis con SQLbaseline. Los errores persistentes deben detener solo dominios no seguros sin loops de log que consumen CPU; no silenciarlos y seguir otorgando objetos sobre estado dudoso.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Recovery nunca inventa objetos/progreso; la copia reparada se valida antes de sustituir la autoridad.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
