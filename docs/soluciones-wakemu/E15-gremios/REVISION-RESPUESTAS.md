# E15 — Decoder de mensajes de gremio

## Contrato comprobado y causa

Se volvió a inspeccionar `cms` del cliente instalado mediante `javap`: `jS(long)` guarda la identidad, `aWH()` escribe ese **i64** con `ayq.gE`, después serializa el texto común, y `d()` retorna **13744**. El cuerpo es `i64 guild_id + u16 longitud UTF-8 + texto`. No usa el mismo cuerpo que General.

En el código actual `protocol_codec.decode_body` incluye 13744 en la rama `(12366,13074,13744,13702)`, que lee solamente texto. Los primeros dos bytes del gremio se interpretan como longitud y los restantes quedan sin consumir o generan truncamiento. No se encontró handler 13744 en `local_game_server.py`; arreglar el decoder no implementaría por sí solo el canal.

## Reproducción y límites

[Probe actual y hash](probe-decoder-actual.json): cuatro cuerpos con texto «Prueba ñ» e identidades 0, 456, 281474976710663 y −1. Todos fallaron con `ValueError`: 17 bytes sin decodificar, 16 bytes sin decodificar o longitud inválida. La identidad grande demuestra que no basta con saltar bytes nulos; debe leerse el i64 completo. Cero y −1 sirven para comprobar framing, no acreditan gremios válidos.

Es una prueba offline del decoder y cotejo del encoder nativo, sin mensajes enviados mediante GUI. No prueba que estos errores concretos desconecten la sesión: debe trazarse si la ruta viva invoca este decoder y dónde captura la excepción. El rechazo silencioso por ausencia de handler es una brecha distinta.

## Solución concreta exclusivamente del servidor

Separar 13744 de la rama de texto y leer identidad i64 seguida de texto u16 UTF-8, verificando consumo completo. Rechazar cuerpos truncados, longitud excesiva, UTF-8 inválido y bytes sobrantes de forma recuperable según el framing del transporte.

El handler debe resolver la pertenencia real del personaje a un gremio bajo la lease de sesión. La identidad enviada por el cliente es contexto, no permiso: compararla con el gremio autorizado y nunca emitir al gremio elegido arbitrariamente. Construir destinatarios desde membresía y sesiones activas; incluir identidades correctas de cuenta/personaje y usar el consumidor nativo específico del canal, sin reutilizar General con un número de canal supuesto. Configurar límites de mensajes en DB, no con constantes dispersas.

Validación necesaria: gremio válido, personaje sin gremio, identidad ajena, dos miembros conectados en mapas distintos, expulsión durante envío, cambio de sesión, texto Unicode, receptor desconectado y error visible nativo. Cotejar primero respuesta y routing de gremio en la evidencia del issue 13. No se implementó la corrección ni se declara funcional el canal.

## Prueba real acordada

El usuario propone crear un gremio cuando esté preparada esta parte y observar el comportamiento real. No se creó un gremio durante esta reorganización. Antes de la prueba deberán cotejarse creación, membresía y canal; después comprobar emisión entre miembros y rechazo de no miembros. El fallo offline del decoder no sustituye esa prueba.

## Aclaración de alcance completo

El usuario precisó que E15 debe investigar todo el sistema de gremios: creación, persistencia y funcionamiento, además del chat. Las pruebas previas corresponden únicamente al decoder de chat. La auditoría integral sigue pendiente; no se sustituyen creación y durabilidad por esa evidencia limitada.

## Creación: requisitos y solicitud nativa acreditados

El controlador `dbA` publica en la UI el ítem de creación referencia **16942** y coste mostrado **10.000 kamas**, obtenidos de `eHt.fwJ/fwI`. También contempla ítem **25100** para cambiar emblema y **25101** para cambiar nombre. Son requisitos del cliente instalado; todavía debe acreditarse el consumo y rechazo autoritativos. El nombre pasa por `eRo.tC/tF`; faltan las reglas exactas.

La creación construye `cpr` (**13757**, categoría 3): emblema empaquetado i64 y tres strings, cada uno con longitud **i32** seguida de bytes: nombre del gremio, nombre localizado del rango superior y del inferior. Se verificó `ayq.vF` como escritura de cuatro bytes; no reutilizar el string u16 del chat. Pendiente verificar encoding de `BV.aS` y ejecutar encoder/consumidor nativos. Cambiar nombre usa `cpq` **12937** y cambiar emblema `cpp` **12575**. No se ejecutó una creación real.

La solución del servidor debe obtener fundador desde la sesión, validar nombre y emblema, y crear gremio/rangos/membresía del fundador junto con coste e ítem en una transacción con recibo idempotente. Un fallo intermedio no debe cobrar sin crear ni crear sin cobrar. No confiar en rangos enviados por cliente como permisos: contrastar sus etiquetas con reglas autoritativas. Los requisitos deben parametrizarse en DB y conservar compatibilidad con la UI instalada. Esquema final, respuesta y bootstrap aún por cotejar. Evidencia: `probe-creacion-contrato-nativo.json`.

## Emblema y encoding: prueba ejecutada

`BV.aS` usa explícitamente UTF-8; «Prueba ñ» produce 9 bytes, por lo que las longitudes de creación miden bytes, no caracteres. Se ejecutó una prueba con `eHs(short,short,short,short) → Sn() → eHs(long)` y se verificaron los cuatro getters para tres casos, incluidos cero y valores extremos signed. El caso `(1,2,3,4)` produce `281487861743620` y se identifica como forma 1, color de forma 2, símbolo 3 y color de símbolo 4. **Roundtrip no acredita emblemas válidos**: negativos/extremos son pruebas del formato, no opciones permitidas. Debe conservarse el i64 sin truncarlo a entero de 32 bits.

`eRA.tJ` aplica una lista de validadores registrados en runtime, y `eRo.tF` añade comprobación `Vb.dO`. No probar un registro vacío ni inventar una regex como reglas reales. Sigue pendiente rastrear registro/catálogos y límites de nombres. Evidencia ejecutada: `probe-emblema-y-utf8.json`.

## Validador registrado de nombres: prueba nativa

`eRz.aQc` registra `fHK()` en `eRA.b`, la lista utilizada por `tJ`, y construye `eRx(5,30,8,4,8,6,1,0,2,20)`. La longitud se valida mediante `String.length` (unidades UTF-16), después de caracteres admisibles. Se ejecutó `fHK().tH`: «Abcd» falla por corto; «Audit», «Audit Guild», «Audit-Guild» y «Audit Guild Name» pasan; «Audit123» y emoji fallan por carácter; 31 letras fallan por longitud y 30 vocales repetidas por composición. Un espacio inicial falla en el ejemplo, uno final pasa este validador. **No convertir esos ejemplos en una normalización inventada**: falta seguir `tC`, comprobación final `Vb.dO`, diccionarios y unicidad del servidor.

La solución debe separar longitud de bytes del paquete de longitud UTF-16 del nombre y replicar reglas acreditadas antes de cobrar; preservar errores específicos y la normalización/canonización para unicidad una vez cotejadas. La prueba no acredita disponibilidad ni crea un gremio. Véase `probe-validador-nombre.json`.

## Confirmación de creación y estado durable son contratos distintos

Se probó el decoder nativo `OK`, opcode **1000**, con «Audit Guild» y «Audit ñ»: ambos decodifican correctamente. Su cuerpo es longitud **byte signed** y nombre UTF-8; prefijo 128 provoca `NegativeArraySizeException` en el consumidor. No enviar longitud u16/i32 en esta respuesta ni confiar solo en el límite de caracteres para limitar bytes.

`chs` procesa 1000 mostrando `notification.guildCreateText` y cerrando el controlador `dbA`; esa rama **no hidrata identidad, miembros ni rangos del gremio**. Por ello emitir una notificación de éxito no demuestra creación ni persistencia: el servidor debe confirmar commit y enviar/restaurar además el estado nativo correspondiente. Se localizaron mensajes compartidos de grupos en `chs`, pero su discriminador debe cotejarse antes de asumir que pertenecen al gremio. Prueba y límites: `probe-confirmacion-creacion.json`.

## Identidad remota de gremio y separación respecto de parties

Se ejecutó `rV.aF/aG`: ID i64, emblema i64, nivel i16, longitud u16 y nombre UTF-8. El ejemplo gremio 456/nivel 3/«Audit Guild» ocupa 31 bytes y conserva todos los campos; instancia vacía ocupa 20. `bjC.zm` traslada ID, emblema, nombre y nivel al modelo `bla`. Esta sección acredita información remota visible, **no** miembros, rangos ni permisos.

El cotejo adicional identificó `bxI/fgq` y la rama 1184 de `chs` como **PARTY** (`group.party.inviting`, enum `fCz.PARTY`). No usarlos como roster de gremio por compartir handler con avisos de gremio. En servidor, `minimal_entity` vacía `GUILD_ID` y `GUILD_BLAZON`; `GUILD_REMOTE_INFO` no tiene rama de hidratación desde un gremio autoritativo. La propuesta debe contemplar identidad remota y estado privado de membresía por contratos separados, restablecidos desde DB al reconectar. Evidencia: `probe-informacion-remota-gremio.json`.
