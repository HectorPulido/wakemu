# Contrato nativo de logros

Fuentes: `oN`, `bjs.zm`, `bdM.dT`, `ctp–cty`, `cED–cEM`, `cnI–cnK`, `biW`, `cYA`. Big-endian. Los tamaños siguientes son **cuerpos de mensaje**, no incluyen framing/transporte.

## Restauración al entrar al mundo

`oN` contiene `u 16 longitud`, blob de esa longitud y `u 8 comprimido`. `Sf=true` usa `fCV.fa`, `InflaterOutputStream`: zlib/DEFLATE, no gzip. Longitud limitada a 65.535 bytes; medir también el blob con personajes avanzados. No truncar entradas para que quepan ni enviar un blob sin cabecera interna.

Blob versión 5 leído por `bdM.dT`:

1. `i 32 version`.
2. `u 8 recientesCount`; cada reciente: `i 32 logroId + i 64 fecha`.
3. `i 32 variablesCount`; cada variable: `i 32 variableId + i 64 valor`.
4. `i 32 logrosCount`; cada entrada: `i 32 id + u 8 activo + u 8 completo + u 8 tieneFecha 1 + u 8 tieneFecha 2`, las fechas `i 64` presentes **en ese orden**, y `u 8 flagV5`. Los métodos consumidores son `V`, `fo`, `jd`, `hl`, `fp`; no convertir el último flag en «premio reclamado» sin cotejar su significado.
5. `i 32 objetivosCompletosCount`; cada entrada `i 32 objetivoId`.
6. `u 8 seguidosCount`; cada entrada `i 32 logroId`.

El estado vacío son **18 bytes de blob**, **21 de sección**. La prueba nativa restauró una variable 695=49 y una fixture con logro 4228 activo/completo, objetivo 8716 completo y seguimiento 4228. Es una fixture de formato: no acredita haber ganado «Madera de jefe» en partida ni entregado su recompensa.

## Cambios incrementales del servidor

| Opcode / consumidor | Cuerpo | Efecto comprobado |
| --- | --- | --- |
| 13295 / `cty`, `cEM` | actor i 64, variable i 32, valor i 64:20B | `bdM.o`: reemplaza por valor absoluto; callback recibe diferencia |
| 12933 / `ctp`, `cED` | actor i 64, logro i 32, fecha i 64:20B | `bdM.p`→callback `biW.a`→`bjT.r`; notificación temporal, **no contador** |
| 13422 / `ctq`, `cEE` | actor i 64, logro i 32, fecha i 64:20B | `bdM.q`: completa, añade reciente, retira seguimiento; puede diferir UI durante timeline |
| 13205 / `ctv`, `cEJ` | actor i 64, logro i 32:12B | `bdM.By`: reinicializa/activa entrada y relaciones |
| 13371 / `cts`, `cEG` | actor i 64, logro i 32, bool:13B | `bdM.r`: seguimiento |
| 13832 / `ctt`, `cEH` | actor i 64, objetivo i 32:12B | `bdM.Br`: objetivo completo |
| 12023 / `ctu`, `cEI` | actor i 64, objetivo i 32:12B | `bdM.Bs`: reset objetivo |
| 12012 / `ctr`, `cEF` | actor i 64, logro i 32:12B | `bdM.Bq/s`: reset logro y seguimiento |

No confundir `13312` conocido por el decoder del repositorio con `13205`: verificar el consumidor particular antes de usarlo. El bootstrap debe contener la misma revisión que los incrementales publicados; no emitir estados antes del commit durable.

## Solicitudes del cliente

- **13175 `cnI`**: logro i 32 + bool seguimiento (5B), enviado por `cYA.J`.
- **12533 `cnJ`**: logro i 32 (4B). `cYA` lo emite en la acción de compartir si existe grupo; `biW` también lo emite para entradas shareable. No etiquetarlo como reclamación de premio.
- **13397 `cnK`**: logro i 32 (4B), desde `bdM.Bv`→`biW.AV`. `bsW` comprueba elegibilidad `Bw` antes de solicitarlo. La espera local de 30 s de `Bv` **no es un cooldown autoritativo**; cotejar aceptación/activación y respuesta de esta acción antes de habilitarla.

El servidor debe inferir actor y permisos desde sesión, aceptar solo IDs existentes/elegibles y rechazar replay indebido. El cliente no envía una prueba suficiente de victoria ni puede fijar contadores. No se acreditó una solicitud universal para «reclamar todos los premios»: determinar si cada tipo de entrada entrega automáticamente al completar o mediante interacción de misión. Los opcodes de eventos internos de UI de `cYA` no son mensajes de red.
