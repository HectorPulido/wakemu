Familia447: propiedad de combate (eWt)

Historial inicial de auditoría. Las afirmaciones iniciales se corrigen explícitamente en el checkpoint de implementación al final; no deben usarse como especificación actual.

C evalúa parámetro0 al nivel de ejecución y lo almacena en aSg. c sólo acepta objetivo eGj y enum ffe.Ua reconocido; ausencia, otro tipo o ID desconocido marca mu(true). Aplica PV.f(propiedad), y bbR retira mediante PV.g(propiedad). Hace falta preservar el contador de propiedades del actor; un simple set que borre una propiedad compartida entre dos efectos no reproduce necesariamente el nativo.

Ramas adicionales, no omitir al implementar: seh con pelea elimina del timeline via fem.rE; sdH recalcula SU.bhM; seb fija PA(AP) al mínimo mediante aZg; see fija PA(MP) al mínimo mediante aZg; sdV notifica listeners PA(WP).aZk. sdC/sdO actualizan ocupación QI.d para QK; al retirar restauran coordenadas y dirección capturadas si existen, y QI.c/e. b(iP) sólo agrega datos de posición/dirección para estas dos últimas propiedades.

bbz=false,bbA=true,bbB=false. La integración requiere central ownership, paquete eWt y retirada coherente, incluyendo ramificaciones de congelación/timeline/ocupación. Evidencia .runtime/local/native-fight-property447-current.txt. No se marca soportado ni probado en GUI por esta auditoría.

ProbeNativeFightPropertyStack ejecuta PB/eHN reales: dos aplicaciones conservan propiedad tras retirar una; retirando ambas desaparece; retirar ausente devuelve0. Contador nativo signedbyte:127+1=-128 sigue activo por ser distinto0; retirarlo produce127. Probe PASS. Este contrato evita borrar una propiedad compartida por varias pasivas.

Contador reutilizable implementado en combat_property_stack.py y tres pruebas aprobadas, basadas en el probe nativo PB/eHN. Valida claves PE.aKg y valores byte firmados; no trata datos desconocidos como población vacía. El manejador447, su integración con actores y los paquetes aún están pendientes: este módulo por sí solo no habilita hechizos.

ProbeNativeFightPropertyCodec PASS: paquete13497 producido por el encoder común del servidor, familia447, UID903/ref348444/propiedad11, caster7/target-7. El eWt original decodifica correctamente identidad y valor sin AdditionalDatas de posición. Esta prueba acredita el formato de propiedades ordinarias; no acredita todavía ramas sdC/sdO ni integración del manejador. Compilar probe con --release21 para el JRE del cliente.

Registro extraído del enum original: server/protocol/native-fight-properties.json contiene120 IDs únicos, sus nombres originales y categoría. Ramas especiales de eWt: INVISIBLE5 e INVISIBLE_SUPERIOR18 ocupación/restauración, HASTE10 recalcula timeline, STASIS_3 25 notifica listeners WP, GROGGY_3 31 fija AP al mínimo, CRIPPLED_3 34 fija MP al mínimo, EXTRA_TURN37 retira timeline. Los símbolos javap sdC/etc no son nombres de producto; ExportFightProperties obtiene Enum.name() real. No convertir estos IDs en heurísticas por hechizo.

Corrección acreditada por ProbeNativePropertyResources PASS: PA.aZg asigna el mínimo actual, no cambia la mutabilidad del recurso. Después on(4) conserva4. PA.aZk itera PD.a(PA), no reinicia directamente WP; con listener real notifica una vez y conserva6. Constructor fff(0,10) fija límites absolutos; hay que inicializar máximo mediante or(10) antes de comprobar cambios. No implementar congelación permanente ni WP=0 basándose en estos métodos.


Checkpoint de implementación común (4 de octubre de 2026)

El manejador NativeFightPropertyHandler está registrado para 447 y conserva contadores byte firmados, UID/caster, duración, ownership y retirada 13560. El formato ordinario 13497 fue decodificado por eWt original. La población inicial se obtiene de los fsp instalados: eGj.d(eGH) reinicia cada propiedad reconocida y añade una unidad; no se infieren contadores a partir de un set de propiedades actuales.

Correcciones a las notas históricas: EXTRA_TURN37 inserta el actor en la ronda actual, inmediatamente después del cursor CURRENT_FIGHTER; no lo retira. Tc.bhP/feq.b restablecen la lista base al terminar la ronda. HASTE10 no modifica el orden bajo la política feq acreditada. GROGGY_3/CRIPPLED_3 asignan el mínimo actual de PA/PM una sola vez; retirar la propiedad no restaura recursos. ProbeNativePropertyTimeline y ProbeNativePropertyResources ejecutan estas rutas originales y pasan.

INVISIBLE5/INVISIBLE_SUPERIOR18 añaden la afiliación a QI.biO, el conjunto que excluye bloqueadores de línea de visión. No eliminan el footprint del actor. QI.c/e al retirar eliminan la afiliación de los conjuntos de movimiento y LOS, sin contar aplicaciones superpuestas. El paquete AdditionalDatas contiene posición15, dirección16 y ejecución33. ProbeNativePropertyVisibilityCodec decodifica esos campos en eWt.ds original. La retirada serializa posición/dirección actuales: reutilizar la posición del paquete de creación provocaría un retorno incorrecto a la casilla antigua. Las consultas LOS del servidor respetan el conjunto de afiliaciones explícito.

STASIS_3 25 notifica observadores WP, no cambia su valor. ProbeNativeFreshPropertyListeners construye biB(false) original y confirma sus observadores WP [bkq,biB], ambos de interfaz. La rama de personaje recién instalado acredita además ausencia de enlaces numéricos propios; registra la notificación sin emitir un evento Qf inventado y sin resetear WP. NPC sin inicialización acreditada u observadores numéricos eWr/eXb rechazan esta rama antes de mutar. El protocolo 447 hace que los observadores de interfaz reales del cliente reaccionen.

Última suite focal de módulos: 22 pruebas aprobadas (propiedades, snapshot de actor y FSM), incluidas superposición/retirada, PA/PM, turno adicional, posición actual e invariancia WP. Focal anterior de catálogo: 18 casos, 16 cambios autoritativos y 2 rechazos posteriores por RESISTANCE_CAP; hashes estables en ese checkpoint y rollback de todos los originales. Esta comprobación es offline y no acredita funcionamiento GUI ni cobertura completa.

Límites explícitos: clones de eventos de 447, observadores numéricos WP no acreditados y combinación de inserción de invocaciones con turno adicional necesitan autoridad propia. Se rechazan; no se sustituyen por no-op. Por tanto, la familia todavía no se declara completa para todo contexto nativo.


Actualización posterior: se retiró el rechazo transitorio de invocación nueva después de un turno adicional. Tc.a(long,short,SQ) calcula pw(slot), número de IDs duplicados antes de la inserción; SX.n/feq.b insertan en la lista base a slot-pw y SX.m/feq.a en la ronda a slot. ProbeNativePropertyTimeline original prueba ronda [7,-7,7,8], inserción901 después del cursor2, base [7,-7,901,8] y supervivencia901 tras bhP. RegisteredSummonAuthority mantiene ambas listas y valida multiplicidades, sin convertir la ronda en set. Prueba del FSM Python atraviesa los turnos y confirma que la invocación sigue en la ronda siguiente. 27 pruebas summon/propiedades/FSM pasan; 12 pruebas específicas de invocaciones pasan tras añadir el recorrido de ronda. Aplicar EXTRA_TURN a un roster que ya contiene invocaciones sigue requiriendo acreditación del callback especial; no se declara resuelto por la inserción inversa.
