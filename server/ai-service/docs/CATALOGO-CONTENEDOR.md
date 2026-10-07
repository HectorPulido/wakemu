# Catálogo completo dentro de ai-service

`Dockerfile` copia `/app` completo desde la imagen que ejecuta world,
incluidos protocolo, motor, entrada, migraciones y archivos futuros. Precarga
también el SDK actual, copiado con una única instrucción `COPY . /app`.
El bootstrap inventaría las raíces `catalog`, `engine` y `server` completas,
con los mismos nombres que usará el puente. Incluye archivos binarios, extensiones
desconocidas y futuras, archivos vacíos y todos los subdirectorios. No filtra
por especie, hechizo, mapa ni formato. No requiere reiniciar world.

## Verificación actual — 2026-10-07

World `3af10843cbc6`, AI `26576b10f2bb`:
**13.269 entradas / 711.838.483 bytes** declarados, catálogo
`d1d98d5f765350e54ac827cc7b2f0eb9c9e1732ab89f50a4806fc1dd95b257d7`.
Sellado por el servicio vivo: `complete=true`, `missing=[]`.

Después de reconstruir, `rebuild.sh` ejecuta `provision_live_catalog.py`:
prepara el índice privado mediante el SDK montado de world, copia TODO `/app`
del contenedor vivo, importa todos los objetos y sella el manifiesto en AI.
Comprueba identidad de world antes y después. No cambia fuentes ni reinicia world.
La caché conserva snapshots completos; cada inventario sigue enumerando todos
los archivos y comprobando sus firmas. Corrupción o cambios invalidan el caché.
Organización: código en `wakfu_ai/`, comandos en `scripts/`; bootstrap se
ejecuta con `python3 -m wakfu_ai.context.catalog_bootstrap`. La entrada
estable de preparación de world se conserva.

7 pruebas de provisión y 5 de caché verifican recuperación, firmas y completitud.

## Verificaciones históricas

## Verificación anterior — 2026-10-07

World `e839fd35a2c1`, AI `58413db8dc02`: catálogo provisionado desde la imagen
viva y SDK completo tras ampliar búsqueda de apoyo. Manifiesto
`65c45a2cc2778bfffda2132642c4b990e8a6e717b20709a41bf250e6ee7641f4`,
**11.048 entradas /689.711.986 bytes**. `ContextStore.manifest` rehashó todos
los objetos: `complete=true`, `missing=[]`. Health y loader privado aprobados.
World mantuvo su arranque: ningún reinicio propio adicional, contador1/3.
Las cifras corresponden a esa imagen; los cambios posteriores del volumen
SDK/documentación producen otro manifiesto completo.

## Verificación anterior — recibos completos

World `6319c87dedd6`, AI `67fe32398bf0`: inventario completo del world vivo
y SDK montado, después de desplegar recibos completos e identidad. Manifiesto
`3f000e85c0c17608c8409551ef76fd4bfabcacc07a8792aef0fba65180d3cb7a`,
**11.052 entradas /689.656.214 bytes**. Rehash completo en el almacén AI:
`complete=true`, `missing=[]`. Las cifras identifican ese snapshot verificado;
los cambios posteriores del SDK/documentación generan otro manifiesto.
Sin reinicio world adicional; contador propio1/3.

## Verificación histórica del despliegue final — 2026-10-07

World `ff2659e929a2`, AI `6f7b4d912f5f`: catálogo completo recibido desde
el world vivo más SDK read-only. Manifiesto
`5cb14b0cbf226c314d512bef5bf757717b1185b05d4782d72c07fdd1ceb59e3a`: 
**11.029 entradas /689.354.892 bytes**, incluye alias deduplicados por hash.
`ContextStore.manifest` rehashó todos los blobs y confirmó `complete=true`,
`missing=[]`. Evidencia histórica anterior debajo; sus cifras corresponden
a las imágenes anteriores, no al despliegue final.

Antes de construir, identificar la imagen real:

Para reconstruir y reiniciar exclusivamente el servicio AI actual:

```sh
sh server/ai-service/rebuild.sh
```

El script identifica automáticamente la imagen viva de world, usa una
etiqueta por hash y comprueba de nuevo su identidad antes de reemplazar AI.
No reinicia world ni sus dependencias. Hay un único Dockerfile y un único
servicio AI; los módulos nuevos entran mediante `COPY . /app`.

```sh
docker inspect wakfu-local-world-1 --format '{{.Image}}'
```

Etiquetar ese ID exacto con un nombre local específico de su hash, y usarlo
como `WORLD_IMAGE`; Docker interpreta un ID `sha256:...` en `FROM` como un
nombre de repositorio, por eso se usa la etiqueta local. No usar una etiqueta
mutable de world sin comprobar el ID.

Ejemplo verificado para la imagen observada durante esta preparación:

```sh
docker tag sha256:9af0658c4e5db5da40debb6ba8c656f248bc10397fb6055a03ae76f215039a28 wakfu-world-catalog-source:9af0658c4e5d
docker build --build-arg WORLD_IMAGE=wakfu-world-catalog-source:9af0658c4e5d -t wakfu-ai-complete-catalog-check server/ai-service
docker run --rm --entrypoint cat wakfu-ai-complete-catalog-check /native/catalog-manifest.json
```

El bootstrap importa los archivos localmente al almacén por contenido y
verifica SHA-256 y tamaño de cada archivo. Conserva todas las rutas, incluso
si varios archivos comparten contenido. El manifiesto usa exactamente la
serialización del transporte: el puente puede comprobar que ya está presente
sin volver a enviar los archivos por HTTP.

La construcción anterior verificó 5.395 archivos y 342.732.020 bytes de
catálogo y motor. Esto acredita la provisión completa de esas dos raíces,
no la terminación del planificador v3 ni su integración en world. El estado
dinámico del combate se transmite por el puente; no se sustituye por el
catálogo estático. Las imágenes de prueba no reemplazan los contenedores
del juego.

Prueba real posterior dentro de la imagen, con red desactivada: el puente
reconoció los 5.395 archivos ya provisionados; realizó 24 comprobaciones y
envió **cero bloques**. Manifiesto:
`d789fa1fbc32b53a52e8f0a69c132ccae95b4d853e0790a7344ea8688a5c6f3c`.

Pruebas automáticas de provisión: cuatro casos en
`test_catalog_bootstrap.py`; además pasan siete pruebas del almacén y seis
del transporte HTTP. Las seis pruebas de `test_native_session.py` verifican
la separación de estados privados, candidatos ilegales, referencias ajenas
y cambios del estado fuente. Los errores nativos de un candidato se
devuelven como `supported:false`; un estado fuente alterado invalida la
consulta completa.
