# Ataques por la espalda: condición común

`IsBackstabbed` usa el criterio original `eNn/eIG`: selecciona el lanzador por
defecto y el objetivo sólo con la cadena `target`, sin distinguir mayúsculas.
Las demás cadenas conservan el lanzador. Admite cero o un argumento de texto.

El actor seleccionado debe ser un luchador `eGj`. El objeto opuesto debe ser
`PV`; una casilla explícita `aBn` no lo es, pero un área registrada `Qq` sí.
El localizador actual `Sl` del actor seleccionado decide si el opuesto está
detrás. La propiedad de combate 47 (`ffe.ser`) anula ese localizador y devuelve
falso. La ausencia de orientación autoritativa sigue siendo un error, no se
sustituye por una dirección inventada.

La geometría reutiliza el mismo cálculo de orientación que el daño ordinario:
resta de enteros Java con desbordamiento, normalización `float32` mediante
recíproco y umbrales originales. Igualdad de XYZ devuelve frontal; XY iguales
con Z distinta devuelve lateral. La posición y dirección se consultan en la
copia de combate actual, después de los efectos anteriores, sin cachearlas al
comenzar el ataque.

Validación contra el cliente original: `ProbeNativeBackstabbed.java` comprueba
ocho casos de selección, ausencia y tipo de objetivo, más 112 combinaciones de
orientación y casilla y un desbordamiento. Los 112 resultados coinciden con el
servidor. Las 48 pruebas de condiciones, adaptador y autoridad pasan.

La auditoría focal crítica prueba Desplume (7318), Cleptosram (4584) y Patada
Azotada (7066) en cinco escenarios antes rechazados: todos aplican cambios,
con fuentes estables y sin modificar el combate original. Evidencia en
`docs/reports/combat-inventory/active-critical-backstabbed-current.json`.
Esto no verifica todas las variantes ni su funcionamiento en pantalla.
