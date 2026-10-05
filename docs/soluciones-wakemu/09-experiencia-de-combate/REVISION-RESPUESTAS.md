# Revisión de respuestas — XP de combate

## Código actual y prueba ejecutada

`combat_lifecycle.policy_from_env` lee `WAKFU_LOCAL_FIGHT_XP` y `WAKFU_LOCAL_FIGHT_KAMAS`, ambos con default **0**. Son importes fijos por victoria, no una fórmula basada en enemigos, niveles o grupo. No hay multiplicador en la base de datos en este recorrido. Esto acredita el default del código, no la configuración efectiva de todos los procesos ni el síntoma de una sesión compartida.

Se ejecutaron los cinco tests de `test_combat_rewards.py`: **OK**. Comprueban persistencia, umbrales de nivel, rechazo de propietario/derrota, límites y recibos. No prueban una victoria visible en dos clientes ni reparto grupal o mazmorras.

En SQLite desechable se premió un combate sintético terminado con XP100/kamas17: repetirlo en la misma generación conservó un único premio y `notification` devolvió null. Después se creó otra generación, se seleccionó el mismo personaje y se entregó **el mismo objeto Fight** a `award`: recibió otro premio, quedando XP200/kamas34 y dos recibos. [Resultado y hashes actuales](probe-recibos-y-generacion.json).

La clave actual `(generation,fight_id,character_id)` permite ese segundo premio por diseño; el test existente también permite reutilizar un ID numérico bajo otra generación. **No se ha demostrado que el servidor real recupere ese Fight y lo reenvíe por esta ruta**. Es un requisito de integración con recuperación de combates, no una afirmación de duplicación explotable en vivo.

## Solución concreta del servidor

Crear una identidad durable `fight_uuid` al iniciar el combate y conservarla en sus checkpoints. Mantener `UNIQUE(fight_uuid,character_id,reward_kind)` para el recibo; la generación autoriza la petición vigente, pero no identifica un premio nuevo. Un combate verdaderamente nuevo obtiene otro UUID aunque reutilice el entero del protocolo. Recuperar el mismo combate conserva UUID y premio.

Persistir una política versionada con multiplicadores separados `xp_multiplier_bp`, `kamas_multiplier_bp`, `drop_multiplier_bp`; propuesta de representación: entero 0–1000000, default10000=1×. Aplicar `floor(base * multiplier_bp / 10000)` usando enteros y validar los límites nativos antes del commit. Cero desactiva ese premio. Congelar versión y cantidades en el resultado durable del combate; cambiar configuración después no altera un reintento. Esta representación es una propuesta del emulador, no una fórmula oficial.

La distribución necesita una lista congelada de participantes elegibles y enemigos derrotados, obtenida del combate autoritativo. `prepare_finish` solo premia al personaje proporcionado; no recorre todo el equipo. Crear primero los resultados por participante, luego conceder cada recibo recuperable; la entrega no debe depender de que cada cliente pulse12925. No premiar espectadores ni duelos. Separar la actualización persistente de XP/nivel del envío13613 y del snapshot absoluto posterior. La integración de hechizos queda reservada a la otra sesión.

## Fórmula solicitada de Dofus y límites

Se corrigió la omisión de inspeccionar el repositorio indicado por el usuario: **`/Users/hectorpulido/dofus/starloco-game`**, leído sin ejecutarlo ni modificarlo. `FormuleOfficiel.getXp`, `Fight` y `Formulas` acreditan una implementación concreta, sin depender de fórmulas web. Véase [FORMULAS-DOFUS.md](FORMULAS-DOFUS.md) y [hashes de fuentes](probe-fuentes-dofus.json). El nombre FormuleOfficiel no demuestra equivalencia con un servidor oficial; la fuente solicitada es este emulador.

Pendientes reales: asignar XP base a referencias de Wakfu, integrar el reparto y sus modificadores con recibos durables, probar fallo entre persistencia y notificación, recuperación con otra sesión, entrega multijugador y victoria real que atraviese un umbral. La fórmula de referencia ya está localizada; no volver a listarla como fuente ausente. No se aplicó ningún fix.
