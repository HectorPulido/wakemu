# Variantes de hijos de estados

El método original eZk.c consulta fyW.guW antes de comparar eVn.dd(1) con rHA. Si guW es false, ejecuta todos los hijos, con independencia de la variante normal/crítica del hechizo que aplicó el estado.

El estado3425, Gestión de Concentración, tiene guW=false y raíz159161 variante0. La autoridad emulada filtraba ese hijo durante los críticos, por heredar CRITICALS_ONLY del hechizo. La selección común usa ahora ALL dentro de esos contenedores. Para estados selectivos, usa rHA acreditado en Additional19 del carrier; si no está disponible, rechaza en lugar de deducirlo del hechizo exterior.

ProbeNativeStateVariantSelection.java verifica con objetos fyW/eVn originales3425/3442/8913; todos guW=false y aceptan sus raíces normales durante crítico. El catálogo exhaustivo ExportStateDecurseRules ya exporta los IDs guW=true.

Validación: dos pruebas de autoridad y doce casts reales4780/4783/4778 a niveles20/200, normales/críticos. Concentración3442 aumenta en las doce variantes y Sacudido8913 se aplica en ambas variantes de4780. El objetivo es el monstruo4085 nivel23 con530HP nativos; sobrevive y recibe daño. El combate original se conserva después de preparar cada transacción. Estos resultados son offline; no certifican presentación en GUI.

La entrega12613 de carriers se revierte por regresión observada en GUI, coordinada por raíz. Este cambio de selección de variantes es independiente del opcode de entrega.
