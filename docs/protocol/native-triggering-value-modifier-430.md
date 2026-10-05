# Familia430: modificación del runner desencadenante

Auditoría del cliente instalado, 2026-10-05. No implementación ni validación gráfica acreditadas todavía. El inventario enlaza esta familia con84 hechizos por sus grafos potenciales; esa cifra no prueba que84 lanzamientos la ejecuten.

El prototipo eZL lee tres parámetros durante C: modo entero, valor entero aSg y replace booleano. En c, si existe Qe desencadenante y el modo es no negativo, llama Qe.a(mode, float(value), replace). Finalmente llama mu(true). No modifica directamente estadísticas del personaje.

Qe.a(int,float,boolean) base es una operación vacía. Entre159 clases de runner distintas de los318 prototipos exportados, cinco declaran overrides: eWN,eWO,eWu,eXs,eXt. Se requiere resolver herencia para todos los prototipos antes de usar esta lista como política.

Los contratos difieren: eXt(daño) admite modos0/1 para aSg y5/6 para camposrDy/rDz; usa UP.bt en varios caminos y clamp final no negativo. eXs(curación) emplea truncamiento o floor según replace, y no comparte todas las reglas de daño. eWu(estado) admite modos4/7 sobre nivel short rBo y reconstruye identidad fyW.ae. eWN/eWO admiten0/1 y pueden ejecutar fRS cuando el importe acaba en cero. Un único modificador porcentual genérico no puede sustituir estas diferencias.

Siguiente trabajo común: acreditar identidad y vida del runner fuente durante fases; resolver propietarios de override por herencia; probar aritmética original, orden respecto a cálculo/criterios/consumo y reset al clonar. Integrar después un callback del runner actual, sin escribir actor.stats ni inferir el valor desde paquetes. Mantener desconocidos explícitos donde falte contrato.

Evidencia reproducible: javap sobre eZL,eYC,Qe y eWN,eWO,eWu,eXs,eXt; salidas de trabajo en .runtime/local/common-families430-345.txt, common-Qe-parameter-modifier.txt, common-runner-method-declarations.txt y common-source-value-modifiers.txt.

Actualización de evidencia: el probe `ProbeNativeTriggerValue430` ejecutó ocho contratos originales de daño y curación: PASS. La reflexión de todos318 prototipos acredita propietarios de método heredado: Qe177, eWW111, eWO8, eWN6, eXt7, eXs7, eWu2. Esto corrige la lista de declaraciones directas anterior: eWW es un propietario adicional imprescindible y comparte sus reglas con eWN/eWO, incluidos efectos de características y armadura. El listado exhaustivo está provisionalmente en .runtime/local/native-trigger-value-owners.json; no se ha conectado ningún manejador430.

Exportación reproducible añadida: `python3 server/tools/export_trigger_value_owners.py --output .runtime/local/native-trigger-value-owners-repro.json`. Resultado318 prototipos/159 clases, idéntico al listado inicial. Probe original ampliado a12 casos incluye armadura heredando eWW: percent-replace es no-op, value-add permite importe negativo, a diferencia del clamp del daño. Aún pendiente integrar430 en el runtime.

Avance de implementación: `combat_trigger_value_modifier.py` implementa aritmética de importe por propietario (daño, cura, eWW/eWN/eWO y no-opQe), con float32, overflow, truncamiento, floor y redondeo probabilístico diferenciados. Tres pruebas pasan, incluidos diez casos correspondientes al probe original y separación estocástica/determinista. Registro de propietarios exportado a server/protocol/native-trigger-value-owners.json. El módulo aún no está conectado a eventos ni existe manejador430; estado y campos auxiliares del daño siguen rechazados explícitamente. No se declara familia soportada.

Checkpoint posterior: handler430 registrado y controladores vivos conectados en armadura, daño, cura, recursos48/55 y estado304. El controlador eWu separa nivel corto del amount.59 pruebas comunes PASS y11 pruebas estado/pipeline PASS. La definición original350672 se ejecuta dentro del dispatcher con fuente de replay real; la selección se inyecta en esa prueba, por lo que no acredita suscripción natural de armadura. Características y auxiliares5/6 pendientes; sin despliegue ni validación gráfica. Las afirmaciones anteriores de ausencia de handler describen checkpoints históricos.

Modos5/6 de eXt integrados posteriormente: asignan rDy/rDz mediante UP.bt sin consultar replace; amount sólo se clampa. rDy→fas.Th→fau.rKC participa en fSI (maestría), rDz→fas.Ti→fau.rKr participa en fSD (resistencia). La máscara1/2 gobierna respectivamente ambas contribuciones. Probe original confirma sustitución y signo;29 pruebas comunes pasan. No acredita todavía activación natural de todas las pasivas ni sincronización gráfica.
