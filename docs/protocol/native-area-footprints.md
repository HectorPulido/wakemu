# Pertenencia de actores con radio físico en áreas

La selección común ignoraba el radio físico en las áreas isotrópicas: puntos, círculos, anillos y cruces. Sólo las formas tratadas por `native_area_shape` usaban dicho dato. Como resultado, un actor cuyo centro quedaba fuera pero cuyo cuerpo tocaba el área podía quedar excluido.

Original: `amQ.a(..., amS)` aplica el selector y, cuando éste exige pertenencia al área, llama `anc.b` con `amP.bcL()`. `anc.b` delega en `amX.a`. Este método transforma primero el centro al sistema local y comprueba los offsets del cuadrado `[-radius,radius]²`; un radio no positivo usa únicamente el centro. La altura no participa en esta pertenencia XY. La ruta sin selector llama `anc.a`, que comprueba solamente el centro: ambas rutas deben conservarse distintas.

`ProbeNativeAreaFootprints` ejecuta los métodos originales para point, circle-1 y ring-1-1. Casos acreditados:

| Área en (0,0) | Centro actor | Radio | Incluido |
|---|---|---:|---|
| Punto | (1,0) | 0 | No |
| Punto | (1,0) | 1 | Sí |
| Círculo1 | (2,0) | 1 | Sí |
| Anillo1 | (0,0) | 0 | No |
| Anillo1 | (0,0) | 1 | Sí |

La corrección compartida en `select_effect_targets` aplica el mismo cuadrado a los offsets isotrópicos cuando `native_radius=True`; el llamador establece este modo sólo con selector presente. No amplía alcance de lanzamiento, LOS, afiliaciones ni criterios. Radio desconocido o fuera del byte firmado se rechaza; no se sustituye por cero.

Validación reproducible:

```sh
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ProbeNativeAreaFootprints.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -cp '.runtime/local/classes:client/lib/*' ProbeNativeAreaFootprints
PYTHONPATH=server:server/tests python3 -m unittest test_combat_area_footprints test_combat_effect_targets test_combat_effect_resolver -q
```

25 pruebas pasan: matriz nativa, hueco de anillo, esquina del cuerpo cuadrado, selector fcE completo frente a selector nulo, afiliación, altura distinta y autoridad de radio. Esta validación acredita selección del motor; no acredita animaciones ni funcionamiento completo de ningún hechizo en GUI. Los actores de radio cero conservan sus resultados.
