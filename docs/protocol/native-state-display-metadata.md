# Metadatos y filtro original de iconos de estado

Auditoría offline del cliente instalado; sin GUI, reinicio ni cambio de motor. Complementa la investigación de entrega/retención de hijos; no acredita resolución visual en producción.

`bbV.Au` crea `bQh extends fyW`; `aNv.cxu → bQj.iq → bQh.erM → bQh.elv` determina elegibilidad de display. La copia por nivel preserva este campo. No se deduce visibilidad del nombre/descripción.

| Estado | elv | Categoría nativa | Icono bcw | Hijo elegible cys |
|---|---|---|---|---|
|3442 Concentración|true|POSITIF|3442|150327, clase400|
|8913 Sacudido|true|NEGATIF|3662|408737, clase330|

Los assets `icons/states/3442.tga` y `icons/states/3662.tga` existen en gui.jar. `bQh.byh` usa `statesIconsPath` de config.properties y el campo bcw; el ID del icono no tiene que coincidir con el estado. `cxv=false` en ambos; no oculta la entrada en el filtro inspeccionado. Niveles probados1/10/30/50; el factory clampa8913 a máximo30.

`bkN.dvf` recorre el manager, llama `big.w`, luego `bPG.c`. `big.w` excluye carrier310 y efectos sin PL; para PLtype1 consulta `bQh.elv`. El carrier registrado por sí solo no representa una entrada en esa lista.

`bPG.c` usa el contenedor PL para el agrupador bPE. Pasa `baZ==null || eVn.cys()` a `bPE.b`; cuando es false no añade ese runner a la lista kJV. Si `elp()==0`, devuelve null. Los otros hijos de3442 (153288/293366/293372, clase330) tienen cys=false; no sustituyen a150327 en la entrada visible.8913 posee408737 cys=true.

Probe durable `sniffer/java/ProbeNativeStateDisplayMetadata.java`: carga las definiciones originales, comprueba elv y assets, crea runners originales eXE/eYg con PK/PL del estado y ejecuta `bPG.c`/`bPE`. Control PLnull: entrada null. PLfyW+cysTRUE: entrada presente, count1 y nivel nativo. cysFALSE: entrada null. PASS; salida privada `.runtime/local/native-state-display-metadata.txt`. Es un probe de modelo UI, no renderizado OpenGL ni una prueba de llegada de esos hijos al cliente actual.

Pendiente operativo: demostrar entrega y retención de150327/408737 con PL correcto, invalidación de caché bkN y getter visible después del cast. Missions posee esa ruta. No cambiar carrier310 para hacerlo visible ni ocultar el problema con un icono forzado.

## Probe de entrega completo330/400

`ProbeNativeStateChildDelivery` usa los iN grabados de los hijos408737/150327. Sólo el control de contenedor9/10 se reconstruye mediante setters originales `iP.eM(1)`/`ao(fyW.QF())`; el resto del payload se conserva. Resuelve el fyW por el decodificador original, enlaza el PK original de ese hijo y actores PN/PW al manager real eZV. No reemplaza Qf.p ni métodos de registro. La ruta13497 ejecuta `aTR.cbj` original;12613 ejecuta `aVo.cYb/cYc/cbj` mediante cola originalaER/aEV, con ejecución=false. No constituye renderizado GUI.

|Hijo|Ty/aZN/bbW|13497(aTR)|12613(aVo,false)|
|---|---|---|---|
|408737/330/8913|true/true/false|Qf1,UI1|Qf1,UI1|
|150327/400/3442|true/false/false|Qf0,UI0|Qf1,UI1|

La ruta400 requiere12613: el guard originalaTR necesita además aZN o bbW y este runner no cumple ninguno. En el caso registrado12613, bbs=false: el cliente no vuelve a ejecutar gameplay. El resultado coincide con las observaciones oficiales330→13497 y400→12613; no justifica cambiar330 a12613.

Comandos reproducibles (JDK22; captura privada ya existente, sin login nuevo):

```sh
python3 sniffer/extract-state-child-probe.py /ruta/privada/events.jsonl .runtime/local
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ProbeNativeStateManager.java sniffer/java/ProbeNativeStateChildDelivery.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -cp '.runtime/local/classes:client/lib/*' ProbeNativeStateChildDelivery .runtime/local/state-ui-delivery-330.bin .runtime/local/state-ui-delivery-400.bin
```

Resultado observado: PASS cuatro rutas, assertions de Qf/display/queue y ejecución deshabilitada. Salida privada `.runtime/local/native-state-child-delivery-probe.txt`. La entrega/refresco gráficos reales continúan pendientes; no declarar iconos resueltos por este probe.
