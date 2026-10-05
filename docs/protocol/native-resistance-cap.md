RESISTANCE_CAP: pila nativa de efectos eWR

Fuente: eWR.C(Qe), eWR.d(PA), eWR.fNM() y eWW.a(PA,int), bytecode original del cliente instalado. Registry effect-characteristic-registry.json selecciona esta política únicamente para familias90/92/93/94/95, todas eWR. No es un límite general de resistencias ni una suma por referencia de hechizo.

Aplicación: después de eWW.C, eWR.C suma aSg propio más valores actuales de runners con el mismo Qe.d y cYh()==0 del Qf del objetivo. Si total>=200, reemplaza aSg por max(0,requested-(total-200)). Esto precede la conversión porcentual y PA.oo. eWW.Mt/rCB conserva el requested original previo al límite/porcentaje. eWR.d guarda el delta real aplicado y establece fc(0). Los cálculos enteros de la pila conservan overflow int32.

Retirada: Qf.dl elimina primero el runner de su LinkedHashMap; eWR.fNM restaura su delta mediante PA.nG y llama eWW.a(PA,200). La capacidad es200-abs(PA.aYS()). Recorre los eWR restantes del mismo Qe.d/status0 en orden de aplicación. Para cada requested distinto del delta, asigna min(capacidad,requested-actual), invoca PA.oo y aumenta aSg por el importe asignado. Importante: el incremento guardado es el importe asignado aunque PA.oo lo limite o el recurso esté congelado. No sustituirlo por delta efectivo de la característica.

El módulo combat_resistance_stack.py planifica esta redistribución antes de mutar, conserva UID/caster/clocks y sustituye únicamente el valor protobuf4 del runner restante. Su AdditionalDatas25 conserva requested. NativeStatHandler aplica el plan a la característica y al ledger antes de retirar el UID original. Se emite únicamente13560: el cliente realiza la misma redistribución al retirar; no se fabrican aplicaciones extra13497.

ProbeNativeResistanceCap ejecuta eWR.C/d/fNM originales, PA real y Qf con su LinkedHashMap. Resultado PASS: requested150+100 produce actual150+50 y resistencia-200; retirando150 el runner restante pasa a actual100 y resistencia-100; retirando el restante vuelve a0. Pruebas Python:19 aprobadas entre stack/handler/arithmetic, incluido roundtrip del payload y retirada final. El test sin bounds explícitos sigue rechazando antes de mutación.

Pendiente de la siguiente validación: combinación con transferencia de valor eVt, que ocurre después de C nativo; la ruta previa del handler aplicaba ese override demasiado pronto respecto al límite. Este orden necesita ajuste coordinado con los callbacks865. No se atribuye validación GUI ni auditoría focal de catálogo a estas pruebas unitarias.


Orden de transferencia corregido y verificado por el probe original: eZR.n llama C y después eVt.SQ. Con un runner150 existente, C limita requested100 a50; SQ100 sustituye después50 por100 y PA llega a-250, sin segunda limitación. Mt conserva100. El handler conserva también requested30 cuando SQ5 fuerza el delta5 de una característica ordinaria. El guard de valor nulo se evalúa después de C/override. 23 pruebas stack/stat/callbacks/transferencia pasan, incluyendo las cinco acciones90/92/93/94/95 y retirada íntegra. La focal del catálogo queda pendiente.


Focal de catálogo terminada sobre producción offline: .runtime/local/resistance-cap-focal.json contiene18/18 actor_state_changed, sources_stable=true y rollback18/18. Antes eran16 cambios y2rechazos por RESISTANCE_CAP. Casos de clases diversas, mismos targets/niveles legales del checkpoint447 anterior; la comparación usa la entrada común del servidor, no un efecto aislado. No se reinició el mundo ni se operó el cliente del usuario. Este resultado acredita ejecución transaccional de los casos auditados; no juego real.
