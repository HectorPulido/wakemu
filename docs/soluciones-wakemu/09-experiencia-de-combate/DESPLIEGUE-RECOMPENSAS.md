# Despliegue de recompensas

Imagen activa: `wakfu-local-world:merged-verified`, SHA256 `9af0658c4e5db5da40debb6ba8c656f248bc10397fb6055a03ae76f215039a28`.

- PostgreSQL activo:48 migraciones; respaldo privado previo al despliegue conservado en `.runtime/backups/pre-rewards-20261007.dump`.
- Gate sobre código/protocolo/migraciones internos de la imagen:259 pruebas aprobadas. Los tests y la configuración privada se montaron aparte; el código probado salió de la imagen.
- Servidor candidato: saludHTTP200 y entrada TLS real, selección de personaje, contactos630, entrada a mapa en caché y DND aprobados.
- Smoke de recompensas con DB candidata: XP positiva, cruce de nivel, kamas, drops deterministas, bolsa llena, overflow durable, bootstrap temporal, reclamación13993, reintentos y reconexión aprobados. Este smoke ejecuta el cierre transaccional real con estado nativo; no sustituye la prueba del combate completo por socket.
- Comparación del directorio de combate con la imagen anterior: cambios de comportamiento limitados a orquestación `combat_lifecycle.py` y serialización `combat_results.py`. `combat_group_store.py` tiene el mismo AST. Los archivos nuevos de IA no se modificaron como parte de recompensas; hechizos, daño y turnos anteriores conservaron sus hashes.

El servicio `world` carga código, protocolo y migraciones de la imagen, sin bind mounts del checkout. Solo conserva montajes de datos privados y fixture. Editar la fuente o crear una migración nueva ya no altera imports diferidos del servidor activo ni mezcla código nuevo con un esquema anterior. Cada actualización requiere imagen construida y pruebas antes de recrear el servicio.

Política actual: drop versión1, multiplicador×1; XP/kamas×1. La prueba corregida usa un Mimic4196 nivel1 con premio nativo garantizado; el multiplicador temporal×4 ya fue retirado. No modificar los porcentajes base visibles de la enciclopedia.

Aceptación del usuario pendiente: [prueba general](PRUEBA-GENERAL-RECOMPENSAS.md). El sistema completo de drop conserva pendientes de criterios complejos, clasificación de mazmorras, tablas externas y rollMax; no se cierra por probar una pluma.

Corrección posterior: al subir de nivel, el callback de cierre adopta también hp/max_hp/hp_damage/health_dead del personaje comprometido. La prueba socket completa confirma puño, resumen, retorno12925 sin stale HP y reconexión con botín temporal. El CAS de salud y el motor de hechizos permanecen intactos.
