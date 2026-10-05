# Solución propuesta

Separar el recálculo del máximo y la curación. Conservar una magnitud autoritativa de daño o salud relativa que no se destruya al recortar la presentación al máximo temporal. Definir una única transición de salud para guardar/activar builds y usarla tanto en SQL como en journal. Una hoja de aptitudes no puede convertirse por sí misma en un evento de curación.

Revisar inicialización y reconexión para que no vuelvan a inferir «sin daño» a partir del valor recortado. Mantener diferenciados creación de personaje, curación explícita, regeneración y derrota. Validar persistencia de la magnitud elegida y su migración sobre copias antes de cambiar el esquema. No se propone tocar el cliente ni los hechizos.
