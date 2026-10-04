# IN 13256: limpieza del contexto de mundo

La clase `ctB` representa una señal con cuerpo vacío, no una respuesta sin efecto. El despachador `ciu.b(aAa)` usa el opcode numérico: su caso 13256, offset 1102, obtiene el jugador local; si existe combate actual, elimina su registro con `aUb.Ae` y ejecuta `bvU.bGG`, que limpia combate, timeline y propiedades de interfaz. Después ejecuta `ciu.ad` (cierre condicionado de diálogos de merkamundo) y `ciu.a` (limpieza de caches cdE/deK/aGZ, refresco del jugador y evento local bty).

La búsqueda anterior de referencias tipadas a ctB no encontraba este handler porque despacha por entero. Un escaneo ASM de constantes/switches encontró únicamente ctB.d, cgD.oh y ciu.b para 13256. No se atribuye nombre oficial al paquete: “limpieza de contexto” describe las mutaciones observadas.

`Verify13256` ejecutado contra los JAR locales confirmó opcode 13256, aceptación de cero bytes y rechazo de un byte. Evidencia: `.runtime/local/ctB-handler-ciu.txt`, `ctB-bvU.txt`, `ctB-factory-audit.txt` y `Verify13256.java`. La auditoría JSON conserva el resultado anterior en review_history y hashes de los bytecodes revisados. No se enviaron solicitudes oficiales ni se modificó o reinició el servidor. El callback completo de interfaz no se ejecutó fuera del cliente gráfico; sus efectos se verificaron por lectura de Java.

Auditoría adicional: `bty.d()` utiliza `btX.jlW`, cuyo nombre nativo es `LEAVE_INSTANCE`. Los métodos `bjo.dsQ/dsR` llamados desde el reset eliminan referencias bLM de objetos visuales, no inventarios o equipo.
