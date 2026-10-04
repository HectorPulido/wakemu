Análisis del protocolo del cliente local Wakfu 1.93.2

La instancia de juego usada para el experimento está cerrada. La captura empezó antes de la autenticación y terminó con capture_stop. Se reconstruyeron 1.158 mensajes recibidos y 26 enviados al dispatcher y Rubilax, con 57 identificadores de entrada y 16 de salida. No quedaron fragmentos incompletos.

La captura recoge observaciones del pipeline Netty. Para evitar duplicados, el decodificador usa únicamente aCl#0 para entrada y SslHandler#0 para salida del dispatcher/servidor. Esos puntos contienen bytes en claro después/antes de TLS. El chat externo, HTTP/HAAPI y Thrift del launcher quedan fuera del análisis principal. La captura original sí contiene las observaciones Netty del chat externo.

Qué se entregó:
- actions.txt: diccionario legible de acciones y mensajes observados o encontrados en el código.
- actions.json: mismo diccionario con id, dirección, formato, evidencia y estado de validación.
- catalog.json: 998 clases de mensajes de red Nt/Nx con identificador constante, campos propios/heredados, llamadas del codec y referencias de uso. Se descartaron 74 candidatos que eran mensajes internos de UI. No es un catálogo exhaustivo de identificadores dinámicos o heredados.
- descriptors.pb: FileDescriptorSet con 48 archivos Protobuf y 220 tipos, incluidos tipos anidados. Se extrajeron descriptores de 204 clases generadas, sin errores.
- descriptors.json: procedencia y nombres de esos archivos.
- wakbox-comparison.txt/json: comparación con el commit fijado de WakBox-Evolution.

Estados del diccionario:
observed_and_source: presente en la captura y con estructura corroborada en el JAR. El nombre puede conservar una semántica pendiente explícita.
observed_unresolved: presente, pero sin significado funcional completo.
source_only_unvalidated: encontrado en código; no se ejecutó durante esta sesión.

Cabecera de aplicación, orden big endian:
Cliente -> servidor: u32 longitud_total, u8 route, u16 opcode, payload. Cabecera de 7 bytes.
Servidor -> cliente: u32 longitud_total, u16 opcode, payload. Cabecera de 6 bytes.
La longitud incluye la cabecera. La reagrupación se hace por canal y sentido: un registro de captura puede contener parte de un mensaje o varios mensajes.
El byte route no es el identificador de acción. En esta sesión se observaron 8 para dispatcher, 1 para autenticación world, 2 para selección de personajes, 3 para acciones de mundo, 4 para solicitudes auxiliares y 6 para solicitudes adicionales. Son asociaciones observadas, no una tabla universal confirmada.

Movimiento fuera de combate, opcode 13331, clase cnl:
i32 movement_mode
 i32 start_x
 i32 start_y
 i16 start_z
 u8 step_count
 u8 packed_step[step_count]

Cada paso: direction = packed_step >> 5; dz = packed_step & 31, con extensión de signo de 5 bits (-16..15).
Direcciones extraídas de aAS:
0 EAST         dx=+1 dy=-1
1 SOUTH_EAST   dx=+1 dy= 0
2 SOUTH        dx=+1 dy=+1
3 SOUTH_WEST   dx= 0 dy=+1
4 WEST         dx=-1 dy=+1
5 NORTH_WEST   dx=-1 dy= 0
6 NORTH        dx=-1 dy=-1
7 NORTH_EAST   dx= 0 dy=-1

Modo 0=WALK, 1=RUN. El catálogo incluye los restantes modos del enum ada.
La solicitud medida de Pekebu contiene inicio (-13,-8,-1), modo RUN y dos pasos NORTH_WEST con dz=0. Su destino calculado es (-15,-8,-1), igual a la posición leída en el cliente después del clic. La captura contiene cuatro solicitudes de movimiento; solo la última tuvo medición directa antes/después.

Actualización de posición, opcode 13530, clase csQ:
i64 actor_id, i32 x, i32 y, i16 z, u8 direction, i32 movement_mode.
El opcode 13046 (csZ) lleva estado serializado de un actor; no debe confundirse con un mensaje de movimiento.

Resultados de verificación:
- Todos los 1.158 mensajes recibidos se procesaron con las clases del JAR sin excepciones; los conteos por clase coinciden con los objetos observados en el cliente activo.
- dp() devuelve true en 1.136 mensajes y false en 22. En esas cuatro clases el false es explícito aunque se hayan leído/guardado campos; el dispatcher del cliente ignora ese retorno. Esto no demuestra que todo bloque interno esté interpretado.
- 878 mensajes de posición/estado/chat tienen campos coincidentes entre el lector Python independiente y el lector Java del cliente.
- 23 de los 26 mensajes enviados se reconstruyeron con los serializadores reales del JAR y coinciden byte por byte. Los tres restantes son solicitudes de opcode 649 con tipos 3,6,10: su semántica/clase aún está pendiente.
- El inicio y destino calculados del último movimiento coinciden con las dos mediciones directas de Pekebu.

Los bloques serializados de personaje, inventario, estado y algunos contenedores aún contienen bytes opacos. Extraer un campo binario no equivale a conocer su formato interno. Chat de salida y combate están documentados por lectura de código y permanecen sin validar en juego.

Reproducción del análisis, sin iniciar el cliente ni abrir conexiones:
./decode-session.sh .runtime/captures/2026-10-03T03-40-46.413625Z-fe2520f4
python3 compare-wakbox.py

El primer comando recompila las herramientas de análisis con el JDK 22 instalado, vuelve a extraer el catálogo y los descriptores, reconstruye mensajes y verifica los serializadores. El segundo necesita la copia de referencia en .runtime/reference/WakBox-Evolution y Python protobuf.
Los datos decodificados específicos de la cuenta permanecen en .runtime/captures/.../decoded/. El diccionario y la comparación describen formatos sin copiar tickets o credenciales de la sesión.

JAR fijado por SHA-256:
e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd
