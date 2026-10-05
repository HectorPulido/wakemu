# Solución propuesta — E11

## 1. Fijar la reproducción mínima

Ejecutar únicamente el test fallido con la misma revisión. Registrar mapa, altura, radio, jump, source y xy del lookup, sin modificar el terreno ni el personaje del usuario. Confirmar que el error corresponde a una clave ausente y no a un archivo/schema incompatible.

## 2. Cotejar fixture y exportación

Localizar la clave exacta en el catálogo autorizado del servidor. Verificar si la coordenada inicial existe en ese mapa y si la autoridad instalada conserva la misma identidad. Si el plano sintético no pertenece al mapa 1134, corregir la fixture futura para usar geometría sintética explícita sin identidad nativa o posiciones reales exportadas; esa elección debe conservar el objetivo de integración que prueba.

## 3. Completar el catálogo solo con evidencia

Si una consulta válida real falta, producir la exportación nativa para la política exacta, comprobar cobertura y registrar versión. No añadir una superficie deducida de aristas de caminar ni rellenar queries desconocidas como colisión. Mantener el rechazo por clave ausente como regresión negativa.

## 4. Preservar la transacción

El fallo de resolución no debe confirmar AP/MP/WP, daño o desplazamiento parcial. Probar antes y después del commit y revisar que los paquetes quedan privados mientras la preparación falla. Mantener el original intacto y la secuencia de acciones.

## 5. Aceptar ambos caminos

La fixture corregida debe demostrar daño y desplazamiento en una sola transacción; la fixture deliberadamente no exportada debe rechazar sin mutación. Añadir un caso con colisión None que se comporte según la regla nativa y no se confunda con dato ausente. Verificar un caso de terreno real del mapa antes de atribuir el defecto al runtime.
