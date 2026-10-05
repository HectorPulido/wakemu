# Familia 430: mutación del aplicador de estados eWu

Auditoría del cliente instalado, 5 de octubre de 2026. Esta evidencia describe
el consumidor eWu de la modificación de un efecto desencadenante; no demuestra
todavía la integración del controlador en una transacción de juego.

## Contrato original

`eWu.a(mode, value, replace)` modifica únicamente los modos 4 y 7. El nivel
pendiente `rBo` y la copia `rBp` son `short`; la referencia es `kFB` y el valor
empaquetado es `rBn`. La cantidad heredada `Qe.aSg/getValue()` permanece intacta.

- Modo 4: reemplazo mediante conversión Java float→int→short, o suma float32
  del nivel y valor seguida de esas conversiones. Trunca hacia cero y envuelve
  el short; no usa RNG.
- Modo 7: calcula float32(float32(nivel × valor) / 100), redondea mediante
  `UP.bt(float)` y reemplaza o suma el resultado, envolviendo el short.
- Otros modos no cambian estos campos.

Después de modificar, ambos caminos reconstruyen `fyW.ae(reference, level)`
y copian el nivel a `rBp`. `ae` empaqueta `(reference << 16) + (level & 65535)`.
No aplican el máximo del estado en este momento. `fyW.cu(requested)` limita
el nivel efectivo por arriba con `min(requested, max)`, pero conserva el nivel
solicitado original en el valor empaquetado. Tampoco impone mínimo cero.

## Orden y notificaciones

`eWu.C` vuelve a calcular referencia y nivel desde los parámetros nativos,
y reconstruye los tres campos. Una modificación previa a C puede perderse.
`eZR.n` ejecuta C, después los callbacks `eVt/eVz.i`, y después la transferencia
SQ a la cantidad Qe. Esa transferencia no sustituye el contrato del nivel.

Los dos caminos Qe tienen órdenes diferentes:

- Ordinario: `Qe.g(PV)` delega en `Qe.d(Collection)`. L1 precede a `n/C`.
- Replay: `Qe.k(Qe)` ejecuta `n/C`, después L1/L2 y después la aplicación.
  `Qe.g(Qe)` adjunta la fuente; no es el ejecutor de replay.

En la aplicación de eWu, `fMY` combina niveles con los estados anteriores,
con conversión short, y `aS` retira los carriers sustituidos. La notificación
`d(source, flag)` precede a `D(source)`, que crea y aplica el nuevo eZk.
La fase final de Qe emite L3/L4 después de la aplicación.

`fRS()` solamente activa `rIW`, suprimiendo la notificación PR repetida.
No recalcula el nivel, no elimina el estado y no aplica un cap. `eZR.a`
restablece ese indicador antes de la fase final L3/L4.

## Propuesta de integración

El controlador efímero debe conservar dos contratos separados: `value` para
Qe.amount y campos de nivel pendiente/reference/packed/seed para eWu. No debe
copiar el nivel a `NativeRunnerAmount.value` ni modificar directamente el
ledger de un carrier ya aplicado.

El handler de estado debe sembrar esos campos en su fase C, exponer el mismo
controlador al observador de la fuente, y consumir el nivel pendiente al entrar
en su camino común de combinación y aplicación. Los modos 4/7 usan el RNG de
la misma transacción. La posición de L1 respecto a C debe conservarse según
ejecución ordinaria o replay. La retirada, el caster, los UID y los clocks
continúan bajo el handler común; no se necesita un efecto 304 sintético.

## Verificación reproducible y límites

`sniffer/java/ProbeNativeStateTriggerValue430.java` ejecuta las clases eWu,
fyW y eZR originales. Resultado: **49 comprobaciones PASS**, incluidos wrap,
truncamiento, límites estocásticos, C que resembra, callback posterior a C,
nivel efectivo frente a empaquetado y supresión de notificación. Salida:
`.runtime/local/native-state-trigger-value430.txt`.

```sh
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ProbeNativeStateTriggerValue430.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -Xmx128m -cp '.runtime/local/classes:client/lib/*' ProbeNativeStateTriggerValue430
```

El probe usa proxies de definición/entorno para aislar esos métodos y no carga
assets de juego. No comprueba el merge completo de eZk, paquetes, activación
de un hechizo real ni presentación gráfica. El orden completo se acredita
con los bytecodes `native-Qe-current.txt`, `native-eZR-current.txt` y
`current-eWu.txt` en `.runtime/local`, no mediante una simulación de combate.
