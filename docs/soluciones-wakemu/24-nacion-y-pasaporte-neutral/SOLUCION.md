# Solución propuesta — 24

Publicar estado nacional neutral y propio del personaje hasta que exista una mecánica nacional; no fabricar ni heredar alineamiento territorial.

El reemplazo de la sección de pasaporte indicada abajo ya está aplicado en fuente. El resto de este plan identifica verificación pendiente, no una afirmación de neutralidad territorial implementada.

## 1. Identificar cada superficie

`/passport` es un comando de UI, no un objeto de inventario: `PassportCommand` abre `passportDialog`, que enlaza `pvpLadderEntry` con el modelo de la nación del personaje. El selector y el estado público de nación son superficies separadas; la ubicación del mapa no es ciudadanía.

## 2. Localizar carriers heredados

El serializador sustituye `NATION_ID` por i32 0 y `PASSEPORT_INFO` por su default nativo de un byte `00`; la sincronización nacional se normaliza por separado. No reemplazar toda aparición de un ID nacional en buffers. Los catálogos de región inspeccionados mapean geografía, no una nación propietaria verificable.

## 3. Modelar neutralidad explícita

El valor de personaje 0 está acreditado como `Neutral` por el parser nativo qZ y el locale. No se encontró un status de “sin nación” para lugares en las fuentes mapa/territorio inspeccionadas. No asignarles 0 hasta identificar su carrier y consumidor.

## 4. Sustituir cada sección por estado propio

El bootstrap/selección actual debe conservar estos defaults propios; falta aceptación visual de selector/pasaporte tras reentrada. La adaptación de `15984` normaliza solo el estado público nacional reconocido; no declara neutral a cada mapa, NPC, nombre geográfico ni titular de territorio.

## 5. Verificar reload y futuras naciones

Probar dos cuentas en regiones con nación distinta de catálogo, reconnect y transición de mapa. Cuando se implemente ciudadanía, la misma autoridad debe poder activar nación real sin mantener hardcode neutral en ramas ocultas.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Ni personaje ni lugar reciben alineamiento de otra cuenta o captura; neutralidad es explícita y consistente.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
