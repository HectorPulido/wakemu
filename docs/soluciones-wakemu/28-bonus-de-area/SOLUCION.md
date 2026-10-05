# Solución propuesta — 28

Aplicar y retirar bonus territoriales una vez y desde fuentes verificadas.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Inventariar origen de cada bonus

Capturar área, miembro de clan/condición, descripción y estadística concreta. zone_challenges desactivado no acredita bonus territorial ausente; separar satisfacción ecológica, ciudadanía, clima y eventos. Neutralidad nacional 24 puede inhabilitar bonus de alineamiento.

## 2. Modelar condiciones por revisión

Definición versionada con fuente, alcance, requisitos, efecto, stacking y expiración. Evaluar población/clima/nación autoritativos; ninguna condición debe salir de una captura de otra cuenta. Guardar o derivar estado territorial de forma reproducible.

## 3. Introducir modificadores nombrados

Usar clave source_type/source_id/zone_revision en un resolver canónico de stats. Entrar sustituye fuente, salir la elimina; no sumar deltas sobre stats efectivas. Incluir bonus en combate solo según política de snapshot/dinámico documentada.

## 4. Sincronizar cambios de zona/condición

Entrada, salida, frontera, satisfacción alterada y reconnect recalculan una vez. Update a presentes muestra icono/texto y características del mismo efecto. Un cambio de build mantiene el modifier zonal sin duplicarlo.

## 5. Validar matemática y lifecycle

Comparar baseline→zona→fuera→zona y varios reconnects. Probar bonus condicional con neutralidad 24, varios efectos y cambio durante combate. Persistir provenance y trace de cálculo para separar fallo de 17 de bonus duplicados.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Cada fuente contribuye una vez; salir o perder condición restaura baseline sin drifts.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
