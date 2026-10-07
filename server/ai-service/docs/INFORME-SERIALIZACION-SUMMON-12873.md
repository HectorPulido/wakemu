# Investigación: refresco 12873 para summons con UID positivo

Revisión de código, bytecode/decompilaciones locales y probes existentes. Solo lectura del runtime y del cliente; no se ejecutaron probes ni se modificó el mundo.

## Conclusión

El envelope genérico de 12873 ya transporta un `actor_id` firmado de 64 bits (`>iq`), por lo que en la capa exterior no hay una restricción a IDs negativos. La limitación actual está en el encoder del cuerpo: `monster_actor_stats` genera el formato 2 de `eHj` (estado público NPC), pero impone explícitamente `identity < 0`. Esa guarda convierte en error un summon válido cuyo UID positivo ya fue creado y registrado por el camino nativo 13497.

La referencia viable del SDK es **el encoder actual `monster_actor_stats` y la snapshot NPC nativa**, reutilizando el cuerpo eHj/formato 2 y sus secciones de características, con una entrada construida desde el summon registrado. Esto es la ruta más próxima a la entidad `eHj` que usa el consumidor de estadísticas, y evita inventar otro formato. Aún no es evidencia suficiente para habilitarlo: falta validar en el JAR que el cliente aplica dicho cuerpo a un summon positivo ya creado por su descriptor `eHD`. El contrato exterior acepta el UID; el parser/aplicador del cuerpo para este caso no tiene prueba diferencial todavía.

## Evidencia concreta

- [`combat_wire.py`](../../wakfu_server/combat/combat_wire.py#L23) empaqueta 12873 como `fight_id:i32`, `actor_id:i64 firmado`, longitud del cuerpo `i16` y bytes. No restringe el signo de `actor_id`.
- [`combat_actor.py`](../../wakfu_server/combat/combat_actor.py#L131) implementa `monster_actor_stats`: su docstring lo identifica como `NPC eHj format2`; el cuerpo incluye posición, fight/obstacle, características, referencia, nivel e identidad repetida al final. En las líneas 143–144 rechaza todos los IDs positivos como “Invalid NPC identity”. [`actual_monster_actor_stats`](../../wakfu_server/combat/combat_actor.py#L225) arma este diccionario desde el actor vivo, incluyendo HP/recursos/posición y una snapshot de características, y luego cae en esa función.
- [`combat_summon_creation.py`](../../wakfu_server/combat/combat_summon_creation.py#L54) crea el summon como `Actor(actor_id, ...)` con UID positivo, instala una snapshot obtenida por `build_npc_snapshot` (curvas NPC nativas, características y recursos), y conserva `native_summon_source={ref, level, direction, caster_id, controller_id}` (líneas 69–77 y 131–137). La autoridad adjunta también conserva `native_instance_id` heredado del actor padre (líneas 114–130), que es la fuente disponible para `map_id`.
- [`combat_summon.py`](../../wakfu_server/combat/combat_summon.py#L158) exige identidad positiva y snapshot completa para registrar el summon. El registro persistente del preview se forma con actor/caster/controller, autoridad y fight/world properties (líneas 236–242); no contiene un descriptor de wire serializado. El actor sí conserva su estado completo (incluido `effect_stats`, mínimos/máximos y congelados) y el origen nativo.
- [`ProbeNativeSummonSnapshot.java`](../../../sniffer/java/ProbeNativeSummonSnapshot.java#L13) ya usa la ruta `bje` + `eHD` con el summon UID 901 y comprueba características reales del summon. [`ProbeNativeSummonDescriptor.java`](../../../sniffer/java/ProbeNativeSummonDescriptor.java#L18) comprueba descriptor `eZl`/13497 y UIDs positivos (summon 902, caster 901). Ninguno arma ni aplica un cuerpo 12873 para refrescar ese summon.
- `.runtime/local/combat-bootstrap-codecs.txt` describe `cuU` como opcode 12873 con campos `long aEp` y `byte[] azM`. `.runtime/local/combat-monster-entity.txt` confirma que `eHj extends eHd` y agrega secciones de estadísticas NPC (`sN`, `sP`, `sU`, `sX`, `sR`, `sL`). Esto apoya el formato NPC actual como referencia para el cuerpo, pero no demuestra que el consumidor de 12873 acepte un `eHj` asociado a un summon positivo.

## Datos que el puente ya puede aportar

Para construir el candidato sin perder autoridad, el SDK puede tomar:

- identidad, team, celda xyz, HP/AP/MP y maxima del `Actor` vivo;
- WP actual/máximo de la autoridad de recursos del fight, como hace ya `actual_monster_actor_stats`;
- referencia, nivel y dirección desde `actor.native_summon_source`;
- mapa/instancia desde `NativeActorAuthority.native_instance_id` del registro;
- snapshot del actor con `snapshot_characteristics(actor)` si existe `effect_stats`, preservando todos los stats instalados por la creación nativa;
- `native_obstacle_id` del actor para el byte obstacle, y `fight.id` del preview candidato.

Con ello, la implementación más segura es factorizar el ensamblado de cuerpo eHj/formato 2 en un helper interno que reciba un `identity` validado contra el registro de summons. `monster_actor_stats` mantiene su contrato NPC negativo; un nuevo serializer explícito de summon permite ID positivo solo cuando el actor está en `native_summon_registrations`, `is_summon=True` y coincide la identidad. Debe compartir el encoder interno de eHj, no clonar sus bytes por separado. La identidad positiva no debe confundirse con una PC: el summon es una entidad NPC `eHj` con origen `eHD`, no `FIGHTER_DATAS_WITH_XP`.

## Prueba diferencial requerida para cerrar el riesgo

Añadir un probe Java contra el mismo JAR, extendiendo las fixtures existentes:

1. Crear en el fight real/sintético un summon con `bje` UID positivo y su descriptor `eHD` mediante la ruta comprobada de 13497.
2. Capturar sus valores iniciales (HP/AP/MP/WP/armor, referencia/nivel/equipo/posición) desde las secciones nativas de `eHj`/`eHd`.
3. Construir con el SDK un cuerpo formato 2 a partir de ese actor ya registrado y envolverlo con 12873 usando el UID positivo.
4. Enviar el mensaje por el decoder `cuU` y ejecutar el mismo consumer `cjU`/aplicador de estado que consume un refresh normal. Comprobar que se resuelve al summon existente, no crea actor duplicado, y que cada stat cambia al valor enviado; verificar también que identidad, referencia y propiedades del descriptor permanecen consistentes.
5. Ejecutar controles con un NPC negativo y con un UID positivo inexistente. El NPC debe mantener el resultado previo; el UID sin registro debe fallar/no aplicarse. Repetir luego de una acción que gaste recursos y de movimiento para demostrar que el snapshot del preview candidato es el que llega al cliente.

La prueba decisiva es que el parser y el aplicador real acepten el body sobre el summon vivo. Que `cuU` decodifique el envelope o que `eHj` pueda parsear el body por separado no basta.

## Resultado diferencial ejecutado en el JAR instalado

Se extendió el probe aislado [`ProbeSummon12873Consumer.java`](../tools/java/ProbeSummon12873Consumer.java) y se agregó [`make_summon12873_fixture.py`](../scripts/make_summon12873_fixture.py). El fixture llama el encoder real `monster_actor_stats` con un descriptor derivado del snapshot vivo, pasa el `snapshot_characteristics(actor)` de SDK como cuerpo completo de estadísticas, y reemplaza únicamente los 8 bytes de identidad repetida al final (`body[-20:-12]`, parte del `>qBqBh`) para ejercer UID 901. El resto permanece exactamente en el formato 2 del SDK; el envelope está empaquetado como `>iqh` y conserva `fight_id=1`, `actor_id=901`. Datos: ref 1153, nivel 20, celda (9,10,0), mapa/instancia 123, dirección 0, obstáculos 4; snapshot HP/AP/MP/WP 17/4/2/2. El cuerpo mide 1.625 bytes, incluye 1.566 bytes de características, SHA-256 `97d72fb6b2047191f02c1279058d82d0f1c66d15dd425e02d0a866390c985600` (packet SHA-256 `4f1f03b6df36272d7501ae216c9aced13dd804c13411420a42d13cb450a68e2e`).

El probe crea un `bje` real con descriptor `eHD` (UID positivo 901, ref 1153/nivel 20), lo instala en el roster por UID de `buH`, decodifica el envelope con `cuU` y llama el método real `cjU.b(cuU)`. Resultado: el `bje` vivo pasa de HP/AP/MP/WP `853/5/5/3` a `17/4/2/2`; ref, nivel y la instancia del descriptor eHD se conservan. Un segundo paquete con UID externo 902 no está registrado: el consumer lo ignora y el summon conserva HP/AP `17/4`. Así queda probado el lookup positivo, la aplicación del cuerpo eHj al actor summon existente y la ausencia de actualización a un actor positivo no registrado.

Comando de reproducción desde la raíz (genera los blobs en `.runtime`, compila el probe en `.runtime/ai-probe-classes` y ejecuta el consumer del JAR):

```sh
PYTHONPATH=server python3 server/ai-service/scripts/make_summon12873_fixture.py
javac -proc:none -cp 'client/lib/wakfu-client.jar:client/lib/*' -d .runtime/ai-probe-classes server/ai-service/tools/java/ProbeSummon12873Consumer.java
javac --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED -proc:none -d .runtime/ai-probe-classes server/ai-service/tools/java/HeadlessFjAgent.java
jar cfm .runtime/headless-fj-agent.jar .runtime/ai-probe-manifest.mf -C .runtime/ai-probe-classes HeadlessFjAgent.class -C .runtime/ai-probe-classes 'HeadlessFjAgent$1.class' -C .runtime/ai-probe-classes 'HeadlessFjAgent$1$1.class' -C .runtime/ai-probe-classes 'HeadlessFjAgent$1$1$1.class'
java --add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED -Djava.awt.headless=true -Djava.library.path=client/natives -javaagent:.runtime/headless-fj-agent.jar -cp '.runtime/ai-probe-classes:client/lib/wakfu-client.jar:client/lib/*' ProbeSummon12873Consumer .runtime/summon-12873-body.bin
```

Salida relevante:

```text
format=2 stats=1566 body=1625 packet=1639 actor=901 ref=1153 level=20 hp=17 ap=4 mp=2 wp=2 body_sha256=97d72fb6b2047191f02c1279058d82d0f1c66d15dd425e02d0a866390c985600 packet_sha256=4f1f03b6df36272d7501ae216c9aced13dd804c13411420a42d13cb450a68e2e
before actor=901 hp=853 ap=5 mp=5 wp=3 ref=1153 level=20
after actor=901 hp=17 ap=4 mp=2 wp=2 ref=1153 level=20
PASS actual cuU12873 -> cjU.b -> registered live bje/eHD UID901 applied eHj body; unregistered UID902 ignored
```

El entorno JVM sin interfaz necesita un shim de harness porque el callback real `fj.zp()` intenta iniciar assets gráficos y lanza `ExceptionInInitializerError` (`aft.bVh == null`). [`HeadlessFjAgent.java`](../tools/java/HeadlessFjAgent.java) conserva `fj.zp` y su callback; captura el error de inicialización alrededor de `fi.zm()` para que el consumer continue, y suprime `PA.aZk()` que solo notifica observadores de UI. La prueba comprueba explícitamente que el actor nativo recibió los cuatro nuevos valores; el shim no reemplaza `cuU.dp`, `cjU.b`, `big.a`, `eGj.ev` ni el parser `eHj.ew`. La limitación restante es que el harness no valida la actualización gráfica/callback de UI, que requiere el cliente con sus assets inicializados.

El generador inyecta dos adaptadores de import aislados porque este checkout carece de `wakfu_server.combat.equipment_damage` (solo se necesita `_float`) y `wakfu_server.combat.paths` (alias de `DATA_ROOT`); ambos son ajenos a la codificación de wire. No se cambió ningún módulo runtime.

## Prioridad / estado

**Bloqueante para combates con summons en roster cuando un commit de movimiento/hechizo refresca 12873 para todos los actores.** El bloqueo actual es verificable en Python y se origina en la guarda de `monster_actor_stats`; el encoding exterior ya es genérico. Hay una ruta SDK concreta y completa para producir un candidato eHj, pero aceptación nativa del cliente para UID positivo sigue sin demostrar. No tratar como solución final excluir summons del roster ni rechazar invocaciones.
