# Solución propuesta — 22

Completar propiedades por unidad, identificación, selección elemental, engastes, reciclaje y sublimaciones con efectos reales.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Separar subfunciones y versiones

El signo? reportado no prueba qué propiedad está ausente. Inventariar estado de identificación, máscaras de dominio/resistencia, número/colores/orden de sockets, efectos/niveles, cargas y sublimaciones. El checkout actual ya añade elementos por concesión y los codecs; la instancia fija anterior no los contiene. Conservar fuentes/hash y no declarar desaparición gráfica de? por un probe offline.

## 2. Especificar estado por UID y migration

Proponer item_instance con reference/quantity, identified, máscaras, sockets ordenados, cargas, inversiones, sublimaciones y revisión. Propiedades de unidades diferentes impiden fusionarlas por referencia solamente. Para legacy sin propiedades decidir identificado/pendiente y generación una sola vez con recibo; no rellenar todos con la misma selección ni rerollear al cargar.

## 3. Capturar identificación y reasignación

Identificar dobleclic/selector/cancelación/reasignación por protocolos nativos. Autorizar UID propio y nivel/tipo; dividir una unidad si el stack pasa a ser individual. Validar número de elementos disponibles, selections únicas y flags. RNG de sockets se confirma una vez; selección manual no se reemplaza silenciosamente por azar del concesión actual.

## 4. Implementar efectos de sockets

Extraer catálogo de efectos, costos por nivel, límites por nivel del objeto, colores/orden y bonus según slot. Resolver forma/color del cuarto tipo y cifras del contexto con datos de la versión: no asumir 90% reembolso ni 7 cargas sin prueba. Aplicar efectos a la evaluación canónica desde el UID, manteniendo condiciones/running-effects que requieran combate.

## 5. Reciclar y sacrificar atómicamente

Destroy actual solo elimina: reciclar calcula esquirlas/polvos, consume y entrega con recibo; taller consume unidad idéntica y añade cargas según catálogo. Validar item ligado/equipado/reservado y espacio de resultado. Un fallo tras consumo recupera recibo, no quita otro item. Documentar RNG/probabilidades y éxito garantizado solo si están acreditados.

## 6. Añadir/retirar efectos y sublimaciones

Consumir esquirlas o pergamino junto con actualización de inversión/sockets y revisión. Retirada devuelve cantidad según regla/redondeo verificados; las mismas esquirlas no se reclaman dos veces. Sublimación valida orden y comodines, slots requeridos, compatibilidad y límite; no confundir scroll reconocido con efecto runtime implementado.

## 7. Sincronizar todas las representaciones

Probar kX/le protobuf, item_form/vj opciones, inventario físico, registro equipo, tooltip y sheet activa. Campo 56/tag 450 transmite elementos actuales; no basta agregar un byte identified ficticio. Actualización del item equipado recalcula bonus sin duplicar preview ni curar gratis; todas las builds que referencian ese UID ven mismas propiedades.

## 8. Recovery y aceptación integral

Recibos/versiones protegen cada identificación, reciclaje, taller y reembolso; Redis/SQL representan las mismas propiedades tras flush. Comparar fuente/UID antes y después en UI y combate. Probar reconnect antes/después del ACK, stack, transferencia, equipo compartido y legacy; ninguna combinación está cubierta completamente por los tres tests de elementos actuales.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Propiedades pertenecen a una unidad; reintento no vuelve a sortear; consumo/reembolso y modificación se confirman juntos.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.

## Contratos nativos resueltos tras las respuestas

[13787, 12487, 13766 y la condición de engastes sin identificar](REVISION-RESPUESTAS.md).
