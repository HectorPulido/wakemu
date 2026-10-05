# Recurso del contador inferior por raza

Auditoría del cliente instalado: `bkR.eH` delega `breedCharacValue` a `bgV.h`, descripción a `bgV.i`, imágenes a `bgV.k/l` y URL de icono a `bgV.m`. Los mapas privados originales `bgV.hXy/hXz` se exportaron por reflexión, sin cambios al motor ni acciones GUI.

El valor ordinario procede de `eGj.e(ffw).aYS()` (bootstrap original de `bgV.e`). **No procede del nivel del estado mostrado en el popup**. En Yopuka: característica 67 y popup 3442 son fuentes diferentes. Esto acredita el contrato de lectura; no identifica todavía por qué el servidor deja 67 en cero.

| ID raza | Nombre enum original | Característica del HUD | Popup de estado |
|---|---|---|---|
| 1 | FECA | 54 FECA_RESOURCE | 6345 |
| 2 | OSAMODAS | 59 OSAMODAS_RESOURCE | — |
| 3 | ENUTROF | 64 ENUTROF_RESOURCE | 8552 |
| 4 | SRAM | 66 SRAM_RESOURCE | 3114 |
| 5 | XELOR | 55 XELOR_RESOURCE | 6759 |
| 6 | ECAFLIP | 60 ECAFLIP_RESOURCE | 3683 |
| 7 | ENIRIPSA | 65 ENIRIPSA_RESOURCE | 3869 |
| 8 | IOP | 67 IOP_RESOURCE | 3442 |
| 9 | CRA | 56 CRA_RESOURCE | 7792 |
| 10 | SADIDA | 61 SADIDA_RESOURCE | — |
| 11 | SACRIER | 50 CHRAGE | — |
| 12 | PANDAWA | 68 PANDAWA_RESOURCE | 3300 |
| 13 | ROUBLARD | 57 ROGUE_RESOURCE | 7919 |
| 14 | ZOBAL | 62 ZOBAL_RESOURCE | — |
| 15 | OUGINAK | 117 OUGINAK_RESOURCE | — |
| 16 | STEAMER | 123 SP | — |
| 17 | SOUL | —  | — |
| 18 | ELIOTROPE | 58 ELIOTROPE_RESOURCE | — |
| 19 | HUPPERMAGE | 63 HUPPERMAGE_RUNE | — |

## Excepciones originales

- Zobal: `bgV.h` interpreta el recurso 62 mediante `bgY.Cj` y devuelve `bgY.djN()`, en vez de mostrar directamente el valor de 62. Descripción e imágenes dependen de la máscara activa.
- Hipermago: `bgV.h` devuelve `Optional.empty()`; el recurso 63 selecciona una entrada `bgX`, utilizada por descripción/icono. La característica 111 no es la entrada de este widget.
- Sacrógrito: descripción especial `critere.chrage`; el valor continúa leyendo 50.
- Steamer: el mapa original usa 123 `SP`.
- El rango 1–19 contiene `SOUL` (17), sin recurso de HUD: son 18 clases jugables, no 19 mapas de recurso.

Los nombres de la tabla son identificadores enum originales, no traducciones de tooltips. La clave general de descripción es `ffw.aYi()`; la localización y los posibles nombres reformados del recurso no se han inferido.

## Reproducción

```sh
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -classpath 'client/lib/*' -d .runtime/local/classes sniffer/java/ExportNativeBreedHudResources.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -classpath '.runtime/local/classes:client/lib/*' ExportNativeBreedHudResources
```

Export ejecutado correctamente. JSON duradero: `docs/reports/combat-inventory/native-breed-hud-resources.json`. No prueba de HUD GUI, ni corrección del suministro de valores al cliente, realizada en esta auditoría.

## Reglas específicas verificadas: Yopuka y Sacrógrito

`ProbeNativeBreedResourceRules.java` lee los árboles originales directamente de bdata. Salida preservada en `docs/reports/combat-inventory/native-breed-resource-rule-evidence.txt`.

### Yopuka

El estado 3442 es Concentración (nivel máximo 400). Al alcanzar una rama:

| Nivel 3442 | PW instantáneos, si no está 8415 en baraja | Preparación 3462 | Furia 8924 | Concentración retirada |
|---|---|---|---|---|
| 100–199 | +1 | 40 | +1 | 100 |
| 200–299 | +2 | 60 | +1 | 200 |
| 300–399 | +3 | 60 | +1 | 300 |

Estos son hijos originales de 153288/293366/293372. El cliente localizado describe 8415 como sustitución de recuperación instantánea de PW por PW/Preparación al final del turno según Furia. No se ha sustituido esa mecánica por un cálculo del HUD. Por ejemplo, 35 de Concentración no supera el umbral100; el contador puede representar35 cuando la característica67 se suministra correctamente. La proyección 3442→67 sería una adaptación explícita del servidor: el cliente lee67, y no se encontró productor cliente que copie3442.

### Sacrógrito

**9313 no es Furor**: es un estado auxiliar sin nombre, con nivel máximo100. El innato3702 reemplaza9313 mediante1047 modo2, que calcula porcentaje actual de HP+VIRTUAL_HP con división entera nativa. Usarlo como contador50 haría mostrar100 a vida llena aunque no exista Furor.

El estado con nombre Furor es **9312**. La ruta original3702→416616 calculaHP% actual;416617 comprueba que es inferior al nivel anterior9313;416618 (844) obtiene la diferencia y416619 aplica9342. Este último aplica9312/9314/9324 con su mismo nivel. La inicialización1003 también aplica9342 a partir del porcentaje perdido (1047modo3); al final del turno1001 hay otra rama para porcentaje perdido. Por eso la cantidad acumulada de Furor no equivale universalmente a `100-HP%` actual.

9312 tiene máximo500. Sus hijos416578/416615 otorgan daño infligido0.5×nivel por debajo200, y100 desde200. Las ramas1–74,75–149,150–200 controlan estados9328/9329/9330. La proyección9312→50 queda distinguida como adaptación servidor pendiente de validación empírica; no existe autorización para copiar9313 ni aplicar una regla universal a todos los estados de popup.

La localización instalada confirma `IOP_RESOURCE=Concentración`, `critere.chrage=Furor`, `content.8.9312=Furor`, `content.8.3462=Preparación` y `content.8.8924=Furia`. No se inferió una descripción ausente del estado.
