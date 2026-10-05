# Solución propuesta — 2

Transformar un monstruo joven en su etapa adulta según una política documentada por familia.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Identificar familia y etapas

Extraer del catálogo las referencias de bebé tofu y adultos compatibles; agrupar escalones por nivel mínimo dentro de la familia e ignorar sexo, como indicó el usuario. monster_growth_member elige una referencia por nivel mínimo, pero ese orden no acredita una cadena de edad. Evaluar probabilidades decrecientes por escalón en intervalos constantes configurables; una evaluación puede mantener la forma actual. Separar explícitamente las variantes de jefe con probabilidad extraordinariamente baja.

## 2. Definir el reloj de maduración

Persistir etapa, tiempo activo acumulado o próxima transición y versión del miembro. Alinear con el requisito de zonas vacías del 20: pausar cuando no haya jugadores, sin procesar maduración durante la ausencia. Separar el temporizador de la semilla que crea el grupo del ciclo de vida del NPC ya creado.

## 3. Programar por zona activa

Indexar miembros con transición pendiente y procesar únicamente zonas/instancias activas. Seleccionar transiciones vencidas con reloj controlable; no barrer todo el catálogo por tick. Al salir último jugador guardar el tiempo restante y quitar la zona del scheduler.

## 4. Aplicar transformación segura

Reservar el miembro y validar que no está muerto, combatiente o recolectado. Cambiar referencia/etapa/stats de forma atómica, conservando identidad coherente del grupo; recalcular HP según regla acordada. Si está en combate, deferir y volver a validar al terminar para no mutar el snapshot del encuentro.

## 5. Sincronizar forma y recuperación

Emitir el mensaje nativo de actualización/recreación demostrado por parser; no adivinar un opcode. Guardar outbox y revisión para que repetir el tick no produzca dos adultos ni cambie el UID de manera incoherente. Bootstrap y actualizaciones deben representar la misma etapa.

## 6. Migrar y aceptar

Definir etapa inicial de los NPC antiguos solo con referencias verificadas. Migrar una copia y comparar población; ningún spawn adicional es una maduración. Probar reloj, reconexión y recovery con tiempo restante; documentar cuándo una especie no tiene etapa adulta conocida.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Madurar no añade población; un miembro solo atraviesa transiciones legales de su familia.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
